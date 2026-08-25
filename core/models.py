from django.db import models, transaction
from django.db.models import F, Max
from django.contrib.auth.models import User, Group
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from . import statuses


# ---------------------------------------------------------------------------
# Suppression douce
#
# GARDE-FOU DONNEES : rien ne doit pouvoir quitter la base par le chemin d'une
# interface web. Supprimer un projet effacait jusqu'ici le projet ET ses cas en
# cascade -- mesure sur P06 : 256 cas detruits derriere une simple page de
# confirmation. Les lignes sont desormais marquees, jamais retirees.
# ---------------------------------------------------------------------------

class AliveManager(models.Manager):
    """Gestionnaire par defaut : ne voit que les lignes non supprimees.

    Sur Case, il ecarte aussi les tentatives archivees par une re-soumission :
    l'affichage doit montrer la soumission en cours, pas celle qui a echoue.
    Rien n'est perdu pour autant -- all_objects les voit, et la fiche du cas en
    cours les liste.
    """

    def get_queryset(self):
        queryset = super().get_queryset().filter(deleted_at__isnull=True)
        if any(f.name == 'is_archived' for f in self.model._meta.get_fields()):
            queryset = queryset.filter(is_archived=False)
        return queryset


class SoftDeleteModel(models.Model):
    deleted_at = models.DateTimeField(
        null=True, blank=True, db_index=True, editable=False,
        verbose_name=_('Deleted at'),
    )

    objects = AliveManager()
    all_objects = models.Manager()  # y compris les lignes supprimees

    class Meta:
        abstract = True
        # Le parcours des cles etrangeres passe par ce gestionnaire : sans cela,
        # un commentaire dont le cas est supprime leverait DoesNotExist au lieu
        # de rester consultable.
        base_manager_name = 'all_objects'

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=['deleted_at'])

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=['deleted_at'])


# ---------------------------------------------------------------------------
# Identifiants generes par le LIMS
#
# L'ACC n'est plus saisi a la main : le LIMS l'attribue. Le compteur est
# monotone et ne reutilise jamais un numero libere -- un ACC retire peut deja
# figurer sur une etiquette de congelateur ou un dossier papier, le reattribuer
# ferait silencieusement porter le meme identifiant a deux patients differents.
# ---------------------------------------------------------------------------

ACC_PREFIX = 'ACC'
ACC_SEQUENCE_KEY = 'acc'


def format_acc(number):
    """1499 -> 'ACC-1499'. Les 1329 cas existants suivent deja ce format."""
    return f"{ACC_PREFIX}-{number:04d}"


class IdentifierSequence(models.Model):
    """Compteur monotone, une ligne par famille d'identifiants."""

    key = models.CharField(max_length=32, primary_key=True)
    last_value = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = _('Identifier sequence')
        verbose_name_plural = _('Identifier sequences')

    def __str__(self):
        return f"{self.key} = {self.last_value}"

    @classmethod
    def allocate(cls, count=1, key=ACC_SEQUENCE_KEY):
        """Reserve `count` numeros consecutifs et les renvoie.

        UPDATE puis SELECT, dans cet ordre : la premiere instruction prend le
        verrou d'ecriture de SQLite et le conserve jusqu'au commit, donc deux
        allocations concurrentes se serialisent au lieu de s'entrelacer. Un
        Max(acc_number) + 1 serait en situation de course avec trois workers
        gunicorn, et select_for_update() n'est pas utilisable : le backend
        SQLite de Django leve NotSupportedError.
        """
        if count < 1:
            raise ValueError("count doit valoir au moins 1")

        with transaction.atomic():
            updated = cls.objects.filter(pk=key).update(last_value=F('last_value') + count)
            if updated:
                last = cls.objects.get(pk=key).last_value
            else:
                # Amorcage : demarrer au-dessus du plus grand numero existant.
                # La migration 0021 seme normalement le compteur ; ce chemin
                # n'est qu'un filet.
                start = Case.all_objects.aggregate(m=Max('acc_number'))['m'] or 0
                cls.objects.create(key=key, last_value=start + count)
                last = start + count

        return list(range(last - count + 1, last + 1))


class ProjectLead(models.Model):
    """Model representing a project lead in the LIMS."""
    name = models.CharField(max_length=255, unique=True)
    
    def __str__(self):
        return self.name
        
    class Meta:
        ordering = ['name']
        verbose_name = _('Project Lead')
        verbose_name_plural = _('Project Leads')

class Project(SoftDeleteModel):
    """Model representing a research project in the LIMS."""

    # Les cas referes par des medecins n'appartiennent a aucun projet de
    # recherche de la phase 1 : ils ont besoin d'une categorie a part, ou le
    # Biobank ID peut manquer a la creation puisqu'il arrive parfois apres.
    KIND_RESEARCH = 'research'
    KIND_REFERRED = 'referred'
    KIND_CHOICES = [
        (KIND_RESEARCH, _('Research project')),
        (KIND_REFERRED, _('Referred cases')),
    ]

    name = models.CharField(max_length=255)
    kind = models.CharField(
        max_length=16, choices=KIND_CHOICES, default=KIND_RESEARCH,
        verbose_name=_('Project type'),
    )
    description = models.TextField(blank=True)
    project_lead = models.ForeignKey(
        ProjectLead, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='projects',
        verbose_name=_('Project Lead')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_projects')

    def __str__(self):
        return self.name

    def get_cases_count(self):
        """Return the number of cases in this project."""
        return self.cases.count()

    def soft_delete(self):
        """Marque le projet et ses cas encore vivants, en une seule transaction.

        Le meme horodatage est pose partout, ce qui permet a restore() de rendre
        exactement l'ensemble retire -- et pas les cas supprimes anterieurement.
        """
        now = timezone.now()
        with transaction.atomic():
            # .update() volontairement : pas de Case.save(), donc aucun tier recalcule.
            self.cases.update(deleted_at=now)
            self.deleted_at = now
            self.save(update_fields=['deleted_at'])

    def restore(self):
        """Rend le projet et les cas retires lors du meme geste."""
        stamp = self.deleted_at
        with transaction.atomic():
            if stamp is not None:
                Case.all_objects.filter(project=self, deleted_at=stamp).update(deleted_at=None)
            self.deleted_at = None
            self.save(update_fields=['deleted_at'])
    
    @classmethod
    def get_unique_project_leads(cls):
        """Return all unique project leads."""
        return ProjectLead.objects.all().order_by('name')

class Case(SoftDeleteModel):
    """Model representing a case within a project."""
    
    # Vocabulaire des statuts : voir core/statuses.py. Les constantes ci-dessous
    # sont conservees sous leurs anciens noms pour que le code appelant n'ait pas
    # a changer, mais elles pointent desormais vers les statuts de la v2.
    STATUS_CHOICES = statuses.ALL_CHOICES
    STATUS_CREATED = statuses.CASE_CREATED
    STATUS_RECEIVED = statuses.RECEIVED
    STATUS_COMPLETED = statuses.ANALYSIS_COMPLETE

    # Tier options
    TIER_A = 'A'
    TIER_B = 'B'
    TIER_FA = 'FAIL'
    
    TIER_CHOICES = [
        (TIER_A, _('A')),
        (TIER_B, _('B')),
        (TIER_FA, _('FAIL')),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='cases')

    # Valeur numerique de l'ACC : c'est elle qui porte la contrainte d'unicite
    # et le tri. `name` reste la chaine affichee partout ('ACC-0142'), derivee
    # d'acc_number, pour ne rien casser dans les templates ni dans les exports.
    acc_number = models.PositiveIntegerField(
        null=True, blank=True, db_index=True, verbose_name=_('ACC number'))
    name = models.CharField(max_length=255, verbose_name=_('ACC'))

    # Anciennement other_id. C'est l'identifiant par lequel la biobanque
    # recherche reellement ; il est rempli sur les 1329 cas existants.
    biobank_id = models.CharField(
        max_length=255, blank=True, null=True, db_index=True,
        verbose_name=_('Biobank ID'),
        help_text=_('The identifier used by the biobank. Searchable.'))
    # Statut DERIVE des specimens, jamais saisi directement -- exactement le
    # patron deja en place pour `tier`. Il survit comme colonne pour que les
    # listes, les filtres, les statistiques et les exports continuent de
    # fonctionner sans jointure, et pour qu'un technicien garde UNE pastille a
    # lire par cas plutot que trois.
    status = models.CharField(
        max_length=50, choices=statuses.ALL_CHOICES, default=statuses.DEFAULT,
        editable=False, db_index=True, verbose_name=_('Status'))
    
    # Coverage values
    rna_coverage = models.FloatField(null=True, blank=True, verbose_name=_('RNA Coverage (M)'))
    dna_t_coverage = models.FloatField(null=True, blank=True, verbose_name=_('DNA (T) Coverage (X)'))
    dna_n_coverage = models.FloatField(null=True, blank=True, verbose_name=_('DNA (N) Coverage (X)'))
    
    # Re-soumission : quand un sequencage echoue, la biobanque soumet un
    # nouveau specimen pour le MEME patient. La nouvelle tentative reprend le
    # meme ACC ; l'ancienne est archivee, avec son historique, ses notes et ses
    # commentaires, qui restent physiquement attaches a elle.
    attempt = models.PositiveSmallIntegerField(
        default=1, verbose_name=_('Attempt'))
    is_archived = models.BooleanField(
        default=False, db_index=True, verbose_name=_('Superseded'),
        help_text=_('A later attempt replaced this one.'))
    superseded_by = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='supersedes', verbose_name=_('Superseded by'))

    # Drapeau pose a la discretion de la biobanque, pour les patients dont le
    # pronostic impose de trouver un traitement ou un test tres vite.
    is_priority = models.BooleanField(
        default=False, db_index=True, verbose_name=_('Priority case'),
        help_text=_('Flags a patient whose prognosis makes this urgent.'),
    )

    tier = models.CharField(max_length=4, choices=TIER_CHOICES, default=TIER_A)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        """Attribue l'ACC si besoin, normalise le Biobank ID, recalcule le tier."""
        # Un cas cree sans identifiant recoit le prochain numero du compteur.
        # Les cas anterieurs a la v2 portent deja un name et un acc_number : rien
        # n'est reattribue.
        if self.acc_number is None and not self.name:
            self.acc_number = IdentifierSequence.allocate()[0]
        if self.acc_number is not None:
            self.name = format_acc(self.acc_number)

        # Espaces superflus et chaine vide ramenes a NULL : sans cela, ' N-BBN 42'
        # et 'N-BBN 42' seraient deux identifiants differents, et les recherches
        # rateraient l'un des deux.
        if self.biobank_id is not None:
            self.biobank_id = self.biobank_id.strip() or None

        self.tier = self.calculate_tier()
        super().save(*args, **kwargs)

    def sync_from_specimens(self):
        """Remet le cas en phase avec ses specimens.

        Deux choses en une : les trois colonnes de couverture redeviennent le
        miroir exact des specimens -- ce qui laisse calculate_tier() inchange,
        donc la migration ne fait bouger aucun tier -- et le statut du cas
        redevient celui du specimen le moins avance.

        Sans specimen (cas cree avant la v2 et pas encore reparti), on ne touche
        a rien : ecraser les couvertures par NULL serait une perte de donnees.
        """
        specimens = list(self.specimens.all())
        if not specimens:
            return

        for specimen in specimens:
            setattr(self, Specimen.MIRROR_FIELD[specimen.specimen_type], specimen.coverage)

        self.status = statuses.least_advanced([s.status for s in specimens])

        self.save(update_fields=[
            'status', 'tier', 'rna_coverage', 'dna_t_coverage', 'dna_n_coverage',
            'updated_at',
        ])

    def ensure_specimens(self, types=None, status=None):
        """Cree les specimens manquants pour ce cas. Ne touche pas aux existants.

        `types` par defaut : les trois. Un cas n'est jamais FORCE a trois pour
        autant -- l'appelant choisit. C'est ce qui evite qu'un projet sans ARN
        affiche « en attente de Tumeur (ARN) » a perpetuite : P10_Prostate a
        32 cas sur 32 sans ARN, et son protocole n'en prevoit pas.
        """
        voulus = list(types or Specimen.ORDERED_TYPES)
        existants = set(self.specimens.values_list('specimen_type', flat=True))
        crees = []
        for specimen_type in Specimen.ORDERED_TYPES:
            if specimen_type in voulus and specimen_type not in existants:
                crees.append(Specimen(
                    case=self,
                    specimen_type=specimen_type,
                    status=status or statuses.DEFAULT,
                    coverage=getattr(self, Specimen.MIRROR_FIELD[specimen_type]),
                ))
        if crees:
            Specimen.objects.bulk_create(crees)
            self.sync_from_specimens()
        return crees

    def specimens_in_order(self):
        """Normal, puis Tumeur-ADN, puis Tumeur-ARN. Seuls ceux qui existent."""
        par_type = {s.specimen_type: s for s in self.specimens.all()}
        return [par_type[t] for t in Specimen.ORDERED_TYPES if t in par_type]

    def blocking_specimen(self):
        """Le specimen qui retient le cas, s'il en reste un en arriere.

        Sert a libeller la pastille « Sequencing Complete · en attente de
        Tumeur (ARN) » plutot que de laisser croire que le cas entier stagne.
        """
        candidats = [s for s in self.specimens.all() if not s.needs_classification]
        if len(candidats) < 2:
            return None
        candidats.sort(key=lambda s: statuses.rank(s.status))
        retard = candidats[0]
        return retard if statuses.rank(retard.status) < statuses.rank(candidats[-1].status) else None

    def specimens_to_classify(self):
        """Nombre de specimens herites de la v1 dont l'etat reste a etablir."""
        return sum(1 for s in self.specimens.all() if s.needs_classification)

    def resubmit(self, user=None, carry_forward=(), note=''):
        """Archive cette tentative et en ouvre une nouvelle, meme ACC.

        L'ordre compte : on archive AVANT de creer. L'unicite de l'ACC ne porte
        que sur les cas actifs, donc creer d'abord ferait exister deux cas
        actifs avec le meme numero, ne serait-ce qu'un instant -- et la
        contrainte tomberait.

        Rien n'est deplace : commentaires, couvertures et statuts restent
        physiquement attaches a la tentative archivee. C'est exactement ce que
        demande « l'historique de l'ancien cas est archive » -- aucune copie,
        donc aucune perte possible dans la copie.

        `carry_forward` liste les types de specimen encore exploitables, dont la
        couverture et le statut sont repris : quand seul l'ARN a echoue, le
        Normal n'a pas a etre reseqUence.
        """
        with transaction.atomic():
            types = [s.specimen_type for s in self.specimens_in_order()]
            repris = {
                s.specimen_type: (s.coverage, s.status, s.external_id)
                for s in self.specimens.all()
                if s.specimen_type in carry_forward
            }

            self.is_archived = True
            self.save(update_fields=['is_archived', 'updated_at'])

            suivant = Case(
                project=self.project,
                acc_number=self.acc_number,
                biobank_id=self.biobank_id,
                is_priority=self.is_priority,
                attempt=self.attempt + 1,
            )
            suivant.save()
            suivant.ensure_specimens(types)

            for specimen in suivant.specimens.all():
                if specimen.specimen_type in repris:
                    couverture, statut, externe = repris[specimen.specimen_type]
                    specimen.coverage = couverture
                    specimen.status = statut
                    specimen.external_id = externe
                    specimen.save()

            suivant.sync_from_specimens()

            self.superseded_by = suivant
            self.save(update_fields=['superseded_by', 'updated_at'])

            # Deux commentaires, pour que le lien se lise dans les deux sens :
            # c'est generalement dans le narratif de la tentative echouee que se
            # trouve la raison de la re-soumission.
            if user is not None:
                raison = f" Reason: {note}" if note else ""
                Comment.objects.create(
                    case=self, user=user,
                    text=f"Resubmitted as attempt {suivant.attempt}.{raison}")
                Comment.objects.create(
                    case=suivant, user=user,
                    text=f"Attempt {suivant.attempt}, replacing attempt {self.attempt}.{raison}")

        return suivant

    def previous_attempts(self):
        """Les tentatives archivees portant le meme ACC, de la plus recente."""
        if self.acc_number is None:
            return Case.all_objects.none()
        return (Case.all_objects
                .filter(acc_number=self.acc_number, is_archived=True)
                .exclude(pk=self.pk)
                .annotate(comment_total=models.Count('comments'))
                .order_by('-attempt'))

    def find_biobank_id_conflict(self):
        """Renvoie le cas actif portant deja ce Biobank ID, ou None.

        Controle SOUPLE, volontairement : deux projets partagent aujourd'hui un
        meme espace de numerotation nu (P08_CRC utilise 5..849, P09_BC_EV
        102..850). Une contrainte dure bloquerait un jour une technicienne sur
        le vrai identifiant d'un patient. La demande dit "ne peut plus etre cree
        dans deux projets PAR ERREUR" : c'est une prevention d'erreur, pas un
        axiome d'unicite.
        """
        if not self.biobank_id:
            return None
        qs = Case.objects.filter(biobank_id__iexact=self.biobank_id.strip())
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        return qs.select_related('project').first()
    
    def calculate_tier(self):
        """Calculate tier based on coverage values."""
        # Return FAIL if DNA coverage values are missing or below thresholds
        if self.dna_t_coverage is None or self.dna_n_coverage is None:
            return self.TIER_FA
            
        # Tier FAIL: DNA(T) < 30X OR DNA(N) < 30X
        if self.dna_t_coverage < 30 or self.dna_n_coverage < 30:
            return self.TIER_FA
        
        # Tier A: DNA(T) >= 80X, DNA(N) >= 30X, RNA >= 80M reads
        if self.dna_t_coverage >= 80 and self.dna_n_coverage >= 30 and self.rna_coverage is not None and self.rna_coverage >= 80:
            return self.TIER_A
        
        # Tier B: Trois cas possibles
        # 1. 30X <= DNA(T) <= 80X, DNA(N) >= 30X, tout ce qui concerne RNA (y compris l'absence de valeur)
        # 2. DNA(T) >= 80X, DNA(N) >= 30X, pas de valeur de RNA
        # 3. DNA(T) >= 80X, DNA(N) >= 30X, RNA < 80M (pas assez pour Tier A)
        if ((30 <= self.dna_t_coverage <= 80 and self.dna_n_coverage >= 30) or 
            (self.dna_t_coverage >= 80 and self.dna_n_coverage >= 30 and self.rna_coverage is None) or
            (self.dna_t_coverage >= 80 and self.dna_n_coverage >= 30 and self.rna_coverage is not None and self.rna_coverage < 80)):
            return self.TIER_B
        
        # Default to FAIL for any other case
        return self.TIER_FA
    
    def __str__(self):
        return f"{self.project.name} - {self.name}"

    class Meta(SoftDeleteModel.Meta):
        # Les cas prioritaires remontent en tete de toute liste. Un cas urgent
        # sorti de l'ecran par le defilement vide la demande de sa substance.
        ordering = ['-is_priority', 'acc_number', 'name']
        constraints = [
            # Unicite DURE sur l'ACC : il est genere par le LIMS, donc gratuite
            # (0 doublon sur les 1329 cas existants). Conditionnee sur les cas
            # vivants pour qu'un cas retire ne bloque rien.
            models.UniqueConstraint(
                fields=['acc_number'],
                # Resout la contradiction entre « la re-soumission reprend le
                # MEME ACC » et « le LIMS bloque les identifiants dupliques » :
                # l'unicite porte sur la tentative EN COURS. Un seul cas actif
                # par ACC, mais les tentatives archivees le partagent librement.
                condition=models.Q(deleted_at__isnull=True, is_archived=False),
                name='uniq_active_acc_number',
                violation_error_message=_(
                    'This ACC identifier is already used by another case.'),
            ),
        ]

class Accession(models.Model):
    """Model to store accession numbers for a case."""
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='accessions')
    accession_number = models.CharField(max_length=255)
    
    def __str__(self):
        return self.accession_number

class Comment(models.Model):
    """Model to store comments for a case."""
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='comments')
    text = models.TextField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Comment by {self.user.username} on {self.case}"

# Create groups for different user roles
def create_groups():
    """Create viewer and editor groups if they don't exist."""
    Group.objects.get_or_create(name='viewer')
    Group.objects.get_or_create(name='editor')

# Create a signal to automatically create groups when Django starts
from django.db.models.signals import post_migrate
from django.dispatch import receiver

@receiver(post_migrate)
def init_groups(sender, **kwargs):
    """Initialize groups after migration."""
    if sender.name == 'core':
        create_groups()


# ---------------------------------------------------------------------------
# Specimens
#
# « Things should be organized by case but tumours and normals should be
#   separate entities inside a case. And the tumour needs to be split into the
#   DNA and the RNA. » -- Daniel, TFRI
#
# Les trois entites correspondent une pour une aux trois colonnes de couverture
# qui existaient sur Case : dna_n -> Normal-ADN, dna_t -> Tumeur-ADN,
# rna -> Tumeur-ARN. La migration est donc sans perte, et les seuils de tier se
# transposent sans changer une valeur.
#
# Ce sont aussi les « types 1, 2 ou 3 » de la note de reunion : un seul concept
# nouveau a introduire dans l'interface, pas deux.
# ---------------------------------------------------------------------------

class Specimen(models.Model):
    TYPE_NORMAL_DNA = 'normal_dna'
    TYPE_TUMOUR_DNA = 'tumour_dna'
    TYPE_TUMOUR_RNA = 'tumour_rna'

    TYPE_CHOICES = [
        (TYPE_NORMAL_DNA, _('Normal (DNA)')),
        (TYPE_TUMOUR_DNA, _('Tumour (DNA)')),
        (TYPE_TUMOUR_RNA, _('Tumour (RNA)')),
    ]

    #: Ordre d'affichage : normal, puis tumeur ADN, puis tumeur ARN.
    ORDERED_TYPES = [TYPE_NORMAL_DNA, TYPE_TUMOUR_DNA, TYPE_TUMOUR_RNA]

    #: Colonne miroir sur Case. Ces trois colonnes restent la source du calcul
    #: du tier, ce qui laisse calculate_tier() inchange.
    MIRROR_FIELD = {
        TYPE_NORMAL_DNA: 'dna_n_coverage',
        TYPE_TUMOUR_DNA: 'dna_t_coverage',
        TYPE_TUMOUR_RNA: 'rna_coverage',
    }

    #: L'unite depend du type. Elle s'affiche DANS le champ de saisie : un
    #: help_text partage entre trois lignes identiques de formulaire n'empeche
    #: pas de taper 80 pour 80 X dans la ligne ARN, ce qui produirait un Tier A
    #: errone.
    UNIT = {
        TYPE_NORMAL_DNA: 'X',
        TYPE_TUMOUR_DNA: 'X',
        TYPE_TUMOUR_RNA: 'M reads',
    }

    #: Abreviation d'une lettre, pour les colonnes etroites.
    SHORT = {TYPE_NORMAL_DNA: 'N', TYPE_TUMOUR_DNA: 'D', TYPE_TUMOUR_RNA: 'R'}

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='specimens')
    specimen_type = models.CharField(
        max_length=16, choices=TYPE_CHOICES, verbose_name=_('Specimen type'))
    status = models.CharField(
        max_length=32, choices=statuses.ALL_CHOICES, default=statuses.DEFAULT,
        db_index=True, verbose_name=_('Status'))
    coverage = models.FloatField(
        null=True, blank=True, verbose_name=_('Coverage'),
        help_text=_('X for DNA, million reads for RNA.'))
    external_id = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name=_('Sequencing centre ID'),
        help_text=_('Identifier issued by the sequencing centre, if any.'))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Specimen')
        verbose_name_plural = _('Specimens')
        constraints = [
            models.UniqueConstraint(
                fields=['case', 'specimen_type'], name='uniq_specimen_per_case'),
        ]

    def __str__(self):
        return f"{self.case.name} · {self.get_specimen_type_display()}"

    @property
    def unit(self):
        return self.UNIT.get(self.specimen_type, '')

    @property
    def short_code(self):
        return self.SHORT.get(self.specimen_type, '?')

    @property
    def stage_index(self):
        """0, 1 ou 2 : nombre de segments pleins dans la barre de progression."""
        return statuses.stage_index(self.status)

    @property
    def needs_classification(self):
        return statuses.is_legacy(self.status)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Le cas reste la source de verite affichee dans les listes : on le
        # remet en phase des qu'un specimen bouge.
        self.case.sync_from_specimens()


# ---------------------------------------------------------------------------
# Changement de statut en lot
#
# Remplace l'aller-retour CSV : cases a cocher dans la liste, un statut, un
# bouton. Chaque application est journalisee ligne par ligne -- c'est ce qui
# rend l'annulation possible. Sans trace, « annuler » ne pourrait que deviner.
# ---------------------------------------------------------------------------

class BatchOperation(models.Model):
    """Une application de statut en lot, annulable."""

    APPLY_ALL = 'all'

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='batch_operations')
    performed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='batch_operations')
    performed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    status_set = models.CharField(max_length=32, choices=statuses.ALL_CHOICES)
    applied_to = models.CharField(max_length=16, default=APPLY_ALL)
    case_count = models.PositiveIntegerField(default=0)

    undone_at = models.DateTimeField(null=True, blank=True)
    undone_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='batch_undos')

    class Meta:
        ordering = ['-performed_at']
        verbose_name = _('Batch operation')
        verbose_name_plural = _('Batch operations')

    def __str__(self):
        return f"{self.case_count} cases -> {self.status_set}"

    @property
    def is_undone(self):
        return self.undone_at is not None

    @property
    def target_label(self):
        if self.applied_to == self.APPLY_ALL:
            return _('all specimens')
        return dict(Specimen.TYPE_CHOICES).get(self.applied_to, self.applied_to)

    def undo(self, user=None):
        """Remet chaque specimen a sa valeur d'avant -- s'il n'a pas rebouge.

        Un specimen modifie depuis n'est PAS touche : annuler une operation ne
        doit pas ecraser le travail fait apres elle. C'est la difference entre
        une annulation et un retour en arriere aveugle.
        """
        if self.is_undone:
            return 0

        rendus = 0
        with transaction.atomic():
            cas_touches = set()
            for change in self.changes.select_related('specimen'):
                specimen = change.specimen
                if specimen.status != change.new_status:
                    continue  # a rebouge depuis : on n'y touche pas
                specimen.status = change.old_status
                specimen.save(update_fields=['status', 'updated_at'])
                cas_touches.add(specimen.case_id)
                rendus += 1

            for case in Case.objects.filter(id__in=cas_touches):
                case.sync_from_specimens()

            self.undone_at = timezone.now()
            self.undone_by = user
            self.save(update_fields=['undone_at', 'undone_by'])

        return rendus


class SpecimenStatusChange(models.Model):
    """Une ligne de journal : ce specimen, de cet etat vers celui-la."""

    batch = models.ForeignKey(
        BatchOperation, on_delete=models.CASCADE, related_name='changes')
    specimen = models.ForeignKey(
        Specimen, on_delete=models.CASCADE, related_name='status_changes')
    old_status = models.CharField(max_length=32)
    new_status = models.CharField(max_length=32)

    class Meta:
        verbose_name = _('Specimen status change')
        verbose_name_plural = _('Specimen status changes')

    def __str__(self):
        return f"{self.specimen_id}: {self.old_status} -> {self.new_status}"

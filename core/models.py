from django.db import models, transaction
from django.db.models import F, Max
from django.contrib.auth.models import User, Group
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# ---------------------------------------------------------------------------
# Suppression douce
#
# GARDE-FOU DONNEES : rien ne doit pouvoir quitter la base par le chemin d'une
# interface web. Supprimer un projet effacait jusqu'ici le projet ET ses cas en
# cascade -- mesure sur P06 : 256 cas detruits derriere une simple page de
# confirmation. Les lignes sont desormais marquees, jamais retirees.
# ---------------------------------------------------------------------------

class AliveManager(models.Manager):
    """Gestionnaire par defaut : ne voit que les lignes non supprimees."""

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


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
    
    # Status options
    STATUS_CREATED = 'created'
    STATUS_RECEIVED = 'received'
    STATUS_INCOMPLETE = 'incomplete'
    STATUS_UNKNOWN = 'unknown'
    STATUS_LIBRARY_PREPPED = 'library_prepped'
    STATUS_SEQUENCED = 'sequenced'
    STATUS_TRANSFERRED = 'transferred_to_nfl'
    STATUS_BIOINFO = 'bioinfo_analysis'
    STATUS_COMPLETED = 'completed'
    
    STATUS_CHOICES = [
        (STATUS_CREATED, _('Created')),
        (STATUS_RECEIVED, _('Received')),
        (STATUS_INCOMPLETE, _('Incomplete')),
        (STATUS_UNKNOWN, _('Unknown')),
        (STATUS_LIBRARY_PREPPED, _('Library Prepped')),
        (STATUS_SEQUENCED, _('Sequenced')),
        (STATUS_TRANSFERRED, _('Transferred to NFL')),
        (STATUS_BIOINFO, _('Bioinfo Analysis')),
        (STATUS_COMPLETED, _('Completed')),
    ]
    
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
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=STATUS_RECEIVED)
    
    # Coverage values
    rna_coverage = models.FloatField(null=True, blank=True, verbose_name=_('RNA Coverage (M)'))
    dna_t_coverage = models.FloatField(null=True, blank=True, verbose_name=_('DNA (T) Coverage (X)'))
    dna_n_coverage = models.FloatField(null=True, blank=True, verbose_name=_('DNA (N) Coverage (X)'))
    
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
                condition=models.Q(deleted_at__isnull=True),
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

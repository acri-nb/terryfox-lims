from django.db import migrations

#: Le projet de phase 1 dont les derniers prelevements appartiennent deja a la
#: phase 2. La lecture de la base du 13 octobre 2026 est formelle : c'est le
#: SEUL projet a porter des cas au-dela du seuil, ce que le consortium
#: soupconnait sans en etre sur.
SOURCE = 'P12_Pan-Cancer EVs'

#: Le nom demande, sans prefixe P01_ / P02_ : la numerotation des projets de la
#: phase 1 n'a pas a etre reconduite dans la seconde.
CIBLE = 'PanCancer-EV'

#: Tout ACC a partir de ce numero est un prelevement de phase 2. A la lecture,
#: les cas concernes vont de 1499 a 1506 -- huit numeros pour huit cas, donc
#: l'intervalle est plein et la coupure ne traverse aucun ensemble.
SEUIL = 1499


def ouvrir_la_phase2(apps, schema_editor):
    """Cree PanCancer-EV et y DEPLACE les cas, sans jamais en recreer un.

    Le point essentiel, et la raison pour laquelle ceci est un deplacement et
    non une suppression suivie d'une creation : les specimens portent deja une
    etiquette imprimee avec leur ACC. Recreer les cas leur attribuerait de
    nouveaux numeros et rendrait fausses des etiquettes collees sur des tubes
    au congelateur. Changer `project_id` laisse l'ACC, les specimens, les
    couvertures, les commentaires, les accessions et l'historique exactement ou
    ils sont.

    Le deplacement vise `all_objects` : une tentative archivee par une
    re-soumission partage l'ACC de la tentative courante, et les separer entre
    deux projets couperait l'historique d'un meme patient en deux.
    """
    Project = apps.get_model('core', 'Project')
    Case = apps.get_model('core', 'Case')

    source = Project.all_objects.filter(name=SOURCE, deleted_at__isnull=True).first()
    if source is None:
        # Deux situations tres differentes derriere la meme absence. Sur une
        # base NEUVE -- une installation depuis zero, ou la base de test que
        # chaque execution de la suite fabrique -- il n'y a simplement rien a
        # deplacer. Sur une base peuplee, le projet a ete renomme ou supprime
        # depuis la lecture du 13 octobre, et deplacer en aveugle serait pire
        # que s'arreter.
        if not Project.all_objects.exists():
            return
        raise RuntimeError(
            f"projet source introuvable : {SOURCE!r}, alors que la base "
            "contient des projets. Il a ete renomme ou supprime depuis la "
            "lecture du 13 octobre ; verifier le nom exact avant de rejouer."
        )

    # `name` ne porte aucune contrainte d'unicite : sans ce get_or_create, une
    # migration rejouee apres une restauration creerait un second PanCancer-EV
    # et repartirait les cas entre les deux.
    cible, cree = Project.all_objects.get_or_create(
        name=CIBLE,
        deleted_at__isnull=True,
        defaults={
            'phase': 2,
            'kind': source.kind,
            'project_lead': source.project_lead,
            'created_by': source.created_by,
            'description': (
                'Phase 2 cohort. Opened from the Phase 2 samples of '
                f'{SOURCE}; the cases were moved, never re-created, so their '
                'ACC numbers still match the labels on the tubes.'
            ),
        },
    )

    deplaces = Case.all_objects.filter(
        project=source, acc_number__gte=SEUIL).update(project=cible)

    print(f"\n    {CIBLE} : {'cree' if cree else 'deja present'}")
    print(f"    {deplaces} cas deplaces depuis {SOURCE} (ACC >= {SEUIL})")


def refermer_la_phase2(apps, schema_editor):
    """Remet les cas dans leur projet d'origine et retire la cible.

    Symetrique du sens direct : le retour arriere deplace lui aussi, il ne
    supprime aucun cas. Le projet n'est retire que s'il est vide, pour qu'un
    cas cree directement dedans entre-temps ne disparaisse pas avec lui.
    """
    Project = apps.get_model('core', 'Project')
    Case = apps.get_model('core', 'Case')

    source = Project.all_objects.filter(name=SOURCE, deleted_at__isnull=True).first()
    cible = Project.all_objects.filter(name=CIBLE, deleted_at__isnull=True).first()
    if source is None or cible is None:
        return

    Case.all_objects.filter(project=cible, acc_number__gte=SEUIL).update(project=source)
    if not Case.all_objects.filter(project=cible).exists():
        cible.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0033_project_phase'),
    ]

    operations = [
        migrations.RunPython(ouvrir_la_phase2, refermer_la_phase2),
    ]

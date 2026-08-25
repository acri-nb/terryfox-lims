"""Cree le projet « Referred Cases ».

Categorie a part pour les patients referes par un medecin -- clinique
d'oncologie, cas urgents -- qui n'appartiennent a aucun projet de recherche de
la phase 1. Sans elle, ces cas atterrissent dans un projet de recherche auquel
ils ne se rattachent pas, et faussent les effectifs que le PI rapporte.

Le retour arriere ne supprime le projet que s'il est reste vide : on ne detruit
pas des cas en revenant sur une migration.
"""

from django.db import migrations

NOM = 'Referred Cases'
DESCRIPTION = (
    'Urgent cases referred by physicians, outside the phase 1 research '
    'projects. The biobank identifier may arrive after the case is created.'
)


def creer(apps, schema_editor):
    Project = apps.get_model('core', 'Project')
    User = apps.get_model('auth', 'User')

    if Project.objects.filter(name=NOM).exists():
        print(f"\n    projet '{NOM}' deja present, rien a faire")
        return

    # created_by est obligatoire. Le premier superutilisateur fait office de
    # createur ; sur une base neuve sans compte -- une base de test -- on ne
    # cree rien plutot que d'inventer un utilisateur.
    createur = User.objects.filter(is_superuser=True).order_by('id').first()
    if createur is None:
        print(f"\n    aucun superutilisateur : projet '{NOM}' non cree")
        return

    Project.objects.create(
        name=NOM,
        kind='referred',
        description=DESCRIPTION,
        created_by=createur,
    )
    print(f"\n    projet '{NOM}' cree")


def retirer(apps, schema_editor):
    Project = apps.get_model('core', 'Project')
    Case = apps.get_model('core', 'Case')

    projet = Project.objects.filter(name=NOM, kind='referred').first()
    if projet is None:
        return
    if Case.objects.filter(project=projet).exists():
        print(f"\n    projet '{NOM}' conserve : il contient des cas")
        return
    projet.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_priority_and_referred'),
    ]

    operations = [
        migrations.RunPython(creer, retirer),
    ]

from django.db import migrations, models


def descendre_les_projets_existants(apps, schema_editor):
    """Tout ce qui existe aujourd'hui appartient a la phase 1.

    Le champ a pour defaut la phase 2, qui est la bonne valeur pour un projet
    CREE a partir de maintenant. Les projets deja en base precedent cette
    notion : les laisser au defaut les afficherait tous comme phase 2, et le
    repli de l'accueil serait vide le jour de la mise en service.

    Une exception, et c'est un choix qui se discute : « Referred Cases » reste
    en phase 2. Ce n'est pas une cohorte de recherche mais une arrivee continue
    de cas references par un medecin, souvent urgents. Le replier derriere un
    clic au motif qu'il est ancien reviendrait a cacher precisement ce qui doit
    rester visible. Le champ est modifiable depuis l'ecran du projet si cette
    lecture ne convient pas.
    """
    Project = apps.get_model('core', 'Project')
    Project.all_objects.exclude(kind='referred').update(phase=1)


def tout_remonter(apps, schema_editor):
    """Retour arriere : on rend au champ sa valeur par defaut partout.

    La migration inverse ne peut pas restaurer une repartition qui n'existait
    pas avant elle ; elle remet simplement l'etat neutre, ce qui est exactement
    ce que RemoveField fera juste apres.
    """
    Project = apps.get_model('core', 'Project')
    Project.all_objects.update(phase=2)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0032_consent_and_report_returned'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='phase',
            field=models.PositiveSmallIntegerField(
                choices=[(1, 'Phase 1'), (2, 'Phase 2')],
                db_index=True, default=2,
                help_text='Phase 1 projects are collapsed on the home page.',
                verbose_name='Phase',
            ),
        ),
        migrations.RunPython(descendre_les_projets_existants, tout_remonter),
    ]

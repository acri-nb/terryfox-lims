"""Schema des identifiants generes par le LIMS.

ECRITE A LA MAIN, DELIBEREMENT.

makemigrations avait produit RemoveField('other_id') + AddField('biobank_id'),
ce qui aurait efface les Biobank ID des 1329 cas -- exactement la colonne par
laquelle la biobanque recherche. RenameField conserve les donnees : la colonne
est renommee en place, aucune valeur n'est touchee.

Migration de schema uniquement. Le remplissage d'acc_number est en 0021, la
contrainte d'unicite en 0022, une fois les donnees propres.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0019_soft_delete_project_case'),
    ]

    operations = [
        migrations.CreateModel(
            name='IdentifierSequence',
            fields=[
                ('key', models.CharField(max_length=32, primary_key=True, serialize=False)),
                ('last_value', models.PositiveIntegerField(default=0)),
            ],
            options={
                'verbose_name': 'Identifier sequence',
                'verbose_name_plural': 'Identifier sequences',
            },
        ),

        # >>> Le coeur de cette migration : renommer, ne pas recreer. <<<
        migrations.RenameField(
            model_name='case',
            old_name='other_id',
            new_name='biobank_id',
        ),
        migrations.AlterField(
            model_name='case',
            name='biobank_id',
            field=models.CharField(
                blank=True, db_index=True, max_length=255, null=True,
                help_text='The identifier used by the biobank. Searchable.',
                verbose_name='Biobank ID',
            ),
        ),

        migrations.AddField(
            model_name='case',
            name='acc_number',
            field=models.PositiveIntegerField(
                blank=True, db_index=True, null=True, verbose_name='ACC number'),
        ),
        migrations.AlterField(
            model_name='case',
            name='name',
            field=models.CharField(max_length=255, verbose_name='ACC'),
        ),
    ]

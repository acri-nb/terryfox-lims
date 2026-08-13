"""Unicite de l'ACC, posee une fois les donnees remplies et verifiees.

Unicite DURE, et gratuite : les 1329 cas existants n'ont aucun doublon de nom,
mesure avant ecriture. Elle est desormais tenable sans risque de bloquer
quiconque, puisque l'ACC est genere par le LIMS et non plus saisi.

Conditionnee sur les cas vivants : un cas retire ne doit pas empecher la
creation d'un autre.

L'unicite du Biobank ID reste volontairement SOUPLE, controlee dans le
formulaire (Case.find_biobank_id_conflict). Deux projets partagent aujourd'hui
un meme espace de numerotation nu -- P08_CRC utilise 5..849, P09_BC_EV
102..850 -- et une contrainte dure bloquerait un jour une technicienne sur le
vrai identifiant d'un patient.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_backfill_acc_numbers'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='case',
            constraint=models.UniqueConstraint(
                fields=('acc_number',),
                condition=models.Q(('deleted_at__isnull', True)),
                name='uniq_active_acc_number',
                violation_error_message='This ACC identifier is already used by another case.',
            ),
        ),
    ]

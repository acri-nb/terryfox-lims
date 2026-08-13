"""Remplit acc_number a partir des noms existants, et amorce le compteur.

Les 1329 cas suivent tous le format 'ACC-####', numeros 1 a 1498, sans aucun
doublon -- verifie sur la base reelle avant d'ecrire cette migration. Le
remplissage se contente donc de lire le nombre deja present dans le nom.

Un cas dont le nom ne suivrait pas ce format garde acc_number a NULL : SQLite
considere les NULL comme distincts dans un index unique, donc la contrainte de
0022 les tolere, et ils apparaissent dans le rapport de fin de migration.

Le compteur demarre au-dessus du plus grand numero rencontre : les 169 trous ne
sont jamais reutilises. Un ACC libere peut deja figurer sur une etiquette de
congelateur ou un dossier papier ; le reattribuer ferait porter le meme
identifiant a deux patients differents.
"""

import re

from django.db import migrations

ACC_RE = re.compile(r'^ACC-(\d+)$')
SEQUENCE_KEY = 'acc'


def fill(apps, schema_editor):
    Case = apps.get_model('core', 'Case')
    IdentifierSequence = apps.get_model('core', 'IdentifierSequence')

    updated, skipped, highest = [], [], 0
    for case in Case.objects.all().only('id', 'name', 'acc_number'):
        match = ACC_RE.match((case.name or '').strip())
        if not match:
            skipped.append(case.name)
            continue
        number = int(match.group(1))
        case.acc_number = number
        highest = max(highest, number)
        updated.append(case)

    Case.objects.bulk_update(updated, ['acc_number'], batch_size=500)

    IdentifierSequence.objects.update_or_create(
        key=SEQUENCE_KEY, defaults={'last_value': highest},
    )

    print(f"\n    acc_number rempli sur {len(updated)} cas, compteur amorce a {highest}")
    if skipped:
        apercu = ', '.join(repr(n) for n in skipped[:10])
        print(f"    {len(skipped)} nom(s) hors format 'ACC-####', laisses a NULL : {apercu}")


def unfill(apps, schema_editor):
    """Reversible : on remet acc_number a NULL et on retire le compteur.

    `name` n'a jamais ete modifie par cette migration, donc rien d'autre a
    defaire -- l'information n'a pas ete deplacee, seulement recopiee.
    """
    Case = apps.get_model('core', 'Case')
    IdentifierSequence = apps.get_model('core', 'IdentifierSequence')

    Case.objects.update(acc_number=None)
    IdentifierSequence.objects.filter(key=SEQUENCE_KEY).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_identifiers'),
    ]

    operations = [
        migrations.RunPython(fill, unfill),
    ]

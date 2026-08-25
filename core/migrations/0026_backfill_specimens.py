"""Repartit les 1329 cas existants en specimens, sans rien perdre.

Les trois colonnes de couverture de Case correspondent une pour une aux trois
specimens : dna_n -> Normal (ADN), dna_t -> Tumeur (ADN), rna -> Tumeur (ARN).
Le remplissage se contente donc de recopier ; aucune valeur n'est calculee, et
les colonnes d'origine sont CONSERVEES comme miroir. C'est ce qui laisse
calculate_tier() inchange, et donc la distribution des tiers identique.

Projets sans ARN
----------------
Le specimen d'ARN n'est pas cree pour les projets dont AUCUN cas ne porte de
valeur d'ARN : leur protocole n'en prevoit pas, et leur en fabriquer un les
laisserait « en attente de Tumeur (ARN) » a perpetuite. La regle est deduite de
la donnee, pas d'une liste en dur, et les projets concernes sont affiches.
Sur la base actuelle cela ne vise que P10_Prostate, 32 cas sur 32.

Statuts
-------
  couverture presente -> le sequencage a produit ce specimen. On reprend le
      statut du cas traduit en v2 ; s'il n'est pas traduisible (incomplete,
      unknown), une couverture mesuree implique tout de meme une analyse, donc
      analysis_complete.

  couverture absente  -> soit rien n'a encore ete produit, soit on l'ignore. Au
      tout debut du parcours on garde le statut du cas ; au-dela, on marque
      « Unknown (pre-V2) », qui forme la file de travail que l'outil de
      changement en lot est fait pour vider.
"""

from django.db import migrations

# Correspondance figee ici : une migration ne doit pas dependre de constantes
# applicatives qui peuvent changer plus tard.
V1_TO_V2 = {
    'created': 'case_created',
    'received': 'received',
    'library_prepped': 'library_complete',
    'sequenced': 'sequencing_complete',
    'transferred_to_nfl': 'transferred_to_cair',
    'bioinfo_analysis': 'analyzing',
    'completed': 'analysis_complete',
    'incomplete': 'unknown_legacy',
    'unknown': 'unknown_legacy',
}
RANG = {
    'unknown_legacy': 0, 'case_created': 10, 'sent_to_sequencing': 20,
    'received': 30, 'qc_complete': 40, 'library_complete': 50,
    'iseq_finished': 60, 'sequencing_complete': 70,
    'transferred_to_cair': 80, 'analyzing': 90, 'analysis_complete': 100,
}
LEGACY = 'unknown_legacy'
DEBUT_DE_PARCOURS = RANG['sent_to_sequencing']

# (type de specimen, colonne miroir sur Case)
TYPES = [
    ('normal_dna', 'dna_n_coverage'),
    ('tumour_dna', 'dna_t_coverage'),
    ('tumour_rna', 'rna_coverage'),
]


def statut_du_specimen(statut_cas_v2, couverture):
    if couverture is not None:
        return statut_cas_v2 if statut_cas_v2 != LEGACY else 'analysis_complete'
    if RANG.get(statut_cas_v2, 0) <= DEBUT_DE_PARCOURS:
        return statut_cas_v2
    return LEGACY


def moins_avance(statuts):
    connus = [s for s in statuts if s != LEGACY]
    if not connus:
        return LEGACY if statuts else 'case_created'
    return min(connus, key=lambda s: RANG.get(s, 0))


def repartir(apps, schema_editor):
    Case = apps.get_model('core', 'Case')
    Specimen = apps.get_model('core', 'Specimen')
    Project = apps.get_model('core', 'Project')

    # Projets sans aucune valeur d'ARN : deduits de la donnee, pas codes en dur.
    sans_arn = set()
    for projet in Project.objects.all():
        cas = Case.objects.filter(project=projet)
        if cas.exists() and not cas.exclude(rna_coverage=None).exists():
            sans_arn.add(projet.id)
            print(f"\n    projet sans ARN : {projet.name} "
                  f"({cas.count()} cas) -> pas de specimen d'ARN")

    a_creer = []
    maj_cas = []
    compte_statuts = {}

    for cas in Case.objects.all().only(
            'id', 'project_id', 'status',
            'dna_n_coverage', 'dna_t_coverage', 'rna_coverage'):

        statut_v2 = V1_TO_V2.get(cas.status, LEGACY)
        statuts_poses = []

        for type_specimen, colonne in TYPES:
            if type_specimen == 'tumour_rna' and cas.project_id in sans_arn:
                continue
            couverture = getattr(cas, colonne)
            statut = statut_du_specimen(statut_v2, couverture)
            statuts_poses.append(statut)
            compte_statuts[statut] = compte_statuts.get(statut, 0) + 1
            a_creer.append(Specimen(
                case_id=cas.id,
                specimen_type=type_specimen,
                status=statut,
                coverage=couverture,
            ))

        cas.status = moins_avance(statuts_poses)
        maj_cas.append(cas)

    Specimen.objects.bulk_create(a_creer, batch_size=500)
    Case.objects.bulk_update(maj_cas, ['status'], batch_size=500)

    print(f"\n    {len(a_creer)} specimens crees pour {len(maj_cas)} cas")
    for statut, n in sorted(compte_statuts.items(), key=lambda kv: -kv[1]):
        print(f"      {statut:22s} {n}")


def defaire(apps, schema_editor):
    """Reversible : on supprime les specimens et on rend aux cas leur statut v1.

    Les couvertures n'ont jamais ete deplacees, seulement recopiees : il n'y a
    donc rien a leur rendre.
    """
    Case = apps.get_model('core', 'Case')
    Specimen = apps.get_model('core', 'Specimen')

    inverse = {}
    for v1, v2 in V1_TO_V2.items():
        inverse.setdefault(v2, v1)
    # unknown_legacy est ambigu (incomplete ou unknown) : on retient incomplete,
    # de loin le plus frequent (428 contre 41).
    inverse[LEGACY] = 'incomplete'

    Specimen.objects.all().delete()
    for cas in Case.objects.all().only('id', 'status'):
        Case.objects.filter(pk=cas.pk).update(
            status=inverse.get(cas.status, 'unknown'))


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_specimens'),
    ]

    operations = [
        migrations.RunPython(repartir, defaire),
    ]

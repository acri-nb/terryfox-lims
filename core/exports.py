"""Construction des exports CSV.

Deux niveaux de granularite, et deux formes differentes a dessein.

`cases.csv` est LARGE : une ligne par cas, avec un bloc de colonnes fixe pour
chacun des trois specimens. C'est ce format qu'un PI croise avec sa feuille
clinique par RECHERCHEV sur le Biobank ID. Un fichier long, une ligne par
specimen, triplerait son effectif sans qu'il s'en apercoive.

`specimens.csv` sert la granularite fine, dans un fichier separe.

Les tentatives archivees vont dans `cases_archived.csv`, jamais melangees aux
cas actifs derriere une colonne d'etat : une erreur de filtre gonflerait un
effectif publie.

Chaque fichier enfant porte (ACC, Attempt) comme cle de jointure. Joindre sur le
seul ACC apres une re-soumission dupliquerait les lignes de la tentative 1 sur
la tentative 2 : c'est le piege de correctitude le plus serieux de ces exports.
"""

import csv
import io
import zipfile
from datetime import datetime, timezone

from . import statuses
from .models import Case, Comment, Specimen

# Ordre fixe des blocs de specimen dans le fichier large.
BLOCS = [
    (Specimen.TYPE_NORMAL_DNA, 'Normal_DNA', 'X'),
    (Specimen.TYPE_TUMOUR_DNA, 'Tumour_DNA', 'X'),
    (Specimen.TYPE_TUMOUR_RNA, 'Tumour_RNA', 'M_reads'),
]

ENTETE_CAS = (
    ['ACC', 'Attempt', 'Biobank_ID', 'Project', 'Project_Lead', 'Priority',
     'Case_Status', 'Tier']
    + [f'{nom}_{champ}' for _t, nom, unite in BLOCS
       for champ in ('Status', 'Preservation', 'Consent', f'Coverage_{unite}')]
    + ['Specimens_To_Classify', 'Consent_Generation_All', 'Report_Returned',
       'Report_Returned_On', 'Comments', 'Created', 'Created_By', 'Updated']
)

ENTETE_SPECIMENS = [
    'ACC', 'Attempt', 'Biobank_ID', 'Project', 'Specimen_Type', 'Status',
    'Stage', 'Preservation', 'Consent_Generation_All', 'Coverage', 'Unit',
    'Sequencing_Centre_ID', 'Updated',
]

ENTETE_COMMENTAIRES = ['ACC', 'Attempt', 'Project', 'Author', 'Created', 'Comment']


def _date(valeur):
    return valeur.strftime('%Y-%m-%d %H:%M') if valeur else ''


def _cases_queryset(project=None, archived=False):
    """Les cas a exporter, avec tout ce qu'il faut pour eviter le N+1."""
    gestionnaire = Case.all_objects if archived else Case.objects
    queryset = (gestionnaire
                .filter(deleted_at__isnull=True)
                .select_related('project', 'project__project_lead', 'created_by')
                .prefetch_related('specimens', 'comments'))
    if archived:
        queryset = queryset.filter(is_archived=True)
    if project is not None:
        queryset = queryset.filter(project=project)
    return queryset.order_by('project__name', 'acc_number', 'attempt')


def ligne_cas(case):
    par_type = {s.specimen_type: s for s in case.specimens.all()}
    ligne = [
        case.name,
        case.attempt,
        case.biobank_id or '',
        case.project.name,
        case.project.project_lead.name if case.project.project_lead else '',
        'yes' if case.is_priority else 'no',
        statuses.LABEL_OF.get(case.status, case.status),
        case.tier,
    ]
    for type_specimen, _nom, _unite in BLOCS:
        specimen = par_type.get(type_specimen)
        if specimen is None:
            # Colonnes vides plutot qu'absentes : l'en-tete doit rester
            # identique d'un projet a l'autre, sinon les fichiers ne
            # s'empilent plus. P10 n'a pas de specimen d'ARN.
            ligne += ['not collected', '', '', '']
        else:
            ligne += [
                statuses.LABEL_OF.get(specimen.status, specimen.status),
                specimen.get_preservation_display(),
                'yes' if specimen.consented_generation_all else 'no',
                '' if specimen.coverage is None else specimen.coverage,
            ]
    specimens = list(case.specimens.all())
    ligne += [
        sum(1 for s in specimens if s.needs_classification),
        # « partial » plutot qu'un booleen : un cas dont deux specimens sur
        # trois sont consentis n'est ni consenti ni non consenti, et l'aplatir
        # dans l'un des deux ferait publier un chiffre faux.
        ('' if not specimens else
         'yes' if all(s.consented_generation_all for s in specimens) else
         'no' if not any(s.consented_generation_all for s in specimens) else
         'partial'),
        'yes' if case.report_returned else 'no',
        _date(case.report_returned_at) if case.report_returned_at else '',
        len(case.comments.all()),
        _date(case.created_at),
        # Vide pour les cas anterieurs a la v2 : ils n'ont pas de createur, et
        # en inventer un fausserait une colonne dont l'interet est l'audit.
        case.created_by.get_username() if case.created_by else '',
        _date(case.updated_at),
    ]
    return ligne


def ecrire_cas(flux, project=None, archived=False):
    writer = csv.writer(flux)
    writer.writerow(ENTETE_CAS)
    n = 0
    for case in _cases_queryset(project, archived):
        writer.writerow(ligne_cas(case))
        n += 1
    return n


def ecrire_specimens(flux, project=None):
    writer = csv.writer(flux)
    writer.writerow(ENTETE_SPECIMENS)
    etapes = {**statuses.STAGE_LABELS}
    n = 0
    for case in _cases_queryset(project):
        for specimen in case.specimens_in_order():
            writer.writerow([
                case.name, case.attempt, case.biobank_id or '', case.project.name,
                specimen.get_specimen_type_display(),
                statuses.LABEL_OF.get(specimen.status, specimen.status),
                etapes.get(statuses.STAGE_OF.get(specimen.status), ''),
                specimen.get_preservation_display(),
                'yes' if specimen.consented_generation_all else 'no',
                '' if specimen.coverage is None else specimen.coverage,
                specimen.unit,
                specimen.external_id or '',
                _date(specimen.updated_at),
            ])
            n += 1
    return n


def ecrire_commentaires(flux, project=None):
    writer = csv.writer(flux)
    writer.writerow(ENTETE_COMMENTAIRES)
    queryset = (Comment.objects
                .select_related('case', 'case__project', 'user')
                .order_by('case__acc_number', 'case__attempt', 'created_at'))
    if project is not None:
        queryset = queryset.filter(case__project=project)
    n = 0
    for comment in queryset:
        writer.writerow([
            comment.case.name, comment.case.attempt, comment.case.project.name,
            comment.user.username if comment.user else '',
            _date(comment.created_at),
            comment.text,
        ])
        n += 1
    return n


LISEZMOI = """TerryFox LIMS — data export
Generated {date}
Scope: {scope}

FILES
-----
cases.csv           One row per ACTIVE case. Wide format: a fixed block of
                    columns for each of the three specimens (Normal DNA,
                    Tumour DNA, Tumour RNA). This is the file to cross-
                    reference with a clinical sheet, keyed on Biobank_ID.

specimens.csv       One row per specimen. Use this when you need the specimens
                    themselves rather than the cases.

comments.csv        Every comment, with its case and author.

cases_archived.csv  Superseded attempts, kept in a SEPARATE file on purpose.
                    They are never mixed into cases.csv behind a state column,
                    because one filter mistake would inflate a published count.

JOINING THESE FILES
-------------------
Join on (ACC, Attempt) — never on ACC alone.

When a case is resubmitted, the new attempt reuses the same ACC. Joining
specimens.csv or comments.csv to cases.csv on ACC alone therefore fans the rows
of attempt 1 onto attempt 2, silently inflating counts and attributing the wrong
narrative to the wrong specimen.

NOTES
-----
- Coverage is in X for DNA and in million reads for RNA. The unit is in the
  column name, and in the Unit column of specimens.csv.
- "not collected" in a specimen block means the protocol does not include that
  specimen, not that the result is pending.
- Case_Status is derived: it is the least advanced specimen whose state is
  known. Specimens_To_Classify counts those inherited from V1 whose state has
  not been established yet.
- Tier is derived from coverage and never entered by hand.

CONTENTS
--------
{counts}
"""


def construire_archive(project=None, scope='All projects'):
    """Assemble le lot ZIP. Bibliotheque standard uniquement, aucune dependance."""
    tampon = io.BytesIO()
    comptes = {}

    with zipfile.ZipFile(tampon, 'w', zipfile.ZIP_DEFLATED) as archive:
        for nom, ecrivain in (
            ('cases.csv', lambda f: ecrire_cas(f, project)),
            ('specimens.csv', lambda f: ecrire_specimens(f, project)),
            ('comments.csv', lambda f: ecrire_commentaires(f, project)),
            ('cases_archived.csv', lambda f: ecrire_cas(f, project, archived=True)),
        ):
            flux = io.StringIO()
            comptes[nom] = ecrivain(flux)
            archive.writestr(nom, flux.getvalue())

        archive.writestr('README.txt', LISEZMOI.format(
            date=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
            scope=scope,
            counts='\n'.join(f'{nom:20s} {n} row{"s" if n != 1 else ""}'
                             for nom, n in comptes.items()),
        ))

    tampon.seek(0)
    return tampon, comptes

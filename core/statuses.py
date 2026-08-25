"""Vocabulaire des statuts de la v2.

Dix statuts repartis en trois etapes, dans l'ordre ou le travail se fait :
biobanque, centre de sequencage, bio-informatique.

Le regroupement n'est pas decoratif, il porte l'ORDRE. Dix badges de couleurs
differentes n'apprennent a personne que « QC complete » precede « Library
complete » ; une liste deroulante groupee, si. C'est aussi ce qui permet a
l'interface de dessiner une progression plutot qu'une pastille.

Le rang sert au calcul du statut de cas : celui-ci vaut le statut du specimen le
moins avance. Les rangs sont espaces de dix pour pouvoir inserer une etape sans
tout renumeroter.
"""

from django.utils.translation import gettext_lazy as _

# --- etapes -----------------------------------------------------------------

STAGE_BIOBANK = 'biobank'
STAGE_SEQUENCING = 'sequencing'
STAGE_BIOINFO = 'bioinformatics'
STAGE_LEGACY = 'legacy'

STAGE_LABELS = {
    STAGE_BIOBANK: _('Biobank'),
    STAGE_SEQUENCING: _('Sequencing Center'),
    STAGE_BIOINFO: _('Bioinformatics'),
    STAGE_LEGACY: _('Needs classification'),
}

ORDERED_STAGES = [STAGE_BIOBANK, STAGE_SEQUENCING, STAGE_BIOINFO]

# --- statuts ----------------------------------------------------------------

CASE_CREATED = 'case_created'
SENT_TO_SEQUENCING = 'sent_to_sequencing'
RECEIVED = 'received'
QC_COMPLETE = 'qc_complete'
LIBRARY_COMPLETE = 'library_complete'
ISEQ_FINISHED = 'iseq_finished'
SEQUENCING_COMPLETE = 'sequencing_complete'
TRANSFERRED_TO_CAIR = 'transferred_to_cair'
ANALYZING = 'analyzing'
ANALYSIS_COMPLETE = 'analysis_complete'

# Statut de transition, pose par la migration sur les specimens dont on ne peut
# pas deduire l'etat reel. Il n'est jamais propose a la saisie : il constitue la
# file de travail que l'outil de changement en lot est fait pour vider.
UNKNOWN_LEGACY = 'unknown_legacy'

# (slug, libelle, etape, rang)
DEFINITIONS = [
    (CASE_CREATED,        _('Case Created'),                STAGE_BIOBANK,     10),
    (SENT_TO_SEQUENCING,  _('Sent to Sequencing Center'),   STAGE_BIOBANK,     20),

    (RECEIVED,            _('Received'),                    STAGE_SEQUENCING,  30),
    (QC_COMPLETE,         _('QC complete'),                 STAGE_SEQUENCING,  40),
    (LIBRARY_COMPLETE,    _('Library complete'),            STAGE_SEQUENCING,  50),
    (ISEQ_FINISHED,       _('iSeq finished'),               STAGE_SEQUENCING,  60),
    (SEQUENCING_COMPLETE, _('Sequencing Complete'),         STAGE_SEQUENCING,  70),

    (TRANSFERRED_TO_CAIR, _('Transferred to CAIR'),         STAGE_BIOINFO,     80),
    (ANALYZING,           _('Analyzing'),                   STAGE_BIOINFO,     90),
    (ANALYSIS_COMPLETE,   _('Analysis complete'),           STAGE_BIOINFO,    100),

    (UNKNOWN_LEGACY,      _('Unknown (pre-V2)'),            STAGE_LEGACY,       0),
]

STAGE_OF = {slug: stage for slug, _label, stage, _rank in DEFINITIONS}
RANK_OF = {slug: rank for slug, _label, _stage, rank in DEFINITIONS}
LABEL_OF = {slug: label for slug, label, _stage, _rank in DEFINITIONS}

ALL_CHOICES = [(slug, label) for slug, label, _stage, _rank in DEFINITIONS]

#: Statuts proposes a la saisie. Exclut le statut de transition : on ne demande
#: a personne de classer un cas en « inconnu ».
SELECTABLE = [slug for slug, _l, stage, _r in DEFINITIONS if stage != STAGE_LEGACY]

#: Choix groupes par etape, pour les listes deroulantes. Les <optgroup> font que
#: le menu lui-meme enseigne l'enchainement du travail.
GROUPED_CHOICES = [
    (STAGE_LABELS[stage], [
        (slug, label) for slug, label, s, _r in DEFINITIONS if s == stage
    ])
    for stage in ORDERED_STAGES
]

DEFAULT = CASE_CREATED


def is_legacy(slug):
    """Vrai pour un statut de transition, a reclasser."""
    return STAGE_OF.get(slug) == STAGE_LEGACY


def rank(slug):
    return RANK_OF.get(slug, 0)


def stage_index(slug):
    """0, 1 ou 2 pour les trois etapes ; -1 pour un statut de transition.

    Sert a remplir la barre de progression : les segments d'indice inferieur ou
    egal sont pleins.
    """
    stage = STAGE_OF.get(slug)
    return ORDERED_STAGES.index(stage) if stage in ORDERED_STAGES else -1


def least_advanced(slugs):
    """Statut du specimen le moins avance, en ignorant ceux a reclasser.

    Les statuts de transition sont ecartes a dessein : un cas dont l'ADN est
    analyse et dont l'ARN reste a classer doit continuer d'afficher l'avancee
    reelle de son ADN. Le sortir comme « inconnu » ferait regresser a l'ecran
    des centaines de cas que le personnel voyait termines.

    Si tous les statuts sont a reclasser, on renvoie le statut de transition :
    il n'y a alors rien d'autre a dire.
    """
    connus = [s for s in slugs if not is_legacy(s)]
    if not connus:
        return UNKNOWN_LEGACY if slugs else DEFAULT
    return min(connus, key=rank)


# --- correspondance avec le vocabulaire de la v1 ----------------------------
#
# La v1 avait neuf statuts, dont six seulement etaient utilises. Deux n'ont
# aucun equivalent v2 et representent 469 cas, soit 35 % de la base :
#
#   incomplete (428) : la donnee tranche a moitie la question -- 385 de ces 428
#       cas ont leurs deux couvertures ADN et pas d'ARN, et leurs commentaires
#       disent « Needs Normal Top-Up », « No DNA Normal fastq ». « incomplete »
#       veut donc dire « ARN en attente », ce que le modele par specimen exprime
#       nativement : les specimens ADN passent a leur etat reel, le specimen ARN
#       reste a classer.
#
#   unknown (41) : rien a en deduire.
#
# Les deux atterrissent sur UNKNOWN_LEGACY, invisible a la saisie mais visible
# dans les filtres, pour que le personnel puisse les retrouver et les vider avec
# l'outil de changement en lot -- l'usage meme pour lequel il a ete demande.

V1_TO_V2 = {
    'created':            CASE_CREATED,
    'received':           RECEIVED,
    'library_prepped':    LIBRARY_COMPLETE,
    'sequenced':          SEQUENCING_COMPLETE,
    'transferred_to_nfl': TRANSFERRED_TO_CAIR,
    'bioinfo_analysis':   ANALYZING,
    'completed':          ANALYSIS_COMPLETE,
    'incomplete':         UNKNOWN_LEGACY,
    'unknown':            UNKNOWN_LEGACY,
}

#: Libelles de la v1, pour que les fichiers CSV existants restent importables.
V1_LABELS = {
    'Created': 'created',
    'Received': 'received',
    'Incomplete': 'incomplete',
    'Unknown': 'unknown',
    'Library Prepped': 'library_prepped',
    'Sequenced': 'sequenced',
    'Transferred to NFL': 'transferred_to_nfl',
    'Bioinfo Analysis': 'bioinfo_analysis',
    'Completed': 'completed',
}


def from_any(value):
    """Accepte un slug v2, un slug v1 ou un libelle v1. Renvoie None si inconnu.

    Sert a l'import CSV : les equipes ont des fichiers au vocabulaire v1, et
    rien ne justifie de les invalider.
    """
    if not value:
        return None
    brut = str(value).strip()

    if brut in RANK_OF:
        return brut
    if brut in V1_TO_V2:
        return V1_TO_V2[brut]

    slug_v1 = V1_LABELS.get(brut)
    if slug_v1:
        return V1_TO_V2[slug_v1]

    # Libelles v2, compares sans tenir compte de la casse.
    for slug, label in ALL_CHOICES:
        if brut.casefold() == str(label).casefold():
            return slug
    return None

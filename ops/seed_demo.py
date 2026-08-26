#!/usr/bin/env python3
"""Peuple une base de DEMONSTRATION, jamais la base reelle.

Les captures du README vivent dans un depot public. Y faire figurer des
identifiants de biobanque reels reviendrait a les publier : ce script fabrique
donc un jeu synthetique, avec des couvertures tirees d'une graine fixe pour que
deux executions donnent la meme image.

    DATABASE_PATH=/tmp/demo.sqlite3 python ops/seed_demo.py
"""
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "terryfox_lims.settings")

import django  # noqa: E402
django.setup()

from django.contrib.auth.models import User  # noqa: E402
from core import statuses  # noqa: E402
from core.models import Case, Comment, Project, ProjectLead, Specimen  # noqa: E402

ALEA = random.Random(20260826)

PROJETS = [
    ("P01_Lung - ctDNA",              "Dr Nguyen",           18),
    ("P02_CRC - Immunoprofiling",     "Dr Okafor/Dr Lindqvist", 24),
    ("P03_GBM - IN-SIGHT",            "Dr Marchetti",        15),
    ("P04_BC_EV - Microenvironment",  "Dr Haugen",           12),
    ("P05_PanCancer - Metabolomics",  "Dr Sorensen/Dr Ibarra", 9),
]

#: Un projet dont le protocole ne prevoit pas d'ARN : le LIMS n'oblige pas a
#: trois specimens, et la demonstration doit le montrer.
SANS_ARN = "P05_PanCancer - Metabolomics"

AVANCEMENT = [
    (statuses.ANALYSIS_COMPLETE,   .46),
    (statuses.ANALYZING,           .12),
    (statuses.TRANSFERRED_TO_CAIR, .10),
    (statuses.SEQUENCING_COMPLETE, .09),
    (statuses.LIBRARY_COMPLETE,    .07),
    (statuses.QC_COMPLETE,         .06),
    (statuses.RECEIVED,            .05),
    (statuses.SENT_TO_SEQUENCING,  .03),
    (statuses.CASE_CREATED,        .02),
]

REMARQUES = [
    "Second aliquot requested from the biobank, first one below input threshold.",
    "Coverage confirmed by the sequencing centre; released for analysis.",
    "Tumour content estimated at 45 %, flagged for the pathology review.",
    "RNA integrity number of 7.2, acceptable for the protocol.",
    "Rerun scheduled: the first library failed quality control.",
]


def statut_tire():
    seuil, cumul = ALEA.random(), 0.0
    for statut, poids in AVANCEMENT:
        cumul += poids
        if seuil <= cumul:
            return statut
    return statuses.ANALYSIS_COMPLETE


def couverture(statut, genre):
    """Les couvertures n'existent qu'une fois le sequencage passe."""
    if statuses.stage_index(statut) < 2:
        return None
    if genre == Specimen.TYPE_TUMOUR_RNA:
        return round(ALEA.uniform(52, 128), 1)
    if genre == Specimen.TYPE_NORMAL_DNA:
        return round(ALEA.uniform(28, 48), 1)
    return round(ALEA.uniform(62, 118), 1)


def main():
    if Project.objects.exists():
        sys.exit("REFUS: la base n'est pas vide. Ce script ne s'applique "
                 "qu'a une base de demonstration neuve.")

    admin = User.objects.create_superuser("demo", "demo@example.org", "demo")
    print(f"  superutilisateur 'demo' cree")

    total = 0
    for nom, chef, effectif in PROJETS:
        lead = ProjectLead.objects.create(name=chef)
        projet = Project.objects.create(
            name=nom, project_lead=lead, created_by=admin,
            description="Synthetic data for documentation screenshots.")
        genres = [Specimen.TYPE_NORMAL_DNA, Specimen.TYPE_TUMOUR_DNA]
        if nom != SANS_ARN:
            genres.append(Specimen.TYPE_TUMOUR_RNA)

        for i in range(effectif):
            cas = Case.objects.create(
                project=projet,
                biobank_id=f"BBN-{ALEA.randrange(1000, 9999)}",
                is_priority=(i == 0 and ALEA.random() < .6),
            )
            cas.ensure_specimens(genres)
            statut = statut_tire()
            for specimen in cas.specimens.all():
                specimen.status = statut
                specimen.coverage = couverture(statut, specimen.specimen_type)
                specimen.save()
            cas.sync_from_specimens()
            cas.save()
            if ALEA.random() < .25:
                Comment.objects.create(case=cas, user=admin,
                                       text=ALEA.choice(REMARQUES))
            total += 1

    # Le projet des cas referes, cree vide : il illustre la separation d'avec
    # les projets de recherche sans inventer de patient.
    Project.objects.create(name="Referred Cases", created_by=admin,
                           kind=Project.KIND_REFERRED,
                           description="Physician-referred urgent cases.")

    print(f"  {Project.objects.count()} projets, {total} cas, "
          f"{Specimen.objects.count()} specimens")
    for tier in ("A", "B", "FAIL"):
        print(f"    tier {tier:4s} {Case.objects.filter(tier=tier).count()}")


if __name__ == "__main__":
    main()

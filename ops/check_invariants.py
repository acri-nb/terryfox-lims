#!/usr/bin/env python3
"""
Controle d'invariants de la base TerryFox LIMS.

Volontairement ecrit en SQL pur, sans Django : il doit pouvoir tourner avant une
migration, apres une migration, et sur une sauvegarde -- y compris quand les
modeles Python ne correspondent plus au schema du fichier.

  ./check_invariants.py                              # afficher l'etat
  ./check_invariants.py --save avant.json            # figer une reference
  ./check_invariants.py --compare avant.json         # comparer, sortir en erreur si ecart
  ./check_invariants.py --compare avant.json --allow core_case=+3
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

COUNT_TABLES = [
    "core_project",
    "core_case",
    "core_specimen",
    "core_comment",
    "core_projectlead",
    "core_accession",
    "auth_user",
]


def fail(msg):
    print(f"ECHEC: {msg}", file=sys.stderr)
    sys.exit(1)


def resolve_db(explicit):
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    if os.environ.get("TERRYFOX_DB"):
        candidates.append(Path(os.environ["TERRYFOX_DB"]))
    candidates.append(Path("/var/lib/terryfox-lims/db.sqlite3"))
    candidates.append(REPO_ROOT / "db.sqlite3")
    for c in candidates:
        if c.is_file():
            return c
    fail("aucune base trouvee. Cherche dans : " + ", ".join(str(c) for c in candidates))


def snapshot(db_path):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        snap = {
            "_db": str(db_path),
            "_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "integrity": conn.execute("PRAGMA integrity_check").fetchone()[0],
        }

        for table in COUNT_TABLES:
            try:
                snap[table] = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            except sqlite3.Error:
                # Table absente de cette version du schema : on omet la cle
                # plutot que d'y mettre un marqueur. Elle apparaitra alors comme
                # mesure NOUVELLE apres la migration qui la cree, sans bloquer --
                # tandis qu'une table qui DISPARAIT reste signalee, sa valeur
                # tombant a zero.
                pass

        # Lignes visibles dans l'application, par opposition aux lignes presentes
        # en base. Depuis la suppression douce, les deux peuvent diverger : une
        # suppression de masse accidentelle ne se verrait pas dans les comptages
        # bruts ci-dessus, mais se voit ici.
        for table in ("core_project", "core_case"):
            try:
                snap[f"vivants:{table}"] = conn.execute(
                    f"SELECT count(*) FROM {table} WHERE deleted_at IS NULL"
                ).fetchone()[0]
            except sqlite3.Error:
                # Colonne deleted_at absente : base anterieure a la migration 0019.
                # Par definition aucune ligne n'y est supprimee, donc vivants == total.
                # Sans cette equivalence, la mesure serait absente de la reference
                # prise AVANT la migration et presente APRES : le controle la lirait
                # comme un ecart de +1329 et annulerait un deploiement parfaitement sain.
                total = snap.get(table)
                if isinstance(total, int):
                    snap[f"vivants:{table}"] = total

        for row in conn.execute("SELECT tier, count(*) FROM core_case GROUP BY tier"):
            snap[f"tier:{row[0]}"] = row[1]

        for row in conn.execute("SELECT status, count(*) FROM core_case GROUP BY status"):
            snap[f"status:{row[0]}"] = row[1]

        # Integrite referentielle : rien ne doit pointer dans le vide.
        snap["orphelins:cas_sans_projet"] = conn.execute(
            "SELECT count(*) FROM core_case c "
            "LEFT JOIN core_project p ON p.id = c.project_id WHERE p.id IS NULL"
        ).fetchone()[0]
        snap["orphelins:commentaires_sans_cas"] = conn.execute(
            "SELECT count(*) FROM core_comment m "
            "LEFT JOIN core_case c ON c.id = m.case_id WHERE c.id IS NULL"
        ).fetchone()[0]

        # Unicite des identifiants : doit rester a 0 avant comme apres la v2.
        snap["doublons:nom_de_cas"] = conn.execute(
            "SELECT count(*) FROM (SELECT name FROM core_case GROUP BY name HAVING count(*) > 1)"
        ).fetchone()[0]

        # Remplissage des colonnes d'identifiants.
        #
        # C'est la mesure qui aurait revele un renommage rate : makemigrations
        # avait genere RemoveField + AddField pour other_id -> biobank_id, ce qui
        # aurait vide la colonne par laquelle la biobanque recherche. Les
        # comptages de lignes, eux, n'auraient rien vu -- 1329 cas avant, 1329
        # apres, tous vides.
        for colonne in ("biobank_id", "acc_number", "other_id"):
            try:
                snap[f"remplis:{colonne}"] = conn.execute(
                    f"SELECT count(*) FROM core_case "
                    f"WHERE {colonne} IS NOT NULL AND {colonne} != ''"
                ).fetchone()[0]
            except sqlite3.Error:
                pass  # colonne absente selon la version du schema

        # Le Biobank ID n'a volontairement PAS de contrainte d'unicite : deux
        # projets partagent un espace de numerotation nu. Le compte est donc un
        # rapport, pas une alarme -- mais un bond soudain merite un regard.
        try:
            snap["doublons:biobank_id"] = conn.execute(
                "SELECT count(*) FROM ("
                "  SELECT lower(trim(biobank_id)) AS b FROM core_case"
                "  WHERE biobank_id IS NOT NULL AND biobank_id != ''"
                "  GROUP BY b HAVING count(*) > 1)"
            ).fetchone()[0]
        except sqlite3.Error:
            pass

        return snap
    finally:
        conn.close()


def parse_allow(items):
    """--allow core_case=+3  ->  {'core_case': 3}"""
    allowed = {}
    for item in items or []:
        if "=" not in item:
            fail(f"--allow mal forme : {item!r} (attendu cle=+N ou cle=-N)")
        key, delta = item.split("=", 1)
        try:
            allowed[key] = int(delta)
        except ValueError:
            fail(f"--allow mal forme : {delta!r} n'est pas un entier")
    return allowed


def render(snap):
    width = max(len(k) for k in snap if not k.startswith("_"))
    for key, value in snap.items():
        if key.startswith("_"):
            continue
        print(f"  {key:<{width}}  {value}")


def compare(before, after, allowed):
    keys = [k for k in sorted(set(before) | set(after)) if not k.startswith("_")]
    problems, expected, unchanged, appeared = [], [], 0, []

    for key in keys:
        # Une cle absente de la reference est une mesure nouvelle, pas une donnee
        # qui a change : elle n'avait pas de valeur anterieure. On la signale sans
        # bloquer. Rien n'est masque pour autant -- si une valeur s'est deplacee
        # d'une cle vers une autre (un statut renomme, par exemple), la cle
        # d'origine chute et reste, elle, signalee comme ecart.
        if key not in before:
            appeared.append(f"{key} = {after[key]}")
            continue

        old = before.get(key, 0)
        new = after.get(key, 0)
        if old == new:
            unchanged += 1
            continue
        if isinstance(old, int) and isinstance(new, int):
            delta = new - old
            if allowed.get(key) == delta:
                expected.append(f"{key}: {old} -> {new} ({delta:+d}, attendu)")
                continue
            problems.append(f"{key}: {old} -> {new} ({delta:+d})")
        else:
            problems.append(f"{key}: {old!r} -> {new!r}")

    if after.get("integrity") != "ok":
        problems.append(f"integrity_check = {after.get('integrity')!r}")

    print(f"  {unchanged} valeurs inchangees")
    for line in appeared:
        print(f"  NOUVEAU  {line}")
    for line in expected:
        print(f"  ATTENDU  {line}")
    for line in problems:
        print(f"  ECART    {line}")

    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", help="chemin de la base")
    ap.add_argument("--save", metavar="FICHIER", help="ecrire la reference")
    ap.add_argument("--compare", metavar="FICHIER", help="comparer a une reference")
    ap.add_argument("--allow", action="append", metavar="CLE=+N", help="ecart attendu, repetable")
    args = ap.parse_args()

    db = resolve_db(args.db)
    try:
        snap = snapshot(db)
    except sqlite3.DatabaseError as exc:
        # Une base corrompue doit produire une phrase, pas une trace Python :
        # ce message est lu pendant un incident, par quelqu'un qui doit decider
        # vite s'il restaure.
        fail(f"base illisible ({db}) -> {exc}. "
             f"Restaurer : sudo {REPO_ROOT}/ops/restore_db.sh")

    if args.save:
        Path(args.save).write_text(json.dumps(snap, indent=2, sort_keys=True))
        print(f"reference ecrite : {args.save}  ({db})")
        render(snap)
        return

    if args.compare:
        ref = Path(args.compare)
        if not ref.is_file():
            fail(f"reference introuvable : {ref}")
        before = json.loads(ref.read_text())
        print(f"reference {before.get('_at')}  ->  maintenant  ({db})")
        problems = compare(before, snap, parse_allow(args.allow))
        if problems:
            print(f"\n{len(problems)} ecart(s) non autorise(s). LA MIGRATION DOIT ETRE ANNULEE.", file=sys.stderr)
            sys.exit(1)
        print("\nOK : tous les invariants sont tenus.")
        return

    print(f"{db}")
    render(snap)


if __name__ == "__main__":
    main()

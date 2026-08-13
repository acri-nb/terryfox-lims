#!/usr/bin/env python3
"""
Auto-test du controle d'invariants.

check_invariants.py est ce qui decide d'annuler ou non une migration de
production. S'il se degrade en silence -- en cessant de detecter une perte, ou
en criant sur un deploiement sain -- personne ne s'en apercoit avant l'incident.
Ces quatre scenarios tournent sur des bases synthetiques jetables, en une seconde.

    python3 ops/selftest.py
"""

import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECK = HERE / "check_invariants.py"

SCHEMA = """
CREATE TABLE core_project (id INTEGER PRIMARY KEY, name TEXT, deleted_at TEXT);
CREATE TABLE core_case (id INTEGER PRIMARY KEY, project_id INTEGER, name TEXT,
                        status TEXT, tier TEXT, deleted_at TEXT);
CREATE TABLE core_comment (id INTEGER PRIMARY KEY, case_id INTEGER, text TEXT);
CREATE TABLE core_projectlead (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE core_accession (id INTEGER PRIMARY KEY, case_id INTEGER);
CREATE TABLE auth_user (id INTEGER PRIMARY KEY, username TEXT);
"""

# Meme schema, mais sans la colonne deleted_at : une base anterieure a la
# migration 0019, telle qu'elle est au moment ou la reference est figee.
SCHEMA_PRE_0019 = SCHEMA.replace(", deleted_at TEXT", "")


def build(path, schema=SCHEMA, cases=100, projects=3):
    conn = sqlite3.connect(path)
    conn.executescript(schema)
    has_deleted = "deleted_at" in schema
    for p in range(projects):
        cols = "(id, name, deleted_at)" if has_deleted else "(id, name)"
        vals = (p, f"P{p}", None) if has_deleted else (p, f"P{p}")
        conn.execute(f"INSERT INTO core_project {cols} VALUES ({','.join('?' * len(vals))})", vals)
    for i in range(cases):
        tier = ("A", "B", "FAIL")[i % 3]
        if has_deleted:
            conn.execute(
                "INSERT INTO core_case (id, project_id, name, status, tier, deleted_at) "
                "VALUES (?,?,?,?,?,NULL)", (i, i % projects, f"ACC-{i:04d}", "completed", tier))
        else:
            conn.execute(
                "INSERT INTO core_case (id, project_id, name, status, tier) "
                "VALUES (?,?,?,?,?)", (i, i % projects, f"ACC-{i:04d}", "completed", tier))
        conn.execute("INSERT INTO core_comment (id, case_id, text) VALUES (?,?,?)", (i, i, "n"))
    conn.execute("INSERT INTO auth_user (id, username) VALUES (1, 'u')")
    conn.commit()
    conn.close()


def run(*args):
    return subprocess.run([sys.executable, str(CHECK), *args],
                          capture_output=True, text=True)


def main():
    failures = []

    def check(label, got, want):
        status = "ok  " if got == want else "ECHEC"
        print(f"  {status} {label}  (code {got}, attendu {want})")
        if got != want:
            failures.append(label)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ref = tmp / "ref.json"

        # --- 1. base saine, aucun changement : doit passer
        db = tmp / "sain.sqlite3"
        build(db)
        run("--db", str(db), "--save", str(ref))
        check("base inchangee", run("--db", str(db), "--compare", str(ref)).returncode, 0)

        # --- 2. lignes supprimees en dur : doit bloquer
        lost = tmp / "perte.sqlite3"
        build(lost)
        sqlite3.connect(lost).executescript("DELETE FROM core_case WHERE id < 5;")
        check("perte de 5 lignes", run("--db", str(lost), "--compare", str(ref)).returncode, 1)

        # --- 3. suppression douce de masse : invisible dans les comptages bruts
        soft = tmp / "douce.sqlite3"
        build(soft)
        c = sqlite3.connect(soft)
        c.executescript("UPDATE core_case SET deleted_at = '2026-01-01' WHERE project_id = 0;")
        c.commit(); c.close()
        out = run("--db", str(soft), "--compare", str(ref))
        check("suppression douce de masse", out.returncode, 1)
        if "vivants:core_case" not in out.stdout:
            failures.append("suppression douce non attribuee a vivants:core_case")
            print("       (l'ecart devrait porter sur vivants:core_case)")

        # --- 4. base pre-0019 puis migree : le deploiement sain ne doit pas bloquer
        pre = tmp / "pre.sqlite3"
        build(pre, schema=SCHEMA_PRE_0019)
        ref_pre = tmp / "ref_pre.json"
        run("--db", str(pre), "--save", str(ref_pre))
        # la migration ajoute la colonne, sans toucher aux donnees
        c = sqlite3.connect(pre)
        c.executescript("ALTER TABLE core_case ADD COLUMN deleted_at TEXT;"
                        "ALTER TABLE core_project ADD COLUMN deleted_at TEXT;")
        c.commit(); c.close()
        check("migration additive 0019", run("--db", str(pre), "--compare", str(ref_pre)).returncode, 0)

        # --- 5. base corrompue : message clair, pas de trace Python
        bad = tmp / "corrompue.sqlite3"
        build(bad)
        # Ecraser a partir de la page 3 : les pages de donnees. Viser le debut du
        # fichier ne sert a rien -- SQLite remplit la page 1 par la fin, donc son
        # milieu est de l'espace libre et integrity_check n'y voit rien.
        page = 4096
        with open(bad, "r+b") as f:
            f.seek(2 * page)
            f.write(b"\xff" * (bad.stat().st_size - 2 * page))
        out = run("--db", str(bad), "--compare", str(ref))
        check("base corrompue", out.returncode, 1)
        if "Traceback" in out.stderr:
            failures.append("base corrompue : trace Python au lieu d'un message")
            print("       (une trace Python est illisible pendant un incident)")

        # --- 6. ecart declare avec --allow : doit passer
        grown = tmp / "ajout.sqlite3"
        build(grown, cases=103)
        out = run("--db", str(grown), "--compare", str(ref),
                  "--allow", "core_case=+3", "--allow", "vivants:core_case=+3",
                  "--allow", "core_comment=+3", "--allow", "tier:A=+1",
                  "--allow", "tier:B=+1", "--allow", "tier:FAIL=+1",
                  "--allow", "status:completed=+3")
        check("ecarts declares avec --allow", out.returncode, 0)

    print()
    if failures:
        print(f"{len(failures)} scenario(s) en echec : {', '.join(failures)}")
        sys.exit(1)
    print("Le controle d'invariants se comporte correctement.")


if __name__ == "__main__":
    main()

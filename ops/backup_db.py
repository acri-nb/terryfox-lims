#!/usr/bin/env python3
"""
Sauvegarde en ligne, verifiee, de la base TerryFox LIMS.

Utilise l'API de sauvegarde en ligne de SQLite (sqlite3.Connection.backup), qui
produit une copie coherente meme pendant que gunicorn ecrit dans la base --
contrairement a un `cp`, qui peut capturer un fichier a moitie ecrit.

Toute sauvegarde est relue et comptee juste apres creation. Si elle ne
correspond pas a la source, le fichier est supprime et le script sort en erreur :
une sauvegarde non verifiee est pire qu'une absence de sauvegarde, parce qu'elle
inspire confiance.

  ./backup_db.py                                   # sauvegarde tournante
  ./backup_db.py --label pre-migration-0019        # conservee indefiniment
  ./backup_db.py --list                            # inventaire
"""

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_DEST = Path("/var/backups/terryfox-lims")
REPO_ROOT = Path(__file__).resolve().parent.parent

# Tables dont le nombre de lignes doit etre identique entre la source et la copie.
VERIFIED_TABLES = [
    "core_project",
    "core_case",
    "core_comment",
    "core_projectlead",
    "auth_user",
]

# Retention des sauvegardes tournantes.
KEEP_HOURLY = 48
KEEP_DAILY = 30
KEEP_MONTHLY = 12

STAMP_FMT = "%Y%m%dT%H%M%SZ"


def fail(msg):
    print(f"ECHEC: {msg}", file=sys.stderr)
    sys.exit(1)


def resolve_db(explicit):
    """Trouve la base : argument, variable d'environnement, /var/lib, puis le depot."""
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


def table_counts(conn):
    counts = {}
    for table in VERIFIED_TABLES:
        try:
            counts[table] = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        except sqlite3.Error:
            counts[table] = None  # table absente (base d'une autre version)
    return counts


def online_backup(src_path, dst_path):
    """Copie coherente via l'API de sauvegarde SQLite."""
    src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)
    dst = sqlite3.connect(str(dst_path))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def verify(src_path, dst_path):
    """Relit la copie : integrite SQLite, puis egalite des comptages avec la source."""
    src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)
    dst = sqlite3.connect(f"file:{dst_path}?mode=ro", uri=True)
    try:
        integrity = dst.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            return False, f"integrity_check = {integrity!r}"

        src_counts = table_counts(src)
        dst_counts = table_counts(dst)
        for table, expected in src_counts.items():
            got = dst_counts.get(table)
            if expected != got:
                return False, f"{table} : source {expected}, copie {got}"

        summary = " ".join(
            f"{t.replace('core_', '').replace('auth_', '')}={v}"
            for t, v in src_counts.items()
            if v is not None
        )
        return True, summary
    finally:
        dst.close()
        src.close()


def parse_stamp(path):
    name = path.name
    if not name.startswith("db-") or not name.endswith(".sqlite3"):
        return None
    try:
        return datetime.strptime(name[3:-8].rstrip("-"), STAMP_FMT).replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def prune(rotating_dir, dry_run=False):
    """Garde 48 horaires, 30 quotidiennes, 12 mensuelles. Supprime le reste."""
    backups = []
    for p in rotating_dir.glob("db-*.sqlite3"):
        stamp = parse_stamp(p)
        if stamp:
            backups.append((stamp, p))
    backups.sort(reverse=True)

    now = datetime.now(timezone.utc)
    keep = set()
    seen_days, seen_months = set(), set()

    for stamp, path in backups:
        age = now - stamp
        if age <= timedelta(hours=KEEP_HOURLY):
            keep.add(path)
            continue
        day = stamp.date()
        if age <= timedelta(days=KEEP_DAILY) and day not in seen_days:
            seen_days.add(day)
            keep.add(path)
            continue
        month = (stamp.year, stamp.month)
        if age <= timedelta(days=31 * KEEP_MONTHLY) and month not in seen_months:
            seen_months.add(month)
            keep.add(path)

    removed = 0
    for _, path in backups:
        if path not in keep:
            if not dry_run:
                path.unlink()
            removed += 1
    return len(keep), removed


def human(n):
    return f"{n / 1024 / 1024:.1f} Mo" if n > 1024 * 1024 else f"{n / 1024:.0f} Ko"


def cmd_list(dest):
    total = 0
    for sub in ("keep", "rotating"):
        d = dest / sub
        if not d.is_dir():
            continue
        files = sorted(d.glob("db-*.sqlite3"), reverse=True)
        label = "CONSERVEES" if sub == "keep" else "TOURNANTES"
        print(f"\n{label}  ({len(files)} fichiers dans {d})")
        for p in files[:15]:
            size = p.stat().st_size
            total += size
            print(f"  {p.name:52s} {human(size):>10s}")
        if len(files) > 15:
            print(f"  ... et {len(files) - 15} de plus")
        total += sum(p.stat().st_size for p in files[15:])
    print(f"\nTotal sur disque : {human(total)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", help="chemin de la base source")
    ap.add_argument("--dest", default=str(DEFAULT_DEST), help="repertoire des sauvegardes")
    ap.add_argument("--label", help="etiquette : la sauvegarde est alors conservee indefiniment")
    ap.add_argument("--list", action="store_true", help="lister les sauvegardes existantes")
    ap.add_argument("--no-prune", action="store_true", help="ne pas appliquer la retention")
    args = ap.parse_args()

    dest = Path(args.dest)

    if args.list:
        cmd_list(dest)
        return

    db = resolve_db(args.db)
    sub = "keep" if args.label else "rotating"
    out_dir = dest / sub
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        fail(f"pas les droits d'ecriture sur {out_dir}. Lancer en root, ou passer --dest.")

    stamp = datetime.now(timezone.utc).strftime(STAMP_FMT)
    suffix = f"-{args.label}" if args.label else ""
    out = out_dir / f"db-{stamp}{suffix}.sqlite3"

    free = shutil.disk_usage(out_dir).free
    needed = db.stat().st_size * 2
    if free < needed:
        fail(f"espace disque insuffisant : {human(free)} libres, {human(needed)} necessaires")

    print(f"source      {db}")
    print(f"destination {out}")

    try:
        online_backup(db, out)
    except sqlite3.Error as e:
        if out.exists():
            out.unlink()
        fail(f"la sauvegarde SQLite a echoue : {e}")

    ok, detail = verify(db, out)
    if not ok:
        out.unlink()
        fail(f"verification echouee, sauvegarde supprimee -> {detail}")

    print(f"verifiee    {detail}")
    print(f"taille      {human(out.stat().st_size)}")

    if args.label:
        print("retention   conservee indefiniment (--label)")
    elif not args.no_prune:
        kept, removed = prune(out_dir)
        print(f"retention   {kept} conservees, {removed} supprimees")

    print("OK")


if __name__ == "__main__":
    main()

#!/bin/bash
#
# Restauration de la base TerryFox LIMS depuis une sauvegarde.
#
# La base courante n'est jamais supprimee : elle est mise de cote sous
# db.sqlite3.remplacee-<horodatage> avant l'echange. Une restauration ratee ne
# doit pas etre une deuxieme perte de donnees.
#
#   sudo ./ops/restore_db.sh                          # choisir dans la liste
#   sudo ./ops/restore_db.sh /var/backups/.../db-....sqlite3
#   sudo ./ops/restore_db.sh --force <fichier>        # sans confirmation
#
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE="terryfox-lims.service"
WATCHDOG="terryfox-lims-watchdog.timer"
BACKUP_DIR="/var/backups/terryfox-lims"
DB="${TERRYFOX_DB:-/var/lib/terryfox-lims/db.sqlite3}"
[ -f "$DB" ] || DB="$REPO/db.sqlite3"

# shellcheck source=ops/lib.sh
source "$REPO/ops/lib.sh"

FORCE=0
SRC=""
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    *)       SRC="$arg" ;;
  esac
done

[ "$EUID" -eq 0 ] || die "ce script doit tourner en root"

# ------------------------------------------------- choix de la sauvegarde
if [ -z "$SRC" ]; then
  say "Sauvegardes disponibles"
  mapfile -t LIST < <(ls -t "$BACKUP_DIR"/keep/*.sqlite3 "$BACKUP_DIR"/rotating/*.sqlite3 2>/dev/null | head -20)
  [ ${#LIST[@]} -gt 0 ] || die "aucune sauvegarde dans $BACKUP_DIR"
  for i in "${!LIST[@]}"; do
    printf '  %2d) %s  (%s)\n' "$((i+1))" "$(basename "${LIST[$i]}")" \
      "$(date -r "${LIST[$i]}" '+%Y-%m-%d %H:%M')"
  done
  read -rp $'\nNumero a restaurer : ' n
  SRC="${LIST[$((n-1))]}"
fi

[ -f "$SRC" ] || die "sauvegarde introuvable : $SRC"

# ------------------------------------------------- verification prealable
say "Verification de la sauvegarde"
python3 - "$SRC" <<'PY' || die "la sauvegarde est inutilisable, restauration annulee"
import sqlite3, sys
p = sys.argv[1]
c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
integ = c.execute("PRAGMA integrity_check").fetchone()[0]
if integ != "ok":
    print(f"   integrity_check = {integ!r}"); sys.exit(1)
for t in ("core_project", "core_case", "core_comment", "auth_user"):
    n = c.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    print(f"   {t:16s} {n}")
    if t == "core_case" and n == 0:
        print("   0 cas : sauvegarde suspecte"); sys.exit(1)
PY
ok "sauvegarde lisible et coherente"

# ------------------------------------------------- confirmation
if [ "$FORCE" -eq 0 ]; then
  echo
  echo "  base actuelle : $DB"
  echo "  remplacee par : $SRC"
  read -rp $'\nTaper RESTAURER pour confirmer : ' answer
  [ "$answer" = "RESTAURER" ] || die "annule"
fi

# ------------------------------------------------- echange
say "Arret des services"
systemctl stop "$WATCHDOG" 2>/dev/null || true
systemctl stop "$SERVICE" 2>/dev/null || true
sleep 2
assert_no_writers

say "Echange"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
if [ -f "$DB" ]; then
  mv "$DB" "${DB}.remplacee-${STAMP}"
  ok "base precedente conservee : ${DB}.remplacee-${STAMP}"
fi
cp "$SRC" "$DB"
chown root:root "$DB" 2>/dev/null || true
chmod 640 "$DB"
rm -f "${DB}-wal" "${DB}-shm"
ok "base restauree depuis $(basename "$SRC")"

say "Redemarrage"
systemctl start "$SERVICE"
sleep 3
systemctl start "$WATCHDOG" 2>/dev/null || true
if ! code="$(wait_for_app 90)"; then
  die "l'application ne repond pas (HTTP $code)"
fi
ok "application en ligne (HTTP $code)"

python3 "$REPO/ops/check_invariants.py" --db "$DB"

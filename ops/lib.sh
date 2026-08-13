#!/bin/bash
# Fonctions communes aux scripts d'exploitation TerryFox LIMS.
# A sourcer, pas a executer.

SERVICE="${SERVICE:-terryfox-lims.service}"
WATCHDOG="${WATCHDOG:-terryfox-lims-watchdog.timer}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/terryfox-lims}"

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
ok()  { printf '   ok  %s\n' "$*"; }
warn(){ printf '   \033[33m!\033[0m  %s\n' "$*"; }
die() { printf '\n\033[1;31mECHEC: %s\033[0m\n' "$*" >&2; exit 1; }

# Chemin de la base : variable d'environnement, puis /var/lib, puis le depot.
resolve_db() {
  local repo="$1"
  if [ -n "${TERRYFOX_DB:-}" ] && [ -f "$TERRYFOX_DB" ]; then
    echo "$TERRYFOX_DB"; return
  fi
  if [ -f /var/lib/terryfox-lims/db.sqlite3 ]; then
    echo /var/lib/terryfox-lims/db.sqlite3; return
  fi
  echo "$repo/db.sqlite3"
}

# PID des workers gunicorn servant CE LIMS.
#
# Le motif vise la ligne de commande reelle ("... gunicorn terryfox_lims.wsgi_prod:application")
# et non un motif large : sur cette machine tournent d'autres gunicorn sans rapport.
# On exclut aussi ce script et son parent, car pgrep -f matche n'importe quel shell
# dont la ligne de commande contient le motif -- y compris celui qui appelle ce script.
lims_writer_pids() {
  pgrep -f 'gunicorn[[:space:]]+terryfox_lims\.wsgi' 2>/dev/null \
    | grep -vx -e "$$" -e "${PPID:-0}" || true
}

# Echoue si un ecrivain touche encore la base.
assert_no_writers() {
  local pids
  pids="$(lims_writer_pids)"
  if [ -n "$pids" ]; then
    echo "   PID encore actifs : $(echo "$pids" | tr '\n' ' ')" >&2
    die "des workers gunicorn ecrivent encore dans la base"
  fi
  if systemctl is-active --quiet "$SERVICE" 2>/dev/null; then
    die "$SERVICE est encore actif"
  fi
  ok "aucun ecrivain sur la base"
}

# Interroge l'application et renvoie le code HTTP (000 si injoignable).
app_http_code() {
  curl -sk -o /dev/null -w '%{http_code}' --max-time 5 https://localhost/ 2>/dev/null || echo 000
}

# Attend que l'application reponde. Renvoie 1 apres expiration.
wait_for_app() {
  local tries="${1:-20}" code
  for _ in $(seq 1 "$tries"); do
    sleep 1
    code="$(app_http_code)"
    if [ "$code" = "302" ] || [ "$code" = "200" ]; then
      echo "$code"; return 0
    fi
  done
  echo "${code:-000}"; return 1
}

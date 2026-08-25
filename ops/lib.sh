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

# PID des workers gunicorn qui ECRIVENT dans la base de production.
#
# Le motif vise wsgi_prod precisement. Un motif plus large attrapait aussi
# l'archive V1 -- « gunicorn terryfox_lims.wsgi_archive:application » -- qui
# tourne sur la meme machine, lit une base FIGEE et n'ecrit nulle part : un
# deploiement etait refuse a cause d'elle.
#
# On exclut aussi ce script et son parent : pgrep -f matche n'importe quel shell
# dont la ligne de commande contient le motif, y compris celui qui l'appelle.
lims_writer_pids() {
  pgrep -f 'gunicorn[[:space:]]+terryfox_lims\.wsgi_prod' 2>/dev/null \
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
#
# Pas de `|| echo 000` : sur un refus de connexion, curl imprime deja 000 ET
# sort en erreur, ce qui produisait un "HTTP 000000" illisible dans les messages.
app_http_code() {
  local code
  code="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 5 https://localhost/ 2>/dev/null)"
  echo "${code:-000}"
}

# Attend que l'application reponde. Renvoie 1 apres expiration.
#
# Le budget est genereux a dessein : gunicorn_start_robust.sh fait tourner
# collectstatic, verifie les certificats et peut installer gunicorn avant meme
# d'ouvrir le port. Une attente trop courte fait echouer la VERIFICATION d'un
# deploiement pourtant reussi -- ce qui s'est produit, et envoie chercher une
# panne qui n'existe pas.
wait_for_app() {
  local tries="${1:-90}" code i
  for i in $(seq 1 "$tries"); do
    sleep 2
    code="$(app_http_code)"
    if [ "$code" = "302" ] || [ "$code" = "200" ]; then
      [ "$i" -gt 5 ] && printf '   (repond apres %s s)\n' "$((i * 2))" >&2
      echo "$code"; return 0
    fi
    # Un point toutes les 10 s, pour que l'attente ne paraisse pas figee.
    [ $((i % 5)) -eq 0 ] && printf '.' >&2
  done
  printf '\n' >&2
  echo "$code"; return 1
}

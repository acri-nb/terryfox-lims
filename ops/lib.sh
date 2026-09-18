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

# Echoue si systemd ne repond pas.
#
# Tout ce script pilote des unites : si le gestionnaire ne repond plus, chaque
# `systemctl` sort en erreur, et une erreur de `is-active` est indiscernable
# d'une unite inactive. On le constate donc UNE fois, franchement, plutot que
# de laisser chaque etape l'interpreter a sa facon.
assert_systemd_ok() {
  local etat
  etat="$(timeout 15 systemctl is-system-running 2>&1 || true)"
  case "$etat" in
    running|degraded|maintenance|starting|stopping|initializing)
      return 0 ;;
    *)
      echo "   systemctl is-system-running -> ${etat:-aucune reponse}" >&2
      die "systemd ne repond pas : impossible d'arreter ou de redemarrer quoi que ce soit.
       L'application n'est pas en cause et continue de servir. Essayer, dans l'ordre :
         sudo systemctl daemon-reexec
         sudo kill -SIGRTMIN+25 1      # re-execution par signal, sans passer par D-Bus
       puis relancer ce deploiement. Un redemarrage de la machine regle le cas restant." ;;
  esac
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

# Verifie que le SCHEMA correspond au CODE, et qu'une lecture reelle passe.
#
# Pourquoi ce controle existe : app_http_code() sonde `/` en anonyme, ce qui
# redirige vers la page de connexion SANS jamais interroger core_case. Une base
# en retard d'une migration laisse donc la sonde a 302 pendant que TOUTES les
# pages authentifiees renvoient 500. C'est arrive : le redemarrage du
# 14 septembre 2026 a charge du code attendant les colonnes de la migration
# 0032 contre une base restee a 0031, et la panne a dure quatre jours pendant
# que le watchdog ecrivait « tous les controles sont OK » toutes les cinq
# minutes.
#
# On teste les deux choses qu'une redirection ne prouve pas : qu'aucune
# migration n'est en attente, et qu'une requete ORM sur core_case aboutit.
PY_ENV="/home/hadriengt/miniconda/envs/django/bin/python"
DJ_SETTINGS="terryfox_lims.settings_prod"

assert_app_reads_db() {
  local sortie

  # La LECTURE d'abord, le controle de migration ensuite. `migrate --check`
  # sort en erreur pour deux raisons sans rapport -- migrations en attente, ou
  # base illisible -- et les confondre redonnerait le message faux que ce
  # projet a deja paye une fois. Une lecture ORM, elle, echoue avec la cause
  # exacte : « unable to open database file » pour un probleme de droits,
  # « no such column » pour un schema en retard.
  if ! sortie="$("$PY_ENV" "$REPO/manage.py" shell --settings="$DJ_SETTINGS" \
        -c 'from core.models import Case, Specimen; print(Case.objects.count(), Specimen.objects.count())' 2>&1)"; then
    die "l'application repond mais ne sait pas lire sa base :
       $(echo "$sortie" | tail -3)"
  fi

  # Arrive ici, la base est lisible et le schema porte les colonnes du code.
  # Un echec de --check signifie donc reellement une migration en attente.
  if ! "$PY_ENV" "$REPO/manage.py" migrate --check --settings="$DJ_SETTINGS" >/dev/null 2>&1; then
    die "des migrations sont EN ATTENTE : le code attend un schema que la base
       n'a pas encore. Lancer :  sudo $REPO/ops/deploy.sh <etiquette>"
  fi

  ok "lecture reelle de la base : $sortie (cas, specimens)"
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

#!/bin/bash
#
# Runbook de deploiement TerryFox LIMS.
#
# Aucune migration ne doit etre lancee a la main sur ce serveur : ce script est
# le seul chemin. Il garantit, dans cet ordre, qu'on ne peut pas :
#   - se faire redemarrer le service par le watchdog au milieu d'un migrate
#   - migrer sans point de restauration frais et verifie
#   - laisser passer une migration qui a perdu des donnees
#
# En cas d'echec du controle d'invariants, la base est restauree automatiquement.
#
#   sudo ./ops/deploy.sh 0019_specimen
#   sudo ./ops/deploy.sh 0019_specimen --allow core_specimen=+3987
#
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONDA_SH="/home/hadriengt/miniconda/etc/profile.d/conda.sh"
SERVICE="terryfox-lims.service"
WATCHDOG="terryfox-lims-watchdog.timer"
BACKUP_DIR="/var/backups/terryfox-lims"
WORK="/var/lib/terryfox-lims/deploy"
SETTINGS="terryfox_lims.settings_prod"

LABEL="${1:-}"
shift || true
ALLOW_ARGS=("$@")

# shellcheck source=ops/lib.sh
source "$REPO/ops/lib.sh"

[ "$EUID" -eq 0 ] || die "ce script doit tourner en root (systemctl + /var/lib)"
[ -n "$LABEL" ] || die "usage: sudo $0 <etiquette> [--allow cle=+N ...]"

mkdir -p "$WORK"
REF="$WORK/invariants-${LABEL}.json"
WATCHDOG_WAS_ACTIVE=0

# ---------------------------------------------------------------- filet
# Quoi qu'il arrive ensuite, le watchdog et le service sont remis en etat.
cleanup() {
  local code=$?
  say "Remise en service"
  systemctl start "$SERVICE" 2>/dev/null || true
  if [ "$WATCHDOG_WAS_ACTIVE" -eq 1 ]; then
    systemctl start "$WATCHDOG" 2>/dev/null || true
    ok "watchdog reactive"
  fi
  exit $code
}
trap cleanup EXIT

# ---------------------------------------------------------------- 1
say "1/7  Neutralisation du watchdog"
if systemctl is-active --quiet "$WATCHDOG"; then
  WATCHDOG_WAS_ACTIVE=1
  systemctl stop "$WATCHDOG"
  ok "$WATCHDOG arrete (il redemarre le service toutes les 5 min)"
else
  ok "$WATCHDOG deja inactif"
fi

# ---------------------------------------------------------------- 2
say "2/7  Point de restauration"
python3 "$REPO/ops/backup_db.py" --dest "$BACKUP_DIR" --label "$LABEL" \
  || die "sauvegarde impossible : on ne migre pas sans filet"
BACKUP=$(ls -t "$BACKUP_DIR/keep/"*"-${LABEL}.sqlite3" | head -1)
[ -f "$BACKUP" ] || die "sauvegarde introuvable apres creation"
ok "restaurable depuis $BACKUP"

# ---------------------------------------------------------------- 3
say "3/7  Reference des invariants (avant)"
python3 "$REPO/ops/check_invariants.py" --save "$REF" || die "impossible de lire la base"

# ---------------------------------------------------------------- 4
say "4/7  Arret du service"
systemctl stop "$SERVICE" || true
sleep 2
assert_no_writers

# ---------------------------------------------------------------- 5
say "5/7  Migration"
set +u; source "$CONDA_SH"; conda activate django; set -u
cd "$REPO"
python manage.py migrate --settings="$SETTINGS" || {
  say "La migration a echoue -- restauration"
  bash "$REPO/ops/restore_db.sh" --force "$BACKUP"
  die "migration echouee, base restauree"
}
python manage.py collectstatic --noinput --settings="$SETTINGS" >/dev/null \
  || die "collectstatic a echoue : le site renverrait des 500 (ManifestStaticFilesStorage)"
ok "migrate + collectstatic"

# ---------------------------------------------------------------- 6
say "6/7  Controle des invariants (apres)"
if ! python3 "$REPO/ops/check_invariants.py" --compare "$REF" ${ALLOW_ARGS[@]+"${ALLOW_ARGS[@]}"}; then
  say "ECARTS NON AUTORISES -- restauration automatique"
  bash "$REPO/ops/restore_db.sh" --force "$BACKUP"
  die "des donnees ont change de facon inattendue, base restauree depuis $BACKUP"
fi

# ---------------------------------------------------------------- 7
say "7/7  Redemarrage et verification"
systemctl start "$SERVICE"
if ! code="$(wait_for_app 90)"; then
  # La migration est passee et les invariants sont tenus : la base est saine.
  # Seul le service ne repond pas. On ne restaure donc PAS.
  die "l'application ne repond pas apres 3 min (HTTP $code).
   La base est migree et verifiee, il n'y a rien a restaurer.
   Regarder :  systemctl status $SERVICE
               tail -40 /var/log/terryfox-lims/error.log"
fi
ok "application en ligne (HTTP $code)"

say "Deploiement '$LABEL' termine"
echo "   sauvegarde conservee : $BACKUP"
echo "   retour arriere       : sudo $REPO/ops/restore_db.sh $BACKUP"

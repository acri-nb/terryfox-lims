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
assert_systemd_ok

# On lit l'etat, on ne se contente pas du code de sortie : `is-active` sort en
# erreur AUSSI BIEN pour une unite inactive que pour un systemd injoignable, et
# les confondre faisait annoncer « deja inactif » alors que le watchdog pouvait
# tourner encore. Une garantie qu'on ne peut pas verifier n'en est pas une.
WATCHDOG_ETAT="$(systemctl is-active "$WATCHDOG" 2>/dev/null || true)"
case "$WATCHDOG_ETAT" in
  active)
    WATCHDOG_WAS_ACTIVE=1
    systemctl stop "$WATCHDOG" || die "$WATCHDOG ne s'arrete pas"
    ok "$WATCHDOG arrete (il redemarre le service toutes les 5 min)"
    ;;
  inactive|failed|dead)
    ok "$WATCHDOG deja inactif"
    ;;
  *)
    die "etat de $WATCHDOG indeterminable (« ${WATCHDOG_ETAT:-aucune reponse} ») :
       on ne migre pas sans savoir si le watchdog peut relancer le service."
    ;;
esac

# Arreter le TIMER n'arrete pas une execution deja en vol. Le watchdog tourne
# toutes les 5 minutes : demarrer un deploiement dans la seconde qui suit un
# declenchement laisse un watchdog.service vivant, qui relancera le service au
# milieu du migrate -- exactement ce que cette etape existe pour empecher.
systemctl stop "${WATCHDOG%.timer}.service" 2>/dev/null || true
ok "aucune execution du watchdog en vol"

# ---------------------------------------------------------------- 2
# L'arret vient AVANT la sauvegarde et la reference, et c'est le point
# important de cet ordre. Les prendre pendant que l'application sert laisse une
# fenetre ou un utilisateur peut ecrire : cette ecriture est absente de la
# reference, presente apres la migration, et l'etape 6 la lit comme une derive
# non declaree. Elle restaure alors la base -- detruisant a la fois la
# migration qui venait de reussir et la saisie de l'utilisateur.
say "2/7  Arret du service"
systemctl stop "$SERVICE" || true
sleep 2
assert_no_writers

# ---------------------------------------------------------------- 3
# Base au repos : la copie est coherente et la reference ne peut plus bouger.
say "3/7  Point de restauration"
python3 "$REPO/ops/backup_db.py" --dest "$BACKUP_DIR" --label "$LABEL" \
  || die "sauvegarde impossible : on ne migre pas sans filet"
BACKUP=$(ls -t "$BACKUP_DIR/keep/"*"-${LABEL}.sqlite3" | head -1)
[ -f "$BACKUP" ] || die "sauvegarde introuvable apres creation"
ok "restaurable depuis $BACKUP"

# ---------------------------------------------------------------- 4
say "4/7  Reference des invariants (avant)"
python3 "$REPO/ops/check_invariants.py" --save "$REF" || die "impossible de lire la base"

# Les --allow sont tapes a la main et ne sont relus qu'a l'etape 6, ou un echec
# declenche la restauration. Une faute de frappe dans un drapeau detruisait donc
# une migration reussie. On les rejoue ici, a blanc : la base n'a pas bouge
# depuis --save, donc la comparaison doit sortir en 0. Tout ce qui echoue ici
# est un probleme d'ARGUMENT, constate avant que quoi que ce soit ne soit en jeu.
python3 "$REPO/ops/check_invariants.py" --compare "$REF" \
    ${ALLOW_ARGS[@]+"${ALLOW_ARGS[@]}"} >/dev/null \
  || die "arguments --allow invalides (ou reference illisible) : rien n'a ete migre.
       Verifier la syntaxe : --allow cle=+N"
[ ${#ALLOW_ARGS[@]} -eq 0 ] || ok "${#ALLOW_ARGS[@]} argument(s) --allow valide(s)"

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
  die "des donnees ont change de facon inattendue, base restauree depuis $BACKUP

       ATTENTION : la base est revenue AVANT la migration, mais l'arbre de
       travail contient toujours le code d'APRES. Le service va redemarrer sur
       ce code et toutes les pages authentifiees renverront 500, pendant que /
       repondra 302. C'est la panne du 14 septembre 2026.
       Remettre le code au niveau de la base avant de rendre la main :
         git -C $REPO log --oneline -5
         git -C $REPO checkout <commit anterieur a la migration>
         sudo systemctl restart $SERVICE"
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

# Repondre n'est pas fonctionner : `/` en anonyme redirige vers la connexion
# sans toucher la base. On verifie donc que le schema suit le code et qu'une
# lecture reelle aboutit, faute de quoi on declarerait « en ligne » une
# application dont toutes les pages utiles renvoient 500.
assert_app_reads_db

say "Deploiement '$LABEL' termine"
echo "   sauvegarde conservee : $BACKUP"
echo "   retour arriere       : sudo $REPO/ops/restore_db.sh $BACKUP"

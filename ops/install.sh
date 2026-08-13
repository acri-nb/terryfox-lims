#!/bin/bash
#
# Incrément 1 -- installation des garde-fous sur le serveur.
#
# Ce script fait trois choses, dans un ordre qui permet d'annuler a chaque etape :
#   1. sort la base vivante de l'arbre git    -> /var/lib/terryfox-lims/db.sqlite3
#   2. installe la sauvegarde horaire verifiee -> /var/backups/terryfox-lims/
#   3. verifie que l'application repond sur la nouvelle base
#
# La base d'origine n'est jamais supprimee : elle est renommee, et seulement une
# fois que l'application a redemarre et repondu correctement sur la nouvelle.
# En cas de probleme, .env est remis en etat et le service redemarre tout seul.
#
#   sudo ./ops/install.sh              # avec confirmation
#   sudo ./ops/install.sh --yes        # sans
#
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPO/ops/lib.sh"

DATA_DIR="/var/lib/terryfox-lims"
NEW_DB="$DATA_DIR/db.sqlite3"
OLD_DB="$REPO/db.sqlite3"
ENV_FILE="$REPO/.env"
UNIT_DIR="/etc/systemd/system"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

ASSUME_YES=0
[ "${1:-}" = "--yes" ] && ASSUME_YES=1

[ "$EUID" -eq 0 ] || die "ce script doit tourner en root : sudo $0"
[ -f "$OLD_DB" ] || die "base introuvable dans le depot : $OLD_DB"
[ -f "$ENV_FILE" ] || die ".env introuvable : $ENV_FILE"

ENV_BACKUP="$ENV_FILE.avant-install-$STAMP"
REVERT_ENV=0

revert() {
  local code=$?
  if [ $code -ne 0 ]; then
    say "Echec -- retour a l'etat initial"
    if [ "$REVERT_ENV" -eq 1 ] && [ -f "$ENV_BACKUP" ]; then
      cp "$ENV_BACKUP" "$ENV_FILE"
      warn ".env restaure (la base redevient celle du depot)"
    fi
    systemctl start "$SERVICE" 2>/dev/null || true
    systemctl start "$WATCHDOG" 2>/dev/null || true
    warn "service et watchdog redemarres"
  fi
  exit $code
}
trap revert EXIT

# --------------------------------------------------------------- resume
say "Ce que ce script va faire"
cat <<RESUME
   base actuelle    $OLD_DB
   nouvelle base    $NEW_DB
   sauvegardes      /var/backups/terryfox-lims/  (horaires, verifiees)
   .env             ajout de DATABASE_PATH=$NEW_DB
   unites systemd   terryfox-lims-backup.{service,timer}

   Le service sera arrete quelques secondes, puis redemarre et verifie.
   Aucune donnee n'est supprimee : l'ancienne base sera seulement renommee.
RESUME

if [ "$ASSUME_YES" -eq 0 ]; then
  read -rp $'\nTaper INSTALLER pour continuer : ' answer
  [ "$answer" = "INSTALLER" ] || die "annule"
fi

# --------------------------------------------------------------- 1
say "1/8  Repertoires"
mkdir -p "$DATA_DIR" /var/backups/terryfox-lims
chmod 750 "$DATA_DIR"
chmod 700 /var/backups/terryfox-lims
ok "$DATA_DIR et /var/backups/terryfox-lims"

if [ -f "$NEW_DB" ]; then
  die "$NEW_DB existe deja. Deplacement probablement deja fait -- verifier avant de relancer."
fi

# --------------------------------------------------------------- 2
say "2/8  Sauvegarde de securite avant toute manipulation"
python3 "$REPO/ops/backup_db.py" --db "$OLD_DB" --dest /var/backups/terryfox-lims \
  --label "avant-deplacement-$STAMP" || die "sauvegarde impossible : on ne touche a rien"
SAFETY=$(ls -t /var/backups/terryfox-lims/keep/*"avant-deplacement-$STAMP"*.sqlite3 | head -1)
ok "filet : $SAFETY"

# --------------------------------------------------------------- 3
say "3/8  Reference des invariants"
python3 "$REPO/ops/check_invariants.py" --db "$OLD_DB" --save "$DATA_DIR/invariants-avant-install.json"

# --------------------------------------------------------------- 4
say "4/8  Arret du service"
systemctl stop "$WATCHDOG" 2>/dev/null || true
systemctl stop "$SERVICE" 2>/dev/null || true
sleep 2
assert_no_writers

# --------------------------------------------------------------- 5
say "5/8  Copie de la base vers son nouvel emplacement"
# Copie, pas deplacement : l'original reste intact tant que tout n'est pas verifie.
python3 - "$OLD_DB" "$NEW_DB" <<'PY'
import sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
d = sqlite3.connect(dst)
s.backup(d)
d.close(); s.close()

s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
d = sqlite3.connect(f"file:{dst}?mode=ro", uri=True)
assert d.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "integrite KO"
for t in ("core_project", "core_case", "core_comment", "core_projectlead", "auth_user"):
    a = s.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    b = d.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    assert a == b, f"{t}: source {a}, copie {b}"
    print(f"   {t:20s} {b}")
PY
chown root:root "$NEW_DB"
chmod 640 "$NEW_DB"
ok "copie verifiee ligne pour ligne"

# --------------------------------------------------------------- 6
say "6/8  Bascule de la configuration"
cp "$ENV_FILE" "$ENV_BACKUP"
REVERT_ENV=1
if grep -q '^DATABASE_PATH=' "$ENV_FILE"; then
  sed -i "s|^DATABASE_PATH=.*|DATABASE_PATH=$NEW_DB|" "$ENV_FILE"
else
  printf '\n# Base de production, hors de l arbre git (incrément 1)\nDATABASE_PATH=%s\n' "$NEW_DB" >> "$ENV_FILE"
fi
ok "DATABASE_PATH=$NEW_DB  (sauvegarde de .env : $ENV_BACKUP)"

# --------------------------------------------------------------- 7
say "7/8  Sauvegarde horaire"
install -m 644 "$REPO/ops/systemd/terryfox-lims-backup.service" "$UNIT_DIR/"
install -m 644 "$REPO/ops/systemd/terryfox-lims-backup.timer" "$UNIT_DIR/"
systemctl daemon-reload
systemctl enable --now terryfox-lims-backup.timer
ok "timer actif : $(systemctl show -p NextElapseUSecRealtime --value terryfox-lims-backup.timer)"

# --------------------------------------------------------------- 8
say "8/8  Redemarrage et verification"
systemctl start "$SERVICE"
if ! code="$(wait_for_app 25)"; then
  die "l'application ne repond pas (HTTP $code) sur la nouvelle base"
fi
ok "application en ligne (HTTP $code)"

python3 "$REPO/ops/check_invariants.py" --db "$NEW_DB" \
  --compare "$DATA_DIR/invariants-avant-install.json" \
  || die "les invariants ne correspondent pas sur la nouvelle base"

systemctl start "$WATCHDOG" 2>/dev/null || true
ok "watchdog reactive"

# --------------------------------------------------------------- fin
# Seulement maintenant, une fois l'application verifiee : on ecarte l'ancienne base.
MOVED="$OLD_DB.deplacee-$STAMP"
mv "$OLD_DB" "$MOVED"
rm -f "$OLD_DB-wal" "$OLD_DB-shm"

trap - EXIT
say "Termine"
cat <<FIN
   base de production   $NEW_DB
   ancienne base        $MOVED   (a supprimer quand vous serez rassure)
   sauvegardes          sudo python3 $REPO/ops/backup_db.py --list
   prochain deploiement sudo $REPO/ops/deploy.sh <etiquette>
   retour arriere       sudo $REPO/ops/restore_db.sh

   Plus aucune commande git dans $REPO ne peut atteindre les donnees vivantes.
FIN

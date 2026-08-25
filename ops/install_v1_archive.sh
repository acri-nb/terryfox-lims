#!/bin/bash
#
# Incrément 5 -- monte l'archive V1, en lecture seule.
#
# La V1 reste consultable apres la bascule, pour comparer et pour retrouver les
# donnees d'avant. Elle est FIGEE, pas branchee sur la base vivante : le code V1
# ignore les specimens, les tentatives archivees et la suppression douce, et lit
# des noms de colonnes que la v2 a renommes. Sur des donnees courantes il
# afficherait des cas incomplets -- une V1 qui ment est pire que pas de V1.
#
# C'est donc une photographie : le code V1 tel qu'il etait, sur les donnees
# telles qu'elles etaient a l'instant de la bascule.
#
#   sudo ./ops/install_v1_archive.sh
#   sudo ./ops/install_v1_archive.sh --force    # reinstaller par-dessus
#
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPO/ops/lib.sh"

V1_COMMIT="${V1_COMMIT:-01811af}"          # dernier etat avant le chantier v2
V1_DIR="/opt/terryfox-lims-v1"
FROZEN="/var/lib/terryfox-lims/v1-frozen.sqlite3"
SOURCE_SNAPSHOT="${V1_SNAPSHOT:-/home/hadriengt/backups/terryfox-lims/db-20260813T131614Z-preflight.sqlite3}"
UNIT="terryfox-lims-v1.service"
PORT=8443
CERT=/root/ssl/v1-archive.crt
KEY=/root/ssl/v1-archive.key
PY="/home/hadriengt/miniconda/envs/django/bin/python"
GUNICORN="/home/hadriengt/miniconda/envs/django/bin/gunicorn"
LIVE_URL="https://candig-lims.cair.mun.ca/"

FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

[ "$EUID" -eq 0 ] || die "ce script doit tourner en root : sudo $0"
[ -f "$SOURCE_SNAPSHOT" ] || die "instantane introuvable : $SOURCE_SNAPSHOT"
[ -x "$GUNICORN" ] || die "gunicorn introuvable dans l'environnement django"

# L'instantane doit etre du schema V1, sinon le code V1 ne saura pas le lire.
"$PY" - "$SOURCE_SNAPSHOT" <<'PY' || die "l'instantane n'est pas au schema V1"
import sqlite3, sys
c = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
cols = [r[1] for r in c.execute("PRAGMA table_info(core_case)")]
assert "other_id" in cols, "colonne other_id absente : instantane deja migre en v2"
assert "biobank_id" not in cols, "colonne biobank_id presente : instantane post-v2"
print(f"   schema V1 confirme, {c.execute('select count(*) from core_case').fetchone()[0]} cas")
PY

if [ -d "$V1_DIR" ] && [ "$FORCE" -eq 0 ]; then
  die "$V1_DIR existe deja. Relancer avec --force pour reinstaller."
fi

FROZEN_ON="$(date -u -r "$SOURCE_SNAPSHOT" '+%Y-%m-%d')"

# --------------------------------------------------------------- 1
say "1/8  Code V1"
systemctl stop "$UNIT" 2>/dev/null || true
rm -rf "$V1_DIR"
mkdir -p "$V1_DIR"
git -C "$REPO" archive "$V1_COMMIT" | tar -x -C "$V1_DIR"
git -C "$REPO" tag -f v1.0-final "$V1_COMMIT" >/dev/null 2>&1 || true
ok "commit $V1_COMMIT extrait dans $V1_DIR (etiquette v1.0-final posee)"

cp "$REPO/.env" "$V1_DIR/.env"
# La V1 lit sa base a BASE_DIR/db.sqlite3 ; on neutralise toute variable qui
# pourrait la detourner vers la base VIVANTE.
sed -i '/^DATABASE_PATH=/d' "$V1_DIR/.env"
ok ".env copie, DATABASE_PATH retire"

# --------------------------------------------------------------- 2
say "2/8  Donnees figees"
install -m 444 -o root -g root "$SOURCE_SNAPSHOT" "$FROZEN"
# Aucun fichier db.sqlite3 dans le repertoire V1 : la seule base atteignable
# doit etre celle, en lecture seule, designee par settings_archive.
rm -f "$V1_DIR/db.sqlite3"
ok "$FROZEN  (444 root, gelees au $FROZEN_ON)"

# --------------------------------------------------------------- 3
say "3/8  Modules de l'archive"
install -m 644 "$REPO/ops/v1/settings_archive.py" "$V1_DIR/terryfox_lims/settings_archive.py"
install -m 644 "$REPO/ops/v1/wsgi_archive.py"     "$V1_DIR/terryfox_lims/wsgi_archive.py"
install -m 644 "$REPO/ops/v1/archive_middleware.py" "$V1_DIR/core/archive_middleware.py"
# Cle propre a l'archive : celle du depot est publique, et avec des sessions en
# cookies signes elle permettrait de forger une session valide.
ARCHIVE_KEY="$("$PY" -c "import secrets,string;print(''.join(secrets.choice(string.ascii_letters+string.digits+'!@#\$%^&*(-_=+)') for _ in range(64)))")"
printf "\nARCHIVE_FROZEN_ON = '%s'\nARCHIVE_LIVE_URL = '%s'\nSECRET_KEY = '%s'\n" \
  "$FROZEN_ON" "$LIVE_URL" "$ARCHIVE_KEY" >> "$V1_DIR/terryfox_lims/settings_archive.py"
chmod 600 "$V1_DIR/terryfox_lims/settings_archive.py"
ok "reglages, wsgi et middleware de lecture seule installes"

# --------------------------------------------------------------- 4
say "4/8  Bandeau permanent"
BANNER="$(sed -e "s|__FROZEN_ON__|$FROZEN_ON|" -e "s|__LIVE_URL__|$LIVE_URL|" "$REPO/ops/v1/banner.html")"
"$PY" - "$V1_DIR/templates/base.html" <<PY
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text()
banner = '''$BANNER'''
if 'V1 ARCHIVE' not in s:
    s = s.replace('<body>', '<body>\n' + banner, 1)
    p.write_text(s)
    print("   bandeau insere en tete de chaque page")
else:
    print("   bandeau deja present")
PY

# --------------------------------------------------------------- 5
say "5/8  Certificat propre a l'archive"
if [ ! -f "$CERT" ] || ! openssl x509 -in "$CERT" -noout -checkend 2592000 >/dev/null 2>&1; then
  mkdir -p /root/ssl
  IP=$(hostname -I | awk '{print $1}')
  openssl req -x509 -nodes -days 3650 -newkey rsa:2048 -keyout "$KEY" -out "$CERT" \
    -subj "/C=CA/ST=NL/O=CAIR/OU=TerryFox LIMS/CN=terryfox-lims-v1" \
    -addext "subjectAltName=DNS:localhost,DNS:$(hostname),IP:127.0.0.1,IP:$IP,IP:10.220.115.67" \
    2>/dev/null
  chmod 600 "$KEY"; chmod 644 "$CERT"
  ok "certificat genere, valide jusqu'au $(openssl x509 -in "$CERT" -noout -enddate | cut -d= -f2)"
else
  ok "certificat existant conserve"
fi

# --------------------------------------------------------------- 6
say "6/8  Fichiers statiques"
cd "$V1_DIR"
DJANGO_SETTINGS_MODULE=terryfox_lims.settings_archive "$PY" manage.py collectstatic --noinput >/dev/null \
  || die "collectstatic a echoue : l'archive renverrait des 500"
ok "collectstatic"

# --------------------------------------------------------------- 7
say "7/8  Service"
install -m 644 "$REPO/ops/v1/$UNIT" "/etc/systemd/system/$UNIT"
systemctl daemon-reload
systemctl enable --now "$UNIT" >/dev/null 2>&1
for _ in $(seq 1 30); do
  sleep 2
  code=$(curl -sk -o /dev/null -w '%{http_code}' --max-time 5 "https://localhost:$PORT/" 2>/dev/null)
  [ "$code" = "302" ] || [ "$code" = "200" ] && break
done
[ "$code" = "302" ] || [ "$code" = "200" ] || die "l'archive ne repond pas (HTTP $code) -- journalctl -u $UNIT -n 40"
ok "archive en ligne sur le port $PORT (HTTP $code)"

# --------------------------------------------------------------- 8
say "8/8  Verification du verrouillage"

printf '   couche 1  permissions du fichier : '
perms=$(stat -c '%a %U' "$FROZEN")
[ "$perms" = "444 root" ] && echo "$perms  ok" || { echo "$perms  ATTENDU 444 root"; exit 1; }

printf '   couche 2  SQLite en lecture seule : '
"$PY" - "$FROZEN" <<'PY'
import sqlite3, sys
c = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
n = c.execute("select count(*) from core_case").fetchone()[0]
try:
    c.execute("update core_case set name=name where id=(select min(id) from core_case)")
    c.commit()
    print("ECRITURE ACCEPTEE -- protection insuffisante"); sys.exit(1)
except sqlite3.OperationalError as e:
    print(f"refusee ({e}), {n} cas lisibles")
PY

printf '   connexion possible ?             : '
cd "$V1_DIR"
DJANGO_SETTINGS_MODULE=terryfox_lims.settings_archive "$PY" - <<'PYCHK' \
  || die "l'archive serait inutilisable : personne ne pourrait s'y connecter"
# Une base en lecture seule casse la connexion de deux facons discretes : les
# sessions s'ecrivent dans django_session, et Django met a jour last_login a
# chaque connexion. Ce controle existe parce que les deux etaient passes
# inapercus a la conception, et qu'aucun ne se voit avant d'essayer de se
# connecter pour de vrai.
import sys

import terryfox_lims.wsgi_archive  # noqa: F401  charge Django et debranche
from django.conf import settings
from django.contrib.auth.signals import user_logged_in

if 'signed_cookies' not in settings.SESSION_ENGINE:
    print(f"sessions en {settings.SESSION_ENGINE} : ecriture en base")
    sys.exit(1)
if user_logged_in.receivers:
    print("update_last_login encore branche : ecriture en base")
    sys.exit(1)
print("sessions en cookies signes, last_login debranche")
PYCHK

printf '   couche 3  middleware HTTP        : '
post=$(curl -sk -o /dev/null -w '%{http_code}' --max-time 8 -X POST "https://localhost:$PORT/accounts/login/" 2>/dev/null)
[ "$post" = "405" ] && echo "POST refuse (HTTP 405)  ok" || { echo "POST a renvoye $post, attendu 405"; exit 1; }

say "Archive V1 en place"
cat <<FIN
   adresse        https://10.220.115.67:$PORT/   (certificat propre a l'archive)
   donnees figees au $FROZEN_ON, $(du -h "$FROZEN" | cut -f1)
   code           commit $V1_COMMIT, etiquette v1.0-final
   service        systemctl status $UNIT

   Les identifiants de connexion sont ceux d'avant la bascule : personne n'a de
   nouveau mot de passe a retenir.

   Pour une adresse publique en /v1/, il faudra une route sur le proxy CAIR
   (candig-lims.cair.mun.ca) -- il n'est pas administre depuis cette machine.
FIN

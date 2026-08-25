#!/bin/bash
#
# Etat complet du LIMS en production. LECTURE SEULE : ne modifie rien.
#
# Rassemble en une commande ce qu'on veut savoir apres un deploiement :
# services, sante de l'application, migrations appliquees, sauvegardes,
# invariants de la base.
#
# Il existe pour eviter un piege : la base et les journaux appartiennent a root,
# et l'application tourne dans l'environnement conda `django`, pas dans le base.
# Un `python manage.py ...` lance a la main prend le mauvais interpreteur et
# echoue sur "No module named 'decouple'", ce qui ressemble a une panne alors
# que tout va bien.
#
#   sudo ./ops/status.sh
#
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPO/ops/lib.sh"

# L'interpreteur de l'application, pas celui du shell courant.
PY="/home/hadriengt/miniconda/envs/django/bin/python"
SETTINGS="terryfox_lims.settings_prod"
DB="$(resolve_db "$REPO")"

[ "$EUID" -eq 0 ] || die "lecture seule, mais la base et les journaux sont a root : sudo $0"

say "Services"
for unit in terryfox-lims.service terryfox-lims-watchdog.timer terryfox-lims-backup.timer; do
  printf '   %-32s %s / %s\n' "$unit" \
    "$(systemctl is-active "$unit" 2>/dev/null)" \
    "$(systemctl is-enabled "$unit" 2>/dev/null)"
done
printf '   %-32s %s\n' "demarre depuis" \
  "$(systemctl show -p ActiveEnterTimestamp --value terryfox-lims.service)"

say "Application"
printf '   %-32s HTTP %s\n' "https://localhost/" "$(app_http_code)"
printf '   %-32s HTTP %s\n' "candig-lims.cair.mun.ca" \
  "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 https://candig-lims.cair.mun.ca/ 2>/dev/null || echo injoignable)"

say "Migrations"
cd "$REPO"
"$PY" manage.py showmigrations core --settings="$SETTINGS" 2>&1 | tail -6 | sed 's/^/   /'
en_attente=$("$PY" manage.py showmigrations core --settings="$SETTINGS" 2>/dev/null | grep -c '^ \[ \]')
if [ "${en_attente:-0}" -gt 0 ]; then
  warn "$en_attente migration(s) NON appliquee(s) -- lancer : sudo ./ops/deploy.sh <etiquette>"
else
  ok "toutes les migrations sont appliquees"
fi

say "Sauvegardes"
printf '   %-32s %s\n' "prochaine" \
  "$(systemctl list-timers terryfox-lims-backup.timer --no-pager 2>/dev/null | sed -n '2p' | awk '{print $1, $2, $3, $4}')"
for sous in rotating keep; do
  d="$BACKUP_DIR/$sous"
  if [ -d "$d" ]; then
    n=$(find "$d" -name 'db-*.sqlite3' | wc -l)
    derniere=$(ls -t "$d"/db-*.sqlite3 2>/dev/null | head -1)
    printf '   %-32s %s fichier(s)%s\n' "$sous" "$n" \
      "$([ -n "$derniere" ] && echo ", derniere $(date -r "$derniere" '+%Y-%m-%d %H:%M')")"
  fi
done
printf '   %-32s %s\n' "espace disque libre" "$(df -h "$BACKUP_DIR" | awk 'NR==2 {print $4}')"

say "Base de donnees"
printf '   %-32s %s\n' "chemin" "$DB"
printf '   %-32s %s\n' "taille" "$(du -h "$DB" | cut -f1)"
printf '   %-32s %s\n' "journal_mode" \
  "$("$PY" -c "import sqlite3,sys; print(sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True).execute('PRAGMA journal_mode').fetchone()[0])" "$DB" 2>/dev/null)"
case "$DB" in
  "$REPO"/*) warn "la base est DANS l'arbre git : un git checkout la detruirait" ;;
  *)         ok "hors de l'arbre git : aucune commande git ne peut l'atteindre" ;;
esac

say "Invariants"
python3 "$REPO/ops/check_invariants.py" --db "$DB" | sed 's/^/ /'

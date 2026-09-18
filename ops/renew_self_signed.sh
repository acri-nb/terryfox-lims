#!/usr/bin/env bash
#
# Regenere le certificat auto-signe de la VM.
#
# Pourquoi ce script existe : gunicorn_start_robust.sh ne genere le certificat
# que s'il est ABSENT, jamais s'il est expire. Celui en place a donc servi
# 77 jours perime sans que rien ne le signale, et son CN etait code en dur sur
# 10.220.115.67 -- une adresse que cette machine n'a plus -- sans mentionner
# candig-lims.cair.mun.ca, qui est pourtant le nom que tapent les utilisateurs.
#
# Ce certificat ne rend PAS le site legitime aux yeux d'un navigateur : rien ne
# remplace un certificat signe par une autorite reconnue. Il supprime seulement
# les erreurs d'expiration et de nom, et redonne un lien chiffre propre entre le
# proxy de MUN et l'application.
#
#   sudo ./ops/renew_self_signed.sh
#   sudo ./ops/renew_self_signed.sh --jours 825
#
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SSL_DIR=/root/ssl
CERT="$SSL_DIR/terryfox.crt"
KEY="$SSL_DIR/terryfox.key"
SERVICE=terryfox-lims.service
JOURS=825

rouge() { printf '\033[1;31m%s\033[0m\n' "$*"; }
say()   { printf '\n\033[1m== %s\033[0m\n' "$*"; }
ok()    { printf '   ok  %s\n' "$*"; }
die()   { rouge "ECHEC: $*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --jours) JOURS="${2:?--jours attend un nombre}"; shift 2 ;;
    *) die "option inconnue : $1" ;;
  esac
done

[ "$EUID" -eq 0 ] || die "ce script doit tourner en root (/root/ssl)"

say "1/4  Etat du certificat actuel"
if [ -f "$CERT" ]; then
  sujet="$(openssl x509 -in "$CERT" -noout -subject | sed 's/^subject=//')"
  emetteur="$(openssl x509 -in "$CERT" -noout -issuer | sed 's/^issuer=//')"
  fin="$(openssl x509 -in "$CERT" -noout -enddate | cut -d= -f2)"
  printf '   sujet    %s\n   emetteur %s\n   expire   %s\n' "$sujet" "$emetteur" "$fin"

  # Garde-fou central : si le certificat a ete signe par une autorite, il ne
  # vient pas de nous et l'ecraser par un auto-signe serait une regression
  # silencieuse -- on remplacerait un certificat de confiance par un qui ne
  # l'est pas, et les navigateurs se remettraient a crier.
  if [ "$sujet" != "$emetteur" ]; then
    die "ce certificat est signe par une autorite ($emetteur), il ne vient pas
       de ce script. Le remplacer par un auto-signe serait une regression.
       Si vous voulez vraiment le remplacer, deplacez-le d'abord a la main."
  fi
  ok "auto-signe : il peut etre remplace"
else
  ok "aucun certificat en place"
fi

say "2/4  Noms couverts"
HOTE="$(hostname)"
IP_PRINCIPALE="$(hostname -I | awk '{print $1}')"
# On liste le nom public EN PREMIER : c'est celui que tapent les utilisateurs,
# et l'ancien certificat ne le contenait pas du tout.
SAN="DNS:candig-lims.cair.mun.ca,DNS:www.candig-lims.cair.mun.ca"
SAN="$SAN,DNS:localhost,DNS:$HOTE"
SAN="$SAN,IP:127.0.0.1,IP:$IP_PRINCIPALE"
for extra in 10.220.115.67; do
  case ",$SAN," in *",IP:$extra,"*) ;; *) SAN="$SAN,IP:$extra" ;; esac
done
printf '   %s\n' "$SAN"
ok "valide $JOURS jours"

say "3/4  Generation"
mkdir -p "$SSL_DIR"
if [ -f "$CERT" ]; then
  horodatage="$(date -u +%Y%m%dT%H%M%SZ)"
  cp -a "$CERT" "$CERT.remplace-$horodatage"
  [ -f "$KEY" ] && cp -a "$KEY" "$KEY.remplace-$horodatage"
  ok "ancien certificat mis de cote : $CERT.remplace-$horodatage"
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
openssl req -x509 -nodes -days "$JOURS" -newkey rsa:2048 \
  -keyout "$TMP/k" -out "$TMP/c" \
  -subj "/C=CA/ST=New Brunswick/O=ACRI/OU=TerryFox LIMS/CN=candig-lims.cair.mun.ca" \
  -addext "subjectAltName=$SAN" \
  -addext "basicConstraints=critical,CA:FALSE" \
  -addext "keyUsage=critical,digitalSignature,keyEncipherment" \
  -addext "extendedKeyUsage=serverAuth" 2>/dev/null \
  || die "openssl a echoue"

# On verifie AVANT d'installer : un certificat illisible mis en place couperait
# le service au redemarrage, et il faudrait le diagnostiquer service arrete.
openssl x509 -in "$TMP/c" -noout -text >/dev/null || die "certificat genere illisible"
openssl rsa  -in "$TMP/k" -check -noout >/dev/null 2>&1 || die "cle generee invalide"
a="$(openssl x509 -in "$TMP/c" -noout -pubkey | openssl md5)"
b="$(openssl rsa  -in "$TMP/k" -pubout 2>/dev/null | openssl md5)"
[ "$a" = "$b" ] || die "la cle ne correspond pas au certificat"

install -m 0644 "$TMP/c" "$CERT"
install -m 0600 "$TMP/k" "$KEY"
ok "installe dans $SSL_DIR"

say "4/4  Redemarrage et verification"
systemctl restart "$SERVICE" || die "le service ne redemarre pas"
for _ in $(seq 1 30); do
  sleep 2
  pem="$(echo | timeout 5 openssl s_client -connect 127.0.0.1:443 2>/dev/null)" || true
  [ -n "$pem" ] && break
done
[ -n "${pem:-}" ] || die "le service ne repond plus en TLS apres le redemarrage.
       L'ancien certificat est dans $CERT.remplace-*"

echo "$pem" | openssl x509 -noout -subject -enddate 2>/dev/null | sed 's/^/   /'
echo "$pem" | openssl x509 -noout -checkend 0 >/dev/null 2>&1 \
  || die "le certificat servi est deja expire"
ok "le service sert bien le nouveau certificat"

printf '\n\033[1m== Termine\033[0m\n'
printf '   Rappel : un certificat auto-signe reste non approuve par les navigateurs.\n'
printf '   Le correctif definitif est un certificat signe pour candig-lims.cair.mun.ca,\n'
printf '   a demander a MUN. Voir la section HTTPS de CLAUDE.md.\n'

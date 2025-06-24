#!/bin/bash

# Vérifier si l'utilisateur est root
if [ "$EUID" -ne 0 ]; then
  echo "Ce script doit être exécuté en tant que root (avec sudo) car il utilise le port 443"
  exit 1
fi

echo "Starting TerryFox LIMS in production mode with HTTPS (DEBUG VERSION)..."

# Kill any existing Django or Gunicorn processes
pkill -f "runserver_plus" || true
pkill -f "gunicorn" || true

# Change to project directory
cd /home/hadriengt/project/lims/terryfox-lims

# Activation directe de l'environnement Conda
source /home/hadriengt/miniconda/etc/profile.d/conda.sh
conda activate django

echo "=== Environnement Python ==="
echo "Conda environment: $(conda info --envs | grep '*')"
echo "Python version: $(python --version)"
pip install python-decouple django-extensions werkzeug pyOpenSSL --quiet

# Diagnostic réseau AVANT démarrage
echo ""
echo "=== DIAGNOSTIC RÉSEAU PRÉ-DÉMARRAGE ==="
echo "Interfaces réseau actives :"
ip addr show | grep -E "inet.*scope global" | head -5

# Détecter automatiquement l'IP principale
MAIN_IP=$(hostname -I | awk '{print $1}')
echo "IP principale détectée : $MAIN_IP"

# Préparation des certificats avec TOUTES les IPs possibles
SSL_DIR=~/ssl
CERTFILE=$SSL_DIR/terryfox.crt
KEYFILE=$SSL_DIR/terryfox.key

# Forcer la régénération des certificats avec debug
echo ""
echo "=== GÉNÉRATION CERTIFICATS SSL (FORCÉE) ==="
mkdir -p $SSL_DIR

# Collecter toutes les IPs disponibles
ALL_IPS=$(hostname -I | tr ' ' ',')
echo "Toutes les IPs détectées : $ALL_IPS"

# Générer certificat avec TOUTES les IPs + localhost + nom de domaine
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout $KEYFILE -out $CERTFILE \
  -subj "/C=CA/ST=Quebec/L=Local/O=TerryFox/OU=LIMS/CN=candig.cair.mun.ca" \
  -addext "subjectAltName=DNS:candig.cair.mun.ca,DNS:localhost,DNS:$(hostname),IP:127.0.0.1,IP:$MAIN_IP,IP:192.168.7.13,IP:10.220.115.67,IP:172.18.0.1,IP:192.168.122.1"

echo "Nouveaux certificats générés avec extensions :"
openssl x509 -in $CERTFILE -text -noout | grep -A 5 "Subject Alternative Name"

# Collecte des fichiers statiques
python manage.py collectstatic --noinput --settings=terryfox_lims.settings_prod

# OPTION 1: Démarrage sur localhost uniquement (pour test)
echo ""
echo "=== OPTION 1: DÉMARRAGE SUR LOCALHOST (SÉCURISÉ) ==="
echo "Lancement Django avec SSL sur localhost:443..."
python manage.py runserver_plus 127.0.0.1:443 --settings=terryfox_lims.settings_prod \
  --cert-file=$CERTFILE --key-file=$KEYFILE &

LOCALHOST_PID=$!
sleep 2

# Test de connectivité localhost
if curl -k -s -o /dev/null https://localhost:443/; then
    echo "✅ https://localhost:443 - ACCESSIBLE"
else
    echo "❌ https://localhost:443 - NON ACCESSIBLE"
fi

# Arrêter le processus localhost
kill $LOCALHOST_PID 2>/dev/null
sleep 1

# OPTION 2: Démarrage sur toutes les interfaces
echo ""
echo "=== OPTION 2: DÉMARRAGE SUR TOUTES LES INTERFACES ==="
echo "Lancement Django avec SSL sur 0.0.0.0:443..."
python manage.py runserver_plus 0.0.0.0:443 --settings=terryfox_lims.settings_prod \
  --cert-file=$CERTFILE --key-file=$KEYFILE &

MAIN_PID=$!
sleep 3

# Tests de connectivité sur toutes les IPs et le nom de domaine
echo ""
echo "=== TESTS DE CONNECTIVITÉ ==="
TEST_IPS=("127.0.0.1" "localhost" "$MAIN_IP" "192.168.7.13" "10.220.115.67" "candig.cair.mun.ca")

for test_ip in "${TEST_IPS[@]}"; do
    echo -n "Test https://$test_ip:443 ... "
    if timeout 5 curl -k -s -o /dev/null https://$test_ip:443/ 2>/dev/null; then
        echo "✅ ACCESSIBLE"
    else
        echo "❌ NON ACCESSIBLE"
    fi
done

# Affichage des informations d'accès
echo ""
echo "=========================================="
echo "TerryFox LIMS is now running with HTTPS!"
echo ""
echo "URLs TESTÉES :"
echo "✅ https://localhost:443"
echo "⚠️  https://127.0.0.1:443"
for test_ip in "$MAIN_IP" "192.168.7.13" "10.220.115.67"; do
    echo "⚠️  https://$test_ip:443"
done
echo "⚠️  https://candig.cair.mun.ca:443"
echo ""
echo "IMPORTANT: "
echo "- Utilisez https://candig.cair.mun.ca:443 (recommandé)"
echo "- Ou utilisez https://localhost:443 (accès local uniquement)"
 echo "- Acceptez les avertissements de sécurité du navigateur"
echo "- Si les autres IPs ne fonctionnent pas, c'est probablement"
echo "  un problème de réseau/firewall, pas de Django"
echo "=========================================="
echo ""
echo "Logs du serveur :"

# Keep the script running and capture logs
wait $MAIN_PID

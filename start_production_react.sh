#!/bin/bash

# Vérifier si l'utilisateur est root
if [ "$EUID" -ne 0 ]; then
  echo "Ce script doit être exécuté en tant que root (avec sudo) car il utilise le port 443"
  exit 1
fi

echo "Starting TerryFox LIMS with React in production mode..."

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
pip install python-decouple django-extensions werkzeug pyOpenSSL requests --quiet

echo ""
echo "=== CONSTRUCTION DE L'APPLICATION REACT ==="
cd frontend

# Vérifier si Node.js est installé
if ! command -v npm &> /dev/null; then
    echo "❌ Node.js/npm n'est pas installé. Installation requise."
    echo "Veuillez installer Node.js depuis https://nodejs.org/"
    exit 1
fi

echo "Node.js version: $(node --version)"
echo "npm version: $(npm --version)"

# Installer les dépendances si nécessaire
if [ ! -d "node_modules" ]; then
    echo "Installation des dépendances npm..."
    npm install
fi

# Construire l'application React
echo "Construction de l'application React..."
npm run build

if [ $? -ne 0 ]; then
    echo "❌ Erreur lors de la construction de React"
    exit 1
fi

echo "✅ Construction React terminée avec succès"

# Retour au répertoire principal
cd ..

echo ""
echo "=== CONFIGURATION SSL ==="
# Préparation des certificats
SSL_DIR=~/ssl
CERTFILE=$SSL_DIR/terryfox.crt
KEYFILE=$SSL_DIR/terryfox.key

# Détecter automatiquement l'IP principale
MAIN_IP=$(hostname -I | awk '{print $1}')
echo "IP principale détectée : $MAIN_IP"

# Forcer la régénération des certificats
echo "Génération des certificats SSL..."
mkdir -p $SSL_DIR

# Générer certificat avec toutes les IPs + localhost
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout $KEYFILE -out $CERTFILE \
  -subj "/C=CA/ST=Quebec/L=Local/O=TerryFox/OU=LIMS/CN=10.220.115.67" \
  -addext "subjectAltName=DNS:localhost,DNS:$(hostname),IP:127.0.0.1,IP:$MAIN_IP,IP:10.220.115.67"

echo "✅ Certificats SSL générés"

echo ""
echo "=== COLLECTE DES FICHIERS STATIQUES ==="
# Collecte des fichiers statiques (inclut maintenant React)
python manage.py collectstatic --noinput --settings=terryfox_lims.settings_prod

if [ $? -ne 0 ]; then
    echo "❌ Erreur lors de la collecte des fichiers statiques"
    exit 1
fi

echo "✅ Fichiers statiques collectés"

echo ""
echo "=== DÉMARRAGE DU SERVEUR ==="
# Lancement Django avec SSL sur toutes les interfaces
echo "Lancement Django avec SSL sur 0.0.0.0:443..."
python manage.py runserver_plus 0.0.0.0:443 --settings=terryfox_lims.settings_prod \
  --cert-file=$CERTFILE --key-file=$KEYFILE &

MAIN_PID=$!
sleep 3

# Tests de connectivité
echo ""
echo "=== TESTS DE CONNECTIVITÉ ==="
TEST_IPS=("127.0.0.1" "localhost" "10.220.115.67")

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
echo "🚀 TerryFox LIMS avec React est en ligne!"
echo ""
echo "🌐 URLs d'accès :"
echo "   • https://localhost:443 (accès local)"
echo "   • https://10.220.115.67:443 (accès réseau)"
echo ""
echo "🎨 Interfaces disponibles :"
echo "   • Interface classique Django : https://localhost:443/"
echo "   • Interface moderne React : https://localhost:443/react/"
echo ""
echo "⚠️  IMPORTANT :"
echo "   • Acceptez les avertissements de sécurité du navigateur"
echo "   • L'interface React est maintenant intégrée en production"
echo "   • Les deux interfaces partagent la même base de données"
echo "=========================================="
echo ""
echo "📊 Logs du serveur (Ctrl+C pour arrêter) :"

# Keep the script running and capture logs
wait $MAIN_PID 
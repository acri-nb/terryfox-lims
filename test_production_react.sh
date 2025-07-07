#!/bin/bash

echo "Testing TerryFox LIMS with React in production mode (port 8443)..."

# Kill any existing Django processes
pkill -f "runserver_plus" || true

# Activation de l'environnement Conda
source ~/miniconda/etc/profile.d/conda.sh
conda activate django

echo "=== Environnement Python ==="
echo "Conda environment: $(conda info --envs | grep '*')"
echo "Python version: $(python --version)"

# Préparation des certificats
SSL_DIR=~/ssl
CERTFILE=$SSL_DIR/terryfox.crt
KEYFILE=$SSL_DIR/terryfox.key

# Créer les certificats si nécessaire
if [ ! -f "$CERTFILE" ] || [ ! -f "$KEYFILE" ]; then
    echo "Génération des certificats SSL..."
    mkdir -p $SSL_DIR
    
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
      -keyout $KEYFILE -out $CERTFILE \
      -subj "/C=CA/ST=Quebec/L=Local/O=TerryFox/OU=LIMS/CN=localhost" \
      -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
    
    echo "✅ Certificats SSL générés"
fi

echo ""
echo "=== COLLECTE DES FICHIERS STATIQUES ==="
python manage.py collectstatic --noinput --settings=terryfox_lims.settings_prod

echo ""
echo "=== DÉMARRAGE DU SERVEUR DE TEST ==="
echo "Lancement Django avec SSL sur localhost:8443..."
python manage.py runserver_plus 127.0.0.1:8443 --settings=terryfox_lims.settings_prod \
  --cert-file=$CERTFILE --key-file=$KEYFILE &

SERVER_PID=$!
sleep 3

# Test de connectivité
echo ""
echo "=== TEST DE CONNECTIVITÉ ==="
echo -n "Test https://localhost:8443 ... "
if timeout 5 curl -k -s -o /dev/null https://localhost:8443/ 2>/dev/null; then
    echo "✅ ACCESSIBLE"
else
    echo "❌ NON ACCESSIBLE"
fi

echo -n "Test React https://localhost:8443/react/ ... "
if timeout 5 curl -k -s -o /dev/null https://localhost:8443/react/ 2>/dev/null; then
    echo "✅ ACCESSIBLE"
else
    echo "❌ NON ACCESSIBLE"
fi

# Affichage des informations d'accès
echo ""
echo "=========================================="
echo "🚀 TerryFox LIMS avec React - TEST MODE"
echo ""
echo "🌐 URLs de test :"
echo "   • Interface classique : https://localhost:8443/"
echo "   • Interface React : https://localhost:8443/react/"
echo ""
echo "⚠️  Acceptez les avertissements SSL du navigateur"
echo "=========================================="
echo ""
echo "Appuyez sur Ctrl+C pour arrêter le serveur de test"

# Keep the script running
wait $SERVER_PID 
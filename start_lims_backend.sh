#!/bin/bash

echo "Démarrage du backend TerryFox LIMS pour utilisation avec Nginx..."

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

# Préparation des certificats
SSL_DIR=~/ssl
CERTFILE=$SSL_DIR/terryfox.crt
KEYFILE=$SSL_DIR/terryfox.key

# Vérifier si le certificat et la clé existent
if [ ! -f "$CERTFILE" ] || [ ! -f "$KEYFILE" ]; then
  echo "ERROR: SSL certificate or key not found! Regenerating..."
  mkdir -p $SSL_DIR
  openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout $KEYFILE -out $CERTFILE \
    -subj "/C=CA/ST=Quebec/L=Local/O=TerryFox/OU=LIMS/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:10.220.115.67,IP:192.168.7.13"
  echo "New certificates generated in $SSL_DIR"
fi

# Collecte des fichiers statiques
echo "Collecte des fichiers statiques..."
python manage.py collectstatic --noinput --settings=terryfox_lims.settings_prod

# Lancer Django avec SSL sur localhost uniquement (pour Nginx)
echo "Démarrage de Django avec SSL sur localhost:8443..."
python manage.py runserver_plus localhost:8443 --settings=terryfox_lims.settings_prod \
  --cert-file=$CERTFILE --key-file=$KEYFILE &

PROCESS_ID=$!

# Wait a moment for the server to start
sleep 3

# Affichage des informations d'accès
echo ""
echo "=========================================="
echo "TerryFox LIMS backend est en cours d'exécution!"
echo ""
echo "IMPORTANT: "
echo "- Le backend est accessible uniquement via localhost:8443"
echo "- Pour y accéder depuis l'extérieur, utilisez Nginx:"
echo "  https://10.220.115.67"
echo ""
echo "- Si Nginx n'est pas configuré, exécutez:"
echo "  sudo ./setup_nginx_production.sh"
echo "=========================================="
echo ""
echo "Logs du serveur backend:"

# Keep the script running and capture logs
wait $PROCESS_ID

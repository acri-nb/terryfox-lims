#!/bin/bash

echo "Starting TerryFox LIMS in production mode with HTTPS..."

# Kill any existing Django or Gunicorn processes
pkill -f "runserver_plus" || true
pkill -f "gunicorn" || true

# Change to project directory
cd /home/hadriengt/project/lims/terryfox-lims

# Activation directe de l'environnement Conda pour vérification
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
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:192.168.7.13"
  echo "New certificates generated in $SSL_DIR"
fi

# Collecte des fichiers statiques
python manage.py collectstatic --noinput --settings=terryfox_lims.settings_prod

# Lancer Django directement avec SSL
echo "Starting Django with SSL on port 8443..."
python manage.py runserver_plus 0.0.0.0:8443 --settings=terryfox_lims.settings_prod \
  --cert-file=$CERTFILE --key-file=$KEYFILE &

PROCESS_ID=$!

# Wait a moment for the server to start
sleep 3

# Get IP address
IP_ADDRESS=$(hostname -I | awk '{print $1}')

# Display access information
echo ""
echo "=========================================="
echo "TerryFox LIMS is now running with HTTPS!"
echo "Access it at: https://localhost:8443"
echo "               https://$IP_ADDRESS:8443"
echo ""
echo "IMPORTANT: Since we're using a self-signed"
echo "certificate, you'll need to accept the"
echo "security warning in your browser."
echo "=========================================="
echo ""
echo "Press Ctrl+C to stop the server"

# Keep the script running and capture logs
wait $PROCESS_ID
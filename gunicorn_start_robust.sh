#!/bin/bash

# Script de démarrage robuste pour TerryFox LIMS avec Gunicorn
# Version: Production Robuste

# Vérifier si l'utilisateur est root
if [ "$EUID" -ne 0 ]; then
  echo "Ce script doit être exécuté en tant que root (avec sudo) car il utilise le port 443"
  exit 1
fi

echo "Starting TerryFox LIMS with Gunicorn (Production Robust Mode)..."

# Créer le répertoire de logs s'il n'existe pas
mkdir -p /var/log/terryfox-lims
chown root:root /var/log/terryfox-lims
chmod 755 /var/log/terryfox-lims

# Kill any existing processes
pkill -f "gunicorn.*terryfox_lims" || true
pkill -f "runserver_plus" || true
sleep 2

# Change to project directory
cd /home/hadriengt/project/lims/terryfox-lims

# Activation de l'environnement Conda
source /home/hadriengt/miniconda/etc/profile.d/conda.sh
conda activate django

echo "=== Environnement Python ==="
echo "Conda environment: $(conda info --envs | grep '*')"
echo "Python version: $(python --version)"

# Installer Gunicorn si nécessaire
pip install gunicorn --quiet

# Préparation des certificats SSL
SSL_DIR=/root/ssl
CERTFILE=$SSL_DIR/terryfox.crt
KEYFILE=$SSL_DIR/terryfox.key

# Vérifier que les certificats existent
if [ ! -f "$CERTFILE" ] || [ ! -f "$KEYFILE" ]; then
    echo "=== GÉNÉRATION CERTIFICATS SSL ==="
    mkdir -p $SSL_DIR
    
    # Détecter l'IP principale
    MAIN_IP=$(hostname -I | awk '{print $1}')
    echo "IP principale détectée : $MAIN_IP"
    
    # Générer certificat avec toutes les IPs
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
      -keyout $KEYFILE -out $CERTFILE \
      -subj "/C=CA/ST=Quebec/L=Local/O=TerryFox/OU=LIMS/CN=10.220.115.67" \
      -addext "subjectAltName=DNS:localhost,DNS:$(hostname),IP:127.0.0.1,IP:$MAIN_IP,IP:10.220.115.67"
    
    echo "Certificats SSL générés avec succès"
fi

# Collecte des fichiers statiques
echo "=== COLLECTE DES FICHIERS STATIQUES ==="
python manage.py collectstatic --noinput --settings=terryfox_lims.settings_prod

# Démarrage de Gunicorn avec SSL
echo "=== DÉMARRAGE DE GUNICORN ==="
echo "Lancement de Gunicorn avec SSL sur 0.0.0.0:443..."

exec gunicorn terryfox_lims.wsgi_prod:application \
  --bind=0.0.0.0:443 \
  --workers=3 \
  --worker-class=sync \
  --timeout=120 \
  --max-requests=1000 \
  --max-requests-jitter=100 \
  --preload \
  --access-logfile=/var/log/terryfox-lims/access.log \
  --error-logfile=/var/log/terryfox-lims/error.log \
  --log-level=info \
  --certfile=$CERTFILE \
  --keyfile=$KEYFILE

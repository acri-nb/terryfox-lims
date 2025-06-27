#!/bin/bash

echo "=== Configuration de Nginx pour TerryFox LIMS ==="
echo "Ce script va configurer Nginx pour rendre le LIMS accessible via l'adresse IP 10.220.115.67"

# Vérifier si l'utilisateur est root
if [ "$EUID" -ne 0 ]; then
  echo "Ce script doit être exécuté en tant que root (avec sudo)"
  exit 1
fi

# Chemin du projet
PROJECT_PATH="/home/hadriengt/project/lims/terryfox-lims"
cd $PROJECT_PATH

# Vérifier si Nginx est installé
if ! command -v nginx &> /dev/null; then
    echo "Nginx n'est pas installé. Installation en cours..."
    apt update
    apt install -y nginx
fi

# Copier la configuration Nginx
echo "Copie de la configuration Nginx..."
cp $PROJECT_PATH/terryfox_nginx_prod.conf /etc/nginx/sites-available/terryfox

# Activer le site
echo "Activation du site Nginx..."
ln -sf /etc/nginx/sites-available/terryfox /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default  # Désactiver le site par défaut

# Vérifier la configuration Nginx
echo "Vérification de la configuration Nginx..."
nginx -t

if [ $? -ne 0 ]; then
    echo "ERREUR: La configuration Nginx contient des erreurs. Veuillez les corriger avant de continuer."
    exit 1
fi

# Redémarrer Nginx
echo "Redémarrage de Nginx..."
systemctl restart nginx

# Vérifier si les certificats SSL existent
SSL_DIR="/home/hadriengt/ssl"
CERTFILE="$SSL_DIR/terryfox.crt"
KEYFILE="$SSL_DIR/terryfox.key"

if [ ! -f "$CERTFILE" ] || [ ! -f "$KEYFILE" ]; then
    echo "Génération des certificats SSL..."
    mkdir -p $SSL_DIR
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
      -keyout $KEYFILE -out $CERTFILE \
      -subj "/C=CA/ST=Quebec/L=Local/O=TerryFox/OU=LIMS/CN=10.220.115.67" \
      -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:10.220.115.67"
    
    # Ajuster les permissions
    chown -R hadriengt:hadriengt $SSL_DIR
    chmod 600 $KEYFILE
fi

echo ""
echo "=== Configuration terminée ==="
echo "Pour démarrer le LIMS en production avec Nginx:"
echo "1. Exécutez: $PROJECT_PATH/start_lims_backend.sh"
echo "2. Accédez au LIMS via: https://10.220.115.67"
echo ""
echo "Note: Vous devrez peut-être accepter le certificat auto-signé dans votre navigateur."

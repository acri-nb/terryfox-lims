#!/bin/bash
# Script pour configurer TerryFox LIMS avec HTTPS sur adresse IP

# Vérifier les privilèges root
if [ "$(id -u)" -ne 0 ]; then
   echo "Ce script doit être exécuté en tant que root" 
   exit 1
fi

# Variables
IP_ADDRESS="192.168.7.13"
SSL_DIR="$HOME/ssl_config"
PROJECT_DIR="$(pwd)"
NGINX_AVAILABLE="/etc/nginx/sites-available"
NGINX_ENABLED="/etc/nginx/sites-enabled"

echo "Configuration HTTPS pour TerryFox LIMS sur $IP_ADDRESS:8000"

# 1. Créer le répertoire pour la configuration SSL si nécessaire
echo "[1/6] Préparation des répertoires de configuration SSL..."
mkdir -p $SSL_DIR

# 2. Créer le fichier de configuration OpenSSL
echo "[2/6] Création du fichier de configuration OpenSSL pour l'adresse IP..."
cat > $SSL_DIR/openssl-san.cnf << EOL
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
C = CA
ST = Nova Scotia
L = Halifax
O = TerryFox LIMS
OU = Bioinformatics
CN = TerryFox LIMS Internal

[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
IP.1 = $IP_ADDRESS
IP.2 = 127.0.0.1
EOL

# 3. Générer le certificat auto-signé
echo "[3/6] Génération du certificat SSL auto-signé..."
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout /etc/ssl/private/terryfox-selfsigned.key \
  -out /etc/ssl/certs/terryfox-selfsigned.crt \
  -config $SSL_DIR/openssl-san.cnf

# Définir les permissions appropriées
chmod 400 /etc/ssl/private/terryfox-selfsigned.key
chmod 444 /etc/ssl/certs/terryfox-selfsigned.crt

# 4. Copier le certificat pour distribution
echo "[4/6] Copie du certificat pour distribution..."
cp /etc/ssl/certs/terryfox-selfsigned.crt $HOME/terryfox-cert.crt
echo "Le certificat a été copié dans $HOME/terryfox-cert.crt"

# 5. Configurer Nginx
echo "[5/6] Configuration de Nginx..."
cp $PROJECT_DIR/terryfox_nginx.conf $NGINX_AVAILABLE/terryfox

# Créer un lien symbolique si nécessaire
if [ ! -f "$NGINX_ENABLED/terryfox" ]; then
  ln -s $NGINX_AVAILABLE/terryfox $NGINX_ENABLED/
  echo "Lien symbolique créé pour la configuration Nginx"
fi

# Tester la configuration Nginx
echo "Test de la configuration Nginx..."
nginx -t

# 6. Redémarrer Nginx
echo "[6/6] Redémarrage de Nginx..."
systemctl restart nginx

echo ""
echo "==================================================="
echo "Configuration HTTPS terminée!"
echo "Vous pouvez maintenant accéder à votre application via:"
echo "https://$IP_ADDRESS:8000"
echo ""
echo "IMPORTANT: Le certificat est auto-signé, vous devrez"
echo "l'accepter dans votre navigateur lors de la première connexion."
echo "===================================================" 
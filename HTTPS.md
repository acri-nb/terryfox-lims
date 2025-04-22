# Configuration HTTPS pour TerryFox LIMS avec adresse IP

Ce document explique comment configurer le TerryFox LIMS pour utiliser HTTPS en environnement interne avec une adresse IP (192.168.7.13:8000).

## Prérequis

- Accès SSH au serveur
- Droits d'administration (sudo)
- Nginx installé sur le serveur
- OpenSSL installé sur le serveur

## Étapes de configuration

### 1. Générer un certificat SSL auto-signé

Comme vous utilisez une adresse IP et non un nom de domaine, nous allons générer un certificat auto-signé:

```bash
# Créer un répertoire pour stocker les fichiers de configuration
mkdir -p ~/ssl_config

# Créer un fichier de configuration OpenSSL pour IP
cat > ~/ssl_config/openssl-san.cnf << EOL
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
IP.1 = 192.168.7.13
IP.2 = 127.0.0.1
EOL

# Générer le certificat auto-signé avec l'extension subjectAltName
sudo openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout /etc/ssl/private/terryfox-selfsigned.key \
  -out /etc/ssl/certs/terryfox-selfsigned.crt \
  -config ~/ssl_config/openssl-san.cnf

# Définir les permissions appropriées
sudo chmod 400 /etc/ssl/private/terryfox-selfsigned.key
sudo chmod 444 /etc/ssl/certs/terryfox-selfsigned.crt
```

### 2. Configurer les variables d'environnement

Le fichier `.env` doit inclure l'adresse IP dans ALLOWED_HOSTS et activer les paramètres HTTPS:

```
ALLOWED_HOSTS=localhost,127.0.0.1,192.168.7.13
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

### 3. Configurer Nginx

Le fichier `terryfox_nginx.conf` doit être configuré pour l'adresse IP et le port 8000:

```bash
# Copier le fichier de configuration
sudo cp terryfox_nginx.conf /etc/nginx/sites-available/terryfox

# Créer un lien symbolique
sudo ln -s /etc/nginx/sites-available/terryfox /etc/nginx/sites-enabled/

# Vérifier la configuration Nginx
sudo nginx -t

# Redémarrer Nginx
sudo systemctl restart nginx
```

### 4. Configurer le serveur pour accepter la connexion HTTPS sur le port 8000

Si vous utilisez un pare-feu comme UFW:

```bash
# Autoriser le trafic HTTPS sur le port 8000
sudo ufw allow 8000/tcp

# Vérifier les règles du pare-feu
sudo ufw status
```

### 5. Accepter le certificat auto-signé dans les navigateurs

Lors de la première connexion à `https://192.168.7.13:8000`, votre navigateur affichera un avertissement de sécurité. Pour chaque utilisateur:

1. Cliquez sur "Avancé" ou "Détails avancés"
2. Cliquez sur "Continuer vers le site" ou "Accepter le risque et continuer"
3. Selon le navigateur, vous pouvez installer le certificat de façon permanente:
   - **Chrome/Edge**: Paramètres > Confidentialité et sécurité > Sécurité > Gérer les certificats > Importation
   - **Firefox**: Préférences > Vie privée et sécurité > Certificats > Afficher les certificats > Importation

Pour une installation plus simple dans un environnement d'entreprise, vous pouvez distribuer le certificat aux utilisateurs:

```bash
# Copier le certificat pour distribution
sudo cp /etc/ssl/certs/terryfox-selfsigned.crt ~/terryfox-cert.crt
```

### 6. Script de configuration automatique

Pour simplifier l'installation, un script shell est fourni: `setup_https_ip.sh`

```bash
# Exécuter le script de configuration
sudo ./setup_https_ip.sh
```

## Vérification de la configuration

Testez l'accès à l'application via:
```
https://192.168.7.13:8000
```

## Résolution des problèmes courants

### Le site n'est pas accessible en HTTPS

Vérifiez:
1. Que le pare-feu autorise le trafic sur le port 8000
2. Que Nginx est en cours d'exécution: `sudo systemctl status nginx`
3. Les journaux d'erreur Nginx: `sudo tail -f /var/log/nginx/error.log`
4. Que les certificats existent aux emplacements spécifiés

### Erreur "connection refused"

Vérifiez:
1. Que le serveur Django/Gunicorn est en cours d'exécution sur le port 8000
2. Que le paramètre proxy_pass dans la configuration Nginx est correct

### Erreur "NET::ERR_CERT_INVALID" dans le navigateur

C'est normal pour un certificat auto-signé. Vous devez:
1. Accepter le risque temporairement
2. Installer le certificat dans votre navigateur pour éviter l'avertissement à l'avenir

## Sécurité supplémentaire

Pour renforcer la sécurité, considérez:

1. Ajouter une authentification à deux facteurs
2. Configurer le Content Security Policy (CSP)
3. Mettre à jour régulièrement tous les composants du système
4. Effectuer des audits de sécurité périodiques

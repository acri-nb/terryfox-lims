# Configuration HTTPS pour TerryFox LIMS avec adresse IP

Ce document explique comment configurer le TerryFox LIMS pour utiliser HTTPS en environnement interne avec une adresse IP (192.168.7.13:8443). La configuration décrite ici utilise Django directement avec extensions SSL sans nécessiter Nginx.

## Prérequis

- Accès SSH au serveur
- Environnement Conda "django" configuré
- Python 3.8+ avec les packages suivants installés:
  - django-extensions
  - werkzeug
  - pyOpenSSL
- OpenSSL installé sur le serveur

## Options de configuration HTTPS

Il existe plusieurs méthodes pour configurer HTTPS avec TerryFox LIMS:

### Option A: Configuration Django avec runserver_plus (développement)
- Solution simple utilisant django-extensions et runserver_plus
- Ne nécessite pas de serveur web séparé comme Nginx
- Certificats stockés dans le répertoire utilisateur (~ssl/)
- Fonctionne sur le port 8443
- **⚠️ Non recommandée pour la production**

### Option B: Configuration avec Nginx (pour environnements à fort trafic)
- Nécessite Nginx installé comme reverse proxy
- Certificats stockés dans /etc/ssl/
- Gestion plus robuste pour les environnements de production à fort trafic

### Option C: Configuration Gunicorn avec SSL (🚀 RECOMMANDÉE POUR LA PRODUCTION)
- **Serveur WSGI robuste** adapté à la production
- **SSL natif** intégré dans Gunicorn
- **Certificats stockés** dans `/root/ssl/`
- **Port 443** (port HTTPS standard)
- **Surveillance automatique** avec systemd + watchdog
- **Logs centralisés** dans `/var/log/terryfox-lims/`
- **Redémarrage automatique** en cas de problème

## Étapes de configuration (Option A - Django avec runserver_plus)

### 1. Générer un certificat SSL auto-signé

Le script `start_production.sh` génère automatiquement un certificat auto-signé s'il n'existe pas déjà. Cependant, vous pouvez également créer manuellement les certificats :

```bash
# Créer un répertoire pour stocker les certificats (Option C - Production)
sudo mkdir -p /root/ssl

# Ou pour développement (Options A/B)
mkdir -p ~/ssl

# Créer un fichier de configuration OpenSSL pour IP
cat > /tmp/openssl-san.cnf << EOL
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
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout ~/ssl/terryfox.key \
  -out ~/ssl/terryfox.crt \
  -config ~/ssl/openssl-san.cnf

# Définir les permissions appropriées
chmod 600 ~/ssl/terryfox.key
chmod 644 ~/ssl/terryfox.crt
```

**Remarque** : Contrairement à la méthode utilisant Nginx, cette configuration stocke les certificats dans votre répertoire personnel sans nécessiter les droits sudo.

### 2. Configurer les variables d'environnement

Le fichier `.env` doit inclure l'adresse IP dans ALLOWED_HOSTS et activer les paramètres HTTPS. Ces configurations sont déjà présentes dans le fichier `.env` :

```
ALLOWED_HOSTS=localhost,127.0.0.1,192.168.7.13
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

### 3. Configurer Django pour HTTPS avec runserver_plus

Le fichier `settings_prod.py` a été mis à jour pour inclure django-extensions:

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    # ...
    'crispy_forms',
    'crispy_bootstrap5',
    'django_extensions',  # Ajouté pour runserver_plus avec SSL
    # ...
]
```

### 4. Démarrer l'application avec HTTPS

Le script `start_production.sh` a été configuré pour lancer automatiquement l'application avec HTTPS:

```bash
# Démarrer l'application en mode production avec HTTPS
./start_production.sh
```

Ce script:
1. Vérifie et active l'environnement Conda
2. Vérifie l'existence des certificats SSL et les génère si nécessaire
3. Collecte les fichiers statiques
4. Démarre Django avec runserver_plus sur le port 8443 avec SSL

### 5. Configurer le serveur pour accepter la connexion HTTPS sur le port 8443

Si vous utilisez un pare-feu comme UFW:

```bash
# Autoriser le trafic HTTPS sur le port 8443
sudo ufw allow 8443/tcp

# Vérifier les règles du pare-feu
sudo ufw status
```

### 6. Accepter le certificat auto-signé dans les navigateurs

Lors de la première connexion à `https://192.168.7.13:8443`, votre navigateur affichera un avertissement de sécurité. Pour chaque utilisateur:

1. Cliquez sur "Avancé" ou "Détails avancés"
2. Cliquez sur "Continuer vers le site" ou "Accepter le risque et continuer"
3. Selon le navigateur, vous pouvez installer le certificat de façon permanente:
   - **Chrome/Edge**: Paramètres > Confidentialité et sécurité > Sécurité > Gérer les certificats > Importation
   - **Firefox**: Préférences > Vie privée et sécurité > Certificats > Afficher les certificats > Importation

**Note importante** : L'avertissement de sécurité est normal et attendu lors de l'utilisation de certificats auto-signés. Dans un environnement interne, cette solution est acceptable. Pour un déploiement public, envisagez un certificat délivré par une autorité de certification reconnue comme Let's Encrypt.

Pour une installation plus simple dans un environnement d'entreprise, vous pouvez distribuer le certificat aux utilisateurs:

```bash
# Créer un fichier .p12 avec le certificat
openssl pkcs12 -export -out terryfox.p12 -inkey ~/ssl/terryfox.key -in ~/ssl/terryfox.crt
# Puis distribuer ce fichier terryfox.p12 aux utilisateurs
```

Les utilisateurs peuvent alors importer ce fichier .p12 dans leur navigateur pour éviter l'avertissement de sécurité.

## Étapes de configuration (Option B - Nginx)

Si vous préférez utiliser Nginx pour gérer HTTPS (recommandé pour les environnements à fort trafic), voici les étapes à suivre:

### 1. Installer Nginx

```bash
sudo apt update
sudo apt install nginx
```

### 2. Générer un certificat dans /etc/ssl/

```bash
# Créer le fichier de configuration OpenSSL
sudo mkdir -p /etc/ssl/config
sudo bash -c 'cat > /etc/ssl/config/openssl-san.cnf << EOL
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
EOL'

# Générer le certificat
sudo openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout /etc/ssl/private/terryfox-selfsigned.key \
  -out /etc/ssl/certs/terryfox-selfsigned.crt \
  -config /etc/ssl/config/openssl-san.cnf

# Définir les permissions
sudo chmod 400 /etc/ssl/private/terryfox-selfsigned.key
sudo chmod 444 /etc/ssl/certs/terryfox-selfsigned.crt
```

### 3. Configurer Nginx

```bash
# Créer la configuration Nginx
sudo bash -c 'cat > /etc/nginx/sites-available/terryfox << EOL
server {
    listen 443 ssl;
    server_name 192.168.7.13;

    ssl_certificate /etc/ssl/certs/terryfox-selfsigned.crt;
    ssl_certificate_key /etc/ssl/private/terryfox-selfsigned.key;
    ssl_protocols TLSv1.2 TLSv1.3;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static/ {
        alias /home/hadriengt/project/lims/terryfox-lims/staticfiles/;
    }
}

server {
    listen 80;
    server_name 192.168.7.13;
    return 301 https://\$host\$request_uri;
}
EOL'

# Activer le site
sudo ln -s /etc/nginx/sites-available/terryfox /etc/nginx/sites-enabled/

# Tester la configuration
sudo nginx -t

# Redémarrer Nginx
sudo systemctl restart nginx
```

### 4. Modifier le script start_production.sh

Dans cette configuration, le script `start_production.sh` devrait démarrer Gunicorn sans SSL sur le port 8000, car Nginx gérera HTTPS:

```bash
# Modifier gunicorn_start.sh pour utiliser Gunicorn sans SSL sur le port 8000
```

## Conclusion

Vous disposez maintenant de deux options pour configurer HTTPS dans TerryFox LIMS :

1. **Option A (Actuelle)** : Utilisation directe de Django avec django-extensions et runserver_plus sur le port 8443
   - Plus simple à configurer
   - Ne nécessite pas d'installation de serveur web supplémentaire
   - Suffisant pour un environnement de développement ou une utilisation interne avec peu d'utilisateurs

2. **Option B** : Configuration avec Nginx comme reverse proxy
   - Configuration plus robuste
   - Meilleure gestion du cache et des fichiers statiques
   - Recommandée pour les environnements de production avec beaucoup d'utilisateurs

**L'option C (Gunicorn) est maintenant la configuration recommandée** et est accessible à l'adresse https://10.220.115.67:443.

## Étapes de configuration (Option C - Gunicorn avec SSL) 🚀

**Cette option est maintenant la configuration recommandée pour la production.**

### 1. Générer les certificats SSL pour la production

```bash
# Créer le répertoire des certificats
sudo mkdir -p /root/ssl

# Générer le certificat auto-signé avec IP 10.220.115.67
sudo openssl req -x509 -newkey rsa:4096 \
  -keyout /root/ssl/terryfox.key \
  -out /root/ssl/terryfox.crt \
  -days 365 -nodes \
  -subj "/C=CA/ST=Nova Scotia/L=Halifax/O=TerryFox/CN=10.220.115.67" \
  -addext "subjectAltName=IP:10.220.115.67,DNS:localhost"

# Définir les permissions appropriées
sudo chmod 600 /root/ssl/terryfox.key
sudo chmod 644 /root/ssl/terryfox.crt
```

### 2. Démarrer le service robuste

```bash
# Démarrer le service systemd
sudo systemctl start terryfox-lims.service

# Activer le démarrage automatique
sudo systemctl enable terryfox-lims.service

# Activer la surveillance automatique
sudo systemctl enable --now terryfox-lims-watchdog.timer
```

### 3. Vérifier le fonctionnement

```bash
# Vérifier le statut du service
sudo systemctl status terryfox-lims.service

# Tester la connectivité HTTPS
curl -k -I https://localhost:443/
curl -k -I https://10.220.115.67:443/

# Voir les logs en temps réel
sudo journalctl -u terryfox-lims.service -f
```

### 4. Accès à l'application

L'application sera accessible via :
- **https://10.220.115.67** (accès réseau)
- **https://localhost** (accès local)

### 5. Surveillance et maintenance

```bash
# Vérifier les logs centralisés
tail -f /var/log/terryfox-lims/access.log
tail -f /var/log/terryfox-lims/error.log
tail -f /var/log/terryfox-lims/watchdog.log

# Redémarrer si nécessaire
sudo systemctl restart terryfox-lims.service
```

## Vérification de la configuration

Testez l'accès à l'application via:
```
https://10.220.115.67
https://localhost
```

## Résolution des problèmes courants

### Le site n'est pas accessible en HTTPS

Vérifiez:
1. Que le pare-feu autorise le trafic sur le port 8000
2. Que Nginx est en cours d'exécution: `sudo systemctl status nginx`
3. Les journaux d'erreur Nginx: `sudo tail -f /var/log/nginx/error.log`
4. Que les certificats existent aux emplacements spécifiés

### Erreur "connection refused"

**Pour l'Option C (Gunicorn) :**
```bash
# Vérifier que Gunicorn écoute sur le port 443
sudo netstat -tlnp | grep :443

# Vérifier les processus Gunicorn
ps aux | grep gunicorn

# Vérifier les logs d'erreur
tail /var/log/terryfox-lims/error.log
```

**Pour les autres options :**
1. Que le serveur Django/Gunicorn est en cours d'exécution sur le port approprié
2. Que la configuration réseau est correcte

### Erreur "NET::ERR_CERT_INVALID" dans le navigateur

C'est normal pour un certificat auto-signé. Vous devez:
1. Accepter le risque temporairement
2. Installer le certificat dans votre navigateur pour éviter l'avertissement à l'avenir

## Comparaison des options

| Aspect | Option A (runserver_plus) | Option B (Nginx) | Option C (Gunicorn) |
|--------|---------------------------|------------------|---------------------|
| **Usage** | Développement | Production haute charge | **Production recommandée** |
| **Port** | 8443 | 443 (via proxy) | **443 (direct)** |
| **Certificats** | ~/ssl/ | /etc/ssl/ | **/root/ssl/** |
| **Supervision** | Manuelle | systemd + Nginx | **systemd + watchdog** |
| **Logs** | Console | Nginx + Django | **Centralisés** |
| **Robustesse** | Faible | Moyenne | **Élevée** |
| **Maintenance** | Élevée | Moyenne | **Faible** |

## Sécurité supplémentaire

Pour renforcer la sécurité, considérez:

1. **Certificats Let's Encrypt** pour éviter les avertissements de navigateur
2. **Pare-feu** configuré pour limiter l'accès aux ports nécessaires
3. **Mises à jour régulières** de tous les composants du système
4. **Surveillance des logs** pour détecter les activités suspectes
5. **Sauvegardes régulières** de la base de données et des certificats

### Configuration Let's Encrypt (optionnel)

```bash
# Installer certbot
sudo apt-get install certbot

# Obtenir un certificat pour l'IP (nécessite un domaine)
# Note: Let's Encrypt ne supporte pas les certificats pour IP
# Utilisez un nom de domaine si possible
sudo certbot certonly --standalone -d votre-domaine.com

# Copier les certificats vers /root/ssl/
sudo cp /etc/letsencrypt/live/votre-domaine.com/fullchain.pem /root/ssl/terryfox.crt
sudo cp /etc/letsencrypt/live/votre-domaine.com/privkey.pem /root/ssl/terryfox.key

# Redémarrer le service
sudo systemctl restart terryfox-lims.service
```

# TerryFox LIMS - Production Setup

Ce document fournit les instructions pour exécuter TerryFox LIMS en mode production avec HTTPS sur l'adresse IP 10.220.115.67.

## Prérequis

- Python 3.8+ (via environnement Conda)
- Django et packages requis
- Packages supplémentaires pour HTTPS : django-extensions, werkzeug, pyOpenSSL
- Nginx (optionnel, pour l'accès multi-utilisateurs)
- Accès root (sudo) pour utiliser le port 443
- Configuration réseau pour l'adresse IP 10.220.115.67

## Options de déploiement

Vous avez deux options pour déployer TerryFox LIMS en production :

### Option 1 : Déploiement simple (accès direct)

Pour un démarrage rapide avec accès direct :

```bash
sudo ./start_production_debug.sh
```

Cette méthode :
1. Démarre Django avec support HTTPS via django-extensions
2. Sert l'application de façon sécurisée sur le port 443 (port HTTPS standard)
3. Utilise les paramètres de production de `terryfox_lims/settings_prod.py`
4. Génère des certificats SSL auto-signés incluant l'IP 10.220.115.67

Accès à l'application :
- https://10.220.115.67 (accès via l'adresse IP)
- https://localhost (accès local uniquement)

**Note** : Les privilèges root (sudo) sont nécessaires car l'application utilise le port 443.

### Option 2 : Déploiement avec Nginx (recommandé pour multi-utilisateurs)

Pour un accès multi-utilisateurs fiable via l'IP :

```bash
# Étape 1 : Configuration de Nginx (une seule fois)
sudo ./setup_nginx_production.sh

# Étape 2 : Démarrage du backend LIMS
./start_lims_backend.sh
```

Cette méthode :
1. Configure Nginx comme proxy inverse sécurisé
2. Démarre Django en mode backend sur localhost:8443
3. Rend l'application accessible via HTTPS sur l'IP

Accès à l'application :
- https://10.220.115.67 (accessible à tous les utilisateurs du réseau)

**Note** : Cette configuration est recommandée pour les environnements avec plus de 10 utilisateurs simultanés.

### Option 3 : Configuration en tant que service systemd (recommandé pour une exécution permanente)

Pour garantir que le LIMS reste actif en permanence, même après déconnexion ou redémarrage du serveur :

```bash
# Étape 1 : Créer un fichier de service systemd
sudo nano /etc/systemd/system/terryfox-lims.service
```

Ajoutez le contenu suivant au fichier :
```ini
[Unit]
Description=TerryFox LIMS Service
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=/home/hadriengt/project/lims/terryfox-lims
ExecStart=/home/hadriengt/project/lims/terryfox-lims/start_production_debug.sh
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=terryfox-lims

[Install]
WantedBy=multi-user.target
```

Puis activez et démarrez le service :
```bash
sudo systemctl daemon-reload
sudo systemctl enable terryfox-lims.service
sudo systemctl start terryfox-lims.service
```

Cette configuration assure que :
1. Le LIMS s'exécute en continu en arrière-plan
2. Il redémarre automatiquement en cas de plantage
3. Il démarre automatiquement au démarrage du serveur
4. Il peut être géré facilement via les commandes systemd

#### Gestion du service

Commandes principales pour gérer le service LIMS :

```bash
# Vérifier l'état du service
sudo systemctl status terryfox-lims.service

# Arrêter le service
sudo systemctl stop terryfox-lims.service

# Redémarrer le service
sudo systemctl restart terryfox-lims.service

# Consulter les logs du service
sudo journalctl -u terryfox-lims.service

# Voir les logs en temps réel
sudo journalctl -u terryfox-lims.service -f
```

## Dépannage

### Erreur "Bad Request (400)" avec l'IP

Si vous obtenez une erreur 400 (Bad Request) lorsque vous accédez à l'application via l'IP, vérifiez les points suivants :

1. **Résolution réseau** : Assurez-vous que l'adresse IP `10.220.115.67` est accessible depuis votre réseau :
   ```bash
   ping 10.220.115.67
   ```

2. **Configuration Django** : Vérifiez que l'IP est incluse dans `ALLOWED_HOSTS` dans `settings_prod.py`.

3. **Certificats SSL** : Vérifiez que les certificats SSL incluent l'IP dans le Subject Alternative Name (SAN) :
   ```bash
   sudo openssl x509 -in ~/ssl/terryfox.crt -text -noout | grep -A1 "Subject Alternative Name"
   ```

### Problèmes de certificat SSL

Si vous rencontrez des avertissements de sécurité dans le navigateur :

1. C'est normal avec des certificats auto-signés. Vous pouvez accepter le risque pour accéder à l'application.

2. Pour une solution plus sécurisée, envisagez d'utiliser Let's Encrypt pour obtenir un certificat SSL valide :
   ```bash
   sudo apt-get install certbot
   sudo certbot certonly --standalone -d 10.220.115.67
   ```
   Puis utilisez les certificats générés dans votre configuration.

## Configuration manuelle

Si vous préférez configurer manuellement :

1. Activer l'environnement conda :
   ```bash
   source /home/hadriengt/miniconda/etc/profile.d/conda.sh
   conda activate django
   ```

2. Générer les certificats SSL si nécessaire :
   ```bash
   mkdir -p ~/ssl
   openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
     -keyout ~/ssl/terryfox.key -out ~/ssl/terryfox.crt \
     -subj "/C=CA/ST=Quebec/L=Local/O=TerryFox/OU=LIMS/CN=localhost" \
     -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:10.220.115.67,IP:192.168.7.13"
   ```

3. Configurer Nginx :
   ```bash
   sudo cp terryfox_nginx_prod.conf /etc/nginx/sites-available/terryfox
   sudo ln -sf /etc/nginx/sites-available/terryfox /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl restart nginx
   ```

4. Démarrer l'application avec HTTPS :
   ```bash
   ./start_lims_backend.sh
   ```

## Configuration

You can modify the following configuration files:

- `.env` - Environment variables (SECRET_KEY, ALLOWED_HOSTS, etc.)
- `terryfox_lims/settings_prod.py` - Production settings (includes HTTPS settings)
- `gunicorn_start.sh` - Server configuration with SSL certificates
- `start_production.sh` - Main production startup script with SSL setup

## Advanced Setup Options

For a more robust production setup, consider:

1. Using PostgreSQL instead of SQLite:
   - Install PostgreSQL
   - Update database settings in `settings_prod.py`
   - Migrate data using Django's `dumpdata` and `loaddata` commands

2. Setting up Nginx as a reverse proxy:
   - Install Nginx
   - Use the provided `terryfox_nginx.conf` configuration
   - Link it to Nginx's sites-available directory
   - Enable the site

3. Setting up HTTPS:
   - **Option A: Using an IP Address with Nginx (recommended for production)**
     - Obtain an SSL certificate (Let's Encrypt recommended)
     - Configure Nginx for HTTPS using the certificate
     - Enable security settings in `settings_prod.py`
     
   - **Option B: Direct HTTPS with Django (current setup)**
     - Uses Django's runserver_plus for direct SSL support
     - Self-signed certificates stored in user directory
     - Simple configuration without requiring Nginx
     - Suitable for development or simple production environments
     - Note: This is the approach currently implemented in the startup scripts

   For detailed HTTPS setup instructions, refer to the dedicated `HTTPS.md` file.

## Accessing the Application with HTTPS

After setting up HTTPS with the current configuration, you can access the application at:
```
https://10.220.115.67:8443
```

## Troubleshooting

- If you can't access the application, check that port 8000 is not blocked by a firewall
- Check the logs output by Gunicorn for any errors
- Ensure the conda environment has all required packages installed

### HTTPS Troubleshooting

- **Certificate errors**: If using a self-signed certificate, browser warnings are normal. You need to accept the certificate.
- **Connection refused**: Ensure the application is running and the port is accessible.
- **SSL certificate problems**: Verify the certificates exist in ~/ssl/ directory.
- **Mixed content warnings**: Ensure all assets are served over HTTPS.
- **Django Extensions errors**: Make sure django-extensions is in INSTALLED_APPS in settings_prod.py
- **Port already in use**: Check for and kill existing processes with `pkill -f "runserver_plus"` or `pkill -f gunicorn`

## Maintenance

- Regularly back up the SQLite database file
- Keep track of Django security updates
- Monitor the application for errors or performance issues
- For self-signed certificates, note they do not expire automatically but should be renewed periodically (2-3 years) 
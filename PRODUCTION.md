# TerryFox LIMS - Production Setup

Ce document fournit les instructions pour exécuter TerryFox LIMS en mode production.

## Prérequis

- Python 3.8+ (via environnement Conda)
- Django et packages requis
- Packages supplémentaires pour HTTPS : django-extensions, werkzeug, pyOpenSSL
- Nginx (pour l'accès multi-utilisateurs)

## Options de déploiement

Vous avez deux options pour déployer TerryFox LIMS en production :

### Option 1 : Déploiement simple (accès limité)

Pour un démarrage rapide avec accès limité :

```bash
./start_production.sh
```

Cette méthode :
1. Démarre Django avec support HTTPS via django-extensions
2. Sert l'application de façon sécurisée sur le port 8443
3. Utilise les paramètres de production de `terryfox_lims/settings_prod.py`
4. Génère des certificats SSL auto-signés si nécessaire

Accès à l'application :
- https://localhost:8443 (accès local uniquement)
- https://SERVER_IP:8443 (peut ne pas fonctionner sur tous les navigateurs)

### Option 2 : Déploiement avec Nginx (recommandé pour multi-utilisateurs)

Pour un accès multi-utilisateurs fiable via l'IP de la VM :

```bash
# Étape 1 : Configuration de Nginx (une seule fois)
sudo ./setup_nginx_production.sh

# Étape 2 : Démarrage du backend LIMS
./start_lims_backend.sh
```

Cette méthode :
1. Configure Nginx comme proxy inverse sécurisé
2. Démarre Django en mode backend sur localhost:8443
3. Rend l'application accessible via HTTPS sur l'adresse IP de la VM

Accès à l'application :
- https://10.220.115.67 (accessible à tous les utilisateurs du réseau)

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
   - **Option A: Using a Domain Name with Nginx (recommended for production)**
     - Obtain an SSL certificate (Let's Encrypt recommended)
     - Configure Nginx for HTTPS using the certificate
     - Enable security settings in `settings_prod.py`
     
   - **Option B: Using an IP Address with Nginx**
     - Run the automated setup script (requires Nginx):
       ```bash
       sudo ./setup_https_ip.sh
       ```
     - The script will:
       - Generate a self-signed certificate valid for IP addresses
       - Configure Nginx for HTTPS
       - Apply appropriate permissions and security headers
     
   - **Option C: Direct HTTPS with Django (current setup)**
     - Uses Django's runserver_plus for direct SSL support
     - Self-signed certificates stored in user directory
     - Simple configuration without requiring Nginx
     - Suitable for development or simple production environments
     - Note: This is the approach currently implemented in the startup scripts

   For detailed HTTPS setup instructions, refer to the dedicated `HTTPS.md` file.

## Accessing the Application with HTTPS

After setting up HTTPS with the current configuration, you can access the application at:
```
https://SERVER_IP:8443
```

For the current IP-based setup, use:
```
https://192.168.7.13:8443
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
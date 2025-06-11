# TerryFox LIMS - Production Setup

This document provides instructions for running TerryFox LIMS in production mode.

## Prerequisites

- Python 3.8+ (via Conda environment)
- Django and required packages
- Additional packages for HTTPS: django-extensions, werkzeug, pyOpenSSL

## Quick Start

To start the application in production mode:

```bash
./start_production.sh
```

This will:
1. Start Django with HTTPS support via django-extensions
2. Serve the application securely on port 8443
3. Use production settings from `terryfox_lims/settings_prod.py`
4. Generate self-signed SSL certificates if they don't exist

Access the application at:
- https://localhost:8443 (if accessing locally)
- https://SERVER_IP:8443 (if accessing from another computer)

## Manual Startup

If you prefer to start the application manually:

1. Activate the conda environment:
   ```bash
   source /home/hadriengt/miniconda/etc/profile.d/conda.sh
   conda activate django
   ```

2. Generate SSL certificates if needed:
   ```bash
   mkdir -p ~/ssl
   openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
     -keyout ~/ssl/terryfox.key -out ~/ssl/terryfox.crt \
     -subj "/C=CA/ST=Quebec/L=Local/O=TerryFox/OU=LIMS/CN=localhost" \
     -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:192.168.7.13"
   ```

3. Start the application with HTTPS:
   ```bash
   ./gunicorn_start.sh
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
# TerryFox LIMS - Production Setup

This document provides instructions for running TerryFox LIMS in production mode.

## Prerequisites

- Python 3.8+ (via Conda environment)
- Django and required packages

## Quick Start

To start the application in production mode:

```bash
./start_production.sh
```

This will:
1. Start Gunicorn with multiple workers
2. Serve the application on port 8000
3. Use production settings from `terryfox_lims/settings_prod.py`

Access the application at:
- http://localhost:8000 (if accessing locally)
- http://SERVER_IP:8000 (if accessing from another computer)

## Manual Startup

If you prefer to start the application manually:

1. Activate the conda environment:
   ```bash
   conda activate django
   ```

2. Start Gunicorn:
   ```bash
   ./gunicorn_start.sh
   ```

## Configuration

You can modify the following configuration files:

- `.env` - Environment variables (SECRET_KEY, ALLOWED_HOSTS, etc.)
- `terryfox_lims/settings_prod.py` - Production settings
- `gunicorn_start.sh` - Gunicorn configuration

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
   - **Option A: Using a Domain Name**
     - Obtain an SSL certificate (Let's Encrypt recommended)
     - Configure Nginx for HTTPS using the certificate
     - Enable security settings in `settings_prod.py`
     
   - **Option B: Using an IP Address (e.g., 192.168.7.13)**
     - Run the automated setup script:
       ```bash
       sudo ./setup_https_ip.sh
       ```
     - The script will:
       - Generate a self-signed certificate valid for IP addresses
       - Configure Nginx for HTTPS
       - Apply appropriate permissions and security headers
     - Note: Users will need to accept the self-signed certificate in their browsers

   For detailed HTTPS setup instructions, refer to the dedicated `HTTPS.md` file.

## Accessing the Application with HTTPS

After setting up HTTPS, you can access the application at:
```
https://SERVER_IP:8000
```

For IP-based setup, use:
```
https://192.168.7.13:8000
```

## Troubleshooting

- If you can't access the application, check that port 8000 is not blocked by a firewall
- Check the logs output by Gunicorn for any errors
- Ensure the conda environment has all required packages installed

### HTTPS Troubleshooting

- **Certificate errors**: If using a self-signed certificate, browser warnings are normal. You need to accept the certificate.
- **Connection refused**: Ensure Nginx is properly configured and running.
- **Nginx configuration errors**: Check Nginx error logs with `sudo tail -f /var/log/nginx/error.log`.
- **Mixed content warnings**: Ensure all assets are served over HTTPS.

## Maintenance

- Regularly back up the SQLite database file
- Keep track of Django security updates
- Monitor the application for errors or performance issues
- For self-signed certificates, note they do not expire automatically but should be renewed periodically (2-3 years) 
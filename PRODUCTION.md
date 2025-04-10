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
   - Obtain an SSL certificate
   - Configure Nginx for HTTPS
   - Enable the security settings in `settings_prod.py`

## Troubleshooting

- If you can't access the application, check that port 8000 is not blocked by a firewall
- Check the logs output by Gunicorn for any errors
- Ensure the conda environment has all required packages installed

## Maintenance

- Regularly back up the SQLite database file
- Keep track of Django security updates
- Monitor the application for errors or performance issues 
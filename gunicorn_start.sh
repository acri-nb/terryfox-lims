#!/bin/bash

NAME="terryfox_lims"
DJANGODIR=/home/hadriengt/project/lims/terryfox-lims
USER=hadriengt
GROUP=hadriengt
PORT=8443  # Utilisation du port 8443 pour HTTPS
DJANGO_SETTINGS_MODULE=terryfox_lims.settings_prod
LOGLEVEL=info
CERTFILE=$HOME/ssl/terryfox.crt
KEYFILE=$HOME/ssl/terryfox.key

echo "Starting $NAME as `whoami`"

cd $DJANGODIR
source /home/hadriengt/miniconda/etc/profile.d/conda.sh
conda activate django

# Make sure the staticfiles directory exists
mkdir -p $DJANGODIR/staticfiles

# Collect static files
python manage.py collectstatic --noinput --settings=$DJANGO_SETTINGS_MODULE

export DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE
export PYTHONPATH=$DJANGODIR:$PYTHONPATH

echo "Starting Django with HTTPS support..."
echo "Using certificate: $CERTFILE"
echo "Using key file: $KEYFILE"

# Vérifier si le certificat et la clé existent
if [ ! -f "$CERTFILE" ] || [ ! -f "$KEYFILE" ]; then
  echo "ERROR: SSL certificate or key not found!"
  echo "Certificate path: $CERTFILE"
  echo "Key path: $KEYFILE"
  exit 1
fi

# Installer django-extensions si nécessaire
pip install django-extensions werkzeug pyOpenSSL --quiet

# Lancer Django avec support SSL
echo "Starting Django runserver_plus with SSL on port $PORT..."
echo "Access the application at: https://$(hostname -I | awk '{print $1}'):$PORT"
python manage.py runserver_plus 0.0.0.0:$PORT --settings=$DJANGO_SETTINGS_MODULE --cert-file=$CERTFILE --key-file=$KEYFILE
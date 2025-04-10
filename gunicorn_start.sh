#!/bin/bash

NAME="terryfox_lims"
DJANGODIR=/home/hadriengt/project/lims/terryfox-lims
USER=hadriengt
GROUP=hadriengt
WORKERS=3
BIND=0.0.0.0:8000
DJANGO_SETTINGS_MODULE=terryfox_lims.settings_prod
DJANGO_WSGI_MODULE=terryfox_lims.wsgi_prod
LOGLEVEL=info

echo "Starting $NAME as `whoami`"

cd $DJANGODIR
source ~/.conda/etc/profile.d/conda.sh
conda activate django

# Make sure the staticfiles directory exists
mkdir -p $DJANGODIR/staticfiles

# Collect static files
python manage.py collectstatic --noinput --settings=$DJANGO_SETTINGS_MODULE

export DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE
export PYTHONPATH=$DJANGODIR:$PYTHONPATH

echo "Starting Gunicorn..."
exec gunicorn ${DJANGO_WSGI_MODULE}:application \
  --name $NAME \
  --workers $WORKERS \
  --bind=$BIND \
  --log-level=$LOGLEVEL \
  --log-file=- \
  --access-logfile=- \
  --error-logfile=- 
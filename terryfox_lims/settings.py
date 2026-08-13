"""
Reglages de developpement.

Tout le commun vit dans settings_base.py ; ce fichier ne contient que ce qui
differe reellement de la production.

    python manage.py runserver
"""

from .settings_base import *  # noqa: F401,F403

# SECURITY WARNING: cette cle est publique et ne doit servir qu'en local.
SECRET_KEY = 'django-insecure-secret-key-for-development-only'

DEBUG = True

ALLOWED_HOSTS = ['10.111.243.103', 'localhost', '127.0.0.1']

WSGI_APPLICATION = 'terryfox_lims.wsgi.application'

# DATABASE_PATH permet de pointer une copie de la base pour un essai, sans
# toucher a celle du depot :
#     DATABASE_PATH=/tmp/copie.sqlite3 python manage.py runserver
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('DATABASE_PATH') or DEFAULT_DB_PATH,
        'OPTIONS': DB_OPTIONS,
    }
}

# Les courriels s'affichent dans la console au lieu d'etre envoyes.
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

"""
Reglages de production.

Tout le commun vit dans settings_base.py ; ce fichier ne contient que ce qui
differe reellement du developpement. Les valeurs sensibles sont lues dans .env
via python-decouple.

    gunicorn terryfox_lims.wsgi_prod:application
"""

from decouple import config

from .settings_base import *  # noqa: F401,F403

SECRET_KEY = config('SECRET_KEY', default='django-insecure-this-should-be-a-long-random-string-in-production')

DEBUG = False

ALLOWED_HOSTS = ['10.220.115.67', 'localhost', '127.0.0.1', 'candig-lims.cair.mun.ca']

WSGI_APPLICATION = 'terryfox_lims.wsgi_prod.application'

# --------------------------------------------------------------------------
# HTTPS
#
# Le TLS est termine par le proxy CAIR (candig-lims.cair.mun.ca), qui relaie
# vers gunicorn : d'ou USE_X_FORWARDED_HOST et SECURE_PROXY_SSL_HEADER.
# La redirection est geree au niveau du serveur, pas par Django.
# --------------------------------------------------------------------------

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000  # 1 annee
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
SECURE_BROWSER_XSS_FILTER = True

# --------------------------------------------------------------------------
# Applications et middleware specifiques a la production
# --------------------------------------------------------------------------

# Insere avant 'core' pour conserver exactement l'ordre d'origine : l'ordre de
# INSTALLED_APPS decide de la priorite des templates, des finders de fichiers
# statiques et des commandes de gestion.
INSTALLED_APPS = (
    INSTALLED_APPS[:-1]
    + ['django_extensions']  # runserver_plus avec SSL
    + INSTALLED_APPS[-1:]
)

# WhiteNoise sert les fichiers statiques et doit venir juste apres
# SecurityMiddleware.
MIDDLEWARE = (
    MIDDLEWARE[:1]
    + ['whitenoise.middleware.WhiteNoiseMiddleware']
    + MIDDLEWARE[1:]
)

# --------------------------------------------------------------------------
# Base de donnees
#
# DATABASE_PATH pointe hors de l'arbre git (/var/lib/terryfox-lims/db.sqlite3) :
# aucune commande git dans le depot ne peut atteindre les donnees vivantes.
# Cette valeur est posee dans .env par ops/install.sh.
# --------------------------------------------------------------------------

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': config('DATABASE_PATH', default=str(DEFAULT_DB_PATH)),
        'OPTIONS': DB_OPTIONS,
    }
}

# --------------------------------------------------------------------------
# Fichiers statiques
#
# CompressedManifestStaticFilesStorage exige que chaque chemin {% static %}
# figure dans staticfiles.json : un redemarrage sans collectstatic renvoie des
# 500 sur tout le site. ops/deploy.sh lance donc collectstatic apres migrate.
# --------------------------------------------------------------------------

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# --------------------------------------------------------------------------
# Courriel
# --------------------------------------------------------------------------

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='localhost')
EMAIL_PORT = config('EMAIL_PORT', default=25, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=False, cast=bool)
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='webmaster@localhost')

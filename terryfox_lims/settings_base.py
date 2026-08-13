"""
Reglages communs au developpement et a la production.

settings.py et settings_prod.py etaient deux fichiers integralement dupliques :
150 reglages, dont 130 identiques. Toute modification devait donc etre faite
deux fois, et l'oubli de l'une des deux ne se voyait qu'en production.

Ce module porte les 130 communs. Les deux autres l'importent puis ne
redefinissent que ce qui doit reellement differer. Leurs noms n'ont pas change,
donc tout ce qui reference terryfox_lims.settings ou terryfox_lims.settings_prod
-- wsgi, wsgi_prod, manage.py, les scripts de demarrage, les unites systemd --
continue de fonctionner sans modification.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------
# Applications
# --------------------------------------------------------------------------

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    'crispy_forms',
    'crispy_bootstrap5',

    # Custom apps
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'terryfox_lims.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# --------------------------------------------------------------------------
# Base de donnees
#
# Le chemin est configurable pour que la base de production puisse vivre hors de
# l'arbre git : aucune commande git ne peut alors atteindre les donnees vivantes.
# Voir ops/install.sh. Chaque module redefinit DATABASES avec sa propre source
# de configuration (variable d'environnement en dev, .env en production).
# --------------------------------------------------------------------------

DEFAULT_DB_PATH = BASE_DIR / 'db.sqlite3'

# SQLite attend plutot que de lever aussitot "database is locked" quand un autre
# worker ecrit. Trois workers gunicorn partagent le meme fichier.
DB_OPTIONS = {'timeout': 20}

# --------------------------------------------------------------------------
# Securite, internationalisation, fichiers statiques
# --------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

SECURE_CONTENT_TYPE_NOSNIFF = True

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/Halifax'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --------------------------------------------------------------------------
# Authentification et formulaires
# --------------------------------------------------------------------------

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'login'

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

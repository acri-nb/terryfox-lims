"""Reglages de l'archive V1 : lecture seule, sur des donnees figees.

Ce module est depose dans le paquet terryfox_lims de la copie V1 au moment de
l'installation. Il part des reglages de production de la V1 et ne change que ce
qui doit l'etre pour qu'une archive ne puisse rien modifier.

Trois couches empechent l'ecriture, parce qu'une seule barriere finit toujours
par sauter :
  1. le fichier est en 444 et appartient a root
  2. SQLite est ouvert en mode=ro : toute ecriture est refusee par le moteur
  3. un middleware rejette les requetes autres que GET et HEAD
"""

from terryfox_lims.settings_prod import *  # noqa: F401,F403

FROZEN_DB = '/var/lib/terryfox-lims/v1-frozen.sqlite3'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': f'file:{FROZEN_DB}?mode=ro',
        'OPTIONS': {'uri': True},
    }
}

# Couche 3. En tete de chaine : on refuse avant d'atteindre la moindre vue.
MIDDLEWARE = ['core.archive_middleware.ReadOnlyMiddleware'] + list(MIDDLEWARE)

# Les sessions sont normalement ecrites dans la table django_session -- une
# ecriture, sur une base en lecture seule : plus personne ne pourrait se
# connecter a l'archive. Les cookies signes ne stockent rien cote serveur.
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'

# Le cookie de session est signe avec SECRET_KEY. Celle du depot est publique,
# l'archive recoit donc la sienne, tiree au hasard a l'installation et jamais
# versionnee (ligne ajoutee en fin de fichier par install_v1_archive.sh).

# L'archive ne doit epingler aucune politique de securite dans les navigateurs :
# elle vit sur un autre port, avec son propre certificat.
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# Ses fichiers statiques lui sont propres.
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')  # noqa: F405

ALLOWED_HOSTS = ['*']  # accessible par IP comme par nom, derriere le pare-feu

# Affiche dans le bandeau permanent, renseigne a l'installation.
ARCHIVE_FROZEN_ON = 'unknown'

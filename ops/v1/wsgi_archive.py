"""Point d'entree WSGI de l'archive V1."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'terryfox_lims.settings_archive')

application = get_wsgi_application()

# Django met a jour User.last_login a chaque connexion reussie : une ecriture,
# sur une base en lecture seule. Sans ce debranchement, se connecter a l'archive
# leve "attempt to write a readonly database" et l'archive est inutilisable.
#
# Le dispatch_uid est indispensable : AuthConfig.ready() branche le recepteur
# avec dispatch_uid="update_last_login", et un disconnect() sans le meme
# identifiant ne trouve rien et ne fait donc rien -- silencieusement.
from django.contrib.auth.models import update_last_login  # noqa: E402
from django.contrib.auth.signals import user_logged_in  # noqa: E402

_debranche = user_logged_in.disconnect(
    update_last_login, dispatch_uid='update_last_login')
if not _debranche:  # pragma: no cover
    raise RuntimeError(
        "update_last_login n'a pas pu etre debranche : la connexion a l'archive "
        "echouerait sur une base en lecture seule."
    )

import logging

from django.apps import AppConfig
from django.db.backends.signals import connection_created

logger = logging.getLogger(__name__)


def _apply_sqlite_pragmas(sender, connection, **kwargs):
    """Passe SQLite en mode WAL a l'ouverture de chaque connexion.

    En mode par defaut (delete), un lecteur bloque un ecrivain et inversement.
    En WAL, les lecteurs ne bloquent plus l'ecrivain -- ce qui compte des lors
    que trois workers gunicorn partagent le meme fichier, et davantage encore
    avec les modifications en lot prevues en v2.

    journal_mode est persistant : la premiere execution bascule reellement le
    fichier, les suivantes ne font que relire le mode. On garde synchronous a sa
    valeur par defaut (FULL) : la priorite est la durabilite, pas le debit.

    L'archive V1 ouvre sa base en lecture seule, ou ce PRAGMA echoue ; l'echec
    est donc silencieux et sans consequence.
    """
    if connection.vendor != 'sqlite':
        return
    try:
        with connection.cursor() as cursor:
            cursor.execute('PRAGMA journal_mode=WAL;')
    except Exception as exc:  # base en lecture seule, ou verrouillee
        logger.debug("PRAGMA journal_mode=WAL ignore : %s", exc)


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        connection_created.connect(_apply_sqlite_pragmas)

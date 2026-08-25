"""Couche 3 du verrouillage de l'archive V1 : refus de toute ecriture HTTP.

Les couches 1 et 2 (permissions du fichier, SQLite en mode=ro) produiraient une
erreur 500 illisible. Ce middleware repond a la place une page claire, avant
meme d'atteindre une vue.
"""

from django.http import HttpResponse

LECTURE_SEULE = frozenset(['GET', 'HEAD', 'OPTIONS'])

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>V1 archive — read only</title>
<style>
 body{{font-family:system-ui,sans-serif;max-width:34rem;margin:16vh auto;padding:0 1.5rem;color:#12222e}}
 h1{{font-size:1.35rem;margin:0 0 .75rem}}
 p{{line-height:1.6;color:#44555f}}
 a{{color:#1c5d99}}
</style></head><body>
<h1>This is the V1 archive — nothing can be changed here</h1>
<p>The data shown was frozen on {date} and is kept for reference and comparison.
It is not the live system.</p>
<p>To make a change, use the current LIMS: <a href="{lims}">{lims}</a></p>
</body></html>"""


class ReadOnlyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method not in LECTURE_SEULE:
            from django.conf import settings
            return HttpResponse(
                PAGE.format(
                    date=getattr(settings, 'ARCHIVE_FROZEN_ON', 'an earlier date'),
                    lims=getattr(settings, 'ARCHIVE_LIVE_URL', 'https://candig-lims.cair.mun.ca/'),
                ),
                status=405,
                content_type='text/html; charset=utf-8',
            )
        return self.get_response(request)

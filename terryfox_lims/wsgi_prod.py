"""
WSGI config for terryfox_lims project in production.

It exposes the WSGI callable as a module-level variable named ``application``.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'terryfox_lims.settings_prod')

application = get_wsgi_application() 
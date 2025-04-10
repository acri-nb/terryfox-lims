#!/usr/bin/env python
"""
Script to check if TerryFox LIMS is properly configured for production.
Run this script before starting the application in production mode.
"""

import os
import sys
import socket
import django
from django.core.management.utils import get_random_secret_key

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'terryfox_lims.settings_prod')
try:
    django.setup()
except Exception as e:
    print(f"❌ Error setting up Django with production settings: {e}")
    sys.exit(1)

from django.conf import settings

def check_debug():
    """Check if DEBUG is disabled in production settings."""
    if settings.DEBUG:
        print("❌ DEBUG is still enabled in production settings")
        print("   Fix: Set DEBUG = False in terryfox_lims/settings_prod.py")
        return False
    else:
        print("✅ DEBUG is correctly disabled")
        return True

def check_secret_key():
    """Check if the SECRET_KEY is secure."""
    if settings.SECRET_KEY == 'django-insecure-this-should-be-a-long-random-string-in-production':
        print("❌ Default insecure SECRET_KEY detected")
        print("   Fix: Update SECRET_KEY in .env file")
        print(f"   Suggested secure key: {get_random_secret_key()}")
        return False
    else:
        print("✅ SECRET_KEY is properly configured")
        return True

def check_allowed_hosts():
    """Check if ALLOWED_HOSTS is properly configured."""
    if len(settings.ALLOWED_HOSTS) == 0:
        print("❌ ALLOWED_HOSTS is empty")
        print("   Fix: Add appropriate hosts to ALLOWED_HOSTS in .env file")
        return False
    elif settings.ALLOWED_HOSTS == ['localhost', '127.0.0.1']:
        # These are safe defaults, but might want to add the actual server IP
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        print(f"ℹ️ ALLOWED_HOSTS contains only localhost. Consider adding server IP: {ip}")
        return True
    else:
        print("✅ ALLOWED_HOSTS is configured")
        return True

def check_static_files():
    """Check if static files are properly configured."""
    static_root = settings.STATIC_ROOT
    if not os.path.exists(static_root):
        print(f"❌ STATIC_ROOT directory does not exist: {static_root}")
        print("   Fix: Run 'python manage.py collectstatic --settings=terryfox_lims.settings_prod'")
        return False
    elif not os.listdir(static_root):
        print(f"❌ STATIC_ROOT directory is empty: {static_root}")
        print("   Fix: Run 'python manage.py collectstatic --settings=terryfox_lims.settings_prod'")
        return False
    else:
        print("✅ Static files are properly collected")
        return True

def check_database():
    """Check if the database is accessible."""
    from django.db import connections
    try:
        connections['default'].cursor()
        print("✅ Database is accessible")
        return True
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        print("   Fix: Check your database settings in terryfox_lims/settings_prod.py")
        return False

def check_gunicorn():
    """Check if Gunicorn is installed."""
    try:
        import gunicorn
        print(f"✅ Gunicorn is installed (version {gunicorn.__version__})")
        return True
    except ImportError:
        print("❌ Gunicorn is not installed")
        print("   Fix: Run 'pip install gunicorn'")
        return False

def check_whitenoise():
    """Check if WhiteNoise is installed and configured."""
    try:
        import whitenoise
        if 'whitenoise.middleware.WhiteNoiseMiddleware' in settings.MIDDLEWARE:
            print("✅ WhiteNoise is properly configured")
            return True
        else:
            print("❌ WhiteNoise middleware is not enabled")
            print("   Fix: Add 'whitenoise.middleware.WhiteNoiseMiddleware' to MIDDLEWARE in settings_prod.py")
            return False
    except ImportError:
        print("❌ WhiteNoise is not installed")
        print("   Fix: Run 'pip install whitenoise'")
        return False

def main():
    """Run all checks and summarize the results."""
    print("=" * 60)
    print("TerryFox LIMS Production Configuration Check")
    print("=" * 60)
    
    checks = [
        check_debug(),
        check_secret_key(),
        check_allowed_hosts(),
        check_static_files(),
        check_database(),
        check_gunicorn(),
        check_whitenoise()
    ]
    
    print("\n" + "=" * 60)
    if all(checks):
        print("✅ All checks passed! TerryFox LIMS is ready for production.")
        print("   Run './start_production.sh' to start the application.")
    else:
        print("❌ Some checks failed. Please fix the issues mentioned above.")
    print("=" * 60)

if __name__ == "__main__":
    main() 
## @file wsgi.py
#  @brief WSGI entry point for the weatherview_project Django application.
#
#  Exposes the WSGI callable as a module-level variable named `application`.
#  Used by gunicorn (production) and Django's built-in development server.
#  The settings module is selected via the `DJANGO_SETTINGS_MODULE` environment
#  variable; it defaults to `weatherview_project.settings`.
#
#  @author Jari Jankkila
#  @date 2026

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'weatherview_project.settings')
application = get_wsgi_application()  ##< WSGI callable used by gunicorn and the Django dev server.

"""WSGI config for LazyFitness."""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lazyfitness.settings')
application = get_wsgi_application()

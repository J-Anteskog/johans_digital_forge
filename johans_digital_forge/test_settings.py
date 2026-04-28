"""
Test-inställningar: SQLite i minnet istället för PostgreSQL.

Används lokalt när Postgres inte är nåbar:
  python manage.py test --settings=johans_digital_forge.test_settings
"""
import os
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

from johans_digital_forge.settings import *  # noqa: F401, F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

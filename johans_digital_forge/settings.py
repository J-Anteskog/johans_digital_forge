from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv

# -----------------------------------------------------------
# LOAD ENVIRONMENT VARIABLES
# -----------------------------------------------------------
# Load .env file if it exists (for local development)
# In production (Coolify), environment variables are injected directly
load_dotenv()

# -----------------------------------------------------------
# BASE DIRECTORY
# -----------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# -----------------------------------------------------------
# SECURITY SETTINGS
# -----------------------------------------------------------
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is not set")

DEBUG = os.environ.get("DEBUG", "False") == "True"

# Allowed Hosts
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "").split(",")
CSRF_TRUSTED_ORIGINS = os.environ.get(
    "CSRF_TRUSTED_ORIGINS",
    "https://www.johans-digital-forge.se,https://johans-digital-forge.se"
).split(",")

# Add Railway domain automatically if available
railway_host = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
if railway_host and railway_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(railway_host)

# HTTPS/Proxy Settings for Coolify/Caddy
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = False
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# -----------------------------------------------------------
# APPLICATIONS
# -----------------------------------------------------------
INSTALLED_APPS = [
    # Django core
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'cloudinary_storage',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.sitemaps',
    'cloudinary',

    # Third-party
    'crispy_forms',
    'crispy_bootstrap5',
    'gunicorn',

    # Local apps
    'home',
    'service',
    'contact',
    'portfolio',
    'custom_admin',
]

SITE_ID = 1

# -----------------------------------------------------------
# MIDDLEWARE
# -----------------------------------------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# -----------------------------------------------------------
# URLS & WSGI
# -----------------------------------------------------------
ROOT_URLCONF = 'johans_digital_forge.urls'
WSGI_APPLICATION = 'johans_digital_forge.wsgi.application'

# -----------------------------------------------------------
# TEMPLATES
# -----------------------------------------------------------
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

# -----------------------------------------------------------
# DATABASE
# -----------------------------------------------------------
database_url = os.environ.get('DATABASE_URL')

if database_url:
    try:
        DATABASES = {
            "default": dj_database_url.config(
                default=database_url,
                conn_max_age=600,
                ssl_require=False
            )
        }
        print(f"✅ Connected to PostgreSQL database")
    except Exception as e:
        print(f"⚠️ Database connection error: {e}")
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / "db.sqlite3",
            }
        }
else:
    print(f"⚠️ DATABASE_URL not found, using SQLite")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# -----------------------------------------------------------
# PASSWORD VALIDATION
# -----------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# -----------------------------------------------------------
# INTERNATIONALIZATION
# -----------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# -----------------------------------------------------------
# STATIC & MEDIA FILES
# -----------------------------------------------------------
STATIC_URL = 'static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Använd CompressedStaticFilesStorage istället för Manifest (mindre strikt)
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

# Cloudinary
CLOUDINARY_STORAGE = {
    "CLOUD_NAME": os.environ.get("CLOUDINARY_CLOUD_NAME", ""),
    "API_KEY": os.environ.get("CLOUDINARY_API_KEY", ""),
    "API_SECRET": os.environ.get("CLOUDINARY_API_SECRET", ""),
}

# För Django 4.2+
STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

# -----------------------------------------------------------
# EMAIL SETTINGS (Resend)
# -----------------------------------------------------------
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.resend.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'False') == 'True'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'resend')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'info@johans-digital-forge.se')

# -----------------------------------------------------------
# AUTH / LOGIN REDIRECTS
# -----------------------------------------------------------
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/admin/"
LOGOUT_REDIRECT_URL = "/login/"

# -----------------------------------------------------------
# CRISPY FORMS
# -----------------------------------------------------------
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# -----------------------------------------------------------
# AUTO FIELD
# -----------------------------------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# -----------------------------------------------------------
# FIXA SITES FÖR SITEMAP (kör vid startup)
# -----------------------------------------------------------
def setup_site():
    """Uppdatera Site-objektet med rätt domän"""
    try:
        from django.contrib.sites.models import Site
        site, created = Site.objects.get_or_create(pk=1)
        if site.domain != 'johans-digital-forge.se':
            site.domain = 'johans-digital-forge.se'
            site.name = 'Johans Digital Forge'
            site.save()
            print(f"✅ Site updated: {site.domain}")
    except Exception as e:
        print(f"⚠️ Could not update Site: {e}")

# Kör setup när Django startar
import sys
if 'runserver' in sys.argv or 'gunicorn' in sys.argv[0]:
    setup_site()
from pathlib import Path
import os
import dj_database_url

# -----------------------------------------------------------
# BASE DIRECTORY
# -----------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# -----------------------------------------------------------
# CORE SETTINGS
# -----------------------------------------------------------
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is not set")

DEBUG = os.environ.get("DEBUG", "False") == "True"

# -----------------------------------------------------------
# ALLOWED HOSTS & CSRF
# -----------------------------------------------------------
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "").split(",")

if not ALLOWED_HOSTS or ALLOWED_HOSTS == [""]:
    ALLOWED_HOSTS = [
        "johans-digital-forge.se",
        "www.johans-digital-forge.se",
    ]

CSRF_TRUSTED_ORIGINS = [
    "https://johans-digital-forge.se",
    "https://www.johans-digital-forge.se",
]

# -----------------------------------------------------------
# HTTPS / PROXY (Coolify / Traefik / Caddy)
# -----------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True

USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# -----------------------------------------------------------
# APPLICATIONS
# -----------------------------------------------------------
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.sitemaps",

    # Media
    "cloudinary_storage",
    "cloudinary",

    # Third-party
    "crispy_forms",
    "crispy_bootstrap5",

    # Local
    "home",
    "service",
    "contact",
    "portfolio",
    "custom_admin",
]

SITE_ID = 1

# -----------------------------------------------------------
# MIDDLEWARE
# -----------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# -----------------------------------------------------------
# URLS / WSGI
# -----------------------------------------------------------
ROOT_URLCONF = "johans_digital_forge.urls"
WSGI_APPLICATION = "johans_digital_forge.wsgi.application"

# -----------------------------------------------------------
# TEMPLATES
# -----------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# -----------------------------------------------------------
# DATABASE
# -----------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

DATABASES = {
    "default": dj_database_url.config(
        default=DATABASE_URL,
        conn_max_age=600,
        ssl_require=False,  # internt nät i Docker
    )
}

# -----------------------------------------------------------
# PASSWORD VALIDATION
# -----------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# -----------------------------------------------------------
# INTERNATIONALIZATION
# -----------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# -----------------------------------------------------------
# STATIC FILES
# -----------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

# -----------------------------------------------------------
# MEDIA (Cloudinary)
# -----------------------------------------------------------
CLOUDINARY_STORAGE = {
    "CLOUD_NAME": os.environ.get("CLOUDINARY_CLOUD_NAME"),
    "API_KEY": os.environ.get("CLOUDINARY_API_KEY"),
    "API_SECRET": os.environ.get("CLOUDINARY_API_SECRET"),
}

STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

# -----------------------------------------------------------
# EMAIL (Resend)
# -----------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.resend.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = "resend"
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = "info@johans-digital-forge.se"

# -----------------------------------------------------------
# AUTH
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
# DEFAULT PK
# -----------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

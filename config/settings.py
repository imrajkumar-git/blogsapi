"""Django settings for the portfolio + community backend.

Configuration comes from environment variables (optionally via a `.env` file
next to manage.py). See `.env.example`.
"""
import os
import sys
from datetime import timedelta
from pathlib import Path
import dj_database_url
import django
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv
load_dotenv()
# Older Django releases can't render the admin on Python 3.14 (AttributeError:
# 'super' object has no attribute 'dicts'), and this project is built for 5.2+.
if django.VERSION < (5, 2):
    raise ImproperlyConfigured(
        f"This project needs Django 5.2 or newer, but {django.get_version()} is installed "
        "in this environment. Activate the project's virtualenv and run: "
        "pip install -r requirements.txt"
    )

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


def env_int(name, default):
    return int(os.environ.get(name, default))


# --------------------------------------------------------------------------- #
# Core
# --------------------------------------------------------------------------- #
DEBUG = os.getenv("DEBUG", False)

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-key-do-not-use-in-production"
    else:
        raise ImproperlyConfigured(
            "The SECRET_KEY environment variable is required when DEBUG is off. "
            "Copy .env.example to .env and set one."
        )
    

ALLOWED_HOSTS = [
    "backend-blogs-sspm.onrender.com",
]


ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    ".onrender.com",
]
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",  
    "corsheaders",
    "rest_framework",
    "accounts",
    "blog",
    "reviews",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    'whitenoise.middleware.WhiteNoiseMiddleware',
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --------------------------------------------------------------------------- #
# Database — SQLite by default. For PostgreSQL, swap this block (see README).
# --------------------------------------------------------------------------- #
DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL')
        
        )
}
# DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------- #
# Django REST framework + JWT
# --------------------------------------------------------------------------- #
REST_FRAMEWORK = {
    # Rejects tokens of users an admin has since un-verified or disabled.
    "DEFAULT_AUTHENTICATION_CLASSES": ["accounts.authentication.VerifiedJWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticatedOrReadOnly"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_RENDERER_CLASSES": (
        ["rest_framework.renderers.JSONRenderer"]
        + (["rest_framework.renderers.BrowsableAPIRenderer"] if DEBUG else [])
    ),
    # The frontend accepts plain arrays or {results: [...]}, but it filters
    # lists client-side (e.g. "My posts"), so pagination is left off on purpose.
    "DEFAULT_PAGINATION_CLASS": None,
    "DEFAULT_THROTTLE_RATES": {
        "login": "10/min",
        "register": "10/hour",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env_int("ACCESS_TOKEN_MINUTES", 60)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env_int("REFRESH_TOKEN_DAYS", 7)),
    # The frontend only stores the new *access* token from /token/refresh/,
    # so refresh-token rotation must stay off.
    "ROTATE_REFRESH_TOKENS": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# --------------------------------------------------------------------------- #
# CORS
# --------------------------------------------------------------------------- #
CORS_ALLOWED_ORIGINS = [
    "https://rajkumarayal.com.np",
    "https://www.rajkumarayal.com.np",
    "https://full-stack-django-nextjs-otpwithjwt.vercel.app",
    "http://localhost:3000",
]
CSRF_TRUSTED_ORIGINS = [
    "https://rajkumarayal.com.np",
    "https://www.rajkumarayal.com.np",
]

# --------------------------------------------------------------------------- #
# Static & media files
# --------------------------------------------------------------------------- #
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
FILE_UPLOAD_PERMISSIONS = 0o644

 # Keep in sync with MAX_BYTES in frontend/components/CoverImagePicker.jsx.
BLOG_COVER_MAX_BYTES = env_int("BLOG_COVER_MAX_BYTES", 5 * 1024 * 1024)
AVATAR_MAX_BYTES = env_int("AVATAR_MAX_BYTES", 5 * 1024 * 1024)

# --------------------------------------------------------------------------- #
# Internationalisation
# --------------------------------------------------------------------------- #
LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------- #
# HTTPS hardening (turn on with USE_HTTPS=True in production)
# --------------------------------------------------------------------------- #
if env_bool("USE_HTTPS", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30

# Fast password hashing so the test suite runs quickly (never used otherwise).
if "test" in sys.argv:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
 

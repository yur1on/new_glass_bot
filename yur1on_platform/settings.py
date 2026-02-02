from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name: str, default=None):
    return os.getenv(name, default)


# =========================================================
# Core
# =========================================================
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-secret-key-change-me")
DEBUG = env("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = [
    "45.128.205.77",
    "localhost",
    "127.0.0.1",
]


# =========================================================
# Applications
# =========================================================
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "premium",
    "bot",
    "panel",
]


# =========================================================
# Middleware
# =========================================================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "yur1on_platform.urls"
WSGI_APPLICATION = "yur1on_platform.wsgi.application"


# =========================================================
# Templates
# =========================================================
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


# =========================================================
# Database
# sqlite локально / postgres на VPS
# =========================================================
if env("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB", "glassbot"),
            "USER": env("POSTGRES_USER", "glassbot"),
            "PASSWORD": env("POSTGRES_PASSWORD", ""),
            "HOST": env("POSTGRES_HOST", "db"),
            "PORT": env("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATA_DIR = BASE_DIR / "data"
    DATA_DIR.mkdir(exist_ok=True)

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": DATA_DIR / "user_database.db",
        }
    }


# =========================================================
# i18n / TZ
# =========================================================
LANGUAGE_CODE = "ru"
TIME_ZONE = "Europe/Vaduz"
USE_I18N = True
USE_TZ = True


# =========================================================
# Static files (АДМИНКА СО СТИЛЯМИ)
# =========================================================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = [
    BASE_DIR / "static",
] if (BASE_DIR / "static").exists() else []


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# =========================================================
# Bot settings
# =========================================================
BOT_TOKEN = env("BOT_TOKEN", "CHANGE_ME")
ADMIN_ID = int(env("ADMIN_ID", "486747175"))
WEBAPP_URL = env("WEBAPP_URL", "https://yur1on.github.io/tg-size-webapp/")


# =========================================================
# CSRF / Security
# =========================================================
CSRF_TRUSTED_ORIGINS = [
    "http://45.128.205.77:8010",
]

# пока без https
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

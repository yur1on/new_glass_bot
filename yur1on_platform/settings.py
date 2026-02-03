from pathlib import Path
import os



BASE_DIR = Path(__file__).resolve().parent.parent


def env(name: str, default=None):
    return os.getenv(name, default)


# ==================================================
# Core
# ==================================================
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-secret-key-change-me")
DEBUG = env("DJANGO_DEBUG", "0") == "1"

ALLOWED_HOSTS = [
    h.strip()
    for h in env("DJANGO_ALLOWED_HOSTS", "").split(",")
    if h.strip()
]

# безопасный дефолт для локалки
if DEBUG and not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# жёсткая защита для продакшена
if not DEBUG and not ALLOWED_HOSTS:
    raise RuntimeError("ALLOWED_HOSTS must be set when DEBUG=False")


# ==================================================
# Applications
# ==================================================
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # local apps
    "premium",
    "bot",
    "panel",
]


# ==================================================
# Middleware
# ==================================================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ==================================================
# URLs / Templates
# ==================================================
ROOT_URLCONF = "yur1on_platform.urls"

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

WSGI_APPLICATION = "yur1on_platform.wsgi.application"


# ==================================================
# Database
# ==================================================
DB_ENGINE = env("DB_ENGINE", "sqlite").lower()

if DB_ENGINE == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB", "glassbot"),
            "USER": env("POSTGRES_USER", "glassbot"),
            "PASSWORD": env("POSTGRES_PASSWORD", "glassbot"),
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
            "NAME": DATA_DIR / "db.sqlite3",
        }
    }


# ==================================================
# i18n / Time
# ==================================================
LANGUAGE_CODE = "ru"
TIME_ZONE = "Europe/Vaduz"

USE_I18N = True
USE_TZ = True


# ==================================================
# Static files
# ==================================================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = (
    [BASE_DIR / "static"]
    if (BASE_DIR / "static").exists()
    else []
)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ==================================================
# Telegram bot
# ==================================================
BOT_TOKEN = env("BOT_TOKEN", "")
ADMIN_ID = int(env("ADMIN_ID", "0") or 0)
WEBAPP_URL = env("WEBAPP_URL", "")


# ==================================================
# Security / CSRF
# ==================================================
CSRF_TRUSTED_ORIGINS = [
    x.strip()
    for x in env("DJANGO_CSRF_TRUSTED", "").split(",")
    if x.strip()
]

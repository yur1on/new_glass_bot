# yur1on_platform/settings.py
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name: str, default=None):
    return os.getenv(name, default)


# -------------------------
# Core
# -------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-secret-key-change-me")

DEBUG = env("DJANGO_DEBUG", "1") == "1"

# Можно задать так:
# DJANGO_ALLOWED_HOSTS=45.128.205.77,localhost,127.0.0.1
ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()]
if DEBUG and not ALLOWED_HOSTS:
    # чтобы локально не мучаться
    ALLOWED_HOSTS = ["127.0.0.1", "localhost"]


# -------------------------
# Apps
# -------------------------
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


# -------------------------
# Middleware
# -------------------------
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


# -------------------------
# Templates
# -------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # твои кастомные шаблоны
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


# -------------------------
# Database переключение: sqlite локально / postgres на VPS
# -------------------------
DB_ENGINE = env("DB_ENGINE", "sqlite").strip().lower()

# Если на VPS ты не хочешь писать DB_ENGINE=postgres, можно авто-включать
# по наличию POSTGRES_HOST или POSTGRES_DB
if env("POSTGRES_HOST") or env("POSTGRES_DB"):
    # но только если явно не указали sqlite
    if DB_ENGINE != "sqlite":
        DB_ENGINE = "postgres"

if DB_ENGINE == "postgres":
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
    # ✅ SQLite по умолчанию
    DATA_DIR = BASE_DIR / "data"
    DB_PATH = DATA_DIR / "user_database.db"
    DATA_DIR.mkdir(exist_ok=True)

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(DB_PATH),
        }
    }


# -------------------------
# i18n / tz
# -------------------------
LANGUAGE_CODE = "ru"
TIME_ZONE = "Europe/Vaduz"
USE_I18N = True
USE_TZ = True


# -------------------------
# Static files
# -------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Если есть свои статические файлы в проекте
STATICFILES_DIRS = [
    BASE_DIR / "static",
] if (BASE_DIR / "static").exists() else []


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# -------------------------
# Bot settings
# -------------------------
BOT_TOKEN = env("BOT_TOKEN", "CHANGE_ME_LOCAL_TOKEN")
ADMIN_ID = int(env("ADMIN_ID", "486747175"))
WEBAPP_URL = env("WEBAPP_URL", "https://yur1on.github.io/tg-size-webapp/")


# -------------------------
# Security / CSRF
# -------------------------
# Для админки на VPS через IP/домен (иначе может ругаться CSRF)
# DJANGO_CSRF_TRUSTED=https://domain.com,http://45.128.205.77:8010
CSRF_TRUSTED_ORIGINS = [x.strip() for x in env("DJANGO_CSRF_TRUSTED", "").split(",") if x.strip()]

# Если trusted не задан, но есть ALLOWED_HOSTS и DEBUG выключен — попробуем собрать базово
if not DEBUG and not CSRF_TRUSTED_ORIGINS:
    # добавим хотя бы по хостам http/https
    for h in ALLOWED_HOSTS:
        if h in ("*",):
            continue
        CSRF_TRUSTED_ORIGINS.append(f"http://{h}")
        CSRF_TRUSTED_ORIGINS.append(f"https://{h}")

# прод-безопасность
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = False  # включим когда будет nginx/https

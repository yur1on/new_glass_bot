from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret-key-change-me")
DEBUG = True
ALLOWED_HOSTS = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "bot",
    "panel",
]

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

# ✅ База: используем существующую sqlite user_database.db
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "user_database.db"
DATA_DIR.mkdir(exist_ok=True)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(DB_PATH),
    }
}

LANGUAGE_CODE = "ru"
TIME_ZONE = "Europe/Vaduz"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ✅ Настройки бота (как было в config.py)
BOT_TOKEN = os.getenv("BOT_TOKEN", "8012740781:AAHbHW8O_cTaiFPLghW7mU-p8i-g4-aT6D0")
ADMIN_ID = int(os.getenv("ADMIN_ID", "486747175"))
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://yur1on.github.io/tg-size-webapp/")

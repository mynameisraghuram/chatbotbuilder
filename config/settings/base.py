from pathlib import Path
import os
from dotenv import load_dotenv
load_dotenv()


BASE_DIR = Path(__file__).resolve().parents[3]

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = os.getenv("DEBUG", "0") == "1"
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "rest_framework",
    "drf_spectacular",

    "core.tenants",
    "core.iam",
    "core.flags",
    "core.search",
    "core.knowledge",
    "core.common",
    "core.chatbots",
    "core.api_keys",
    "core.conversations",
    "core.leads.apps.LeadsConfig",
    "core.public",
    "core.analytics",
    "core.webhooks",
    "core.notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    "core.common.middleware.TenantScopeMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": [
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
        ]},
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "chatbuilder"),
        "USER": os.getenv("DB_USER", "chatbuilder"),
        "PASSWORD": os.getenv("DB_PASSWORD", "chatbuilder"),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {"TITLE": "ChatbotBuilder API", "VERSION": "0.0.0-sprint0"}

TENANT_HEADER = os.getenv("TENANT_HEADER", "X-Tenant-Id")

# Redis (used for rate limiting)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "http://127.0.0.1:9200")
OPENSEARCH_INDEX_PREFIX = os.getenv("OPENSEARCH_INDEX_PREFIX", "chatbuilder")
OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "http://localhost:9200")
OPENSEARCH_KB_INDEX = os.getenv("OPENSEARCH_KB_INDEX", "kb_chunks_v1")
OPENSEARCH_TIMEOUT = int(os.getenv("OPENSEARCH_TIMEOUT", "15"))

# Celery
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_ALWAYS_EAGER = False
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_CREATE_MISSING_QUEUES = True
CELERY_TASK_DEFAULT_QUEUE = "celery"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Asia/Kolkata"
CELERY_ENABLE_UTC = True

CELERY_BEAT_SCHEDULE = {
    "schedule-lead-reminders-every-5-min": {
        "task": "core.leads.tasks_sla.schedule_lead_reminders",
        "schedule": 300.0,
    },
}


EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@chatbotbuilder.local")

EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "0") == "1"

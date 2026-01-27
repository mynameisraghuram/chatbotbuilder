from .base import *  # noqa

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
DATABASES["default"]["NAME"] = "chatbuilder_test"

# Keep tests fast/deterministic
CELERY_TASK_ALWAYS_EAGER = True

from .base import *  # noqa: F401, F403

DEBUG = False

DATABASES["default"]["NAME"] = "test_saasvault_db"  # noqa: F405

# Use fast hasher so tests run quickly
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Run Celery tasks synchronously in tests — no broker needed
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Skip whitenoise compression in tests
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

# Silence logging noise in test output
LOGGING["root"]["level"] = "CRITICAL"  # noqa: F405

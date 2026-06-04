from datetime import timedelta

from decouple import Csv, config

from .base import *  # noqa: F401, F403

DEBUG = False

ALLOWED_HOSTS = config("DJANGO_ALLOWED_HOSTS", cast=Csv())

# Shorter access token lifetime in production
SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] = timedelta(minutes=15)  # noqa: F405

# HTTPS security
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="", cast=Csv())

# ---------------------------------------------------------------------------
# Logging — switch console handler to JSON formatter for log aggregators
# ---------------------------------------------------------------------------

LOGGING["handlers"]["console"]["formatter"] = "json"  # noqa: F405

# ---------------------------------------------------------------------------
# Sentry — error tracking (disabled when SENTRY_DSN is empty)
# ---------------------------------------------------------------------------

SENTRY_DSN = config("SENTRY_DSN", default="")
SENTRY_ENVIRONMENT = config("SENTRY_ENVIRONMENT", default="production")

if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    def _scrub_sensitive_headers(event: dict, hint: dict) -> dict | None:
        """Strip Authorization header and /auth/ request bodies before sending to Sentry.

        GDPR / CLAUDE.md §10: never expose credentials to third parties.
        """
        request = event.get("request", {})

        # Remove Authorization header from all requests.
        headers = request.get("headers", {})
        headers.pop("Authorization", None)
        headers.pop("authorization", None)

        # Remove request body for auth endpoints (may contain passwords).
        url = request.get("url", "")
        if "/auth/" in url:
            request.pop("data", None)
            request.pop("body", None)

        return event

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=SENTRY_ENVIRONMENT,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,  # GDPR: do not send IPs or emails by default
        before_send=_scrub_sensitive_headers,
    )

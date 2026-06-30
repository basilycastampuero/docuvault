# ---- Stage 1: builder ----
# Install Python dependencies in an isolated layer so the runtime image stays lean.
FROM python:3.13-slim AS builder

WORKDIR /app

RUN pip install --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Stage 2: runtime ----
FROM python:3.13-slim AS runtime

# PYTHONUNBUFFERED=1  — stdout/stderr are not buffered so logs appear
#                       immediately in `docker logs` without delay.
# PYTHONDONTWRITEBYTECODE=1 — skip .pyc files; cleaner image, faster builds.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# System dependencies required at runtime:
#   libmagic1      — python-magic (file type detection / FileValidator)
#   tesseract-ocr  — OCR engine
#   tesseract-ocr-spa — Spanish language pack for Tesseract
#   poppler-utils  — pdf2image (PDF → image conversion for OCR)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    tesseract-ocr \
    tesseract-ocr-spa \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy project source
COPY . .

# Bake static files into the image so every container (web, worker, beat, migrate)
# has the manifest without needing a shared volume or a runtime collectstatic step.
# Uses config.settings.base to avoid requiring production-only env vars at build time.
# DJANGO_SECRET_KEY is required by Django to import settings; the dummy value is
# never used at runtime — real secrets come from .env.production via env_file.
RUN DJANGO_SECRET_KEY=build-placeholder \
    DJANGO_SETTINGS_MODULE=config.settings.base \
    python manage.py collectstatic --noinput

# Set correct ownership before switching to a non-root user.
# COPY runs as root, so without chown appuser cannot write to /app (e.g. pidfiles).
RUN useradd --create-home appuser \
    && chown -R appuser:appuser /app

USER appuser

# Default command: Gunicorn web server.
# Overridden per service in docker-compose.prod.yml (worker, beat, migrate).
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]

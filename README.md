# SasVault

Enterprise document management SaaS platform with multi-tenancy, role-based access control, automated workflows, and full-text search.

[![CI](https://github.com/basilycastampuero/SasVault/actions/workflows/ci.yml/badge.svg)](https://github.com/basilycastampuero/SasVault/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/basilycastampuero/SasVault/branch/main/graph/badge.svg)](https://codecov.io/gh/basilycastampuero/SasVault)

## Tech Stack

**Backend:** Python 3.13 · Django 5.1 · Django REST Framework · PostgreSQL 16 · Redis 7 · Celery
**Storage:** MinIO (dev) · AWS S3 (prod)
**Infrastructure:** Docker · Nginx · GitHub Actions
**Observability:** Sentry · Structured JSON logging

## Architecture

Modular monolith with domain-driven structure, designed for future service extraction.

```
backend/
  apps/
    authentication/   # Custom User, JWT auth, token management
    organizations/    # Multi-tenancy, tenant isolation
    permissions/      # RBAC, granular permissions
    documents/        # File management, versioning, OCR
    workflows/        # State machines, approval flows
    audit/            # Immutable audit log
    notifications/    # Event-driven notifications
    search/           # PostgreSQL full-text search
    core/             # BaseModel, exceptions, pagination
```

## Key Features

- **Multi-tenancy** — complete organization isolation via shared schema with `organization_id` on every domain table
- **RBAC** — six-role system (super_admin, org_admin, supervisor, editor, viewer, auditor) with permission classes per endpoint
- **JWT auth** — rotating refresh tokens with blacklist, custom claims (organization_id, role, email)
- **Document versioning** — immutable version history, no file overwrites
- **Audit logging** — who, what, when, from where, old/new values
- **Async processing** — OCR, thumbnails, exports via Celery
- **Full-text search** — PostgreSQL tsvector with GIN indexing

## Running Locally

### Prerequisites
- Docker Desktop with WSL2 integration
- Python 3.13+

### Setup

```bash
# Clone
git clone git@github.com:<your-user>/SasVault.git
cd SasVault

# Start infrastructure services
docker compose up -d

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your values
python manage.py migrate
python manage.py init_storage   # creates MinIO bucket (idempotent)
python manage.py runserver
```

API running at `http://localhost:8000/api/v1/`
Swagger UI at `http://localhost:8000/api/docs/`
MinIO console at `http://localhost:9001`

## Development

```bash
# Run tests
pytest

# Format + lint
black .
isort .
flake8

# Celery worker (for async tasks)
celery -A config.celery worker --loglevel=info
```

See `docs/manual-testing.md` for step-by-step curl examples testing all features.

## Deploy

### VPS requirements

- Ubuntu 22.04 LTS
- Docker Engine + Docker Compose plugin installed
- `openssl` available (pre-installed on Ubuntu)
- Port 80 and 443 open in the firewall

### Initial setup

```bash
# On the VPS — clone the repo
git clone git@github.com:<your-user>/SasVault.git /opt/saasvault
cd /opt/saasvault

# Copy the production env template and fill in all values
cp backend/.env.production.example backend/.env.production
nano backend/.env.production   # set DB_PASSWORD, DJANGO_SECRET_KEY, etc.

# Make scripts executable
chmod +x scripts/deploy.sh scripts/backup_db.sh

# Deploy (builds images, runs migrations, starts all services)
bash scripts/deploy.sh
```

A self-signed certificate is generated automatically on the first run. The browser will warn on first visit — this is expected without a real domain. To replace with a real certificate, put your `.crt` and `.key` files in `nginx/certs/` before running `deploy.sh`.

Services after deploy:
- API: `https://<VPS_IP>/api/v1/`
- Frontend: `https://<VPS_IP>/`
- Django admin: `https://<VPS_IP>/admin/`

### Subsequent deploys

Re-running `deploy.sh` is idempotent: it pulls latest code, skips cert generation if the cert exists, rebuilds images, runs pending migrations, and restarts services.

### GitHub Actions deploy (workflow_dispatch)

Set these three secrets in **Settings → Secrets and variables → Actions** on GitHub:

| Secret | Value |
|--------|-------|
| `VPS_HOST` | IP address or hostname of the VPS |
| `VPS_USER` | SSH username (e.g. `ubuntu`) |
| `VPS_SSH_KEY` | Private SSH key whose public key is in `~/.ssh/authorized_keys` on the VPS |

Then trigger a deploy from **Actions → Deploy to VPS → Run workflow**.

### Backup and restore

```bash
# Create a compressed backup (7-day retention in /var/backups/saasvault/)
bash scripts/backup_db.sh

# Add to crontab for nightly automated backups at 02:00
# 0 2 * * * cd /opt/saasvault && bash scripts/backup_db.sh >> /var/log/saasvault-backup.log 2>&1

# Restore from a backup file
gunzip -c /var/backups/saasvault/saasvault_<timestamp>.sql.gz \
  | docker compose -f docker-compose.prod.yml exec -T postgres \
      psql -U saasvault_user saasvault_prod
```

## Status

Active development — **Phase 5 in progress (5.4 complete).** Next: Phase 5.5 (VPS deploy).

| Phase | Scope | Status |
|-------|-------|--------|
| 0 | Setup (Docker, pre-commit, env) | ✅ Complete |
| 1 | Auth + Organizations + RBAC + Users | ✅ Complete |
| 2 | Document management + versioning + storage + audit | ✅ Complete |
| 3.1 | Audit read API with filters and role-based access | ✅ Complete |
| 3.2 | Workflow engine (templates, steps, executions, approval flows) | ✅ Complete |
| 3.3 | Full-text search with PostgreSQL tsvector + GIN | ✅ Complete |
| 4 | Celery pipelines + OCR + AI analysis (Claude Haiku) | ✅ Complete |
| 5.1 | Frontend setup + auth (React + Vite + Tailwind + shadcn/ui) | ✅ Complete |
| 5.2 | Frontend document management (upload, folders, search) | ✅ Complete |
| 5.3 | Frontend workflows + audit log + AI analysis tab | ✅ Complete |
| 5.4 | CI/CD GitHub Actions (backend + frontend parallel jobs) | ✅ Complete |
| 5.5 | Deploy VPS (Gunicorn + Nginx + SSL) | 🔄 Next |
| 5.6 | Observability: health check, Sentry, JSON logging | ✅ Complete |
| 5.7 | Email notifications (Celery + step-assigned events) | ✅ Complete |

**~526 tests passing, 95% coverage.**

---

Built as a portfolio project demonstrating enterprise backend architecture.

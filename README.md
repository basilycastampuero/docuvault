# SasVault

Enterprise document management SaaS platform with multi-tenancy, role-based access control, automated workflows, and full-text search.

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

## Status

Active development — **Phase 5 in progress (5.6 complete).** Next: Phase 5.1 (React frontend).

| Phase | Scope | Status |
|-------|-------|--------|
| 0 | Setup (Docker, pre-commit, env) | ✅ Complete |
| 1 | Auth + Organizations + RBAC + Users | ✅ Complete |
| 2 | Document management + versioning + storage + audit | ✅ Complete |
| 3.1 | Audit read API with filters and role-based access | ✅ Complete |
| 3.2 | Workflow engine (templates, steps, executions, approval flows) | ✅ Complete |
| 3.3 | Full-text search with PostgreSQL tsvector + GIN | ✅ Complete |
| 4 | Celery pipelines + OCR + AI analysis (Claude Haiku) | ✅ Complete |
| 5.6 | Observability: health check, Sentry, JSON logging | ✅ Complete |
| 5.1–5.5, 5.7 | Frontend, CI/CD, deploy, notifications | 🔄 In progress |

**501 tests passing, 99% coverage.**

---

Built as a portfolio project demonstrating enterprise backend architecture.

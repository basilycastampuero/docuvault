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
python manage.py runserver
```

API running at `http://localhost:8000/api/v1/`
MinIO console at `http://localhost:9001`

## Development

```bash
# Run tests
pytest

# Format code
black .
isort .

# Lint
flake8
```

## Status

Active development — Phase 1 (Auth + Organizations + RBAC + User management) complete.
166 tests passing, 99% coverage.

---

Built as a portfolio project demonstrating enterprise backend architecture.

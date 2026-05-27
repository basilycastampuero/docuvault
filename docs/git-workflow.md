# docs/git-workflow.md — Git Workflow SasVault

> Convenciones de Git para el proyecto.
> Un historial limpio y legible es parte del portafolio.

---

## 1. Estrategia de ramas

```
main
  └── develop
        ├── feature/jwt-authentication
        ├── feature/organization-model
        ├── feature/document-upload
        ├── fix/tenant-isolation-bug
        └── chore/update-dependencies
```

### Reglas

| Rama | Propósito | Quién hace push |
|------|-----------|-----------------|
| `main` | Código de producción estable | Solo merge desde develop |
| `develop` | Integración continua de features | Merge de feature branches |
| `feature/*` | Una feature específica | Desarrollo activo |
| `fix/*` | Corrección de bug | Desarrollo activo |
| `chore/*` | Mantenimiento, deps, config | Desarrollo activo |
| `docs/*` | Solo documentación | Desarrollo activo |

### Flujo de trabajo diario

```bash
# 1. Partir siempre desde develop actualizado
git checkout develop
git pull origin develop

# 2. Crear rama para la feature
git checkout -b feature/document-upload

# 3. Desarrollar con commits pequeños y frecuentes
git add apps/documents/services/document_service.py
git commit -m "feat(documents): add file validation in create_document service"

git add apps/documents/tests/test_document_service.py
git commit -m "test(documents): add tests for document creation and validation"

# 4. Cuando la feature está completa y con tests
git checkout develop
git pull origin develop
git merge feature/document-upload
git push origin develop

# 5. Borrar la rama local (ya está mergeada)
git branch -d feature/document-upload
```

---

## 2. Conventional Commits

Formato obligatorio para todos los commits:

```
<type>(<scope>)?: <descripción en imperativo, minúscula, sin punto final>

[body opcional — explica el POR QUÉ, no el qué]

[footer opcional — referencias a issues, breaking changes]
```

El **scope es recomendado pero opcional**:
- Úsalo cuando el cambio toca un solo dominio: `feat(auth): ...`, `fix(documents): ...`
- Omítelo cuando el cambio abarca múltiples dominios (fases completas, refactors transversales)
  o cuando el dominio ya es claro por la descripción: `feat: implement authentication app (Phase 1.4)`

### Tipos permitidos

| Tipo | Cuándo |
|------|--------|
| `feat` | Nueva funcionalidad |
| `fix` | Corrección de bug |
| `test` | Agregar o corregir tests |
| `docs` | Solo documentación |
| `chore` | Mantenimiento (deps, config, build) |
| `refactor` | Refactoring sin cambio de comportamiento |
| `perf` | Mejora de performance |
| `style` | Formato, espacios (sin lógica) |
| `ci` | Cambios en CI/CD |

### Scopes recomendados

```
auth, organizations, documents, folders, workflows,
audit, permissions, notifications, search, celery,
docker, nginx, settings, deps
```

### Ejemplos correctos

```
feat(auth): implement JWT login with custom claims
feat(documents): add presigned URL generation for file download
feat(audit): register audit log on document status change
fix(permissions): correct tenant isolation in document selector
test(auth): add tests for token refresh and blacklist
test(documents): add tenant isolation tests for folder API
refactor(documents): extract file validation to dedicated validator module
chore(deps): update djangorestframework to 3.15.2
perf(documents): add composite index on organization_id and status
docs(api): document error response format in api-conventions.md
ci: add pytest coverage check to GitHub Actions pipeline
```

### Ejemplos incorrectos

```
❌ fix                          → sin descripción
❌ update stuff                 → vago, sin tipo
❌ WIP                          → no commitear WIPs
❌ Fixed the bug                → pasado, mayúscula, con punto
❌ feat: Add document upload.   → mayúscula, con punto
❌ changes                      → completamente inútil
```

---

## 3. Tamaño de commits

**Un commit = un cambio lógico.**

```
# ✅ CORRECTO — commits pequeños y específicos
feat(documents): add Document model with BaseModel
test(documents): add DocumentFactory for tests
feat(documents): add document_service.create_document
test(documents): add tests for document creation service
feat(documents): add DocumentListCreateView
test(documents): add API tests for document endpoints

# ❌ INCORRECTO — todo en un commit gigante
feat: add documents feature with model, service, views, tests, serializers and urls
```

---

## 4. .gitignore — Qué nunca commitear

Crítico — verificar antes de cada push:

```
.env                 ← NUNCA — contiene secrets
.env.local           ← NUNCA
.env.production      ← NUNCA
*.pyc                ← bytecode compilado
__pycache__/         ← caché de Python
.venv/               ← entorno virtual
staticfiles/         ← archivos estáticos generados
mediafiles/          ← uploads locales
.coverage            ← reporte de cobertura binario
*.sqlite3            ← base de datos local
```

`.env.example` SÍ va en el repo — es el template sin valores reales.

---

## 5. GitHub — Buenas prácticas de portafolio

### README.md

El README es la portada del proyecto. Debe incluir:
- Descripción del proyecto (1 párrafo)
- Tech stack con badges
- Diagrama de arquitectura (simple, en ASCII o Mermaid)
- Instrucciones para correr localmente (claras y completas)
- Features implementadas
- Estado actual del proyecto
- Screenshots o GIFs del frontend (cuando esté listo)

### Badges en README

```markdown
![Python](https://img.shields.io/badge/Python-3.13-blue)
![Django](https://img.shields.io/badge/Django-5.1-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)
![Tests](https://github.com/user/saasvault/actions/workflows/ci.yml/badge.svg)
![Coverage](https://img.shields.io/badge/coverage-85%25-brightgreen)
```

### Issues y milestones (opcional pero valorado)

Crear issues en GitHub por fase/feature y cerrarlos con commits:
```bash
git commit -m "feat(auth): implement JWT authentication

Closes #12"
```

Esto demuestra trabajo organizado y trazabilidad.

---

## 6. GitHub Actions — CI pipeline

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - run: pip install black isort flake8
      - run: black --check backend/
      - run: isort --check-only backend/
      - run: flake8 backend/

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: test_db
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_pass
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - run: pip install -r backend/requirements.txt
      - run: pytest backend/ --cov=apps --cov-fail-under=75
        env:
          DJANGO_SETTINGS_MODULE: config.settings.test
          DB_NAME: test_db
          DB_USER: test_user
          DB_PASSWORD: test_pass
          DB_HOST: localhost
```

---

## 7. Comandos Git útiles

```bash
# Ver historial limpio
git log --oneline --graph --decorate

# Ver qué cambió en el último commit
git show --stat

# Ver diferencias antes de commitear
git diff

# Deshacer el último commit (manteniendo cambios)
git reset --soft HEAD~1

# Ver ramas locales y remotas
git branch -a

# Limpiar ramas locales ya mergeadas
git branch --merged | grep -v main | grep -v develop | xargs git branch -d

# Stash de cambios temporales
git stash
git stash pop
```

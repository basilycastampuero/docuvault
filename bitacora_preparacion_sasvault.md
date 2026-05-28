# SasVault — Bitácora de Preparación del Proyecto
## Autodocumentación completa: todo lo hecho, por qué se hizo, y el estado actual

> Este documento es tu referencia personal. Explica qué se hizo, por qué, en qué orden,
> y dónde estamos ahora. Léelo cada vez que necesites reorientarte.
> Última actualización: Fase 1 completa (1.1–1.6), Fase 2 plan cerrado, listo para empezar.

---

## ¿Qué es SasVault?

Una plataforma SaaS empresarial de gestión documental y automatización de workflows. Múltiples empresas pueden usar el sistema de forma completamente aislada (multi-tenant). Cada empresa gestiona sus usuarios, documentos, carpetas, permisos, workflows y auditoría.

**No es un CRUD universitario.** Es un proyecto de portafolio diseñado para demostrar arquitectura backend profesional, comparable a productos como Google Drive, DocuWare o SharePoint, pero enfocado en mostrar habilidades técnicas reales.

**Objetivo real del proyecto:** conseguir primer empleo como desarrollador junior destacándose sobre otros candidatos.

---

## Perfil del desarrollador (contexto de las decisiones)

| Aspecto | Detalle |
|--------|---------|
| Nivel Python/Django | Intermedio — proyectos propios, sin producción |
| Tiempo disponible | 7–12 horas por semana |
| Entorno | Windows 11 + WSL2 (Ubuntu) |
| Docker | Experiencia básica — contenedores simples |
| React/Frontend | Features construidas, sin producción |
| GitHub actual | Tareas universitarias, sin convenciones |
| Uso de IA | Pide funciones o bloques específicos a Claude |
| Meta | Primer empleo como junior |

Estas respuestas condicionaron todas las decisiones del plan: el orden de las fases, qué priorizar, qué simplificar y cómo usar Claude Code estratégicamente.

---

# PARTE 1 — Planificación estratégica

## Paso 1: Análisis del spec técnico

Se analizó la especificación técnica del proyecto (`especificacion_proyecto_saas_documental_django.md`) que detalla 51 secciones cubriendo arquitectura, stack, multi-tenancy, módulos, seguridad, testing y deploy.

**Decisiones clave tomadas del spec:**

- **Monolito modular** (no microservicios) — menor complejidad, más mantenible, mejor para un solo desarrollador
- **Shared schema** para multi-tenancy — una sola base PostgreSQL con `organization_id` en cada tabla
- **REST API** con Django REST Framework — estándar de la industria
- **JWT** con access + refresh tokens + blacklist — autenticación profesional
- **RBAC** con 6 roles — control de acceso granular
- **Celery + Redis** para tareas asíncronas — OCR, emails, thumbnails
- **MinIO** en desarrollo, **AWS S3** en producción — nunca guardar binarios en PostgreSQL

## Paso 2: Roadmap de 6 fases (~24 semanas)

Se organizó el desarrollo en fases ordenadas por dependencia. Cada fase debe completarse con tests antes de avanzar a la siguiente.

| Fase | Contenido | Semanas |
|------|-----------|---------|
| **0** | Setup y entorno profesional | 1–2 |
| **1** | Django base + Auth + Organizations + RBAC | 3–6 |
| **2** | Gestión documental: carpetas, uploads, versionado | 7–11 |
| **3** | Auditoría + Workflows + Full Text Search | 12–16 |
| **4** | Celery + OCR + integración IA | 17–19 |
| **5** | Frontend + CI/CD + Deploy + Observabilidad | 20–24 |

**Por qué este orden:**
- Sin auth y multi-tenancy (Fase 1) nada de lo demás tiene base
- Sin documentos (Fase 2) no hay qué auditar ni en qué correr workflows
- El frontend va al final porque el foco es el backend

**Lo que más diferencia en entrevistas para junior:**
1. Multi-tenancy con aislamiento real
2. JWT con refresh token rotation
3. RBAC con permisos granulares
4. Auditoría automática con old/new values
5. Pipeline async con Celery

---

## Paso 3: Estrategia con Claude Code

Se definió cómo usar la IA correctamente en este proyecto, subiendo el nivel de uso actual ("pedir funciones sueltas") a algo más estratégico:

**Flujo correcto:**
1. Tú defines la interfaz: qué debe hacer una función, qué recibe, qué retorna
2. Claude Code implementa el cuerpo
3. Tú revisas y entiendes cada línea antes de hacer commit
4. El código es tuyo para defenderlo en entrevistas

**Por qué esto importa:** si no entiendes el código que genera la IA, no puedes defenderlo en una entrevista técnica. El objetivo es usar Claude Code como acelerador, no como reemplazo del entendimiento.

Adicionalmente, documentar el uso de IA en el README es hoy un **diferenciador positivo**, no negativo.

---

# PARTE 2 — Setup del entorno

## Paso 4: Verificación del estado inicial

Antes de instalar nada, se estableció qué revisar para no romper lo que ya funciona:

```bash
python3 --version       # verificar versión Python
git --version           # verificar Git
docker --version        # verificar Docker
docker compose version  # verificar Docker Compose
```

**Regla:** si algo falla en este paso, detenerse y resolverlo antes de continuar.

---

## Paso 5: Configuración profesional de Git

Git sin usuario configurado no puede hacer commits. Se configura una sola vez de forma global.

```bash
git config --global user.name "Tu Nombre"
git config --global user.email "tu@email.com"
git config --global init.defaultBranch main        # main, no master (estándar actual)
git config --global core.editor "code --wait"      # VS Code como editor de commits
git config --global core.autocrlf input            # evita problemas de line endings WSL/Windows
```

**Por qué `core.autocrlf input`:** Windows usa CRLF como fin de línea, Linux usa LF. Sin esta config, Git en WSL2 puede modificar todos los archivos al hacer checkout, ensuciando el historial.

### Conexión SSH con GitHub

SSH es más seguro que usuario/contraseña y no pide credenciales en cada push.

```bash
ssh-keygen -t ed25519 -C "tu@email.com"   # genera par de claves
eval "$(ssh-agent -s)"                     # inicia el agente
ssh-add ~/.ssh/id_ed25519                  # agrega clave al agente
cat ~/.ssh/id_ed25519.pub                  # imprime la clave pública
```

La clave pública se pega en: GitHub → Settings → SSH and GPG keys → New SSH key.

Verificación: `ssh -T git@github.com` debe responder "Hi TuUsuario! You've successfully authenticated..."

---

## Paso 6: pyenv — manejo profesional de versiones Python

**¿Por qué pyenv si ya tenía Python?** Python instalado directamente en Ubuntu no permite cambiar fácilmente de versión por proyecto, y puede romperse con actualizaciones del sistema. pyenv permite tener múltiples versiones y asignar una específica por proyecto mediante un archivo `.python-version`.

**Instalación:**

```bash
# Dependencias del sistema (pyenv compila Python desde fuente)
sudo apt update && sudo apt install -y \
  make build-essential libssl-dev zlib1g-dev \
  libbz2-dev libreadline-dev libsqlite3-dev wget curl \
  llvm libncursesw5-dev xz-utils tk-dev libxml2-dev \
  libxmlsec1-dev libffi-dev liblzma-dev

# Instalar pyenv
curl https://pyenv.run | bash
```

Se agregan estas líneas al final de `~/.bashrc`:
```bash
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"
```

```bash
source ~/.bashrc          # recargar configuración
pyenv install 3.13.0      # instalar Python 3.13 (tarda ~5 min)
```

En la carpeta del proyecto:
```bash
pyenv local 3.13.0        # crea .python-version — pyenv lo lee automáticamente
```

---

## Paso 7: Crear repositorio en GitHub

**Configuración del repo en GitHub.com:**
- Nombre: `saasvault`
- Descripción: `Enterprise document management SaaS platform built with Django, PostgreSQL, Redis and Celery`
- Visibilidad: **Public** — los recruiters necesitan poder verlo
- NO inicializar con README (se hace manualmente)

```bash
mkdir -p ~/projects
cd ~/projects
git clone git@github.com:TU_USUARIO/saasvault.git
cd saasvault
pyenv local 3.13.0
python --version           # debe mostrar 3.13.0
```

---

## Paso 8: Estructura de carpetas del proyecto

La estructura refleja la arquitectura: monolito modular desacoplado por dominio de negocio.

```bash
mkdir -p \
  backend/apps/authentication \
  backend/apps/organizations \
  backend/apps/documents \
  backend/apps/workflows \
  backend/apps/permissions \
  backend/apps/audit \
  backend/apps/notifications \
  backend/apps/billing \
  backend/apps/search \
  backend/config \
  backend/tests \
  frontend \
  nginx \
  scripts \
  docs
```

**Por qué esta estructura:**
- `backend/apps/` — cada carpeta es un dominio de negocio independiente
- `backend/config/` — settings de Django, urls principales, celery
- `backend/tests/` — factories y fixtures compartidos entre apps
- `frontend/` — React, separado del backend
- `nginx/` — configuración del reverse proxy
- `docs/` — documentación técnica del proyecto
- `scripts/` — scripts de utilidad (deploy, seed data, etc.)

Dentro de cada app habrá esta estructura (se completa en la Fase 1):
```
{app}/
  models/        ← solo persistencia
  services/      ← toda la lógica de negocio
  selectors/     ← todas las consultas complejas
  api/           ← views, serializers, urls
  permissions/   ← clases de permiso DRF
  tasks/         ← tareas Celery
  tests/         ← tests de la app
```

---

## Paso 9: Entorno virtual Python (venv)

Cada proyecto tiene su propio entorno aislado. Las dependencias no se mezclan entre proyectos.

```bash
cd ~/projects/saasvault
python -m venv backend/.venv
source backend/.venv/bin/activate
# El prompt debe mostrar (.venv) cuando está activo
```

**Por qué `.venv` dentro de `backend/` y no en la raíz:** mantiene el entorno virtual cerca del código Python. Está en `.gitignore` — nunca se commitea.

---

## Paso 10: Instalación de dependencias

Se instalaron todas las dependencias del proyecto de una vez, con versiones fijadas. Versiones fijadas garantizan que el proyecto funcione igual en tu máquina, en CI y en producción.

**Dependencias instaladas y para qué sirve cada grupo:**

| Paquete | Para qué |
|---------|----------|
| `django` | Framework principal |
| `djangorestframework` | API REST |
| `djangorestframework-simplejwt` | Autenticación JWT |
| `django-cors-headers` | Permitir requests desde el frontend React |
| `django-filter` | Filtros declarativos en endpoints de lista |
| `django-storages` | Integración con MinIO/S3 |
| `celery` | Cola de tareas asíncronas |
| `redis` | Cliente Python para Redis |
| `django-redis` | Integración Django ↔ Redis para cache |
| `psycopg2-binary` | Driver PostgreSQL para Python |
| `boto3` | SDK de AWS (también funciona con MinIO) |
| `Pillow` | Procesamiento de imágenes |
| `python-magic` | Detectar MIME type real de archivos |
| `pytest` + `pytest-django` | Testing |
| `pytest-cov` | Cobertura de tests |
| `factory-boy` | Factories para tests (reemplaza fixtures) |
| `black` | Formateador automático de código |
| `isort` | Ordenador automático de imports |
| `flake8` | Linter de estilo |
| `pre-commit` | Hooks que corren antes de cada commit |
| `python-decouple` | Manejo de variables de entorno |
| `gunicorn` | Servidor WSGI para producción |
| `whitenoise` | Servir archivos estáticos desde Django |
| `sentry-sdk` | Error tracking en producción |

```bash
pip freeze > backend/requirements.txt   # guardar versiones exactas
```

---

## Paso 11: Variables de entorno

**Regla absoluta:** nunca hardcodear credenciales, URLs ni secrets en el código.

Se crearon dos archivos:
- `backend/.env` — valores reales para desarrollo local. **En `.gitignore`, nunca sube al repo.**
- `backend/.env.example` — template sin valores reales. **Sí sube al repo.** Los otros desarrolladores (o recruiters) copian este archivo y ponen sus propios valores.

Variables configuradas:
```
DJANGO_SECRET_KEY      # clave secreta de Django
DJANGO_DEBUG           # True en dev, False en prod
DJANGO_ALLOWED_HOSTS   # hosts permitidos
DB_NAME / DB_USER / DB_PASSWORD / DB_HOST / DB_PORT  # PostgreSQL
REDIS_URL              # conexión a Redis
MINIO_ENDPOINT / MINIO_ACCESS_KEY / MINIO_SECRET_KEY  # object storage
CELERY_BROKER_URL / CELERY_RESULT_BACKEND              # Celery
SENTRY_DSN             # error tracking (vacío en dev)
```

---

## Paso 12: Docker Compose — servicios de infraestructura

**Decisión de arquitectura:** Docker corre la infraestructura (PostgreSQL, Redis, MinIO), pero Django se corre directamente en el venv durante desarrollo. Esto facilita el debugging: puedes poner `breakpoints`, ver logs directamente, y reiniciar el servidor instantáneamente.

```yaml
# docker-compose.yml — 3 servicios
services:
  postgres:   imagen postgres:16-alpine, puerto 5432
  redis:      imagen redis:7-alpine, puerto 6379
  minio:      imagen minio/minio, puertos 9000 (API) y 9001 (consola web)
```

Cada servicio tiene:
- `healthcheck` — Docker verifica que el servicio esté realmente listo
- `volumes` — los datos persisten aunque el contenedor se reinicie
- `restart: unless-stopped` — se reinicia automáticamente si falla

```bash
docker compose up -d      # levantar en background
docker compose ps         # verificar que los 3 están corriendo
docker compose down       # apagar (los datos se conservan en volumes)
```

**Consola web de MinIO:** http://localhost:9001 (minioadmin / minioadmin)

---

## Paso 13: Configuración de calidad de código

Estos archivos definen las reglas de formato. Hacen que el código se vea profesional y consistente.

### `backend/pyproject.toml`
Configura black (formateador) e isort (ordenador de imports):
- Línea máxima: 88 caracteres (estándar de black)
- Excluir: `.venv/`, `migrations/`
- isort compatible con black (profile = "black")

### `backend/.flake8`
Configura flake8 (linter):
- Excluir `.venv/` y `migrations/`
- Compatible con black (ignora E203, W503)

### `.pre-commit-config.yaml`
Define qué se ejecuta automáticamente antes de cada `git commit`:
1. Limpieza de espacios en blanco al final de líneas
2. Asegurar que los archivos terminen en newline
3. Validar syntax de archivos YAML
4. Bloquear archivos > 5MB
5. Detectar conflictos de merge sin resolver
6. Detectar `print()` de debugging
7. **black** — formatear código Python
8. **isort** — ordenar imports
9. **flake8** — verificar estilo

```bash
pre-commit install          # instalar los hooks en el repo (una sola vez)
pre-commit run --all-files  # correr sobre todos los archivos actuales
```

**Por qué pre-commit:** si tu código no pasa los checks, el commit se rechaza automáticamente. Esto garantiza que cada commit en el historial tiene código limpio. Es lo que hacen los equipos profesionales.

---

## Paso 14: .gitignore profesional

Archivos que **nunca** deben subir al repositorio:
- `.env`, `.env.local`, `.env.production` — credenciales
- `.venv/` — entorno virtual (se recrea con `pip install -r requirements.txt`)
- `__pycache__/`, `*.pyc` — bytecode compilado de Python
- `staticfiles/`, `mediafiles/` — archivos generados, no versionables
- `.coverage`, `.pytest_cache/` — artefactos de testing
- `*.sqlite3` — base de datos local (usamos PostgreSQL)
- `.vscode/`, `.idea/` — configuración personal del editor

---

## Paso 15: README inicial profesional

El README es lo primero que ve un recruiter al entrar al repo. Se creó desde el principio con:
- Descripción del proyecto
- Tech stack completo
- Diagrama de arquitectura en texto
- Key features (multi-tenancy, RBAC, versionado, auditoría, FTS)
- Instrucciones para correr localmente (claras y completas)
- Comandos de desarrollo
- Estado actual del proyecto

---

## Paso 16: Primer commit

El primer commit agrupa todo el setup con un mensaje descriptivo siguiendo Conventional Commits:

```bash
git add .
git commit -m "chore: initial project setup and environment configuration

- Configure pyenv with Python 3.13
- Add Docker Compose for PostgreSQL, Redis and MinIO
- Set up pre-commit hooks (black, isort, flake8)
- Add professional .gitignore
- Create modular app structure under backend/apps/
- Add README with architecture overview"

git push -u origin main
```

---

# PARTE 3 — Documentación pre-desarrollo para Claude Code

## Paso 17: Paquete de documentación técnica

Se generaron 5 documentos para contextualizar a Claude Code en cada sesión de desarrollo. La clave es que Claude Code los puede leer al inicio de cada sesión y trabajar con criterio consistente sin necesidad de repetir instrucciones.

### CLAUDE.md (el más importante)

**Ubicación:** raíz del proyecto `/CLAUDE.md`

**Por qué existe:** Claude Code lee este archivo automáticamente al abrir el proyecto. Es el "briefing" completo del proyecto. Sin él, Claude Code toma decisiones por defecto que pueden no alinearse con la arquitectura.

**Contenido (19 secciones):**
1. Qué es DocuVault y su objetivo
2. Arquitectura — monolito modular, separación services/selectors/api
3. Stack tecnológico completo con versiones
4. Multi-tenancy — regla crítica de `organization_id` en todo modelo
5. BaseModel — del que heredan TODOS los modelos
6. Soft delete — qué entidades lo usan y cómo
7. Convenciones de base de datos — naming, índices, JSONB
8. API REST — URLs, formato de respuesta, códigos HTTP
9. Auth y permisos — JWT, RBAC, permission classes
10. Auditoría — qué eventos registrar y desde dónde
11. Variables de entorno — uso de python-decouple
12. Testing — pytest, factory-boy, qué testear siempre
13. Celery — patrón de tasks que llaman services
14. Settings en capas — base/development/test/production
15. Reglas de estilo — black, type hints, docstrings
16. Git — conventional commits, estrategia de ramas
17. **Lo que NUNCA hacer** — lista explícita de antipatrones prohibidos
18. Estado actual del proyecto — checklist de lo completado
19. Cómo correr el proyecto localmente

### docs/phase-plan.md

Plan detallado de desarrollo fase por fase. Cada subtarea especifica:
- Qué modelos crear (con todos los campos)
- Qué servicios y selectores implementar
- Qué endpoints exponer
- Qué tests escribir
- Reglas de negocio específicas

Claude Code puede leer "Fase 1.4 - JWT" y saber exactamente qué implementar.

### docs/coding-patterns.md

Patrones de código con ejemplos reales (no pseudocódigo):
- Service completo con `@transaction.atomic`, validación, storage, Celery, auditoría
- Selector con filtros, tenant isolation, `select_related`
- View que solo orquesta (no tiene lógica de negocio)
- BaseModel con SoftDeleteManager
- Permission classes (IsOrganizationMember, HasRole, IsSuperAdmin)
- Tests con factory-boy — happy path, error cases, tenant isolation
- Factories para Organization, User, Folder, Document
- Serializers de lectura vs escritura separados
- Celery tasks con reintentos

### docs/api-conventions.md

Referencia REST completa:
- Estructura de todas las URLs del proyecto
- Métodos HTTP y cuándo usar cada uno
- Formato de respuesta con envelope `{ "data": ... }` y `{ "error": ... }`
- Tabla de códigos HTTP por situación
- Paginación — parámetros, defaults, máximos
- Filtros con django-filter
- Flujo completo de tokens JWT
- Cómo hacer uploads multipart
- Cómo funcionan las presigned URLs para descarga
- Documentación automática con drf-spectacular (Swagger)

### docs/database-conventions.md

Convenciones de base de datos:
- Por qué PostgreSQL (y no SQLite ni MySQL)
- Naming conventions para tablas, campos e índices
- Esquema completo de las tablas principales con tipos de dato y constraints
- Uso de JSONB — cuándo y cómo
- Full Text Search — `SearchVectorField`, signal de actualización, búsqueda con ranking
- Transacciones con `@transaction.atomic`
- Optimización: `select_related`, `prefetch_related`, `EXPLAIN ANALYZE`
- Convenciones de migraciones

### docs/git-workflow.md

Flujo de trabajo Git:
- Estrategia de ramas: main / develop / feature/* / fix/* / chore/*
- Flujo diario paso a paso
- Conventional Commits — tipos, scopes, ejemplos correctos e incorrectos
- Regla de tamaño de commits (uno por cambio lógico)
- Qué nunca commitear
- Buenas prácticas de GitHub para portafolio (badges, issues, README)
- GitHub Actions CI pipeline completo (lint + tests)
- Comandos Git útiles del día a día

---

# Resumen del estado actual

## ✅ Completado

| Qué | Dónde |
|-----|-------|
| Roadmap de 6 fases (~24 semanas) | Este documento |
| Decisiones de arquitectura | `CLAUDE.md` |
| Configuración de Git y SSH con GitHub | WSL2 local |
| pyenv con Python 3.13 | WSL2 local |
| Repositorio `saasvault` en GitHub | github.com/TU_USUARIO/saasvault |
| Estructura de carpetas `backend/apps/` | Repo |
| Entorno virtual `.venv` | `backend/.venv/` |
| Dependencias instaladas | `backend/requirements.txt` |
| Variables de entorno | `backend/.env` + `backend/.env.example` |
| Docker Compose (PostgreSQL + Redis + MinIO) | `docker-compose.yml` |
| Calidad de código (black, isort, flake8) | `pyproject.toml`, `.flake8` |
| Pre-commit hooks | `.pre-commit-config.yaml` |
| `.gitignore` profesional | `.gitignore` |
| README inicial | `README.md` |
| Primer commit | git log |
| CLAUDE.md (contexto para Claude Code) | `CLAUDE.md` |
| Plan de fases detallado | `docs/phase-plan.md` |
| Patrones de código con ejemplos | `docs/coding-patterns.md` |
| Convenciones REST | `docs/api-conventions.md` |
| Convenciones de base de datos | `docs/database-conventions.md` |
| Flujo de trabajo Git | `docs/git-workflow.md` |

---

# PARTE 4 — Desarrollo: Fase 1 completada y Fase 2 planificada

## Sesión de desarrollo: Phase 1 (1.1–1.6) y correcciones

### Recapitulación de Phase 1 — Autenticación + Organizaciones + RBAC

**Fase 1.1 — Django base + settings en 4 capas**
- Settings en `base.py` (común), `development.py`, `test.py` (PostgreSQL real), `production.py`
- Configuración de PostgreSQL via python-decouple (variables de entorno)
- Django REST Framework + simplejwt + drf-spectacular integrados
- Configuración de logging estructurado (JSON)

**Fase 1.2 — Core app: BaseModel y utilidades**
- `BaseModel` con UUID pk, `created_at`, `updated_at`, `deleted_at` (con `db_index=True` — crítico para soft delete)
- `SoftDeleteManager` que filtra automáticamente `deleted_at IS NULL`
- `AllObjectsManager` para acceder a registros eliminados (admin, auditoría)
- `ApplicationError` hierarchy (`PermissionDenied`, `NotFound`, `ValidationError` con `details`, `ConflictError`)
- Custom exception handler que transforma todo a envelope `{"error": {"code", "message", "details"}}`
- `StandardPagination` que retorna `{"data": [...], "meta": {count, page, page_size, total_pages, next, previous}}`

**Fase 1.3 — Organizations app**
- Modelo `Organization` con `name`, `slug` (unique), `is_active`, `settings` (JSONB)
- `OrganizationService` (create, update, deactivate)
- `OrganizationSelector` (get_by_id, get_by_slug)
- `OrganizationViewSet` (solo SUPER_ADMIN puede crear orgs)
- Tests: aislamiento de tenant, permisos

**Fase 1.4 — Authentication app: Custom User + JWT**
- `UserRole` TextChoices: `super_admin`, `org_admin`, `supervisor`, `editor`, `viewer`, `auditor`
- `User` model (hereda `AbstractBaseUser`, no `AbstractUser`)
  - `organization` FK nullable (SUPER_ADMIN no pertenece a org)
  - `role` campo con choices
  - Custom `UserManager` que extiende `BaseUserManager` + filtra soft-deleted
  - `AllUsersManager` para admin
- JWT con claims personalizados: `organization_id`, `role`, `email` en ambos refresh y access tokens
- Token blacklist en logout (via `simplejwt.token_blacklist`)
- Rotating refresh tokens
- `OrganizationTenantMiddleware`: inyecta `request.organization` en cada request autenticado (decodifica Bearer token, extrae org_id, fetchea Organization)
- Endpoints: `/api/v1/auth/login/`, `/api/v1/auth/refresh/`, `/api/v1/auth/logout/`, `/api/v1/auth/me/`
- Services: `auth_service.login()` (verificación manual en 3 pasos para diferenciar "credenciales incorrectas" de "cuenta desactivada"), `logout()`, `refresh_token_pair()`
- User management endpoints: listar usuarios de org, crear, actualizar, desactivar (soft delete = `is_active=False`, no `deleted_at`)

**Fase 1.5 — Permissions app: RBAC**
- `IsOrganizationMember`: verifica `request.user.organization == request.organization`
- `HasRole(*roles)`: class factory que retorna una clase (permite `permission_classes = [HasRole(EDITOR, ORG_ADMIN)]`)
- Aliases: `IsOrgAdmin`, `IsSuperAdmin`
- Tests: cada combinación de usuario/rol/org

**Fase 1.6 — User management endpoints**
- `UserListCreateView` (GET: listar usuarios de la org, POST: crear usuario — requiere OrgAdmin)
- `UserDetailView` (GET: detalle, PATCH: actualizar, DELETE: desactivar — requiere OrgAdmin)
- `UserSelector` con tenant isolation
- Serializers separados para lectura vs escritura

**Tests y Coverage:** 167 tests pasando, 99% cobertura.

**drf-spectacular:** Schema con 0 errores, 0 warnings. Endpoints Swagger en `/api/docs/`, Redoc en `/api/redoc/`.

### Correcciones identificadas y aplicadas

Después de completar Phase 1, se revisaron todos los archivos `.md` para alineación con el código real. Se encontraron y corrigieron 6 desajustes:

**1. `db_index=True` en `BaseModel.deleted_at`** (commit: `54b0319`)
- CLAUDE.md §6 lo documentaba pero el modelo no lo tenía
- Se añadió al campo; se generaron migraciones en `authentication` y `organizations`
- Impacto: queries de soft delete (`WHERE deleted_at IS NULL`) usan índice en lugar de full table scan

**2. `StandardPagination` con formato meta completo** (commit: `2e5184f`)
- CLAUDE.md §7 especificaba formato pero la paginación no estaba implementada
- Se creó `apps/core/pagination.py` con envelope `{data: [...], meta: {count, page, page_size, total_pages, next, previous}}`
- Impacto: todos los endpoints de lista retornan el envelope consistente

**3. `drf-spectacular` instalado y configurado** (commit: `2e5184f`)
- `base.py` referenciaba schema pero paquete no estaba en `requirements.txt`, views sin decoradores
- Se instaló `drf-spectacular==0.27.2`, se añadieron endpoints `/api/schema/`, `/api/docs/`, `/api/redoc/`
- Se decoraron todas las views con `@extend_schema`
- Impacto: documentación automática e interactiva de API en Swagger/Redoc

**4. `README.md` actualizado** (commit: `e6db851`)
- Nombre "DocuVault" → "SasVault", arquitectura desactualizada, faltaban features
- Se reescribió con apps actuales, custom JWT claims, 6 roles RBAC, estado Phase 1 complete

**5. `docs/database-conventions.md` corregido** (commit: `e6db851`)
- Nombres de tablas erróneos (`organizations_organization` → `organizations`, `auth_user` → `users`)
- Schema del User desactualizado (faltaban `role`, `organization_id`)
- Se corrigió todo; se marcó CLAUDE.md §6 como fuente autoritativa

**6. `docs/git-workflow.md` actualizado** (commit: `e6db851`)
- Nombre "DocuVault" → "SasVault"
- Scope en commits de obligatorio a recomendado-pero-opcional (para commits transversales como "feat: implement authentication app (Phase 1.4)")

### Correcciones adicionales en esta sesión (commits: `dae4199`, `d373fe4`)

**Security fix:** `backend/.env` estaba trackeado en git desde el commit inicial (con placeholders genéricos). Working copy tenía credenciales dev (`minioadmin`/`minioadmin`). Se hizo `git rm --cached backend/.env` para dejar de trackearlo (el archivo sigue en disco para dev local).

**Sync con código real:**
- `docs/coding-patterns.md`: reemplazado `DocuVaultException` con `ApplicationError` real
- `docs/coding-patterns.md`: actualizado exception handler con `ConflictError`, `ValidationError.details`, DRF passthrough
- `docs/coding-patterns.md`: bug fix en `BaseModel.soft_delete()` — `update_fields=["deleted_at", "updated_at"]` (sin `updated_at`, `auto_now=True` no se dispara)

**Rename DocuVault → SasVault:** en headers de `api-conventions.md`, `coding-patterns.md`, `phase-plan.md`.

**CLAUDE.md §17 actualizado:** estado de "Fase 0" a "Fase 2 próxima a iniciar", Fase 1 completa, 167 tests / 99% coverage, decisiones Phase 2 documentadas.

**Memory updated:** `current_phase.md` reescrita con Phase 1 detalle y 5 decisiones locked de Phase 2.

---

## Fase 2: Plan cerrado con 5 decisiones de diseño

### Decisiones críticas (NO re-discutir durante implementación)

1. **AuditLog mínimo en Fase 2.1** — Se construye el modelo + `audit_service.log()` ahora. Endpoints, filtros y permisos de lectura se difieren a Fase 3.1. Razón: CLAUDE.md §9 obliga a registrar todo evento crítico desde los services — no se puede dejar el hook vacío.

2. **Storage tests mockeados primero** — `StorageService` tests unitarios con `boto3.client` mockeado. Integración real contra MinIO test bucket (`saasvault-test`) viene después. Razón: más rápido iterar con mocks; integración real cuando hay CI y el código esté estable.

3. **Status approval deferred a Phase 3** — `Document.status` tiene 5 valores enum, pero Phase 2 services SOLO permiten draft ↔ under_review manuales. Transiciones a `approved`/`rejected` SOLO vía `WorkflowExecution` (Fase 3.2) — cambio a `approved` directo es rechazado con `ConflictError`. Razón: separar lógica de gestión documental (Phase 2) de workflows (Phase 3.2).

4. **OCR task stub** — `process_ocr.delay()` como Celery task vacía invocada vía `transaction.on_commit()` desde `DocumentService.create_document`. Cuerpo real en Fase 4.2. Razón: infraestructura lista; comportamiento a rellenar cuando Celery esté configurado.

5. **`AuditLog` usa `BigAutoField`, NO hereda `BaseModel`** — Logs inmutables (sin `updated_at`, sin `deleted_at`). Se escribe muchísimo, se lee por orden cronológico. BigAutoField indexado supera UUID v4 para este caso. Razón: performance en escritura/lectura secuencial de auditoría.

### Plan de Fase 2 — Estructura y estimación

**Subfases (en orden):**
- **2.0** Pre-flight: crear app skeletons, registrar en INSTALLED_APPS, settings
- **2.1** AuditLog model + service (4 tests estimados)
- **2.2** Folder/Document/DocumentVersion models con índices (15 tests)
- **2.3** FileValidator + StorageService (14 tests — 8 validator, 6 storage mocked)
- **2.4** FolderService/Selector (18 tests — 12 service, 6 selector)
- **2.5** DocumentService/Selector + OCR task stub (26 tests — 18 service, 8 selector)
- **2.6** REST endpoints (27 tests — 12 folders, 15 documents)

**Total estimado:** ~104 tests para mantener ≥95% coverage.

**Commits anticipados:** 10 commits separados por lógica (model → service → selector → api).

**Duración estimada:** 18–21 horas de trabajo efectivo (~3 semanas calendario).

### Estado actual después de Phase 1

| Métrica | Valor |
|---------|-------|
| Tests | 167 pasando |
| Cobertura | 99% |
| Schema OpenAPI | 0 errors / 0 warnings |
| Branch | `develop`, 14 commits ahead de origin |
| Apps completadas | auth + organizations + permissions + core + audit (skeleton) + documents (skeleton) |
| Endpoints funcionales | 14 endpoints (6 auth + 4 organizations + 4 user management) |
| Features funcionales | JWT con claims custom, multi-tenancy, RBAC 6 roles, soft delete, auditoría hooks ready |

### Próximos pasos

1. Commitear cambios (HECHO: `dae4199`, `d373fe4`)
2. Iniciar Fase 2.0: crear app skeletons
3. Implementar Fase 2.1–2.6 según el plan en `docs/phase-plan.md`

---

## 🔜 Próximo paso: Fase 2.0 — Pre-flight

Cuando estés listo, la primera tarea de Fase 2:

```bash
# 1. Verificar que todo funciona
source backend/.venv/bin/activate
docker compose up -d
docker compose ps

# 2. Crear apps skeletons
cd backend
python manage.py startapp audit apps/audit
python manage.py startapp documents apps/documents

# 3. Actualizar apps.py en ambas y INSTALLED_APPS en base.py
# (El plan en docs/phase-plan.md Fase 2.0 detalla esto)

# 4. Crear manage.py init_storage command
# 5. Primer commit: chore(documents,audit): create app skeletons
```

El plan detallado para cada subfase está en `docs/phase-plan.md` Fase 2.

---

## Comandos del día a día

```bash
# Activar entorno virtual
source backend/.venv/bin/activate

# Levantar infraestructura
docker compose up -d

# Apagar infraestructura (datos se conservan)
docker compose down

# Ver estado de los contenedores
docker compose ps

# Ver logs de un servicio
docker compose logs -f postgres

# Correr Django
cd backend && python manage.py runserver

# Correr tests
cd backend && pytest

# Formatear código manualmente
cd backend && black . && isort .

# Ver historial de commits
git log --oneline --graph --decorate

# Crear rama para nueva feature
git checkout develop && git pull origin develop
git checkout -b feature/nombre-de-la-feature

# Hacer commit con formato correcto
git commit -m "feat(scope): descripción en imperativo, sin punto final"
```

---

## Referencia rápida de archivos críticos

| Archivo | Para qué revisarlo |
|---------|-------------------|
| `CLAUDE.md` | Contexto completo del proyecto para Claude Code |
| `docs/phase-plan.md` | Qué construir en cada fase |
| `docs/coding-patterns.md` | Cómo debe verse el código |
| `docs/api-conventions.md` | Diseño de endpoints |
| `docs/database-conventions.md` | Modelos, índices, migraciones |
| `docs/git-workflow.md` | Commits, ramas, CI/CD |
| `backend/.env.example` | Qué variables de entorno necesita el proyecto |
| `backend/requirements.txt` | Dependencias Python con versiones fijadas |
| `docker-compose.yml` | Servicios de infraestructura local |
| `.pre-commit-config.yaml` | Checks automáticos antes de cada commit |

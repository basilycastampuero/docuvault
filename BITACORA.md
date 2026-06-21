# SasVault — Bitácora del Proyecto
## Diario de desarrollo: el camino, las decisiones, las complicaciones y lo aprendido

> Este documento está escrito **para humanos** (vos, un recruiter, tu yo del futuro).
> Cuenta la historia del proyecto en lenguaje natural: qué se construyó, qué se complicó,
> qué se decidió y por qué. No es una referencia técnica exhaustiva — para eso están
> `CLAUDE.md`, `docs/phase-plan.md` y los demás `.md` de `docs/`, escritos para que Claude
> Code y vos tengan contexto preciso al programar.
>
> **Cómo leerlo:** las Partes 1–4 son el setup y la Fase 1 (historia ya estable). La
> Parte 5 (al final) es el diario vivo de las Fases 2 y 3 — empezá por ahí si querés saber
> dónde estamos hoy.
>
> Última actualización: **Fase 5.3 completa** (2026-06-21). ~526 tests backend + 163 frontend.
> Próximo hito: Fase 5.4 (CI/CD GitHub Actions: lint+test+build en paralelo, coverage gate 95%).

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

---

# PARTE 5 — Diario vivo: Fases 2, 3 y 4

> Todo lo de arriba es el setup y la Fase 1, que quedaron estables hace tiempo. Desde acá
> empieza el diario real de construcción del producto: la gestión documental (Fase 2), la
> capa de auditoría + workflows + búsqueda (Fase 3) y el procesamiento asíncrono con OCR
> (Fase 4). Escrito en lenguaje llano, con las complicaciones tal como pasaron.

## Mapa rápido de dónde estamos (2026-06-21)

| Fase | Qué es | Estado |
|------|--------|--------|
| 2 | Documentos: carpetas, upload a MinIO, versionado, validación de archivos, auditoría | ✅ |
| 3.1 | API de lectura de auditoría (quién hizo qué, con filtros y permisos) | ✅ |
| 3.2 | Motor de workflows (plantillas de aprobación, ejecuciones, pasos) | ✅ |
| 3.3 | Búsqueda full-text con PostgreSQL (sin Elasticsearch) | ✅ |
| — | Auditoría de toda la Fase 3 con correcciones | ✅ |
| 4.0 | Pre-flight: dependencias OCR, descarga de blobs, settings de Celery/OCR | ✅ |
| 4.1 | Endurecimiento de Celery: reintentos inteligentes e idempotencia | ✅ |
| 4.2 | Pipeline OCR real (PDF + imágenes → texto buscable) | ✅ |
| 4.3 | Limpieza periódica de archivos huérfanos en MinIO | ✅ |
| 4.4 | Análisis con IA (Claude API) — opcional | ✅ |
| 5.6 | Observabilidad: health check, Sentry, JSON logging (backend) | ✅ |
| 5.1 | Frontend: scaffold React+TS+Vite + auth (login, tokens, layout) | ✅ |
| 5.7 | Notificaciones email por workflow (nueva app `notifications`) | ✅ |
| — | Auditoría completa de Fase 5 (5.1 + 5.7) con correcciones | ✅ |
| 5.2 | Frontend gestión documental: carpetas, upload, OCR badge, búsqueda | ✅ |
| 5.3 | Frontend workflows + auditoría + panel IA opcional | ✅ |

**~526 tests backend + 163 tests frontend (2026-06-21). Cobertura backend: 95%.** Los tests
backend corren contra PostgreSQL real; si fallan con "connection refused" es que falta
`docker compose up -d`, no es un bug del código.

---

## Fase 2 — Gestión documental (el corazón del producto)

Esta fase fue la más larga y la que más se parece a "construir un producto de verdad".
La idea: que una organización pueda subir archivos, organizarlos en carpetas, versionarlos
y que todo quede auditado.

**Lo que se construyó, en cristiano:**
- **Carpetas jerárquicas** con detección de ciclos (no podés meter una carpeta dentro de
  sí misma ni de sus descendientes). Suena trivial hasta que lo implementás bien.
- **Upload de archivos a MinIO** (el "S3 local"). El archivo nunca toca PostgreSQL — la DB
  solo guarda metadata y la ruta del blob. Esto es lo correcto y lo que se espera en
  producción.
- **Validación de archivos por "magic bytes"**, no por extensión. Si alguien renombra un
  `.exe` a `.pdf`, el sistema lo detecta leyendo los primeros bytes reales del archivo
  (con `python-magic`). Más checksum SHA-256 y límite de 50 MB.
- **Versionado**: cada vez que subís una versión nueva, la anterior se preserva. No hay
  sobrescritura destructiva.
- **Auditoría desde el día uno**: cada create/update/delete genera un registro inmutable.

**Complicaciones reales de esta fase:**
- `python-magic` necesita la librería `libmagic1` del sistema operativo. En WSL hubo que
  instalarla aparte — no basta con `pip install`.
- boto3 contra MinIO necesita `signature_version="s3v4"` para que las URLs prefirmadas
  (presigned URLs) funcionen. Sin eso, las descargas fallan de formas confusas.
- Decidimos **mockear** los tests de almacenamiento (no pegarle a MinIO de verdad todavía).
  Más rápido para iterar; la integración real se deja para Fase 4 cuando haya CI.
- Quedó una **deuda conocida y documentada**: al borrar (soft-delete) un documento, el blob
  en MinIO NO se elimina. Eso lo limpia una tarea periódica en Fase 4
  (`cleanup_orphan_blobs`). Preferimos dejarlo anotado que improvisar.

**Decisión que marcó el resto del proyecto:** `Document.status` tiene 5 estados posibles
(draft, under_review, approved, rejected, archived), pero en Fase 2 **solo** permitimos las
transiciones manuales `draft ↔ under_review`. Llegar a `approved`/`rejected` quedó
bloqueado a propósito — eso solo puede pasar por un workflow (Fase 3.2). Separar "gestión de
archivos" de "lógica de aprobación" mantuvo cada parte limpia.

---

## Fase 3 — Auditoría, workflows y búsqueda

### 3.1 — Leer la auditoría (la parte fácil de una idea importante)

El modelo de auditoría ya existía desde Fase 2 (se escribía en cada evento). Lo que faltaba
era **poder leerla**: un endpoint `GET /api/v1/audit-logs/` con filtros (por acción, por
entidad, por usuario, por rango de fechas) y permisos (solo auditor/admin pueden ver).

Dos decisiones que vale la pena recordar:
- **Leer la auditoría NO genera un registro de auditoría.** Si lo hiciera, cada lectura
  crearía un log, que a su vez se podría leer... ruido infinito y una tabla que crece sin
  control. La lectura de logs simplemente no se audita.
- La API es **estrictamente de solo lectura**. No hay POST/PATCH/DELETE — un log de
  auditoría que se pudiera editar o borrar no serviría para nada. Cualquier intento de
  escritura devuelve 405.

### 3.2 — El motor de workflows (la parte difícil e interesante)

Acá es donde el proyecto deja de ser "un Drive" y se vuelve "un DocuWare". La idea: una
organización define **plantillas de aprobación** (ej: "Revisión legal" → paso 1 lo aprueba
un supervisor, paso 2 lo aprueba un admin, y recién ahí el documento queda aprobado). Cada
documento puede correr una de esas plantillas.

**Las piezas:** plantillas (`WorkflowTemplate`) con pasos ordenados (`WorkflowStep`),
ejecuciones en curso (`WorkflowExecution`) y una bitácora de cada acción
(`WorkflowStepLog`). El servicio sabe avanzar paso a paso: aprobar lleva al siguiente paso
(o completa el workflow si era el final), rechazar lo corta, comentar solo deja una nota.

**La conexión clave con Fase 2:** el workflow es la ÚNICA vía privilegiada para llevar un
documento a `approved`/`rejected`. Escribe el status directamente, saltándose el guard
manual de Fase 2 (que sigue rechazando esas transiciones por la API normal). Esto se
documentó con un comentario en el código para que nadie lo "arregle" por error.

**Regla de negocio crítica:** un documento solo puede tener **una** ejecución activa a la
vez. No tiene sentido aprobar el mismo documento por dos flujos en paralelo. (Spoiler: esta
regla tenía un bug sutil que encontramos después, en la auditoría — ver más abajo).

### 3.3 — Búsqueda full-text (PostgreSQL, no Elasticsearch)

Mucha gente metería Elasticsearch acá. Decisión deliberada: **no**. PostgreSQL tiene
búsqueda full-text nativa muy capaz, y meter Elasticsearch significaría otro servicio que
mantener, sincronizar y desplegar. Para el tamaño de este proyecto, es complejidad
innecesaria — y saber cuándo NO añadir una tecnología es criterio de ingeniería.

**Cómo funciona:** cada documento tiene una columna `search_vector` (un `tsvector` de
Postgres) que se arma combinando su nombre, descripción, tags y contenido OCR, cada uno con
un **peso de relevancia** distinto (el nombre pesa más que el contenido OCR). Un índice GIN
hace que la búsqueda sea rápida. El endpoint `GET /api/v1/search/?q=contrato` devuelve los
resultados **ordenados por relevancia**.

**Complicaciones reales de esta fase:**
- **El guion bajo rompe la búsqueda.** PostgreSQL tokeniza `"annual_report.pdf"` como UN
  solo token (`annual_report`), así que buscar "annual" no lo encontraba. Los tests
  fallaban hasta que entendimos esto y usamos nombres con espacios naturales. Lección: el
  tokenizador de FTS no es magia, hay que entender cómo parte el texto.
- **Idioma.** Usamos `config="simple"` (sin stemming) a propósito, porque el sistema es
  multi-tenant y puede mezclar español e inglés. El trade-off honesto: "contratos" no
  matchea "contrato". Se puede afinar por-tenant en el futuro.
- **Tags son un array**, y PostgreSQL no deja meter un array directo en el vector de
  búsqueda. Hubo que unirlos a texto (`" ".join(tags)`) antes de indexarlos.
- **Documentos viejos.** El vector se llena con un signal al guardar, pero los documentos
  creados antes de existir el signal quedarían invisibles. Se escribió una migración de
  "backfill" que los reindexó a todos.

---

## La auditoría de Fase 3 (revisar el propio trabajo)

Antes de cerrar la fase, en vez de hacer commit y seguir, paramos a **auditar todo lo
construido en Fase 3** contra las reglas del proyecto. Esto encontró 3 problemas reales que
ya están corregidos. Vale documentarlos porque son justo el tipo de cosa que diferencia en
una entrevista técnica.

**1. 🔴 Race condition en "una sola ejecución activa por documento" (bug de verdad).**
La regla se aplicaba con un check del estilo "¿ya hay una ejecución activa? si no, creá
una". El problema clásico: si dos requests llegan **al mismo tiempo**, ambos preguntan
"¿hay una activa?", ambos reciben "no", y ambos crean una → terminás con dos ejecuciones
activas, justo lo que la regla prohibía. No había nada en la base de datos que lo impidiera.
**La corrección** tiene dos capas: (a) un constraint único parcial en PostgreSQL que hace
físicamente imposible tener dos ejecuciones activas para el mismo documento, y (b) el código
ahora atrapa el error de la base de datos y devuelve un 409 limpio en vez de reventar con un
500. El check rápido se queda como atajo amigable. *Entender y resolver race conditions a
nivel de DB, no solo en código, es exactamente lo que se evalúa en roles senior.*

**2. 🟡 Doble-avance en workflows.** Parecido pero más leve: dos aprobadores actuando sobre
la misma ejecución en el mismo instante podían avanzarla dos veces. Se corrigió bloqueando
la fila de la ejecución (`SELECT ... FOR UPDATE`) mientras se procesa. Detalle técnico que
costó un rato: hubo que usar `of=("self",)` porque la consulta hace un LEFT JOIN con el paso
actual (que puede ser nulo), y PostgreSQL no deja bloquear el lado nullable de un join.

**3. 🟡 Paginación inconsistente.** Dos listados de workflows devolvían todos los resultados
sin paginar, mientras el resto de la API sí paginaba. Inconsistencia de diseño — se unificó.
Pequeño, pero "consistencia" es justo lo que se mira en "diseño de API profesional".

**De yapa**, durante la búsqueda se afinó el signal que reconstruye el `search_vector`: antes
se reconstruía en CADA guardado de documento (incluso al cambiar solo el status), lo cual es
desperdicio de escrituras. Ahora solo se reconstruye si cambió un campo de texto.

**La lección de meta-nivel:** auditar tu propio trabajo antes de darlo por terminado
encuentra cosas que el "happy path" de los tests no toca — sobre todo concurrencia. Vale la
pena el rato extra.

---

## Fase 4 — Procesamiento asíncrono (Celery + OCR)

La pregunta que responde esta fase: hasta ahora un documento se podía buscar **por su
nombre**, pero no **por lo que dice adentro**. Si subís un PDF escaneado llamado
`escaneo_001.pdf`, buscar "contrato de arrendamiento" no lo encuentra aunque esas palabras
estén dentro. El OCR (reconocimiento óptico de caracteres) extrae el texto de la imagen, y
ese texto se vuelve buscable. Pero el OCR es lento: no podés hacerlo mientras el usuario
espera la respuesta del upload. Por eso entra **Celery**: el upload responde al instante y el
OCR corre después, en segundo plano, en un proceso aparte (un "worker").

La infraestructura de Celery ya existía desde fases anteriores (el broker Redis, la config),
pero estaba "vacía": cableada pero sin hacer nada real. Esta fase la pone a trabajar. Decidí
ir **por partes**, con un commit lógico por pieza, porque mezclar "instalar dependencias",
"lógica de reintentos" y "OCR real" en un solo commit gigante es justo lo que la guía de Git
del proyecto prohíbe.

### 4.0 — Pre-flight: preparar el terreno

Antes de escribir nada de OCR, hay que tener las herramientas instaladas. Acá apareció el
**gotcha más típico de OCR en Python**: Tesseract (el motor de OCR) y Poppler (para leer
PDFs) **no son paquetes de Python** — son programas del sistema operativo. Se instalan con
`apt`, no con `pip`. Los wrappers de Python (`pytesseract`, `pdf2image`) son solo un puente:
si el programa de sistema no está, fallan con un error confuso. Documenté esto en
`.env.example` y en el plan para que no sea una sorpresa al desplegar en producción.

Otra pieza que faltaba: el `StorageService` sabía **subir** archivos a MinIO pero no
**descargarlos**. El OCR necesita leer el archivo de vuelta para procesarlo, así que agregué
`download_file()`. Pieza chica pero es la que conecta el almacenamiento con el OCR.

El resto fueron *settings*: el idioma del OCR (`spa+eng`, porque el corpus mezcla español e
inglés y no quiero asumir un solo idioma), la resolución a la que se convierte un PDF a
imagen (más resolución = más preciso pero más lento), y la política de reintentos. Todo por
variable de entorno, nunca hardcodeado.

**Cómo verifiqué que la base funcionaba (sin haber escrito OCR todavía):** levanté un worker
de Celery **de verdad** (no el modo de tests), le mandé la tarea stub, y confirmé en los logs
que el worker la recibió y la ejecutó. Esto separa dos preguntas que conviene no mezclar:
"¿la fontanería async funciona?" (4.0) y "¿mi lógica de OCR funciona?" (4.2). Si algo falla
más adelante, ya sé que no es Celery.

### 4.1 — Reintentos inteligentes: no todos los errores son iguales

Esta sub-fase es chica en código pero es **la decisión de diseño más interesante de la
fase**. La idea: cuando una tarea en segundo plano falla, ¿hay que reintentarla?

Depende del **tipo** de error, y tratarlos a todos igual es un error de novato:

- **Error transitorio:** MinIO tardó demasiado, Redis estaba ocupado un instante. Esto es
  pasajero — reintentar en unos segundos probablemente funcione. **Sí reintentar.**
- **Error permanente:** el PDF está corrupto, el documento fue borrado. Esto no se va a
  arreglar solo — reintentarlo 3 veces es desperdiciar el worker haciendo lo mismo una y
  otra vez (un "retry-loop"). **No reintentar; marcar como fallido y seguir.**

La solución fue crear una excepción propia, `TransientError`, que significa exactamente "esto
es recuperable, vale la pena reintentar". La tarea se configura para reintentar **solo** ante
ese error específico; cualquier otra excepción se propaga y la tarea queda fallida sin
reintentos. Además, los reintentos usan *backoff exponencial* (espera 1s, luego 2s, luego
4s…) en vez de martillar el recurso que ya estaba caído.

Un detalle de diseño que me gustó: `TransientError` **no** hereda de la excepción base del
proyecto (la que se convierte en respuestas HTTP de error). ¿Por qué? Porque este error
nunca llega al usuario por HTTP — vive enteramente dentro del worker, como una señal interna.
Mezclarla con las excepciones de la API habría sido conceptualmente sucio. Hay un test que
"congela" esa decisión: verifica que el manejador de errores HTTP la ignora.

La tarea quedó **fina**: no tiene lógica, solo busca el documento y delega en un service
(`ocr_service`), respetando la regla del proyecto de que las tareas Celery no llevan lógica
de negocio. El `ocr_service` por ahora es un stub; su cuerpo real es la 4.2.

**Una complicación al testear:** en los tests, Celery corre las tareas de forma síncrona
(modo "eager"), y en ese modo **no existe el reintento de verdad** — no hay un broker que
reprograme la tarea, así que `retry()` lanza una excepción especial (`Retry`) en lugar de
volver a ejecutar. Al principio mis tests asumían que contaría los reintentos reales y
fallaron. La lección: en modo eager no se puede testear "cuántas veces reintentó", pero sí se
puede testear lo que realmente importa — **la política**: que un `TransientError` se enrute
por el mecanismo de reintento (lanza `Retry`), mientras que un error permanente se propaga
tal cual sin pasar por ahí. Eso es exactamente la distinción que define la fase.

### 4.2 — El OCR real: el corazón de la fase

Acá es donde el documento empieza a ser buscable **por lo que dice adentro**. La idea
completa: subís un PDF escaneado o una foto de un contrato, un proceso en segundo plano le
extrae el texto, y a los segundos podés buscar una palabra que está dentro de la imagen y el
documento aparece.

**Lo primero fue agregar una columna `ocr_status`** al documento, con cinco estados posibles:
pendiente → procesando → completado / fallido / omitido. ¿Por qué una columna de verdad y no
guardarlo en un campo JSON flexible? Porque es algo que vas a querer **consultar**: "mostrame
todos los documentos a los que les falló el OCR". Lo que se filtra va en una columna real con
posible índice; el JSON es para datos que solo lees enteros. Además da **observabilidad**: de
un vistazo sabés en qué estado está el pipeline de cada documento.

**El servicio de OCR** (`ocr_service`) es el que hace el trabajo pesado, y se ramifica según
el tipo de archivo: una imagen (JPG/PNG) se abre con Pillow y se le pasa Tesseract directo;
un PDF primero se convierte a imágenes página por página (con Poppler), y cada página se
OCR-ea por separado. Cualquier otra cosa (un Word, un Excel, un ZIP) se marca como "omitido"
— extraer texto de Office es otra técnica distinta, queda como trabajo futuro.

**La conexión más elegante de toda la fase** es que no escribí *ni una línea* de código para
indexar el texto en la búsqueda. ¿Cómo? En la Fase 3.3 había un "signal" (un disparador) que
reconstruye el vector de búsqueda cada vez que cambia un campo de texto del documento. El OCR,
al guardar el texto extraído en el campo `ocr_content`, **dispara ese signal automáticamente**.
El documento se vuelve buscable solo, gratis. Las piezas de fases distintas encajan sin
pegamento. Eso es lo que se siente cuando la arquitectura está bien pensada desde el principio.

**Dónde se nota la 4.1:** ahora que el OCR hace cosas reales, los errores reales aparecen, y
la distinción transitorio/permanente que parecía teórica se vuelve concreta:
- MinIO tarda en responder al descargar el archivo → transitorio → reintenta.
- El archivo no existe en MinIO (`NoSuchKey`) → permanente → marca "fallido" y para (¿para
  qué reintentar descargar algo que no está?).
- El archivo está corrupto y Tesseract no puede leerlo → permanente → "fallido".
- Una página en blanco → no es un error: texto vacío, estado "completado".

**Un endpoint de re-OCR** (`POST /documents/{id}/reprocess-ocr/`) permite re-disparar el
proceso a mano — útil si un documento quedó en "fallido" por un problema temporal ya resuelto,
o si se mejora el motor de OCR. Devuelve `202 Accepted`, el código HTTP que significa
"recibí tu pedido y lo voy a procesar, pero todavía no terminé" — correcto para algo asíncrono.

**Sobre testear OCR:** los tests unitarios **no corren Tesseract de verdad** — sería lento y
dependería de que el binario esté instalado en cada máquina. En su lugar se "mockea" el motor:
se le dice "cuando te llamen, devolvé este texto", y se verifica que el servicio haga lo
correcto con esa respuesta (guardar el texto, cambiar el estado, auditar, hacerlo buscable).
Aparte, hice **una prueba manual con Tesseract real**: generé una imagen con la palabra
"CONTRATO ARRENDAMIENTO" y confirmé que el motor la lee. Esa separación —lógica con mocks,
binario real verificado a mano— es la práctica estándar: tests rápidos y deterministas para
la lógica, una verificación puntual de que la integración con la herramienta externa funciona.

---

## 2026-06-04 — Fase 5.6 completa: health check + Sentry + JSON logging

Primera sub-fase de Fase 5 completada — toda la infraestructura de observabilidad del backend.

**Piezas entregadas:**
- `GET /api/v1/health/` en `apps/core/api/health_view.py`: público, `AllowAny`,
  `authentication_classes=[]`, sin envelope `{data, meta}` (excepción documentada en
  CLAUDE.md decisión #24).
- `apps/core/services/health_service.py`: `check_health()` agrega tres checkers;
  ningún checker propaga excepciones (siempre devuelven "ok"/"error").
- `apps/core/logging.py`: `RequestContextFilter` + `set_request_context`/`clear_request_context`
  via thread-local; JSON formatter activo en production.py.
- Sentry: init condicional a `SENTRY_DSN`, scrubbing de headers de auth, `CeleryIntegration`.
- 56 tests nuevos. Suite: 501 tests, 99%.

**Deuda técnica conocida:** `RequestContextFilter` popula los campos solo cuando el middleware
llame a `set_request_context()` — pendiente de integrar en `OrganizationTenantMiddleware` (Fase 5.x).

**Estado de la rama:** `develop`, limpia.

---

## 2026-06-04 — Sesión: auditoría Fase 4, merge, plan Fase 5, Fase 5.6

**Resumen de la sesión:**
- Auditoría completa de Fase 4: sin bugs críticos, 3 advertencias corregidas (ver
  decisión #23 en CLAUDE.md): (a) `ai_service` mapea `RateLimitError`/`APITimeoutError`/
  `APIConnectionError` del SDK Anthropic a `TransientError`; (b) `reprocess_ocr` resetea
  `ocr_status` a `PENDING` antes del `on_commit`; (c) `max_retries=3` inline en decoradores.
- Merge `feature/celery-ocr-pipeline` → `develop` (fast-forward, 17 commits).
- Plan completo de Fase 5 documentado: 7 sub-fases (5.1 Frontend→5.7 Notificaciones).
- Fase 5.6 implementada y testeada: health check, Sentry, JSON logging.

**Métricas:** 501 tests, 99% cobertura.
**Próximo:** Fase 5.1 — scaffold frontend React+TS+Vite (usuario con poca experiencia
frontend, requerirá guía detallada).

---

## 2026-06-04 — Plan de Fase 5 redactado (Frontend + CI/CD + Deploy + Observabilidad)

Arquitectura y plan de implementación completo de Fase 5 documentado en `docs/phase-plan.md`.

**Sub-fases planificadas:**
- **5.1** Frontend setup + auth: React+TS+Vite, Tailwind, shadcn/ui, axios+interceptors, TanStack Query v5,
  Zustand, react-router data router. Estructura feature-based en `frontend/src/features/`.
- **5.2** Gestión documental: upload drag&drop con progreso, OCR badge polling, folder browser, FTS.
- **5.3** Workflows + auditoría: builder de pasos dinámico, AdvanceStepDialog, consola de auditoría.
- **5.4** CI/CD GitHub Actions: lint+test+build en paralelo, PostgreSQL 16 + Redis 7 reales en runner,
  coverage gate 95%, Codecov badge en README.
- **5.5** Deploy VPS: Dockerfile multi-stage con binarios OCR, docker-compose.prod.yml, Nginx+TLS,
  backup pg_dump, vars de entorno de producción endurecidas.
- **5.6** Observabilidad: Sentry back+front (DSN-gated), JSON logs, health check `/api/v1/health/`.
- **5.7** Notificaciones email: `apps/notifications` (nueva app de dominio), envío vía Celery
  `on_commit` desde `workflow_service`, `EMAIL_BACKEND` por entorno.

**Estimación:** 6–8 semanas. ~70–90 tests backend nuevos + ~40–60 tests UI (Vitest).
**Orden de implementación:** 5.6 (health) → 5.1 → 5.2 → 5.4 → 5.7 → 5.3 → 5.5.

---

## 2026-06-03 — Fase 4 COMPLETA: Celery + OCR + Housekeeping + IA opcional

Cerrada la Fase 4 completa con la entrega de 4.4 (análisis IA con Claude API).

**Resumen de la Fase 4 (todas las sub-fases):**
- **4.0 Pre-flight:** deps pip (pytesseract, pdf2image), `StorageService.download_file()`, settings OCR/Celery.
- **4.1 Celery hardening:** `TransientError`, `process_ocr` con retry_backoff, task fina.
- **4.2 Pipeline OCR:** `Document.ocr_status`, `ocr_service.process()` real, endpoint reprocess-ocr.
- **4.3 Housekeeping:** `cleanup_orphan_blobs` Beat diaria, cierra deuda de Fase 2 (#5).
- **4.4 IA opcional:** `ai_service.analyze()` con Haiku + prompt caching, feature-flag por `ANTHROPIC_API_KEY`.

**Métricas finales Fase 4:** 445 tests, 99% cobertura, 0 warnings en drf-spectacular.

**Decisión confirmada:** la IA queda implementada pero inactiva hasta que el usuario añada
`ANTHROPIC_API_KEY` al `.env`. Sin key → 503. El código está listo para activar sin cambios.

**Siguiente hito:** Fase 5 — Frontend React, CI/CD, deploy VPS, Sentry, notificaciones email.

---

## 2026-06-03 — Fase 4.4 completa: análisis IA con Claude API

Implementado el análisis IA de documentos como feature opcional diferenciadora de portafolio.

**Piezas entregadas:**
- `AIServiceUnavailableError` (503) en `apps/core/exceptions.py`.
- `ai_service.analyze()`: Claude Haiku, prompt caching del system prompt (`cache_control: ephemeral`),
  truncado a 12000 chars, output JSON estructurado → `metadata["ai_analysis"]`, audit via=ai_analysis.
- `document_service.request_ai_analysis()`: validación fail-fast en el request (no en el worker).
- Task `analyze_document`: thin dispatcher, reintentable por `TransientError`.
- `POST /api/v1/documents/{id}/analyze/` (Editor+, 202 async). Resultado en `GET /documents/{id}/`.
- 20 tests nuevos. Sin nueva migración (usa JSONB `metadata` existente).

**Decisión técnica:** el cliente `anthropic.Anthropic(...)` se instancia dentro de la función
(no a nivel de módulo) para que un `ANTHROPIC_API_KEY` ausente no rompa el arranque de Django
ni los tests que no tocan IA. El import de `anthropic` también es local a la función.

---

## 2026-06-03 — Fase 4.3 completa: cleanup_orphan_blobs

Implementada la tarea Beat diaria que cierra la deuda de Fase 2 (decisión cerrada #5): los
blobs en MinIO no se borraban al soft-delete un documento. La deuda estaba registrada desde
Fase 2 y tenía su plan detallado desde la sesión del 2026-06-03.

**Piezas entregadas:**
- `StorageService.list_objects()` — paginado con boto3 paginator, devuelve
  `(key, last_modified)`. La encapsulación de boto3 se mantiene: el cleanup nunca habla
  directamente con el cliente S3.
- `cleanup_service.delete_orphan_blobs()` — fuente de verdad en DB: construye set de paths
  vivos de `Document` Y `DocumentVersion` cuyo padre esté vivo, compara con bucket, borra
  huérfanos. Período de gracia 24h por `LastModified` para no competir con uploads en vuelo.
- Task Beat `cleanup_orphan_blobs` (thin dispatcher, sin retry — idempotente y diaria).
- `CELERY_BEAT_SCHEDULE` con entrada 03:00 UTC diaria; `ORPHAN_BLOB_GRACE_HOURS` configurable
  por env var (default 24h), documentado en `.env.example`.
- 9 tests nuevos. Suite: 422 tests, 99% cobertura.

**Decisión técnica confirmada:** el cleanup es tenant-agnóstico — única excepción justificada
a la regla multi-tenancy del proyecto. No hay `organization` ni `user` naturales para una
tarea de GC de sistema. La tarea actúa sobre el bucket globalmente (los paths ya incluyen
`{org_id}/` como prefijo; no hay riesgo de cruce entre tenants). Observabilidad por
`logger.info` con conteo agregado (scanned/deleted/skipped_grace), no por AuditLog.

**`manage.py check`, black, isort, flake8:** todos limpios.

**Próximo:** Fase 4.4 — análisis IA con Claude API (feature-flagged por `ANTHROPIC_API_KEY`).

---

## 2026-06-03 — Plan detallado de Fases 4.3 y 4.4 redactado por arquitecto

Con las sub-fases 4.0, 4.1 y 4.2 completas, el arquitecto produjo el plan de implementación
detallado para las dos sub-fases restantes de la Fase 4.

**Fase 4.3 — `cleanup_orphan_blobs`:** cierra la deuda de diseño de Fase 2 (los blobs en
MinIO no se borran al soft-deletear un documento). La tarea Beat diaria a las 03:00 UTC
recorre el bucket, calcula qué paths no están referenciados por ningún `Document` ni
`DocumentVersion` vivo, y los borra. La decisión más importante: **la fuente de verdad es
la DB, no el bucket** — se construye el set de paths vivos en memoria y se resta. También
se incorporó un período de gracia de 24h (configurable vía `ORPHAN_BLOB_GRACE_HOURS`) para
no borrar accidentalmente blobs de uploads en vuelo cuyo commit de DB aún no fue visible.
Una segunda decisión clave: la tarea es **tenant-agnóstica** — es mantenimiento global del
sistema, no una operación de dominio. Excepción justificada y documentada a la regla
multi-tenant. Sin auditoría por blob; solo `logger.info` con conteo agregado.

**Fase 4.4 — Análisis IA con Claude API (opcional):** diferenciador de portafolio. Endpoint
`POST /documents/{id}/analyze/` que dispara una tarea Celery que llama a Claude (Haiku) y
guarda el resultado en `metadata["ai_analysis"]`. La característica más importante del diseño
es el **feature-flag completo**: `ANTHROPIC_API_KEY=` vacía → el código existe y el endpoint
existe, pero devuelve 503. El usuario activa la feature poniendo la key en su `.env`. Esto
significa que el código puede mergearse y desplegarse sin key, sin riesgo. Mismo patrón async
202 que `reprocess-ocr`. Prompt caching del system prompt (instrucciones estables) → reduce
costo en llamadas repetidas. Nueva excepción `AIServiceUnavailable` (503) en
`apps/core/exceptions.py`.

Ver `docs/phase-plan.md` §4.3 y §4.4 para el plan completo con contratos, tests y DoD.

---

## 2026-06-15 — Auditoría completa de Fase 5 (5.1 + 5.7): 5 hallazgos corregidos

Antes de avanzar a la Fase 5.2, se hizo una auditoría completa del código de las Fases 5.1
(frontend auth) y 5.7 (notificaciones email). Misma metodología que la auditoría de Fase 3:
revisar el propio trabajo buscando bugs, race conditions e inconsistencias antes de dar la
fase por cerrada. Se encontraron 5 hallazgos (1 HIGH + 4 IMPORTANT) y se corrigieron todos.

**Commits:**
- `f9d4eff — fix(frontend): correct Promise.reject in 401 interceptor, add global error toast, fix type narrowing in auth forms`
- `cb0654d — fix(notifications): use atomic UPDATE claim to prevent concurrent double-send`
- `043136d — docs: compress CLAUDE.md for AI token efficiency`

---

### HIGH — Perfil de usuario no se rehidrataba tras silent refresh

**Dónde:** `frontend/src/shared/components/ProtectedRoute.tsx`

**Qué pasaba:** al recargar la página, `ProtectedRoute` restauraba el `accessToken` desde el
refresh token del `localStorage`, pero nunca llamaba a `/auth/me/` para restaurar el objeto
`user` en el store de Zustand. El resultado visible para el usuario:
- El `Header` mostraba iniciales `?` en el avatar (user undefined).
- El `Sidebar` ocultaba ítems con `allowedRoles` — incluyendo "Auditoría" para roles
  autorizados — porque `userRole` era `undefined` y las comparaciones de rol fallaban.
La app parecía funcionar (rutas protegidas, tokens renovados) pero el estado de sesión
estaba incompleto.

**La corrección:** bootstrap secuencial en un `useEffect`: `refreshToken()` → si éxito,
`setAccessToken(access)` → `getMe()` → `setUser(profile)`. Si `getMe()` falla (token válido
pero `/auth/me/` falla) → `logout()`. El skeleton de carga cubre TODO el proceso (token
+ perfil) antes de renderizar el `<Outlet>`. Casos resueltos: reload con token expirado →
redirect a login; reload con token válido → perfil completo.

**Decisión de diseño (cerrada #33):** se usa `getMe()` imperativo (opción A) en lugar de
`useMe()` hook (opción B). El bootstrap es un flujo imperativo secuencial; un hook
declarativo introduce una condición de carrera con el flag `restorationAttempted` que ya
está en el estado de Zustand.

**Tests nuevos:** 5 tests en `frontend/src/shared/components/__tests__/ProtectedRoute.test.tsx`:
sin token → redirect a `/login`; refresh válido → perfil rehidratado + Outlet renderizado;
`getMe()` falla → logout; refresh inválido → logout; token + user ya en memoria → Outlet
directo sin llamadas de red.

---

### IMPORTANTE #1 — Promise.reject faltante en interceptor 401

**Dónde:** `frontend/src/lib/api-client.ts`

**Qué pasaba:** en el response interceptor, si el refresh tenía éxito pero `originalRequest`
era falsy, no había un `return Promise.reject(...)` explícito — el handler podía resolver con
`undefined`, pasando silenciosamente un error como respuesta exitosa.

**La corrección:** añadido `return Promise.reject(parseApiError(error))` como fallback
explícito cuando existe esa rama.

---

### IMPORTANTE #2 — Doble envío concurrente de notificaciones

**Dónde:** `backend/apps/notifications/services/notification_service.py`

**Qué pasaba:** el guard de idempotencia leía `notification.status` sin `select_for_update`.
Dos workers Celery procesando la misma tarea (re-entrega de Celery, pod duplicado en prod)
podían leer ambos `PENDING`, pasar el guard y enviar el mismo email dos veces.

**La corrección:** claim atómico vía `UPDATE WHERE status IN ('pending', 'failed')`
devolviendo `rowcount`. Solo el worker con `rowcount == 1` procede al envío SMTP; el worker
que recibe `rowcount == 0` hace skip. No se mantiene ningún lock de DB durante el I/O externo
(la conexión SMTP), que puede tardar segundos.

**Por qué `status IN (pending, failed)` y no solo `pending`:** permite que Celery reintente
la tarea tras un fallo SMTP definitivo — el job de reintento también puede reclamar. Si la
notificación ya está `sent`, ningún worker la puede reclamar.

**Decisión de diseño (cerrada #34):** no se introduce un estado `processing` (evitaría
introducir una migración de enum y una sweep task para limpiar notificaciones que quedaran
en `processing` si el worker muere a mitad del SMTP). La semántica es at-least-once, igual
que antes; se cierra la ventana de doble envío concurrente. Si se requiere exactly-once
estricto en el futuro → deuda técnica anotada: introducir `processing` + sweep task.

**Tests nuevos (2):** `test_send_concurrent_claim_sends_once` (simula una instancia stale
del objeto + un segundo intento concurrente: solo 1 email en `mail.outbox`) y
`test_send_failure_releases_claim_for_retry` (fallo SMTP → `FAILED` → segundo intento
exitoso → `SENT`).

---

### IMPORTANTE #3 — Mutaciones fallidas silenciosas (toasts globales)

**Dónde:** `frontend/src/lib/query-client.ts`

**Qué pasaba:** `<Toaster>` de sonner estaba montado en el layout pero ninguna mutación lo
usaba. Un fallo de mutación (ej: subir un documento y recibir un 400) era invisible para
el usuario salvo que esa mutación específica tuviera manejo de error inline.

**La corrección:** `MutationCache({ onError })` global en `query-client.ts` que dispara
`toast.error(parseApiError(e).message)` para cualquier mutación fallida. Las mutaciones con
UI de error inline propia pueden optar por no disparar el toast global añadiendo
`meta: { suppressGlobalToast: true }` en su definición. `useLogin` usa `suppressGlobalToast`
porque muestra el error en el formulario.

**Decisión de diseño (cerrada #35):** el `onError` global va en `MutationCache` (no en
`defaultOptions.mutations.onError`). La diferencia: `MutationCache.onError` se ejecuta
ADEMÁS del `onError` por-mutación; `defaultOptions.mutations.onError` lo reemplaza.
Las queries no tienen handler global de error (demasiado ruido con refetches en background).

**Tests nuevos (2):** en `frontend/src/lib/__tests__/query-client.test.ts`.

---

### IMPORTANTE #4 — Narrowing inseguro de ApiError en LoginForm

**Dónde:** `frontend/src/features/auth/components/LoginForm.tsx`

**Qué pasaba:** el código usaba un double cast `loginMutation.error as ApiError`. Si el
error no era una instancia de `ApiError`, acceder a `.code` o `.status` devolvería
`undefined` silenciosamente en lugar de mostrar el error real.

**La corrección:** `instanceof ApiError` con `import { ApiError }` como valor (no como
`import type`), que es lo que permite usar `instanceof` en tiempo de ejecución.

**Tests nuevos (5):** en `frontend/src/features/auth/__tests__/LoginForm.test.tsx`.

---

### IMPORTANTE #5 — Tests de wiring workflow → notificaciones (casos de rollback)

**Dónde:** `backend/apps/workflows/tests/test_workflow_notifications.py`

**Qué faltaba:** no había tests que verificaran que las notificaciones NO se envían cuando
el workflow no debería enviarlas.

**Tests nuevos (2):** `test_cancel_workflow_sends_no_notification` (cancelar no envía email)
y `test_notification_not_sent_on_rollback` (si `start_workflow` hace rollback por cualquier
razón, el `on_commit` no dispara y no se envía ninguna notificación — porque `on_commit`
es exactamente ese contrato: solo se ejecuta si la transacción llega a commit).

---

### Métricas actualizadas tras la auditoría

| Métrica | Antes | Después |
|---------|-------|---------|
| Tests frontend (Vitest) | 22 | 34 (+12) |
| Tests backend (pytest) | 522 | ~526 (+4) |
| TypeScript errors | 0 | 0 |
| black/isort/flake8 | limpio | limpio |

**Cobertura backend:** 95% mantenida.

---

## 2026-06-10 — Fases 5.1 y 5.7 completas: frontend scaffold + auth y notificaciones email

**Resumen de la sesión:** se implementaron dos sub-fases de Fase 5 de forma independiente y
paralela. El frontend tiene ahora su cimiento completo; el backend cierra la deuda de
notificaciones que quedó pendiente desde Fase 3.

### Fase 5.1 — Frontend: scaffold + autenticación

El punto de partida del frontend. Se tomaron muchas decisiones de arquitectura antes de
escribir la primera línea de código — decisiones que afectan todo lo que viene en 5.2 y 5.3.

**Estructura elegida (feature-based, no layer-based):** cada dominio funcional agrupa sus
propios componentes, hooks y llamadas a API. Espeja el monolito modular del backend. Lo
transversal va en `shared/` y `lib/`. Razón: una carpeta `components/` con 80 archivos
es inmanejable; cohesión por dominio es más fácil de navegar y de escalar.

**La pieza más interesante: el interceptor de refresh en `api-client.ts`.**
El problema: si el access token expira mientras el usuario tiene N tabs abiertos o N
requests en vuelo, todos reciben 401 al mismo tiempo. Sin coordinación, N requests
intentarían refrescar el token simultáneamente — y el primero que lo logra invalida el
refresh token rotativo, dejando los demás en un loop de 401. La solución es una cola:
un flag `isRefreshing` y un array `failedQueue` de resolvers pendientes. El primer 401
setea el flag, hace el refresh, y cuando resuelve vacía la cola reintentando todas las
requests originales con el nuevo token. Los 401 subsiguientes (mientras el flag está
activo) simplemente se suman a la cola. Exactamente 1 refresh para N 401. Hay un test
explícito de este comportamiento concurrente.

**Decisión de almacenamiento de tokens:** `accessToken` en memoria (Zustand), nunca en
`localStorage`. `refreshToken` en `localStorage` para sobrevivir reloads. El trade-off de
seguridad (XSS) está documentado como deuda consciente; migrar a cookies httpOnly queda para
cuando el backend soporte `set-cookie`.

**Stack de UI:** Vite 8 + React 18 + TypeScript + Tailwind v3 + shadcn/ui (tema Slate).
TanStack Query v5 para server state. Zustand v5 para client state (solo sesión de auth,
sidebar, toasts — nada del servidor). react-hook-form + zod para formularios.
`createBrowserRouter` (data router de React Router v6.4+).

**Tests:** 22 tests Vitest en verde. `store.test.ts` (12): cubre login, logout, persistencia
de refresh en localStorage, restauración silenciosa, limpieza de tokens. `interceptor.test.ts`
(10): cubre inyección del Bearer header, retry tras refresh, logout ante refresh fallido, y
el queue pattern para N 401 simultáneos. `npm run build` sin errores de tipos.

### Fase 5.7 — Notificaciones email por workflow

Cierra el placeholder que quedó en Fase 3.2 ("config/actions JSONB reservado para
notificaciones") y en Fase 4 ("notificaciones diferidas a Fase 5").

**Nueva app `apps/notifications`** (ya existía como skeleton vacío). Modelo `Notification`
hereda de `BaseModel` con FK obligatoria a `Organization` — consistent con la regla de
multi-tenancy del proyecto. Índices compuestos `(organization, recipient)` y
`(organization, status)` para consultas futuras de observabilidad.

**Decisión de desacoplamiento:** `workflow_service` no importa directamente el backend de
email ni crea emails. Encola un evento llamando a `notification_service.notify_step_assigned`,
que crea el registro `Notification` (status `pending`) y programa la task via
`transaction.on_commit`. El acoplamiento es vía service, no vía transporte. Esto significa
que el día que se agregue notificación in-app o push, solo cambia la capa de transporte
(`_send`), no el workflow ni el modelo.

**Lazy import para evitar circulares:** `workflow_service` importa `notification_service`
dentro de la función que lo llama (no a nivel de módulo). Evita el ciclo de importación
entre dos apps de dominio que se necesitan mutuamente.

**Tests:** 21 nuevos tests pytest en verde: selector (5), service (8), tasks (2),
workflow_notifications (6). Cubre destinatario correcto por rol, tenant isolation, verificación
de `mail.outbox` con backend locmem, que `on_commit` dispara la task, e idempotencia.

**Métricas finales:** 522 tests backend (495 normales + 27 integración) + 22 frontend.
Cobertura backend: 95%.

---

## 2026-06-09 — Deuda técnica cerrada: tests de integración reales con MinIO

Cerrada la deuda de tests de integración con MinIO que había quedado pendiente desde
la Fase 2. La decisión original (documentada en `docs/phase-plan.md` §2.3 y en
CLAUDE.md decisión #2) era: "mocked primero, integración real después". El "después"
nunca llegó en Fases 3 o 4.

**Archivos creados:**
- `backend/apps/documents/tests/test_storage_integration.py` — 20 tests reales contra MinIO:
  - `TestEnsureBucket` (2): creación idempotente de bucket.
  - `TestUploadDownload` (4): upload + download round-trip, incluyendo binarios.
  - `TestDeleteFile` (2): borrado y verificación de ausencia.
  - `TestPresignedUrl` (3): generación y acceso HTTP a URL prefirmada.
  - `TestListObjects` (3): paginación y filtrado por prefijo.
  - `TestBuildStoragePath` (6, unitarios): formato de path `{org_id}/{YYYY}/{MM}/{doc_id}/{filename}`.
- `backend/apps/documents/tests/test_cleanup_integration.py` — 7 tests end-to-end de
  `cleanup_service.delete_orphan_blobs()` con PostgreSQL + MinIO reales: detecta huérfanos,
  respeta período de gracia, no borra paths de docs vivos, maneja bucket vacío.

**Configuración:**
- `backend/pyproject.toml` — añadido marker `integration` en `[tool.pytest.ini_options].markers`.
  Permite ejecutar solo tests de integración con `-m integration` o excluirlos con `-m "not integration"`.

**Métricas:** 501 → 528 tests (+27). Los 27 nuevos son `@pytest.mark.integration` y
requieren `docker compose up -d` con MinIO. La suite normal (sin flag) sigue siendo 501.
Flake8 limpio, cobertura 99% mantenida.

---

## 2026-06-09 — Dependencia de sistema faltante: `redis-tools`

`redis-cli` (usado en pruebas manuales de Redis) requiere el paquete apt `redis-tools`,
que no viene preinstalado en Ubuntu/WSL2. Se identificó al intentar verificar Redis desde
la terminal sin el binario disponible.

Documentación actualizada:
- `docs/manual-testing.md` — nota en la sección Redis (Nivel 1) y en la sección
  "redis-cli — Inspección de Redis" con el comando de instalación.
- `backend/.env.example` — añadido `redis-tools` a la lista consolidada de dependencias
  apt del proyecto (junto a `tesseract-ocr`, `poppler-utils`, `libmagic1`).

---

## 2026-06-21 — Fase 5.3 completa: workflows + auditoría en el frontend

La última pieza de UI que faltaba para que la plataforma sea navegable de punta a punta:
el motor de workflows (templates, ejecuciones, avance de pasos) y la consola de auditoría.
También el panel de análisis IA en la vista de detalle de documento.

### Workflows: el builder dinámico y el diálogo de avance

El formulario de creación de templates usa `useFieldArray` de react-hook-form. La idea:
los pasos del template son un array que el usuario puede crecer o encoger con botones
"Añadir paso" / "Eliminar". El orden se asigna automáticamente desde el índice del array,
así el usuario no tiene que numerarlos a mano (y no puede crear huecos ni duplicados).

La validación con zod replica las reglas del backend: exactamente un paso marcado como
`is_final`, mínimo un paso. Esto da feedback inmediato antes de enviar la request, pero
el backend sigue siendo la autoridad — si alguien mandara un request malformado
directamente a la API, el service lo rechaza igual.

Para avanzar un paso (aprobar / rechazar / comentar) se usa un `<AlertDialog>`: el
usuario elige la acción con un select y opcionalmente agrega un comentario (el comentario
es obligatorio solo para la acción "comentar"). La decisión de diseño más importante acá
es que el frontend **no valida el rol del usuario antes de mostrar el botón**: simplemente
manda la request y, si el backend responde 403 (porque ese usuario no tiene el rol del
paso actual), muestra un toast de error. El backend es quien tiene la información de
autoridad — el cliente podría tener datos de rol desactualizados o cacheados. Esto
evita duplicar lógica de RBAC en el frontend y simplifica mucho el componente.

El `useWorkflowExecution` usa polling de TanStack Query cada 5 segundos mientras la
ejecución está en estado `pending` o `in_progress`. Cuando llega a un estado terminal
(completed / rejected / cancelled) el polling se detiene solo. Mismo patrón que el
polling del `ocr_status` en 5.2.

La línea de tiempo de pasos (`WorkflowStepLogTimeline`) muestra cada acción registrada
en orden cronológico con `formatDistanceToNow` de date-fns — "hace 3 minutos", "hace
2 horas". Esto hace la historia del workflow legible de un vistazo.

### Auditoría: consola filtrable con restricción de acceso

La consola de auditoría es básicamente un `<table>` paginado con filtros server-side
que van en los query params de la request: tipo de acción, tipo de entidad, email de
usuario, y rangos de fecha con inputs nativos de tipo `date`. El componente `AuditLogFilters`
construye los params y el hook los pasa directamente a `GET /api/v1/audit-logs/`.

La restricción de acceso se maneja en dos capas: la ruta `/audit-logs` no aparece en
el sidebar para roles sin permiso, y si alguien la visita directamente sin el rol correcto
se redirige. El backend devuelve 403 igualmente — la UI solo hace UX, no seguridad.

Los badges de acción están coloreados por tipo (create=verde, delete=rojo, update=amarillo)
para que el ojo del auditor pueda escanear visualmente el listado.

### Panel de análisis IA en el detalle de documento

Se añadió una pestaña "Análisis IA" a `DocumentDetailPage`. Cuando el usuario presiona
"Analizar", la UI manda `POST /documents/{id}/analyze/` y recibe un 202 (el análisis
corre en background). A partir de ahí, la misma query de TanStack que carga el documento
empieza a refetchear cada pocos segundos esperando que `metadata.ai_analysis` aparezca.

Si el backend responde 503 (`AI_SERVICE_UNAVAILABLE` — sin key de Anthropic), la pestaña
muestra "Análisis IA no habilitado" y oculta el botón. Si el documento no tiene contenido
OCR (`AI_NO_CONTENT`, 409), muestra un mensaje explicativo.

El patrón de polling + manejo graceful de 503/409 hace que la feature funcione bien tanto
en el contexto del portafolio (con la key activa) como en una demo sin ella.

### Nuevos componentes shadcn/ui

Se añadieron `textarea`, `checkbox`, `separator` y `accordion`. El checkbox se usa en
el `WorkflowStepEditor` para el campo `is_final`; el textarea para el comentario en
`AdvanceStepDialog`; el separator en la línea de tiempo de pasos; el accordion para
expandir/colapsar detalles en vistas de lista.

### Métricas tras Fase 5.3

| Métrica | Valor |
|---------|-------|
| Tests frontend (Vitest) | 163 (+74 vs 5.2; 89 preexistentes + 74 nuevos) |
| Tests backend (pytest) | ~526 (sin cambios) |
| TypeScript errors | 0 |

**Deuda conocida anotada (no bloqueante):**
- Las páginas de lista de templates y ejecuciones no paginan todavía — muestran solo la
  primera página. El backend soporta paginación; el componente `<Pagination>` de 5.2
  existe. Se aplazó para no inflar el scope de 5.3.
- El bundle pesa ~790KB (un solo chunk). Code-splitting con lazy imports queda para 5.5
  (deploy), donde también se optimiza el build de producción.

**Próximo:** Fase 5.4 — CI/CD con GitHub Actions (lint+test+build en paralelo, PostgreSQL 16
+ Redis 7 como services del runner, coverage gate 95%, Codecov badge en README).

---

## Ideas y pendientes anotados (para no perderlos)

- ✅ **OCR real (Fase 4.2 — hecho):** cada documento subido ya es buscable por su contenido
  interno, no solo por su nombre. (Ver la sección de Fase 4.2 más arriba.)
- ✅ **`cleanup_orphan_blobs` (Fase 4.3 — hecho):** tarea Beat diaria que borra de MinIO los
  archivos cuyo documento fue soft-deleted. Cierra la deuda de Fase 2. (Ver entrada 2026-06-03.)
- **`bulk_create` salta el signal de búsqueda:** si en Fase 4 el OCR inserta documentos en
  masa, hay que reindexar a mano. Anotado para no olvidarlo.
- **IA con Claude API (Fase 4.4, opcional):** resumen automático, extracción de entidades
  (fechas, montos, nombres), categorización sugerida. Es el "diferenciador de portafolio".
  Plan detallado listo; activar con `ANTHROPIC_API_KEY`.
- **Stemming por idioma:** si algún día importa que "contrato" matchee "contratos", se puede
  configurar FTS por-tenant según su idioma.

---

## Cómo se está usando Claude Code en este proyecto (nota de proceso)

El flujo se mantuvo: **yo defino la interfaz** (qué hace cada función, qué recibe, qué
devuelve), **Claude implementa el cuerpo**, y **reviso cada línea antes del commit**. La
auditoría de Fase 3 es buen ejemplo de usar la IA más allá de "escribime esta función":
sirvió para revisar críticamente el código ya escrito y encontrar problemas de concurrencia
que yo no había mirado. El objetivo sigue siendo el mismo — entender el código lo suficiente
para defenderlo en una entrevista.

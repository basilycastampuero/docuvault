# DocuVault — Bitácora de Preparación del Proyecto
## Autodocumentación completa: todo lo hecho antes de escribir código

> Este documento es tu referencia personal. Explica qué se hizo, por qué se hizo,
> y en qué orden. Léelo cada vez que necesites reorientarte.
> Última actualización: Fase 0 — Pre-desarrollo completada.

---

## ¿Qué es DocuVault?

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

## 🔜 Próximo paso: Fase 1

La primera tarea de código real es inicializar Django correctamente:

```bash
# 1. Activar entorno virtual
source backend/.venv/bin/activate

# 2. Verificar que los servicios de infraestructura corren
docker compose up -d
docker compose ps

# 3. Inicializar proyecto Django
cd backend
django-admin startproject config .

# 4. Primera tarea en Claude Code:
# "Lee CLAUDE.md y docs/phase-plan.md sección Fase 1.1.
#  Configura settings en 4 capas: base.py, development.py, test.py, production.py.
#  Conecta PostgreSQL usando python-decouple y el archivo .env existente."
```

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

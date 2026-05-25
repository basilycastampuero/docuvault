# docs/phase-plan.md — Plan de Desarrollo DocuVault

> Documento de referencia para Claude Code.
> Cada fase debe completarse con tests antes de avanzar a la siguiente.
> El orden importa: cada fase depende de la anterior.

---

## Fase 0 — Setup y entorno (COMPLETADA)

**Objetivo:** Entorno profesional listo para desarrollo.

### Checklist
- [x] WSL2 + Ubuntu configurado
- [x] pyenv + Python 3.13 instalado
- [x] Docker Compose: PostgreSQL 16, Redis 7, MinIO
- [x] Pre-commit hooks: black, isort, flake8
- [x] Git configurado con SSH a GitHub
- [x] .gitignore y .env.example profesionales
- [x] README inicial con arquitectura
- [x] Estructura de carpetas `backend/apps/`

---

## Fase 1 — Django base + Auth + Organizations + RBAC

**Objetivo:** Sistema de autenticación y multi-tenancy funcional con tests completos.
**Estimación:** 3–4 semanas

### 1.1 Inicializar Django

```
Tareas:
- django-admin startproject config backend/
- Configurar settings en 4 capas: base.py, development.py, test.py, production.py
- Conectar PostgreSQL via python-decouple
- Configurar INSTALLED_APPS con las apps del proyecto
- Configurar Django REST Framework en settings
- Configurar simplejwt en settings
- Primer migrate y verificar conexión a DB
- Configurar logging estructurado (JSON) desde base.py
```

**Estructura de settings esperada:**
```python
# base.py — sin valores hardcodeados, todo desde decouple
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}
```

### 1.2 Core app — BaseModel y utilidades compartidas

```
Tareas:
- Crear apps/core/ (no es un dominio de negocio, es infraestructura compartida)
- BaseModel con UUID pk, created_at, updated_at, deleted_at
- SoftDeleteManager personalizado
- Clase base de excepción del proyecto
- Utilidades: generate_slug, validate_file_mime, etc.
```

### 1.3 App: organizations

```
Modelos:
- Organization
    id: UUID
    name: str
    slug: str (unique)
    is_active: bool
    settings: JSONB
    created_at, updated_at, deleted_at

Tareas:
- Modelo Organization con BaseModel
- OrganizationService: create, update, deactivate
- OrganizationSelector: get_by_id, get_by_slug
- Serializers: OrganizationSerializer, OrganizationCreateSerializer
- Views: OrganizationViewSet (solo SuperAdmin puede crear orgs)
- Tests: TestOrganizationModel, TestOrganizationService, TestOrganizationAPI
```

### 1.4 App: authentication — Custom User + JWT

```
Modelos:
- User (AbstractBaseUser)
    id: UUID
    email: str (unique, usado como username)
    organization: FK → Organization
    role: TextChoices (super_admin, org_admin, supervisor, editor, viewer, auditor)
    is_active: bool
    last_login_at: datetime
    created_at, updated_at

Tareas:
- Custom User model (heredar AbstractBaseUser, no AbstractUser)
- UserManager personalizado
- Configurar AUTH_USER_MODEL en settings
- JWT: access token (60 min dev / 15 min prod), refresh (7 días), rotating
- Blacklist activado (TokenBlacklist app de simplejwt)
- Claims JWT personalizados: user_id, organization_id, role, email
- Endpoints:
    POST /api/v1/auth/login/        → obtener tokens
    POST /api/v1/auth/refresh/      → renovar access token
    POST /api/v1/auth/logout/       → blacklistear refresh token
    GET  /api/v1/auth/me/           → datos del usuario autenticado
- Middleware: OrganizationTenantMiddleware (inyecta request.organization)
- AuthService: login, logout, refresh
- UserService: create_user, update_user, deactivate_user
- Tests:
    - Login con credenciales correctas → tokens válidos
    - Login con credenciales incorrectas → 401
    - Refresh con token válido → nuevo access token
    - Logout → token en blacklist
    - Request con token expirado → 401
    - Request sin token → 401
    - Aislamiento: usuario de org A no puede ver datos de org B
```

### 1.5 App: permissions — RBAC

```
Tareas:
- Permission classes DRF:
    IsAuthenticated (usar la de DRF)
    IsOrganizationMember → user.organization == request.organization
    HasRole(roles=[...]) → user.role in roles
    IsSuperAdmin
    IsOrgAdmin
- Decoradores de conveniencia si aplica
- Tests exhaustivos de cada permission class:
    - usuario autenticado de la org → pasa
    - usuario autenticado de otra org → 403
    - usuario sin el rol requerido → 403
    - usuario no autenticado → 401
```

### 1.6 App: users (gestión de usuarios dentro de org)

```
Endpoints:
    GET    /api/v1/users/              → listar usuarios de mi org (OrgAdmin+)
    POST   /api/v1/users/             → invitar usuario a la org (OrgAdmin)
    GET    /api/v1/users/{id}/        → detalle de usuario
    PATCH  /api/v1/users/{id}/        → actualizar usuario (OrgAdmin)
    DELETE /api/v1/users/{id}/        → desactivar usuario (soft delete)

Reglas de negocio:
    - Un usuario solo puede ver usuarios de su organización
    - Solo OrgAdmin+ puede crear/editar/desactivar usuarios
    - Un usuario no puede cambiar su propio rol
    - SuperAdmin puede gestionar usuarios de cualquier org
```

### Entregable Fase 1
- [ ] Django corriendo y conectado a PostgreSQL
- [ ] JWT auth funcional con blacklist
- [ ] Multi-tenancy: Organization model + middleware
- [ ] RBAC: 6 roles, permission classes en DRF
- [ ] Usuarios gestionables dentro de org
- [ ] Cobertura de tests > 80% en las apps de esta fase
- [ ] Commit limpio con mensaje `feat: phase 1 - auth, organizations and RBAC`

---

## Fase 2 — Gestión Documental Core

**Objetivo:** Upload, almacenamiento, versionado y estructura de carpetas.
**Estimación:** 4–5 semanas

### 2.1 App: documents — Modelos

```
Modelos:

Folder
    id: UUID
    organization: FK → Organization
    name: str
    parent: FK → self (null para carpetas raíz)
    owner: FK → User
    created_at, updated_at, deleted_at

Document
    id: UUID
    organization: FK → Organization
    folder: FK → Folder (null permitido, para documentos sin carpeta)
    name: str
    description: str (optional)
    mime_type: str
    file_size: int (bytes)
    checksum: str (SHA256 del archivo)
    storage_path: str (ruta en MinIO/S3)
    status: TextChoices (draft, under_review, approved, archived, rejected)
    version: int (versión actual)
    created_by: FK → User
    tags: ArrayField o JSONField
    metadata: JSONB
    ocr_content: TextField (null, resultado del OCR)
    search_vector: SearchVectorField (para FTS)
    created_at, updated_at, deleted_at

DocumentVersion
    id: UUID
    document: FK → Document
    version_number: int
    storage_path: str
    file_size: int
    checksum: str
    created_by: FK → User
    change_description: str
    created_at

Índices requeridos:
    idx_documents_org_status → (organization_id, status)
    idx_documents_org_folder → (organization_id, folder_id)
    idx_documents_org_created → (organization_id, created_at)
    idx_documents_search_vector → GIN (search_vector)
    idx_folders_org_parent → (organization_id, parent_id)
```

### 2.2 Object Storage — MinIO/S3

```
Tareas:
- Configurar django-storages con MinIO para desarrollo
- StorageService:
    upload_file(file, path) → storage_path
    get_presigned_url(storage_path, expires=3600) → url temporal
    delete_file(storage_path) → void
- Path pattern: {org_id}/{year}/{month}/{document_id}/{filename}
- Validación de archivos ANTES de subir:
    - MIME type permitido: PDF, DOCX, XLSX, JPG, PNG, ZIP
    - Tamaño máximo: 50MB
    - Calcular SHA256 para detectar duplicados
```

### 2.3 Folder service

```
FolderService:
    create_folder(organization, owner, name, parent=None) → Folder
    rename_folder(organization, folder, name) → Folder
    move_folder(organization, folder, new_parent) → Folder
    soft_delete_folder(organization, folder, deleted_by) → void

FolderSelector:
    get_folder_tree(organization) → árbol jerárquico
    get_folder_by_id(organization, folder_id) → Folder
    get_children(organization, folder) → QuerySet[Folder]

Reglas:
    - No permitir mover una carpeta dentro de sí misma
    - Al eliminar carpeta, verificar si tiene contenido (documentos o subcarpetas)
    - Soft delete en cascada a subcarpetas y documentos (task Celery)
```

### 2.4 Document service — Upload

```
DocumentService:
    create_document(organization, user, folder, file, name, description, tags) → Document
        1. Validar archivo (MIME, tamaño)
        2. Calcular checksum
        3. Subir a MinIO/S3
        4. Crear registro Document en DB
        5. Crear primera DocumentVersion
        6. Disparar tarea OCR async (Celery)
        7. Registrar AuditLog
        8. Retornar document

    upload_new_version(organization, user, document, file, change_description) → Document
        1. Validar archivo
        2. Subir nueva versión a storage
        3. Crear DocumentVersion
        4. Incrementar document.version
        5. Registrar AuditLog
        6. Retornar document

    soft_delete_document(organization, user, document) → void
        1. Marcar deleted_at
        2. NO eliminar de storage todavía
        3. Registrar AuditLog

DocumentSelector:
    get_documents(organization, user, folder=None, status=None, search=None) → QuerySet
    get_document_by_id(organization, document_id) → Document
    get_document_versions(organization, document) → QuerySet[DocumentVersion]
```

### 2.5 Endpoints de documentos

```
GET    /api/v1/folders/                    → listar carpetas raíz
POST   /api/v1/folders/                    → crear carpeta
GET    /api/v1/folders/{id}/               → detalle
PATCH  /api/v1/folders/{id}/               → renombrar
DELETE /api/v1/folders/{id}/               → soft delete
GET    /api/v1/folders/{id}/children/      → subcarpetas
GET    /api/v1/folders/{id}/documents/     → documentos en carpeta

GET    /api/v1/documents/                  → listar documentos (filtros: folder, status, search)
POST   /api/v1/documents/                  → subir documento (multipart/form-data)
GET    /api/v1/documents/{id}/             → detalle
PATCH  /api/v1/documents/{id}/             → editar metadata
DELETE /api/v1/documents/{id}/             → soft delete
GET    /api/v1/documents/{id}/download/    → presigned URL de descarga
GET    /api/v1/documents/{id}/versions/    → historial de versiones
POST   /api/v1/documents/{id}/versions/    → subir nueva versión
```

### Entregable Fase 2
- [ ] Upload funcional a MinIO con validación
- [ ] Versionado de documentos
- [ ] Árbol de carpetas jerárquico
- [ ] Presigned URLs para descarga
- [ ] Tests de upload, versionado y aislamiento de tenant
- [ ] Índices PostgreSQL aplicados y verificados con EXPLAIN ANALYZE

---

## Fase 3 — Auditoría + Workflows + FTS

**Objetivo:** Sistema de auditoría completo, motor de workflows y búsqueda full-text.
**Estimación:** 4–5 semanas

### 3.1 App: audit

```
Modelo AuditLog:
    id: UUID (BigAutoField para performance)
    organization: FK → Organization
    user: FK → User (null si sistema)
    entity_type: str (ej: 'document', 'workflow', 'user')
    entity_id: str
    action: TextChoices (create, update, delete, view, login, logout, ...)
    old_values: JSONB
    new_values: JSONB
    ip_address: GenericIPAddressField
    user_agent: str
    metadata: JSONB
    created_at: datetime (NO updated_at — logs son inmutables)

IMPORTANTE: AuditLog NO tiene soft delete. Los logs son inmutables.

AuditService:
    log(organization, user, entity, action, old_values, new_values, request=None)

Endpoints:
    GET /api/v1/audit-logs/    → listar con filtros (entity_type, action, user, date_range)
    GET /api/v1/audit-logs/{id}/

Permisos: solo Auditor, OrgAdmin, SuperAdmin pueden leer audit logs.
```

### 3.2 App: workflows

```
Modelos:

WorkflowTemplate
    organization: FK
    name: str
    description: str
    is_active: bool
    config: JSONB (configuración del flujo)

WorkflowStep
    template: FK → WorkflowTemplate
    name: str
    order: int
    required_role: TextChoices (quién puede completar este paso)
    is_final: bool
    actions: JSONB (qué hace al completarse: notificar, cambiar estado, etc.)

WorkflowExecution
    organization: FK
    template: FK → WorkflowTemplate
    document: FK → Document
    current_step: FK → WorkflowStep
    status: TextChoices (pending, in_progress, completed, rejected, cancelled)
    started_by: FK → User
    started_at: datetime
    completed_at: datetime (null)

WorkflowStepLog
    execution: FK → WorkflowExecution
    step: FK → WorkflowStep
    action: TextChoices (approved, rejected, commented)
    performed_by: FK → User
    comment: str
    performed_at: datetime

Flujo ejemplo:
    Draft → Under Review → Approved → Archived
                        ↓
                    Rejected → Draft

WorkflowService:
    start_workflow(organization, user, document, template) → WorkflowExecution
    advance_step(organization, user, execution, action, comment) → WorkflowExecution
    reject_workflow(organization, user, execution, reason) → WorkflowExecution
```

### 3.3 Full Text Search

```
Implementar con PostgreSQL nativo (no Elasticsearch):

1. Campo search_vector en Document (SearchVectorField)
2. Signal o trigger que actualiza search_vector al guardar
3. Índice GIN sobre search_vector
4. SearchSelector:
    search_documents(organization, query, filters={}) → QuerySet
    - Usar SearchQuery y SearchRank de django.contrib.postgres.search
    - Buscar en: name, tags, ocr_content, description
    - Ordenar por relevancia (SearchRank)

Endpoint:
    GET /api/v1/search/?q=contrato&folder=&status=
```

### Entregable Fase 3
- [ ] AuditLog registrando todos los eventos críticos
- [ ] Workflows funcionando con al menos 1 template de ejemplo
- [ ] Full-text search con ranking de relevancia
- [ ] Tests de audit, workflows y search

---

## Fase 4 — Celery + OCR + IA

**Objetivo:** Procesamiento async, OCR de documentos e integración IA opcional.
**Estimación:** 2–3 semanas

### 4.1 Celery setup

```
Configuración:
- Broker: Redis (db 1)
- Result backend: Redis (db 2)
- Celery Beat para tareas programadas
- Configurar en config/celery.py

Tareas iniciales:
    tasks.documents.process_ocr(document_id)
    tasks.documents.generate_thumbnail(document_id)
    tasks.notifications.send_email(user_id, template, context)
    tasks.audit.cleanup_old_logs()  (Celery Beat, mensual)
```

### 4.2 Pipeline OCR

```
Flujo:
1. POST /api/v1/documents/ → crea documento
2. DocumentService dispara: process_ocr.delay(document.id)
3. Tarea Celery:
   a. Descarga archivo de MinIO/S3
   b. Si PDF: convertir páginas a imágenes (pdf2image)
   c. Tesseract OCR sobre cada página
   d. Concatenar texto extraído
   e. Actualizar document.ocr_content
   f. Actualizar document.search_vector
   g. Registrar en AuditLog
4. Documento ahora buscable por su contenido interno
```

### 4.3 Integración IA (diferenciador de portafolio)

```
Usando Claude API (Anthropic):
- Summarización automática de documentos largos
- Extracción de entidades clave (fechas, montos, nombres)
- Categorización automática sugerida

Endpoint:
    POST /api/v1/documents/{id}/analyze/
    → Dispara tarea Celery que llama Claude API
    → Guarda resultado en document.metadata['ai_analysis']

Esto es opcional pero muy diferenciador en portafolio.
```

### Entregable Fase 4
- [ ] Celery funcionando con Redis
- [ ] OCR pipeline para PDFs e imágenes
- [ ] Documentos indexados y buscables por contenido
- [ ] (Opcional) Análisis IA de documentos

---

## Fase 5 — Frontend + Deploy + Observabilidad

**Objetivo:** Frontend funcional, CI/CD, deploy en VPS, monitoring.
**Estimación:** 4–5 semanas

### 5.1 Frontend React (básico funcional)

```
Stack: React + TypeScript + Vite + Tailwind + shadcn/ui

Páginas mínimas:
- Login / Logout
- Dashboard (documentos recientes, stats básicas)
- File explorer (carpetas + documentos)
- Upload de documento
- Detalle de documento (versiones, audit trail)
- Gestión de usuarios (solo OrgAdmin)
- Búsqueda

Estado: React Query para server state, Zustand para UI state
Auth: almacenar tokens en httpOnly cookies (más seguro que localStorage)
```

### 5.2 GitHub Actions — CI/CD

```yaml
# .github/workflows/ci.yml
Pipeline:
  1. Lint (black, isort, flake8)
  2. Tests (pytest con cobertura)
  3. Build Docker image
  4. Deploy a VPS (solo en push a main)

Secrets necesarios en GitHub:
  - VPS_HOST, VPS_USER, VPS_SSH_KEY
  - DOCKER_HUB_USER, DOCKER_HUB_TOKEN (si se usa Docker Hub)
```

### 5.3 Deploy en VPS

```
Proveedor: Hetzner CX21 (~6 USD/mes) o DigitalOcean Droplet

Setup en VPS:
- Ubuntu 22.04
- Docker + Docker Compose
- Nginx como reverse proxy
- SSL con Let's Encrypt (certbot)
- docker-compose.prod.yml con todos los servicios

Stack en producción:
  nginx → gunicorn → django
  celery worker
  celery beat
  postgres (o RDS externo)
  redis
  minio (o S3)
```

### 5.4 Observabilidad

```
Sentry:
- Instalar sentry-sdk en Django
- Configurar con DSN de variable de entorno
- Error tracking automático en producción

Logging estructurado:
- JSON logs en producción
- python-json-logger
- Niveles: DEBUG (dev), INFO (prod)

Prometheus + Grafana (opcional avanzado):
- django-prometheus para métricas
- Grafana dashboard básico de requests/errores
```

### Entregable Fase 5 (proyecto completo)
- [ ] Frontend funcional y navegable
- [ ] CI/CD con GitHub Actions pasando en verde
- [ ] App desplegada en VPS con HTTPS
- [ ] Sentry configurado
- [ ] README completo con arquitectura, screenshots, y cómo correrlo
- [ ] Documentación de API (puede ser Swagger/OpenAPI automático via drf-spectacular)

---

## Reglas generales para Claude Code en cada fase

1. **Completar tests antes de avanzar** — no iniciar fase siguiente con tests en rojo
2. **Un commit por subtarea** — no acumular todo en un solo commit gigante
3. **Revisar EXPLAIN ANALYZE** al agregar índices — verificar que se usan
4. **Documentar decisiones no obvias** — comentario breve en el código si algo no es evidente
5. **Verificar aislamiento de tenant en cada feature** — test explícito de que org A no ve datos de org B
6. **Consultar este documento** antes de empezar cualquier nueva tarea

# docs/phase-plan.md — Plan de Desarrollo SasVault

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
- [x] Django corriendo y conectado a PostgreSQL
- [x] JWT auth funcional con blacklist
- [x] Multi-tenancy: Organization model + middleware
- [x] RBAC: 6 roles, permission classes en DRF
- [x] Usuarios gestionables dentro de org
- [x] Cobertura de tests > 80% en las apps de esta fase
- [x] Commit limpio con mensaje `feat: phase 1 - auth, organizations and RBAC`

---

## Fase 2 — Gestión Documental Core

**Objetivo:** Upload, almacenamiento, versionado y estructura de carpetas, con auditoría
mínima desde el primer día.
**Estimación:** 18–21 horas de trabajo efectivo (≈ 3 semanas de calendario).

### Decisiones de diseño (cerradas — no re-discutir durante la implementación)

1. **AuditLog mínimo en Fase 2.** Se crea `apps/audit/` con modelo `AuditLog` y
   `audit_service.log()`. Endpoints, filtros y permisos de lectura quedan para Fase 3.1.
   *Razón:* CLAUDE.md §9 obliga a registrar todo evento crítico desde los services. No
   se puede dejar el hook vacío sin violar la regla.
2. **Tests de StorageService → mocked primero, MinIO real después.**
   Iniciar con tests unitarios mockeando `boto3.client` (rápidos, sin dependencia
   externa). Cuando el código esté estable y haya CI configurada, añadir un set
   paralelo de tests de integración contra el bucket `saasvault-test`.
3. **Status approval queda fuera de Fase 2.**
   `Document.status` admite los 5 valores del enum, pero los services solo permiten
   transiciones manuales **draft ↔ under_review** en Fase 2. Las transiciones a
   `approved`/`rejected` se habilitarán únicamente vía WorkflowExecution en Fase 3.2.
4. **OCR async → stub en Fase 2.**
   `process_ocr.delay()` existe como Celery task vacía y se invoca vía
   `transaction.on_commit()` desde `DocumentService.create_document`. El cuerpo real
   se implementa en Fase 4.2.
5. **`AuditLog` usa BigAutoField (no UUID) y NO hereda de BaseModel.** Logs son
   inmutables (sin `updated_at`, sin `deleted_at`). Se escribe muchísimo y se lee por
   orden cronológico — un BigAutoField indexado supera al UUID v4.

### 2.0 Pre-flight — skeletons y settings

```
Tareas:
- Crear apps/audit/ y apps/documents/ con apps.py mínimos
- Registrar en INSTALLED_APPS (uncomment en base.py)
- Añadir a settings:
    MAX_UPLOAD_SIZE = 50 * 1024 * 1024   # 50MB
    ALLOWED_UPLOAD_MIME_TYPES = frozenset({...})  # ver 2.2
- config/settings/test.py: AWS_STORAGE_BUCKET_NAME = "saasvault-test"

Commit: chore(documents,audit): create app skeletons and register in INSTALLED_APPS
```

### 2.1 App: audit — modelo y service mínimo

```
Modelo AuditLog (NO hereda de BaseModel — inmutable):
    id            BigAutoField
    organization  FK → Organization (CASCADE, db_index=True)
    user          FK → User (SET_NULL, null=True, blank=True)
    entity_type   CharField(64)             ← 'document', 'folder', 'user', ...
    entity_id     CharField(64)             ← UUID en string (genérico)
    action        CharField + TextChoices   ← create, update, delete, view, download,
                                              login, logout, restore, status_change, ...
    old_values    JSONField(default=dict, blank=True)
    new_values    JSONField(default=dict, blank=True)
    ip_address    GenericIPAddressField(null=True, blank=True)
    user_agent    CharField(255, blank=True)
    metadata      JSONField(default=dict, blank=True)
    created_at    DateTimeField(auto_now_add=True)

Meta:
    db_table = "audit_logs"
    ordering = ["-created_at"]
    indexes:
        idx_audit_logs_org_created       (organization, -created_at)
        idx_audit_logs_org_entity        (organization, entity_type, entity_id)
        idx_audit_logs_org_user_action   (organization, user, action)

AuditService:
    log(organization, user, entity_type, entity_id, action,
        old_values=None, new_values=None, request=None, metadata=None) → AuditLog

Tests (~4): log con/sin user, snapshot correcto, sin updated_at expuesto.

Commits:
    feat(audit): add immutable AuditLog model and audit_service.log
    test(audit): add tests for audit service
```

### 2.2 App: documents — modelos

```
DocumentStatus (TextChoices): draft, under_review, approved, rejected, archived

Folder (hereda BaseModel):
    organization FK → Organization (CASCADE)
    name         CharField(255)
    parent       FK → self (CASCADE, null=True, blank=True, related_name="children")
    owner        FK → User (PROTECT, related_name="owned_folders")

    Meta:
        db_table = "folders"
        indexes:
            idx_folders_org_parent       (organization, parent)
            idx_folders_org_owner        (organization, owner)
        constraints:
            uq_folders_org_parent_name_alive  (UniqueConstraint con
                condition=Q(deleted_at__isnull=True))

Document (hereda BaseModel):
    organization  FK → Organization (CASCADE)
    folder        FK → Folder (SET_NULL, null=True, blank=True, related_name="documents")
    name          CharField(255)
    description   TextField(blank=True)
    mime_type     CharField(120)
    file_size     PositiveBigIntegerField()
    checksum      CharField(64)             ← sha256 hex
    storage_path  CharField(500)             ← ruta de la versión actual en MinIO
    status        CharField(20, choices=DocumentStatus, default=DRAFT)
    version       PositiveIntegerField(default=1)
    created_by    FK → User (PROTECT, related_name="created_documents")
    tags          ArrayField(CharField(50), default=list, blank=True)
    metadata      JSONField(default=dict, blank=True)
    ocr_content   TextField(blank=True)            ← se rellena en Fase 4.2
    search_vector SearchVectorField(null=True)     ← se rellena en Fase 3.3

    Meta:
        db_table = "documents"
        indexes:
            idx_documents_org_status         (organization, status)
            idx_documents_org_folder         (organization, folder)
            idx_documents_org_created        (organization, -created_at)
            idx_documents_org_checksum       (organization, checksum)
            GinIndex(search_vector)          idx_documents_search_vector
            GinIndex(metadata, jsonb_path_ops) idx_documents_metadata_gin
            GinIndex(tags)                   idx_documents_tags
        constraints:
            uq_documents_org_folder_name_alive  (UniqueConstraint condicional)

DocumentVersion (hereda BaseModel):
    document            FK → Document (CASCADE, related_name="versions")
    version_number      PositiveIntegerField()
    storage_path        CharField(500)
    file_size           PositiveBigIntegerField()
    checksum            CharField(64)
    mime_type           CharField(120)
    created_by          FK → User (PROTECT)
    change_description  CharField(500, blank=True)

    Meta:
        db_table = "document_versions"
        ordering = ["-version_number"]
        indexes:
            idx_doc_versions_doc_version    (document, -version_number)
            # Nota: Django limita nombres de índices a 30 caracteres, por eso
            # se abrevia "document_versions" a "doc_versions".
        constraints:
            uq_document_versions_doc_version_alive

Tests (~15): unique constraints respetan soft delete, Folder.clean() rechaza parent==self,
relaciones funcionan, ordering de versions descendente.

Commits:
    feat(documents): add Folder, Document, DocumentVersion models with indexes
    test(documents): add factories and model tests
```

### 2.3 File validator + Storage service

```
file_validator.py:
    ALLOWED_UPLOAD_MIME_TYPES = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/msword",
        "application/vnd.ms-excel",
        "image/jpeg",
        "image/png",
        "application/zip",
    }
    MAX_UPLOAD_SIZE = 50 * 1024 * 1024

    validate_file(file) → (detected_mime, size, sha256_hex)
        - chequea size primero (rechaza temprano)
        - lee primeros 2048 bytes → python-magic (magic numbers, NO extensión)
        - stream-read en chunks → sha256
        - file.seek(0) al terminar (importante: el archivo se subirá después)

StorageService:
    __init__: boto3.client("s3", endpoint_url, signature_version="s3v4", ...)
    ensure_bucket():  head_bucket → si 404, create_bucket   (idempotente)
    upload_file(file, path, content_type) → str
    get_presigned_url(path, expires=3600) → str
    delete_file(path) → None

    build_storage_path(org_id, document_id, filename) → str
        # {org_id}/{YYYY}/{MM}/{document_id}/{filename}

management/commands/init_storage.py:
    Llama StorageService().ensure_bucket(). Idempotente. Documentado en README.

Tests:
    file_validator (~8): tamaño, mime real vs disfrazado (.exe→.pdf), checksum estable.
    storage_service (~6) MOCKED (Fase 2):
        - boto3.client mockeado con monkeypatch
        - upload_file llama put_object con args correctos
        - get_presigned_url llama generate_presigned_url
        - delete_file llama delete_object
        - ensure_bucket: head_bucket 404 → crea
        - ensure_bucket: head_bucket 200 → no crea
    storage_service integración real (Fase 2 tarde / Fase 4):
        - fixture session-scoped que crea bucket "saasvault-test"
        - subir/leer/borrar de verdad

Commit: feat(documents): add file validator and MinIO storage service
        test(documents): add tests for validator and mocked storage service
```

### 2.4 Folder service y selector

```
FolderService:
    create_folder(organization, owner, name, parent=None) → Folder
        - valida parent.organization == organization
        - log audit CREATE
    rename_folder(organization, user, folder, new_name) → Folder
        - audit UPDATE con old/new values
    move_folder(organization, user, folder, new_parent) → Folder
        - valida new_parent.organization == organization
        - detección de ciclos (subir por .parent hasta None, no debe encontrar folder.id)
        - audit UPDATE
    soft_delete_folder(organization, user, folder) → None
        - rechaza si tiene hijos vivos o documentos vivos
        - audit DELETE
        - (cascade real → tarea Celery en Fase 4)

FolderSelector:
    get_folder_by_id(organization, folder_id) → Folder       (NotFound si no es de la org)
    get_root_folders(organization) → QuerySet
    get_children(organization, folder) → QuerySet
    get_folder_tree(organization) → list[dict]               (construcción Python sobre
                                                              .select_related("owner"))

Tests (~12 service + ~6 selector): tenant isolation, cycle detection, soft delete
con hijos vivos, N+1 en get_root_folders.

Commit: feat(documents): add FolderService, FolderSelector and tests
```

### 2.5 Document service y selector

```python
DocumentService:
    @transaction.atomic
    create_document(organization, user, file, name, folder=None,
                    description="", tags=None) → Document
        1. Validar folder.organization == organization si folder
        2. validate_file(file) → (mime, size, checksum)
        3. Crear Document (storage_path="" temporal)
        4. path = build_storage_path(org.id, doc.id, filename)
        5. storage.upload_file(file, path, content_type=mime)
        6. doc.storage_path = path; doc.save(update_fields=["storage_path"])
        7. Crear DocumentVersion(version_number=1, ...)
        8. audit_service.log(CREATE, new_values=...)
        9. transaction.on_commit(lambda: process_ocr.delay(doc.id))

    @transaction.atomic
    upload_new_version(organization, user, document, file, change_description="") → Document
        - validar, validar archivo
        - subir a path nuevo, crear DocumentVersion(v=N+1)
        - actualizar document.storage_path, document.version
        - audit UPDATE

    @transaction.atomic
    update_document_metadata(organization, user, document, **fields) → Document
        - solo name, description, tags
        - audit UPDATE

    @transaction.atomic
    change_document_status(organization, user, document, new_status) → Document
        # Fase 2: SOLO permite draft ↔ under_review
        # approved/rejected: deben ir por workflows (Fase 3.2) — rechaza con ConflictError
        - audit STATUS_CHANGE

    @transaction.atomic
    soft_delete_document(organization, user, document) → None
        - marcar deleted_at; NO eliminar de storage (housekeeping en Fase 4)
        - audit DELETE

DocumentSelector:
    get_documents(organization, folder=None, status=None, tags=None, search=None) → QuerySet
        .filter(org).select_related(folder, created_by)
        if folder:  filter(folder=folder)
        if status:  filter(status=status)
        if tags:    filter(tags__overlap=tags)
        if search:  filter(name__icontains=search)   # FTS real en Fase 3.3
    get_document_by_id(organization, document_id) → Document
    get_document_versions(organization, document) → QuerySet[DocumentVersion]

Tasks:
    tasks/document_tasks.py:
        @shared_task
        def process_ocr(document_id: str) -> None:
            # Stub vacío en Fase 2. Cuerpo real en Fase 4.2.
            logger.info("OCR stub for document %s", document_id)

Tests (~18 service + ~8 selector):
    - happy path: doc, version, audit log, on_commit hook llamado
    - archivo > 50MB → ValidationError, nada subido (transacción revertida)
    - folder de otra org → falla
    - upload falla mid-transaction → no doc en DB
    - change_status draft → under_review OK
    - change_status draft → approved → ConflictError (Fase 2 lock)
    - upload_new_version incrementa version, preserva histórica
    - soft_delete no borra del storage
    - selector N+1: assertNumQueries(2) listando 10 docs
    - selector tenant isolation

Commit: feat(documents): add DocumentService, DocumentSelector and OCR task stub
```

### 2.6 Endpoints REST

```
api/v1/folders/                                 GET, POST          IsOrganizationMember (POST: Editor+)
api/v1/folders/<uuid:folder_id>/                GET, PATCH, DELETE  (escritura: Editor+)
api/v1/folders/<uuid:folder_id>/children/       GET
api/v1/folders/<uuid:folder_id>/documents/      GET

api/v1/documents/                               GET, POST           (POST: Editor+, multipart)
api/v1/documents/<uuid:document_id>/            GET, PATCH, DELETE
api/v1/documents/<uuid:document_id>/download/   GET → presigned URL
api/v1/documents/<uuid:document_id>/versions/   GET, POST           (POST: Editor+, multipart)

Serializers:
    FolderSerializer, FolderCreateSerializer, FolderUpdateSerializer
    DocumentSerializer (read; incluye folder, created_by anidados)
    DocumentUploadSerializer (write; file + name + folder_id + description + tags)
    DocumentMetadataUpdateSerializer (write; name, description, tags, status*)
    DocumentVersionSerializer
    DocumentVersionUploadSerializer

    * status solo acepta draft ↔ under_review en Fase 2.

Todos los views decorados con @extend_schema. drf-spectacular debe seguir en 0 warnings.

Tests (~12 folders + ~15 documents): permissions por rol, envelope, paginación,
tenant isolation, multipart upload.

Commit: feat(documents): add REST endpoints for folders and documents
```

### Estrategia de tests

| Tipo                | Tests | Notas |
|---------------------|-------|-------|
| Modelos             | ~15   | constraints, soft delete |
| FileValidator       | ~8    | MIME real, size, checksum |
| StorageService      | ~6    | **mocked en Fase 2**, real después |
| FolderService       | ~12   | hierarchy, cycle, cascade, tenant |
| FolderSelector      | ~6    | tenant isolation, N+1 |
| DocumentService     | ~18   | atomicidad, on_commit, status lock |
| DocumentSelector    | ~8    | filters, tenant, N+1 |
| API Folders         | ~12   | CRUD, permisos, envelope |
| API Documents       | ~15   | upload, versions, download |
| AuditService        | ~4    | snapshots, sin user |

**Total estimado: ~104 tests** → proyecto cierra Fase 2 con ~270 tests.
Cobertura objetivo: mantener ≥ 95%.

### Riesgos conocidos

| Riesgo | Mitigación |
|--------|-----------|
| Bucket MinIO no existe en local | Comando `init_storage` + check defensivo idempotente |
| `python-magic` requiere `libmagic1` del sistema | Verificar en WSL antes (`apt list --installed`) |
| boto3 + MinIO necesita `signature_version='s3v4'` para presigned URLs | Documentado en StorageService |
| `transaction.on_commit` no dispara en tests con `@django_db(transaction=False)` | Tests del dispatch usan `transaction=True` |
| Blob huérfano si DB falla tras upload exitoso | Conocido: Fase 4 tendrá tarea `cleanup_orphan_blobs` |

### Entregable Fase 2
- [ ] AuditLog model + audit_service.log funcional
- [ ] Upload funcional a MinIO con validación de MIME real (magic numbers)
- [ ] Versionado de documentos
- [ ] Árbol de carpetas jerárquico con detección de ciclos
- [ ] Presigned URLs para descarga
- [ ] Status lock: solo draft ↔ under_review en API; approved/rejected vía workflows
- [ ] OCR task stub conectado vía `transaction.on_commit`
- [ ] Tests de upload, versionado y aislamiento de tenant
- [ ] Índices PostgreSQL aplicados (verificados con `EXPLAIN ANALYZE` antes de mergear)
- [ ] drf-spectacular schema sigue en 0 errors / 0 warnings

---

## Fase 3 — Auditoría + Workflows + FTS

**Objetivo:** Sistema de auditoría completo, motor de workflows y búsqueda full-text.
**Estimación:** 4–5 semanas

### 3.1 App: audit — endpoints y filtros

> **Nota:** el modelo `AuditLog` y `audit_service.log()` ya se construyeron en Fase 2.1.
> En esta fase se añade solo la capa de lectura (endpoints, filtros, permisos).

```
Endpoints:
    GET /api/v1/audit-logs/    → listar con filtros (entity_type, action, user, date_range)
    GET /api/v1/audit-logs/{id}/

Filtros via django-filter:
    - entity_type, entity_id
    - action
    - user (FK id)
    - created_at__gte, created_at__lte

AuditLogSelector:
    get_logs(organization, **filters) → QuerySet
    get_log_by_id(organization, log_id) → AuditLog

Permisos: solo AUDITOR, ORG_ADMIN, SUPER_ADMIN pueden leer audit logs.
Los logs siguen siendo inmutables: la API no expone POST/PATCH/DELETE.
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
    tasks.documents.cleanup_orphan_blobs()  (Celery Beat, diario — ver nota Fase 2)
    tasks.notifications.send_email(user_id, template, context)
    tasks.audit.cleanup_old_logs()  (Celery Beat, mensual)

Nota cleanup_orphan_blobs (deuda conocida de Fase 2):
    Al hacer soft-delete de un documento, el archivo en MinIO/S3 NO se elimina
    inmediatamente. Esta tarea periódica lista objetos en el bucket cuyo path
    no tiene un Document vivo correspondiente en DB y los elimina.
    Evita que el storage crezca indefinidamente con blobs huérfanos.
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

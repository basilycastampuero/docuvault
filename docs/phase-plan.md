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
2. **Tests de StorageService → mocked primero, MinIO real después. Deuda cerrada (2026-06-09).**
   La base son tests unitarios mockeando `boto3.client` (rápidos, sin dependencia
   externa). Los tests de integración reales contra MinIO se implementaron en Fase 5:
   `test_storage_integration.py` (20 tests) + `test_cleanup_integration.py` (7 tests),
   marker `@pytest.mark.integration`, requieren Docker con MinIO levantado.
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
    storage_service integración real (✅ implementado en Fase 5 — 2026-06-09):
        - fixture session-scoped que crea bucket "saasvault-test"
        - subir/leer/borrar de verdad
        - ver test_storage_integration.py y test_cleanup_integration.py

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
| StorageService      | ~6 mock + 27 integración | **mock en Fase 2**, integración real cerrada 2026-06-09 (`@pytest.mark.integration`) |
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

### Entregable Fase 2 — ✅ COMPLETADO
- [x] AuditLog model + audit_service.log funcional
- [x] Upload funcional a MinIO con validación de MIME real (magic numbers)
- [x] Versionado de documentos
- [x] Árbol de carpetas jerárquico con detección de ciclos
- [x] Presigned URLs para descarga
- [x] Status lock: solo draft ↔ under_review en API; approved/rejected vía workflows
- [x] OCR task stub conectado vía `transaction.on_commit`
- [x] Tests de upload, versionado y aislamiento de tenant
- [x] Índices PostgreSQL aplicados (verificados con `EXPLAIN ANALYZE` antes de mergear)
- [x] drf-spectacular schema sigue en 0 errors / 0 warnings

---

## Fase 3 — Auditoría + Workflows + FTS

**Objetivo:** Sistema de auditoría completo, motor de workflows y búsqueda full-text.
**Estimación:** 4–5 semanas

### 3.1 App: audit — endpoints y filtros (capa de lectura)

> **Nota:** el modelo `AuditLog` y `audit_service.log()` ya se construyeron en Fase 2.1.
> En esta fase se añade SOLO la capa de lectura (selector, serializer, endpoints,
> filtros, permisos). El modelo no se toca.

#### Decisiones cerradas (no re-discutir durante la implementación)

1. **`django-filter` para los filtros** — ya está en `requirements.txt` (24.3) y
   registrado como `DEFAULT_FILTER_BACKENDS` en `base.py`. Se usa un `FilterSet`
   explícito, no filtrado manual en la view (a diferencia de `documents`, donde el
   filtrado es manual por simplicidad). Razón: los filtros de auditoría son más ricos
   (rangos de fecha) y `django-filter` ya está disponible.
2. **PK entera, no UUID.** `AuditLog.id` es `BigAutoField`. La ruta de detalle usa
   `<int:log_id>`, NO `<uuid:...>`.
3. **API estrictamente de solo lectura.** Solo se exponen `GET`. No hay POST/PATCH/
   DELETE. Las views heredan de `APIView` con un único método `get` (mismo patrón que
   `documents`), no de un `ModelViewSet`.
4. **Leer audit logs NO genera un audit log.** Evita ruido infinito y crecimiento
   descontrolado de la tabla. El acceso de lectura a la auditoría no se audita.
5. **Permiso nuevo `CanReadAuditLogs`.** Se construye con el factory existente:
   `HasRole("auditor", "org_admin", "super_admin")`. Se combina con
   `IsOrganizationMember` en `permission_classes`. No se inventa lógica ad-hoc en la
   view.

#### Archivos a crear

```
apps/audit/selectors/__init__.py
apps/audit/selectors/audit_log_selector.py
    get_logs(organization) → QuerySet[AuditLog]
        Document.objects.filter(organization=organization).select_related("user")
        # ordering ya viene de Meta.ordering = ["-created_at"]; el FilterSet aplica el resto
    get_log_by_id(organization, log_id) → AuditLog   (NotFound si no es de la org)

apps/audit/api/__init__.py
apps/audit/api/filters.py
    class AuditLogFilter(django_filters.FilterSet):
        action        = filtro exacto (choices de AuditAction)
        entity_type   = filtro exacto
        entity_id     = filtro exacto
        user          = filtro por FK id
        created_after  = DateTimeFilter(field_name="created_at", lookup_expr="gte")
        created_before = DateTimeFilter(field_name="created_at", lookup_expr="lte")

apps/audit/api/serializers.py
    AuditLogSerializer (read-only):
        id, action, entity_type, entity_id, old_values, new_values,
        ip_address, user_agent, metadata, created_at,
        user → anidado mínimo (id, email) o user_id + user_email (SerializerMethodField)

apps/audit/api/views.py
    AuditLogListView(APIView)   GET   permission_classes = [IsOrganizationMember, CanReadAuditLogs]
        - aplica AuditLogFilter sobre get_logs(organization)
        - StandardPagination + envelope {data, meta}
        - @extend_schema con tags=["Audit"]
    AuditLogDetailView(APIView) GET   mismos permisos
        - get_log_by_id(organization, log_id) → envelope {data}

apps/audit/api/urls.py
    path("audit-logs/", AuditLogListView.as_view(), name="audit-log-list")
    path("audit-logs/<int:log_id>/", AuditLogDetailView.as_view(), name="audit-log-detail")

apps/permissions/permissions.py
    CanReadAuditLogs = HasRole(UserRole.AUDITOR, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN)
```

#### Wiring

```
config/api_urls.py → añadir:  path("", include("apps.audit.api.urls"))
                              (las rutas ya empiezan con "audit-logs/")
```

#### Tests (~14)

```
test_audit_log_selector.py (~4):
    - get_logs filtra por organization (tenant isolation: org A no ve logs de org B)
    - get_logs aplica select_related("user") → N+1 controlado (assertNumQueries)
    - get_log_by_id devuelve el log de la org
    - get_log_by_id de otra org → NotFound

test_audit_api.py (~10):
    - auditor lista logs → 200, envelope correcto, paginado
    - org_admin lista → 200
    - editor/viewer → 403
    - no autenticado → 401
    - filtro por action → solo devuelve esa acción
    - filtro por entity_type + entity_id
    - filtro por rango de fechas (created_after / created_before)
    - filtro por user
    - detalle por id → 200
    - POST/PATCH/DELETE → 405 (método no permitido)
    - tenant isolation: auditor de org A no ve log de org B (404 en detalle)
```

#### Entregable 3.1 — ✅ COMPLETADO (2026-05-30, commit 9279819)
- [x] Endpoints `GET /api/v1/audit-logs/` y `/{id}/` operativos con envelope
- [x] Filtros por action, entity, user y rango de fechas vía `django-filter`
- [x] Solo AUDITOR/ORG_ADMIN/SUPER_ADMIN pueden leer; resto 403
- [x] API de solo lectura (sin POST/PATCH/DELETE → 405)
- [x] drf-spectacular sigue en 0 errors / 0 warnings
- [x] Tests de filtros, permisos y aislamiento de tenant en verde (26 tests)

Commits sugeridos:
```
feat(permissions): add CanReadAuditLogs role permission
feat(audit): add AuditLogSelector and read-only API with filters
test(audit): add tests for audit log selector and API
```

### 3.2 App: workflows

> Esta sub-fase **desbloquea las transiciones `approved`/`rejected`** de
> `Document.status` que la Fase 2 dejó bloqueadas a propósito. Hoy
> `document_service.change_document_status` solo permite `draft ↔ under_review` y
> lanza `ConflictError` para el resto. El motor de workflows es la ÚNICA vía
> privilegiada hacia `approved`/`rejected`.

#### Pre-flight

```
- Registrar "apps.workflows" en INSTALLED_APPS (base.py) — hoy es un skeleton vacío
- Crear estructura: models/, services/, selectors/, api/, tasks/ (vacío por ahora), tests/
```

#### Decisiones cerradas (no re-discutir durante la implementación)

1. **Todos los modelos heredan de `BaseModel`** (UUID + soft delete), incluido
   `WorkflowStepLog`. Aunque `WorkflowStepLog` es append-only por convención (el service
   nunca lo actualiza), NO se replica el patrón inmutable de `AuditLog`: es dato de
   dominio, no la bitácora de auditoría. CLAUDE.md §5 obliga `BaseModel`.
2. **Workflows escribe `Document.status` directamente, NO vía `change_document_status`.**
   El guard de transiciones manuales de Fase 2 sigue intacto para la API normal. El
   `workflow_service` setea `document.status = APPROVED/REJECTED` con su propio
   `save(update_fields=...)` + `audit_service.log(STATUS_CHANGE)`. Documentar con un
   comentario por qué se omite el guard.
3. **Un documento solo puede tener UNA ejecución activa a la vez** (status
   `pending`/`in_progress`). Iniciar una segunda → `ConflictError`.
4. **`required_role` por paso** usa los mismos valores de `UserRole`. Quien avanza un
   paso debe tener exactamente ese rol (o ser ORG_ADMIN/SUPER_ADMIN, que pueden todo).
   La validación va en el service, no en la view.
5. **`config`/`actions` (JSONB) se reservan para Fase 4** (notificaciones, side-effects
   automáticos). En Fase 3.2 se persisten pero NO se interpretan. Default `dict`.
6. **`reject_workflow` se implementa como `advance_step(action=REJECTED)`**, no como
   método separado, para no duplicar lógica. Se expone igual en un endpoint claro.

#### Modelos (`apps/workflows/models/`)

```python
# enums.py
class WorkflowStatus(TextChoices):
    PENDING, IN_PROGRESS, COMPLETED, REJECTED, CANCELLED

class WorkflowStepAction(TextChoices):
    APPROVED = "approved"
    REJECTED = "rejected"
    COMMENTED = "commented"

WorkflowTemplate(BaseModel):
    organization FK → Organization (CASCADE, related_name="workflow_templates")
    name         CharField(255)
    description  TextField(blank=True)
    is_active    BooleanField(default=True)
    config       JSONField(default=dict, blank=True)
    Meta:
        db_table = "workflow_templates"
        indexes: idx_wf_templates_org_active (organization, is_active)
        constraints: uq_wf_templates_org_name_alive (org, name) WHERE deleted_at IS NULL

WorkflowStep(BaseModel):
    template       FK → WorkflowTemplate (CASCADE, related_name="steps")
    name           CharField(255)
    order          PositiveIntegerField()
    required_role  CharField(choices=UserRole.choices)
    is_final       BooleanField(default=False)
    actions        JSONField(default=dict, blank=True)
    Meta:
        db_table = "workflow_steps"
        ordering = ["order"]
        indexes: idx_wf_steps_template_order (template, order)
        constraints: uq_wf_steps_template_order_alive (template, order) WHERE alive

WorkflowExecution(BaseModel):
    organization FK → Organization (CASCADE, related_name="workflow_executions")
    template     FK → WorkflowTemplate (PROTECT, related_name="executions")
    document     FK → Document (CASCADE, related_name="workflow_executions")
    current_step FK → WorkflowStep (SET_NULL, null=True, blank=True)
    status       CharField(choices=WorkflowStatus, default=PENDING)
    started_by   FK → User (PROTECT, related_name="started_workflows")
    started_at   DateTimeField(null=True, blank=True)
    completed_at DateTimeField(null=True, blank=True)
    Meta:
        db_table = "workflow_executions"
        indexes:
            idx_wf_exec_org_status   (organization, status)
            idx_wf_exec_org_document (organization, document)
            idx_wf_exec_org_created  (organization, -created_at)
        # Una sola ejecución activa por documento se valida en el service
        # (constraint parcial con dos valores de status no es trivial; va en service).

WorkflowStepLog(BaseModel):
    execution    FK → WorkflowExecution (CASCADE, related_name="step_logs")
    step         FK → WorkflowStep (PROTECT)
    action       CharField(choices=WorkflowStepAction)
    performed_by FK → User (PROTECT, related_name="workflow_actions")
    comment      TextField(blank=True)
    Meta:
        db_table = "workflow_step_logs"
        ordering = ["created_at"]
        indexes: idx_wf_step_logs_exec_created (execution, created_at)
```

> Nota nombres de índice: Django limita a 30 chars; por eso `wf_` y abreviaturas.

#### Service (`apps/workflows/services/workflow_service.py`)

```python
@transaction.atomic
create_template(organization, user, name, description="", steps=[...]) → WorkflowTemplate
    - crea template + sus WorkflowStep en orden (valida al menos 1 paso, exactamente 1 is_final)
    - valida orders únicos y consecutivos
    - audit CREATE

@transaction.atomic
start_workflow(organization, user, document, template) → WorkflowExecution
    1. valida template.organization == organization y document.organization == organization
    2. valida template.is_active (si no → ConflictError)
    3. valida que document NO tenga ejecución activa (pending/in_progress) → ConflictError
    4. first_step = template.steps.order_by("order").first()
    5. crea WorkflowExecution(status=IN_PROGRESS, current_step=first_step, started_at=now)
    6. document.status → UNDER_REVIEW (escritura directa + audit STATUS_CHANGE)
    7. audit CREATE sobre la ejecución
    8. (Fase 4: transaction.on_commit → notificar al responsable del primer paso)

@transaction.atomic
advance_step(organization, user, execution, action, comment="") → WorkflowExecution
    1. valida execution.organization == organization
    2. valida execution.status == IN_PROGRESS (si no → ConflictError)
    3. valida rol: user.role == current_step.required_role o user es ORG_ADMIN/SUPER_ADMIN
       (si no → PermissionDenied)
    4. crea WorkflowStepLog(step=current_step, action, performed_by=user, comment)
    5. si action == REJECTED:
        execution.status = REJECTED, completed_at = now, current_step = None
        document.status → REJECTED (escritura directa + audit)
    6. si action == APPROVED:
        si current_step.is_final:
            execution.status = COMPLETED, completed_at = now, current_step = None
            document.status → APPROVED (escritura directa + audit)
        si no:
            current_step = siguiente paso por order
            (sigue IN_PROGRESS)
    7. si action == COMMENTED: solo registra el log, no cambia estado
    8. audit UPDATE/STATUS_CHANGE sobre la ejecución

reject_workflow(organization, user, execution, reason) → WorkflowExecution
    # azúcar sintáctico → advance_step(action=REJECTED, comment=reason)

@transaction.atomic
cancel_workflow(organization, user, execution) → WorkflowExecution
    - solo started_by o ORG_ADMIN+; execution.status → CANCELLED
    - el documento vuelve a DRAFT (escritura directa + audit)
```

#### Selector (`apps/workflows/selectors/workflow_selector.py`)

```python
get_templates(organization) → QuerySet[WorkflowTemplate]      # prefetch_related("steps")
get_template_by_id(organization, template_id) → WorkflowTemplate
get_executions(organization, document=None, status=None) → QuerySet[WorkflowExecution]
    .select_related("template", "document", "current_step", "started_by")
get_execution_by_id(organization, execution_id) → WorkflowExecution
get_step_logs(organization, execution) → QuerySet[WorkflowStepLog]
    .select_related("step", "performed_by")
```

#### API REST (`apps/workflows/api/`)

```
# Templates (gestión: OrgAdmin+ para escritura, cualquier miembro lee)
GET, POST           /api/v1/workflows/templates/
GET, PATCH, DELETE  /api/v1/workflows/templates/<uuid:template_id>/

# Executions
GET                 /api/v1/workflows/executions/             (filtros: document, status)
POST                /api/v1/workflows/executions/             (= start_workflow; Editor+)
GET                 /api/v1/workflows/executions/<uuid:execution_id>/
POST                /api/v1/workflows/executions/<uuid:execution_id>/advance/   (action+comment)
GET                 /api/v1/workflows/executions/<uuid:execution_id>/logs/

Serializers:
    WorkflowTemplateSerializer (read; steps anidados)
    WorkflowTemplateCreateSerializer (write; name, description, steps[])
    WorkflowStepSerializer
    WorkflowExecutionSerializer (read; template/document/current_step anidados)
    WorkflowStartSerializer (write; document_id, template_id)
    WorkflowAdvanceSerializer (write; action ∈ {approved,rejected,commented}, comment)
    WorkflowStepLogSerializer

Permisos:
    Templates escritura → IsOrganizationMember + HasRole(org_admin, super_admin)
    Start execution     → IsOrganizationMember + HasRole(editor, supervisor, org_admin, super_admin)
    Advance step        → IsOrganizationMember (el rol del paso se valida en el service)
    Lecturas            → IsOrganizationMember

Wiring: config/api_urls.py → path("workflows/", include("apps.workflows.api.urls"))
Todas las views con @extend_schema. drf-spectacular debe seguir en 0 warnings.
```

#### Flujo ejemplo

```
Draft ──start_workflow──▶ Under Review ──approve (final)──▶ Approved
                              │
                              └── reject ──▶ Rejected
                              └── cancel ──▶ Draft (execution CANCELLED)
```

#### Tests (~35)

```
test_models.py (~6):
    constraints (order único por template, name único por org alive),
    ordering de steps por order, ordering de step_logs por created_at, tenant.

test_workflow_service.py (~18):
    - create_template: crea template + steps en orden; rechaza sin is_final; rechaza orders duplicados
    - start_workflow happy path: execution IN_PROGRESS, current_step = primero, document → under_review
    - start con template inactivo → ConflictError
    - start con template de otra org → PermissionDenied/Error
    - start con ejecución activa existente → ConflictError
    - advance approve paso NO final → avanza al siguiente step, sigue in_progress
    - advance approve paso final → execution COMPLETED, document → APPROVED
    - advance reject → execution REJECTED, document → REJECTED
    - advance con rol incorrecto → PermissionDenied
    - advance con org_admin (override de rol) → permitido
    - advance sobre execution ya completada → ConflictError
    - cancel_workflow → CANCELLED, document → DRAFT
    - **document llega a approved/rejected SOLO vía workflow** (verificar que la API
      manual sigue lanzando ConflictError)
    - cada transición genera audit log
    - tenant isolation

test_workflow_selector.py (~5):
    N+1 en get_executions (assertNumQueries), tenant isolation, prefetch de steps.

test_workflow_api.py (~6+):
    permisos por rol, envelope, flujo completo start→advance→complete vía HTTP,
    advance por usuario sin rol → 403, tenant isolation.
```

#### Entregable 3.2 — ✅ COMPLETADO (2026-05-30, commit b80a43e)
- [x] 4 modelos (`WorkflowTemplate`, `WorkflowStep`, `WorkflowExecution`, `WorkflowStepLog`) con índices
- [x] `apps.workflows` registrado en INSTALLED_APPS; migración revisada a mano
- [x] `workflow_service`: create_template, update_template, soft_delete_template, start, advance, reject, cancel
- [x] Transiciones `approved`/`rejected` de `Document` funcionando SOLO vía workflow
- [x] El guard manual de Fase 2 (`change_document_status`) sigue rechazando approved/rejected
- [x] Endpoints REST con RBAC y validación de rol por paso
- [x] Todas las transiciones auditadas vía `audit_service.log`
- [x] Tests de service, selector y API en verde; tenant isolation explícito (62 tests)
- [x] drf-spectacular en 0 errors / 0 warnings (vía `ENUM_NAME_OVERRIDES`)

Commits sugeridos:
```
chore(workflows): register app and create package structure
feat(workflows): add WorkflowTemplate/Step/Execution/StepLog models with indexes
feat(workflows): add workflow_service (start, advance, reject, cancel)
feat(workflows): add workflow_selector with N+1-safe querysets
feat(workflows): add REST endpoints with role-per-step validation
test(workflows): add model, service, selector and API tests
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

#### Decisiones cerradas (no re-discutir durante la implementación)

1. **Signal `post_save`, no trigger de PostgreSQL.** El vector se reconstruye desde
   un `@receiver(post_save, sender=Document)` que hace `Document.objects.filter(pk=...)
   .update(search_vector=...)` (sin recursión: `.update()` no dispara `post_save`). Un
   trigger SQL sería más eficiente pero el signal es suficiente para el volumen actual y
   más legible. Reevaluar en Fase 4 si el OCR async escribe `ocr_content` en masa.
2. **Pesos de relevancia:** `name`=A, `description`=B, `tags`=C, `ocr_content`=D.
   `tags` es `ArrayField` → se une a string con `Value(" ".join(tags))` porque no se
   puede pasar como nombre de columna a `SearchVector`.
3. **`config="simple"`** (sin stemming) en `SearchVector` y `SearchQuery`. Decisión
   deliberada para un corpus multi-tenant que mezcla ES/EN: `simple` no asume idioma.
   El trade-off es que "contratos" no matchea "contrato". Reevaluable por-tenant a futuro.
4. **`SearchQuery(..., search_type="websearch")`** en el selector: tolera input natural
   de usuario (varias palabras, `"frase exacta"`, `-excluir`) sin operadores AND
   explícitos ni romperse con entradas inesperadas.
5. **El guard del signal solo reconstruye si cambió un campo de texto** (`name`,
   `description`, `tags`, `ocr_content`). Un save de solo `status`/`version`/
   `storage_path` no toca el vector → se evita write-amplification.
6. **Data migration de backfill** para documentos creados antes del signal. `bulk_create`
   seguiría saltándose el signal — caveat conocido para el OCR async de Fase 4.

#### Entregable 3.3 — ✅ COMPLETADO (2026-05-31, commit ec691d9)
- [x] Signal que puebla `search_vector` con pesos A/B/C/D (índice GIN ya existía)
- [x] `SearchSelector.search_documents` con `SearchQuery`/`SearchRank`, N+1-safe, filtros
- [x] `GET /api/v1/search/` con envelope `{data, meta}`, paginación, `IsOrganizationMember`
- [x] Data migration de backfill
- [x] Tenant isolation explícito en selector y API
- [x] drf-spectacular en 0 errors / 0 warnings (`DocumentStatusEnum` en overrides)
- [x] 18 tests (signal, selector, API) en verde

### Auditoría de Fase 3 — correcciones aplicadas (2026-05-31)

Tras completar 3.3 se hizo una auditoría completa de toda la Fase 3. Se encontraron y
corrigieron 3 hallazgos accionables (1 de correctitud, 2 de calidad):

1. **🔴 Race condition en `start_workflow`** (commit c9258ea). La regla "una sola
   ejecución activa por documento" se aplicaba solo con un `.exists()` no atómico → dos
   requests concurrentes podían crear dos ejecuciones activas. **Fix:** `UniqueConstraint`
   parcial `uq_wf_exec_one_active_per_document` sobre `(document)` WHERE
   `status IN (pending, in_progress) AND deleted_at IS NULL` + `try/except IntegrityError
   → ConflictError` (409 limpio). El `.exists()` queda como fast-path.
2. **🟡 `advance_step` sin lock de fila** (commit c9258ea). Dos aprobadores concurrentes
   podían leer `IN_PROGRESS` y doble-avanzar. **Fix:** `select_for_update(of=("self",))`
   al re-fetchear la ejecución (`of=self` porque `current_step` es FK nullable → LEFT JOIN,
   y Postgres prohíbe `FOR UPDATE` sobre el lado nullable de un outer join).
3. **🟡 Paginación inconsistente** (commit 6162e74). `GET /workflows/templates/` y
   `.../logs/` devolvían listas sin paginar (`meta: {}`), violando CLAUDE.md §7. **Fix:**
   `StandardPagination` en ambos.

Nota de corrección al plan original: la nota de §3.2 decía "constraint parcial con dos
valores de status no es trivial; va en service". Era incorrecta: sí es expresable con
`status__in`. El constraint es ahora el backstop race-proof.

### Entregable Fase 3 — ✅ COMPLETADO (2026-05-31)
- [x] AuditLog registrando todos los eventos críticos (3.1 + hooks de Fase 2)
- [x] Workflows funcionando con motor de templates/steps/executions (3.2)
- [x] Full-text search con ranking de relevancia (3.3)
- [x] Tests de audit, workflows y search (394 tests totales, 98% cobertura)
- [x] Auditoría de fase con correcciones de concurrencia y consistencia aplicadas

---

## Fase 4 — Procesamiento Asíncrono (Celery + OCR + IA opcional)

**Objetivo:** que un documento subido se procese en segundo plano, se le extraiga el
texto por OCR, y ese texto lo vuelva **buscable por su contenido interno** (no solo por su
nombre). Más cerrar la deuda de blobs huérfanos de Fase 2.
**Estimación:** 2–3 semanas (~30-40 tests, meta cobertura ≥ 95%).

**Por qué importa:** un pipeline async real (cola → worker → side-effects) con reintentos,
idempotencia y tareas periódicas es de los puntos que más diferencian para un junior. La
infra Celery ya existe (broker redis/1, backend redis/2, `config/celery.py`,
`autodiscover_tasks`, `CELERY_TASK_ALWAYS_EAGER=True` en tests) pero está "vacía": esta fase
la pone a trabajar. `process_ocr` ya está cableado vía `transaction.on_commit` desde
`create_document` como stub.

### Alcance cerrado (decidido antes de implementar — no re-discutir)

1. **OCR cubre solo PDF + imágenes** (Tesseract). Office (docx/xlsx/zip) → `ocr_status =
   skipped`. La extracción de texto de Office (con `python-docx`/`openpyxl`) es trabajo
   futuro, fuera de Fase 4.
2. **`ocr_status` es una columna real** (no JSONB), default `pending`. No hay re-OCR masivo
   automático de los documentos existentes (quedan en `pending`).
3. **Dev corre worker + beat en terminales del venv** (consistente con "Django en venv en
   desarrollo"). Los servicios docker-compose de worker/beat pertenecen a la compose de
   producción (Fase 5).
4. **`CELERY_BEAT_SCHEDULE` estático** en settings. `django-celery-beat` (schedules
   editables desde el admin) queda como mejora futura.
5. **OCR completion se audita** con `AuditAction.UPDATE` + `metadata={"via": "ocr"}` (sin
   añadir un valor nuevo al enum).
6. **`cleanup_orphan_blobs` mira `Document` Y `DocumentVersion`** (las versiones tienen sus
   propios blobs), con un **período de gracia** para no borrar uploads en vuelo.
7. **IA (4.4) es opcional y va al final.** Modelo Haiku 4.5 por costo, prompt caching, key
   por env (feature deshabilitada si no hay key).
8. **Notificaciones y thumbnails se difieren a Fase 5** (necesitan infra de email / UI).

### Qué falta hoy (inventario)

| Pieza | Estado | Sub-fase |
|-------|--------|----------|
| `pytesseract`, `pdf2image` (pip) | ✅ instaladas | 4.0 |
| `tesseract-ocr`, `tesseract-ocr-spa`, `poppler-utils` (apt, NO pip) | ✅ (manual) | 4.0 |
| `StorageService.download_file()` | ✅ implementado | 4.0 |
| `Document.ocr_status` | ✅ columna real | 4.2 |
| `process_ocr` cuerpo real + `ocr_service` | ✅ implementado | 4.2 |
| `CELERY_BEAT_SCHEDULE` + tareas periódicas | ✅ | 4.1 / 4.3 |
| `cleanup_orphan_blobs` (deuda Fase 2) | ✅ | 4.3 |
| `anthropic` SDK + `ai_service` | ✅ implementado | 4.4 |

### 4.0 Pre-flight (infra y dependencias)

*DoD: `celery worker` levanta y `process_ocr` (aún stub) corre en un worker real.*

```
Dependencias Python (requirements.txt):
    pytesseract        # wrapper de Python sobre el binario Tesseract
    pdf2image          # convierte páginas PDF a imágenes PIL (requiere poppler)

Dependencias de sistema (WSL Ubuntu) — gotcha: NO se instalan con pip:
    sudo apt install -y tesseract-ocr tesseract-ocr-spa poppler-utils
    (documentar en README; en prod van en el Dockerfile — Fase 5)

StorageService.download_file(path) -> bytes:
    boto3 get_object → devuelve los bytes crudos del blob. Pieza faltante
    que conecta storage ↔ OCR.

Settings nuevos (base.py, vía decouple):
    OCR_LANGUAGES = config("OCR_LANGUAGES", default="spa+eng")
    OCR_PDF_DPI   = config("OCR_PDF_DPI", default=200, cast=int)
    CELERY_TASK_DEFAULT_RETRY_DELAY, CELERY_TASK_MAX_RETRIES
    CELERY_BEAT_SCHEDULE = {}   # se puebla en 4.3

Correr en dev (terminales separadas del venv):
    celery -A config.celery worker -l info
    celery -A config.celery beat   -l info
```

#### Entregable 4.0 — ✅ COMPLETADO (2026-06-02)

Detalle de lo implementado y el porqué de cada pieza:

1. **Dependencias pip** (`requirements.txt`): `pdf2image==1.17.0` y
   `pytesseract==0.3.13`. Son wrappers Python: `pytesseract` invoca el binario
   Tesseract; `pdf2image` rasteriza páginas PDF a imágenes PIL (Tesseract no lee PDF
   nativo). Instalados en el venv y fijados con versión exacta. `pillow` ya estaba.
2. **Dependencias de sistema (apt)**: `tesseract-ocr`, `tesseract-ocr-spa`,
   `poppler-utils`. **Gotcha:** NO se instalan con pip; son binarios del SO. Sin ellos
   `pytesseract` lanza `TesseractNotFoundError` y `pdf2image` falla. No bloquean 4.0/4.1
   (el stub no los usa); son requisito de 4.2 (OCR real). Documentados en `.env.example`.
3. **`StorageService.download_file(path) -> bytes`** (`storage_service.py`): pieza
   faltante que conecta storage↔OCR. Usa `get_object` y devuelve los bytes crudos del
   blob. El OCR necesita leer el archivo desde MinIO. Test mockeado añadido
   (`test_storage_service.py`) siguiendo el patrón de Fase 2 (boto3 vía monkeypatch).
4. **Settings OCR** (`base.py`, vía `decouple`): `OCR_LANGUAGES="spa+eng"` (corpus
   multi-tenant ES/EN) y `OCR_PDF_DPI=200` (trade-off precisión/velocidad al rasterizar).
5. **Settings Celery** (`base.py`): `CELERY_TASK_DEFAULT_RETRY_DELAY=60`,
   `CELERY_TASK_MAX_RETRIES=3` (cimientos de la política de reintentos de 4.1),
   `CELERY_BEAT_SCHEDULE={}` (se puebla en 4.3) y
   `CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP=True` (mantiene el comportamiento actual
   ante el cambio de default en Celery 6.0; silencia el `CPendingDeprecationWarning`).
6. **`.env.example`**: documentadas las nuevas variables (OCR + Celery retry) con una
   nota recordando los paquetes apt requeridos.

**Verificación (DoD cumplido):** `manage.py check` sin issues; un worker Celery **real**
(`celery -A config.celery worker`) booteó contra Redis (`redis/1`), recibió un
`process_ocr.delay(...)` y ejecutó el stub con resultado `succeeded` — la fontanería
async funciona fuera del modo EAGER. Suite completa en verde: **395 tests, 99%
cobertura**. black/isort/flake8 limpios.

### 4.1 Endurecimiento de Celery

*DoD: una tarea que falla por error transitorio reintenta; una que falla por error
permanente se marca fallida sin reintentar en loop.*

```
- Política de reintentos: bind=True, autoretry_for=(TransientError,),
  max_retries, retry_backoff=True. Distinguir transitorio (timeout de storage
  → reintenta) de permanente (archivo corrupto → no reintenta, marca failed).
- Idempotencia: process_ocr seguro de correr dos veces (sobrescribe ocr_content).
  Celery puede re-entregar un mensaje.
- CLAUDE.md §12: la tarea NO tiene lógica → llama a un service. process_ocr fino,
  lógica en ocr_service.
```

#### Entregable 4.1 — ✅ COMPLETADO (2026-06-02)

Detalle de lo implementado y el porqué:

1. **`TransientError`** (`apps/core/exceptions.py`): excepción que marca un fallo
   **recuperable** (timeout de storage/red). **Deliberadamente NO hereda de
   `ApplicationError`**: nunca llega a la capa HTTP; es una señal interna para la
   política de reintentos. El `custom_exception_handler` la ignora (devuelve `None`),
   verificado en test.
2. **`process_ocr` endurecida** (`apps/documents/tasks/document_tasks.py`):
   `@shared_task(bind=True, autoretry_for=(TransientError,), retry_backoff=True,
   retry_jitter=True, retry_kwargs={"max_retries": settings.CELERY_TASK_MAX_RETRIES})`.
   - Solo reintenta ante `TransientError`; cualquier otra excepción se propaga y la
     tarea queda fallida sin reintentar (evita retry-loops con fallos permanentes).
   - `retry_backoff` exponencial + jitter para no martillar el recurso caído.
   - `max_retries` desde settings (configurable por entorno).
3. **Tarea fina → `ocr_service`** (CLAUDE.md §12): la tarea solo hace fetch del
   `Document` y delega en `ocr_service.process(document)` (imports lazy para evitar
   ciclos). `Document.DoesNotExist` → return sin reintentar (es permanente: el
   `on_commit` pudo dispararse para una transacción que hizo rollback).
4. **`ocr_service.process(document)`** (`apps/documents/services/ocr_service.py`):
   creado como stub fino y documentado como idempotente (Celery puede re-entregar).
   El cuerpo OCR real + `ocr_status` llegan en 4.2; aquí solo se establece el cableado
   y la política de reintentos, ya testeable de forma aislada.

**Nota de testing (modo eager):** con `CELERY_TASK_ALWAYS_EAGER` +
`EAGER_PROPAGATES`, una tarea eager no reintenta en bucle (no hay broker que
reprograme): `self.retry()` lanza `celery.exceptions.Retry`. Los tests verifican la
**política** (no el conteo de reintentos): `TransientError` → se lanza `Retry` (en
prod reintentaría); error permanente → se propaga tal cual sin pasar por `retry()`.

**Verificación:** suite completa en verde — **401 tests, 99% cobertura** (+6 vs 4.0:
4 de la tarea + 2 de `TransientError`). black/isort/flake8 limpios.

### 4.2 Pipeline OCR (corazón de la fase)

*DoD: subo un PDF escaneado y segundos después GET /api/v1/search/?q=<palabra del
contenido> lo encuentra.*

```
Campo nuevo Document.ocr_status (CharField + choices, migración):
    pending → processing → completed / failed / skipped
    Da observabilidad ("docs que fallaron OCR") y habilita re-procesar.
    Docs existentes quedan en 'pending' por default (sin re-OCR masivo).

ocr_service.process(document)  (apps/documents/services/ocr_service.py):
    1. ocr_status = processing
    2. blob = storage.download_file(document.storage_path)
    3. ramificar por mime_type:
       - image/jpeg, image/png → PIL.Image.open → pytesseract.image_to_string(lang=…)
       - application/pdf → pdf2image.convert_from_bytes(dpi=…) → OCR por página → concat
       - otros (docx/xlsx/zip) → ocr_status = skipped
    4. document.ocr_content = texto; ocr_status = completed
    5. document.save(update_fields=["ocr_content", "ocr_status", "updated_at"])
       → DISPARA el signal de búsqueda (ocr_content es campo de texto) →
         search_vector se reconstruye solo. CONEXIÓN CLAVE con Fase 3.3:
         el OCR alimenta la búsqueda automáticamente, sin código extra.
    6. audit_service.log(UPDATE, metadata={"via": "ocr"})

Casos borde:
    - página en blanco → ocr_content="", status completed
    - archivo corrupto → failed, sin reintento
    - timeout de storage → reintento (transitorio)

Endpoint opcional de re-OCR:
    POST /api/v1/documents/{id}/reprocess-ocr/  (Editor+) → re-dispara la tarea.
```

#### Entregable 4.2 — ✅ COMPLETADO (2026-06-02)

Detalle de lo implementado y el porqué:

1. **`Document.ocr_status`** (columna real, `OcrStatus` TextChoices: pending/processing/
   completed/failed/skipped, default `pending`). Columna real (no JSONB) porque se filtra
   y da observabilidad del pipeline (CLAUDE.md §6). Migración `0003_add_document_ocr_status`
   con default constante (operación de metadata en PG16, no reescribe tabla). Docs
   existentes quedan en `pending` (sin re-OCR masivo). Sin índice por ahora (query de baja
   frecuencia; "no índices por si acaso").
2. **`ocr_service.process(document)`** (cuerpo real): `processing` → ramifica por mime
   (imagen vía `PIL.Image.open` + `pytesseract`; PDF vía `pdf2image.convert_from_bytes`
   a `OCR_PDF_DPI` + OCR por página; resto → `skipped`) → guarda `ocr_content` +
   `completed` → audita `UPDATE` con `metadata={"via":"ocr"}` (user=None, acción de
   sistema). Idempotente (sobrescribe).
3. **Conexión clave con 3.3 (sin código de indexación):** el `save(update_fields=
   ["ocr_content", ...])` dispara el signal `post_save` de FTS → `search_vector` se
   reconstruye solo → el documento se vuelve buscable por su contenido. Las transiciones
   de solo-status (`_set_status`) usan `update_fields` sin campos de texto → el signal las
   ignora (sin write-amplification).
4. **Transitorio vs permanente** (apoya 4.1): descarga con timeout/error de red →
   `TransientError` (reintenta); blob inexistente (`NoSuchKey`/`404`/`NoSuchBucket`) →
   `failed` sin reintento; archivo corrupto (Tesseract/Pillow revienta) → `failed` sin
   reintento; página en blanco → `completed` con `ocr_content=""`.
5. **Endpoint `POST /api/v1/documents/{id}/reprocess-ocr/`** (Editor+, `202 Accepted`).
   View orquesta; lógica en `document_service.reprocess_ocr` (audita `via=ocr_reprocess`
   + `transaction.on_commit(process_ocr.delay)`).
6. **`ocr_status` expuesto** read-only en `DocumentSerializer`.

**Verificación:** 413 tests en verde (+12), 99% cobertura. drf-spectacular 0 warnings.
Smoke test con **Tesseract real** sobre una imagen generada confirma la cadena
Pillow→Tesseract→Poppler operativa end-to-end (los unit tests mockean el motor por
velocidad/determinismo). El test `test_document_is_searchable_by_ocr_content` cierra el
DoD: tras el OCR, el documento aparece en `search_documents(q=<palabra del contenido>)`.

### 4.3 Housekeeping periódico (cleanup_orphan_blobs) — Plan detallado

*DoD: soft-deleteo un documento, corre la tarea diaria, y su blob (y los de sus
versiones) desaparecen de MinIO.*

#### Decisiones cerradas (no re-discutir durante la implementación)

1. **La fuente de verdad es la DB, no el bucket.** Un blob es huérfano si su key NO
   está referenciada por NINGÚN `Document` vivo (`storage_path`, `deleted_at IS NULL`)
   NI por NINGÚN `DocumentVersion` de un documento vivo. Construir el set de paths
   vivos en memoria y restar. *Razón:* el bucket es global; la key ya incluye
   `{org_id}/...` y es única.
2. **Mirar `Document` Y `DocumentVersion`.** Al soft-deletear un documento se
   huérfanan su blob actual Y los blobs de TODAS sus versiones. *Razón:* cada versión
   tiene su propio blob (CLAUDE.md §6, deuda #5 de Fase 2).
3. **`DocumentVersion` se considera vivo solo si su `Document` padre está vivo.** Se
   filtra `DocumentVersion.objects.filter(document__deleted_at__isnull=True)`.
4. **Período de gracia de 24h vía `LastModified` del objeto S3.** `list_objects_v2`
   devuelve `LastModified` (datetime tz-aware) por objeto. NO se borra ningún blob con
   `LastModified > now - GRACE`. *Razón:* evita borrar un upload en vuelo cuyo commit
   de DB aún no es visible. Configurable: `ORPHAN_BLOB_GRACE_HOURS` (default 24) vía
   decouple.
5. **`list_objects` se añade a `StorageService`**, no se usa boto3 crudo desde el
   service de cleanup. Devuelve un iterador de `(key, last_modified)` paginado
   internamente con el `paginator` de boto3.
6. **La lógica vive en `cleanup_service`, la task es fina** (CLAUDE.md §12). La task
   Beat solo invoca `cleanup_service.delete_orphan_blobs()`.
7. **Sin tenant en la firma del cleanup.** Tarea de mantenimiento global del sistema,
   no una operación de dominio por-organización. Única excepción justificada a "todo
   recibe organization". Documentar el porqué en el docstring.
8. **Auditoría: NO se audita cada blob borrado.** No hay `organization` ni `user`
   natural (acción de sistema global). Se registra el resultado agregado con
   `logger.info` (cuántos blobs escaneados / borrados / saltados por gracia).
9. **`cleanup_old_audit_logs` queda FUERA de Fase 4.** Sensible (compliance); se
   deja documentado como trabajo futuro.

#### Piezas a implementar (rutas exactas)

```
apps/documents/storage/storage_service.py   ← añadir método list_objects()
apps/documents/services/cleanup_service.py   ← NUEVO: delete_orphan_blobs()
apps/documents/tasks/document_tasks.py        ← añadir task cleanup_orphan_blobs (fina)
config/settings/base.py                        ← ORPHAN_BLOB_GRACE_HOURS + CELERY_BEAT_SCHEDULE entry
backend/.env.example                           ← documentar ORPHAN_BLOB_GRACE_HOURS
apps/documents/tests/test_cleanup_service.py   ← NUEVO (~7 tests)
apps/documents/tests/test_document_tasks.py    ← +1 test de la task fina
```

#### Contratos

```python
# storage_service.py — nuevo método
def list_objects(self) -> Iterator[tuple[str, datetime]]:
    """Yield (key, last_modified) for every object in the bucket, paginated.

    Uses the boto3 paginator (list_objects_v2 caps each page at 1000 keys).
    last_modified is timezone-aware (UTC) as returned by S3/MinIO.
    """
    paginator = self._client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=self._bucket):
        for obj in page.get("Contents", []):
            yield obj["Key"], obj["LastModified"]
```

```python
# apps/documents/services/cleanup_service.py — NUEVO
def delete_orphan_blobs(grace_hours: int | None = None) -> dict:
    """Delete blobs in the bucket not referenced by any live Document or
    DocumentVersion. System-wide maintenance: deliberately tenant-agnostic
    (no request, no organization). Returns a summary dict for logging.

    A blob is kept if EITHER:
      - it is referenced by a live Document.storage_path, OR
      - it is referenced by a DocumentVersion.storage_path whose parent
        Document is alive, OR
      - it was modified less than grace_hours ago (upload-in-flight guard).
    """
    grace = grace_hours if grace_hours is not None else settings.ORPHAN_BLOB_GRACE_HOURS
    cutoff = timezone.now() - timedelta(hours=grace)

    live_paths: set[str] = set(
        Document.objects.values_list("storage_path", flat=True)
    )
    live_paths.update(
        DocumentVersion.objects
        .filter(document__deleted_at__isnull=True)
        .values_list("storage_path", flat=True)
    )
    live_paths.discard("")

    storage = StorageService()
    scanned = deleted = skipped_grace = 0
    for key, last_modified in storage.list_objects():
        scanned += 1
        if key in live_paths:
            continue
        if last_modified > cutoff:
            skipped_grace += 1
            continue
        storage.delete_file(key)
        deleted += 1

    summary = {"scanned": scanned, "deleted": deleted, "skipped_grace": skipped_grace}
    logger.info("cleanup_orphan_blobs: %s", summary)
    return summary
```

> **Nota de escala:** `live_paths` se materializa en memoria. Para volúmenes de
> portafolio es trivial. Si el corpus creciera a millones de blobs, la mejora sería
> barrer por prefijo `{org_id}/` y comparar contra sets por-tenant. Out of scope
> de Fase 4; dejar un comentario en el código.

```python
# apps/documents/tasks/document_tasks.py
@shared_task
def cleanup_orphan_blobs() -> dict:
    """Daily Beat task. Thin dispatcher → cleanup_service (CLAUDE.md §12)."""
    from apps.documents.services import cleanup_service
    return cleanup_service.delete_orphan_blobs()
```

#### Configuración Beat (`config/settings/base.py`)

```python
from celery.schedules import crontab

ORPHAN_BLOB_GRACE_HOURS = config("ORPHAN_BLOB_GRACE_HOURS", default=24, cast=int)

CELERY_BEAT_SCHEDULE = {
    "cleanup-orphan-blobs-daily": {
        "task": "apps.documents.tasks.document_tasks.cleanup_orphan_blobs",
        "schedule": crontab(hour=3, minute=0),  # 03:00 UTC diario
    },
}
```

> El nombre de la task es el path completo del módulo (así lo registra Celery con
> `autodiscover_tasks` sin `name=` explícito; verificar con
> `celery -A config.celery inspect registered`). En `config/settings/test.py` el
> schedule puede quedar vacío para no arrastrar Beat a los tests.

#### Algoritmo (resumen)

1. Calcular `cutoff = now - grace_hours`.
2. `live_paths` = union de `Document.storage_path` (vivos) + `DocumentVersion.storage_path` de versiones cuyo documento está vivo. Quitar `""`.
3. Por cada `(key, last_modified)` del bucket (paginado): si `key in live_paths` → conservar; elif `last_modified > cutoff` → conservar (gracia); else → `delete_file(key)`, contar.
4. Loggear `{scanned, deleted, skipped_grace}`.

#### Tests (`test_cleanup_service.py`, ~7)

`StorageService` mockeado por monkeypatch. `Document`/`DocumentVersion` reales en DB (factories + PostgreSQL).

```
- happy path: doc soft-deleted → su blob se borra; blob de doc vivo → conservado.
- versiones: doc vivo con 2 versiones → los 3 paths se conservan.
- doc soft-deleted con versiones → blobs del doc Y de sus versiones se borran.
- período de gracia: blob huérfano pero inside window → NO se borra (skipped_grace++).
- sin huérfanos: bucket == live_paths → deleted == 0.
- storage_path vacío ("") → nunca se borra accidentalmente.
- summary devuelto tiene los conteos correctos.
+1 en test_document_tasks.py: task cleanup_orphan_blobs delega en el service (mock).
```

#### DoD 4.3 — ✅ COMPLETADO (2026-06-03)

- [x] `StorageService.list_objects()` paginado, devuelve `(key, last_modified)`.
- [x] `cleanup_service.delete_orphan_blobs()` mira `Document` Y `DocumentVersion`, respeta período de gracia, tenant-agnóstico documentado.
- [x] Task Beat `cleanup_orphan_blobs` fina + entrada en `CELERY_BEAT_SCHEDULE` (diaria, 03:00 UTC).
- [x] `ORPHAN_BLOB_GRACE_HOURS` vía decouple + `.env.example`.
- [x] Tests: happy path, gracia, versiones, sin huérfanos, path vacío (~7+1).
- [x] No se audita cada borrado; resultado agregado por `logger.info`.
- [x] Verificación manual: soft-delete un doc, correr la task, el blob desaparece de MinIO.

Commits sugeridos:
```
feat(documents): add StorageService.list_objects with pagination
feat(documents): add cleanup_service.delete_orphan_blobs (orphan blob GC)
feat(documents): schedule daily cleanup_orphan_blobs Beat task
test(documents): add tests for orphan blob cleanup
```

---

### 4.4 Análisis IA con Claude API (opcional, diferenciador de portafolio) — Plan detallado

*DoD: `POST /api/v1/documents/{id}/analyze/` devuelve resumen + entidades + categoría
sugerida, guardado en `metadata["ai_analysis"]`.*

#### Decisiones cerradas (no re-discutir durante la implementación)

1. **Feature-flag por env var.** `ANTHROPIC_API_KEY` vía decouple (default `""`). Si
   está vacía, la feature está OFF: el service lanza `AIServiceUnavailable` → **503**.
   El código queda 100% implementado; el usuario activa poniendo la key. NUNCA
   hardcodear la key (CLAUDE.md §10, §16).
2. **Modelo Haiku por costo.** `ANTHROPIC_MODEL` vía decouple, default
   `claude-haiku-4-5-20251001`. Centralizado en settings (cambiar modelo = cambiar env
   var). Confirmar el ID exacto con el skill `claude-api` al implementar.
3. **Prompt caching del system prompt.** El system prompt (instrucciones de extracción +
   esquema de salida) es estable → se marca con `cache_control: {"type": "ephemeral"}`.
   El `ocr_content` va en el `user` message (variable, NO cacheado).
4. **Input truncado a `AI_MAX_INPUT_CHARS`** (default 12000 chars ≈ 3000 tokens). Si
   `ocr_content` está vacío → `ConflictError(code="AI_NO_CONTENT")` (falla rápido en el
   request, no en el worker).
5. **Salida JSON estructurada:** `{summary, entities: {dates, amounts, names}, suggested_category}`. `json.loads` del texto del modelo; si falla → `TransientError` (reintentable). Validación ligera (defaults vacíos para claves faltantes).
6. **Resultado en `metadata["ai_analysis"]`** (JSONB existente). Guardar con
   `update_fields=["metadata", "updated_at"]`. El signal FTS de 3.3 NO se dispara
   (metadata no es campo de texto indexado). Incluir `ai_analysis_at` (ISO timestamp)
   dentro del dict.
7. **Endpoint asíncrono (202), no síncrono.** `POST /analyze/` valida, dispara la task
   via `transaction.on_commit` y devuelve **202** (mismo patrón que `reprocess-ocr`).
   El resultado se consulta en `GET /documents/{id}/`.
8. **Permiso Editor+** (`IsOrganizationMember` + `_require_editor`): mismo gate que
   reprocess-ocr.
9. **Auditoría: `AuditAction.UPDATE` + `metadata={"via": "ai_analysis"}`** (sin enum
   nuevo, precedente del OCR §4.2 decisión 18). Auditado desde el service.
10. **Cliente Anthropic instanciado dentro de la función** (no a nivel de módulo) para
    que la ausencia de key no rompa imports ni tests que no tocan IA. SDK `anthropic`
    fijado en `requirements.txt`.

#### Piezas a implementar (rutas exactas)

```
backend/requirements.txt                        ← añadir anthropic (versión fijada)
config/settings/base.py                          ← ANTHROPIC_API_KEY, ANTHROPIC_MODEL, AI_MAX_INPUT_CHARS
backend/.env.example                             ← documentar las 3 vars (key vacía por defecto)
apps/core/exceptions.py                          ← AIServiceUnavailable (503, ApplicationError)
apps/documents/services/ai_service.py            ← NUEVO: analyze(document)
apps/documents/services/document_service.py       ← NUEVO: request_ai_analysis(org, user, document)
apps/documents/tasks/document_tasks.py             ← NUEVO task analyze_document (fina, reintentable)
apps/documents/api/views.py                         ← NUEVO DocumentAnalyzeView
apps/documents/api/urls.py                           ← ruta documents/<uuid>/analyze/
apps/documents/api/serializers.py                     ← AiAnalysisSerializer (read, para schema)
apps/documents/tests/test_ai_service.py               ← NUEVO (~8 tests, mock anthropic)
apps/documents/tests/test_api.py                       ← +tests del endpoint (~4)
apps/documents/tests/test_document_tasks.py             ← +1 test task fina
```

#### Diseño del service (`apps/documents/services/ai_service.py`)

```python
def analyze(document: "Document") -> dict:
    """Run Claude analysis over a document's OCR content and persist the result
    in document.metadata['ai_analysis']. Returns the analysis dict.

    Feature-flagged: raises AIServiceUnavailable (503) if ANTHROPIC_API_KEY is unset.
    Raises ConflictError if the document has no OCR content to analyze.
    Raises TransientError on a malformed model response (Celery will retry).
    """
    if not settings.ANTHROPIC_API_KEY:
        raise AIServiceUnavailable()

    content = (document.ocr_content or "").strip()
    if not content:
        raise ConflictError("Document has no OCR content", code="AI_NO_CONTENT")

    truncated = content[: settings.AI_MAX_INPUT_CHARS]

    # Instantiated here (not module-level): missing key must not break imports.
    import anthropic
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    response = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,                 # stable → cacheable
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": truncated}],
    )

    analysis = _parse_response(response)   # json.loads → TransientError si falla
    analysis["ai_analysis_at"] = timezone.now().isoformat()

    document.metadata["ai_analysis"] = analysis
    document.save(update_fields=["metadata", "updated_at"])

    audit_service.log(
        organization=document.organization,
        user=None,
        entity_type="document",
        entity_id=str(document.pk),
        action=AuditAction.UPDATE,
        metadata={"via": "ai_analysis"},
    )
    return analysis
```

```python
# _SYSTEM_PROMPT (constante de módulo, estable → cacheado en Anthropic)
# Instruye: "Eres un extractor de información. Devuelve SOLO JSON válido con
# esta forma exacta: {\"summary\": str, \"entities\": {\"dates\": [str],
# \"amounts\": [str], \"names\": [str]}, \"suggested_category\": str}.
# Sin texto fuera del JSON."

# _parse_response(response) -> dict:
#   text = response.content[0].text
#   try: data = json.loads(text)
#   except (json.JSONDecodeError, IndexError, AttributeError):
#       raise TransientError("AI returned malformed JSON")
#   normaliza: asegura claves con defaults vacíos si faltan.
```

> **Al implementar, invocar el skill `claude-api`** para confirmar la firma exacta
> de `messages.create`, el formato de `system` con `cache_control`, el acceso a
> `response.content[0].text` y el ID de modelo vigente.

```python
# document_service.request_ai_analysis(organization, user, document) -> Document
#   - chequea settings.ANTHROPIC_API_KEY → si vacío, raise AIServiceUnavailable()
#     (falla rápido en el request, no en el worker)
#   - valida que document.ocr_content no esté vacío → ConflictError AI_NO_CONTENT
#   - transaction.on_commit(lambda: analyze_document.delay(str(document.id)))
#   - return document
```

```python
# apps/documents/tasks/document_tasks.py
@shared_task(
    bind=True,
    autoretry_for=(TransientError,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": settings.CELERY_TASK_MAX_RETRIES},
)
def analyze_document(self, document_id: str) -> None:
    """Thin dispatcher → ai_service.analyze (CLAUDE.md §12)."""
    from apps.documents.models import Document
    from apps.documents.services import ai_service
    try:
        document = Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        logger.warning("analyze_document: document %s not found; skipping", document_id)
        return
    ai_service.analyze(document)
```

#### Endpoint (`POST /api/v1/documents/{id}/analyze/`)

```python
@extend_schema(tags=["Documents"])
class DocumentAnalyzeView(APIView):
    permission_classes = [IsOrganizationMember]

    @extend_schema(
        summary="Request AI analysis for a document",
        request=None,
        responses={202: DocumentSerializer},
    )
    def post(self, request, document_id) -> Response:
        FolderListCreateView._require_editor(request)
        doc = get_document_by_id(
            organization=request.organization, document_id=document_id
        )
        doc = document_service.request_ai_analysis(
            organization=request.organization, user=request.user, document=doc
        )
        return Response(
            {"data": DocumentSerializer(doc).data}, status=status.HTTP_202_ACCEPTED
        )
```

- **Quién:** Editor+ (`org_admin`, `supervisor`, `editor`).
- **Async (202):** el análisis corre en el worker; el resultado se lee en `GET /documents/{id}/` → `metadata.ai_analysis`.
- **Ruta en `urls.py`:** `documents/<uuid:document_id>/analyze/`, name `document-analyze`.
- `DocumentSerializer` ya expone `metadata`; `AiAnalysisSerializer` opcional solo para documentar el shape en drf-spectacular (0 warnings objetivo).

#### Configuración (`config/settings/base.py`)

```python
ANTHROPIC_API_KEY = config("ANTHROPIC_API_KEY", default="")
ANTHROPIC_MODEL   = config("ANTHROPIC_MODEL", default="claude-haiku-4-5-20251001")
AI_MAX_INPUT_CHARS = config("AI_MAX_INPUT_CHARS", default=12000, cast=int)
```

`.env.example`: las 3 vars con `ANTHROPIC_API_KEY=` vacío + comentario "Dejar vacía para desactivar análisis IA (devuelve 503). Completar para habilitar la feature."

#### Tests (`test_ai_service.py`, ~8) — cliente anthropic siempre mockeado

```
- happy path: analyze devuelve dict con summary/entities/suggested_category;
  metadata["ai_analysis"] persistido; ai_analysis_at presente; audit UPDATE via=ai_analysis.
- sin key (ANTHROPIC_API_KEY="") → AIServiceUnavailable.
- ocr_content vacío → ConflictError AI_NO_CONTENT.
- respuesta malformada (no-JSON) → TransientError.
- truncado: ocr_content > AI_MAX_INPUT_CHARS → cliente recibe texto truncado (assert arg).
- system prompt lleva cache_control ephemeral (assert sobre el arg de create).
- guardar metadata NO dispara signal FTS (search_vector no cambia).
- auditoría: organización correcta del documento en el AuditLog.
test_api.py (+4): editor → 202; viewer → 403; no auth → 401;
  sin key → 503 AI_SERVICE_UNAVAILABLE; tenant isolation (doc otra org → 404).
test_document_tasks.py (+1): analyze_document delega en ai_service (mock);
  doc inexistente → no-op sin error.
```

#### DoD 4.4 — ✅ COMPLETADO (2026-06-03)

- [x] `anthropic` en `requirements.txt` (versión fijada).
- [x] `AIServiceUnavailable` en `apps/core/exceptions.py` (status 503).
- [x] `ai_service.analyze`: Haiku, prompt caching, input truncado, salida JSON validada → `metadata["ai_analysis"]`.
- [x] Feature-flag: sin key → 503 `AI_SERVICE_UNAVAILABLE`. Key nunca hardcodeada.
- [x] Task `analyze_document` fina (delega en service), reintentable.
- [x] `POST /api/v1/documents/{id}/analyze/` (Editor+, 202 async).
- [x] Análisis auditado (`UPDATE` + `metadata.via=ai_analysis`).
- [x] Tests con cliente anthropic mockeado; cero llamadas reales.
- [x] drf-spectacular 0 errors / 0 warnings.
- [x] La feature activa cuando el usuario añade la key (configuración manual suya).

Commits sugeridos:
```
chore(documents): add anthropic SDK and AI settings (feature-flagged)
feat(core): add AIServiceUnavailable (503) exception
feat(documents): add ai_service.analyze with Claude + prompt caching
feat(documents): add analyze_document task and analyze endpoint
test(documents): add tests for ai_service and analyze endpoint (mocked SDK)
```

### Estrategia de tests

Como `CELERY_TASK_ALWAYS_EAGER=True`, las tareas corren síncronas. **Se mockea el motor
OCR** (no se corre Tesseract real en unit tests — lento y depende del binario):

| Grupo | Qué cubrir |
|-------|-----------|
| `ocr_service` | mock de `pytesseract.image_to_string` + `storage.download_file`; ramas por mime; update de campos; audit; **doc queda buscable tras OCR** |
| Fallos OCR | corrupto → `failed` sin reintento; status transiciona correctamente |
| `cleanup_orphan_blobs` | mock de list del bucket + docs reales; borra solo huérfanos; respeta período de gracia; considera versiones |
| IA (4.4) | mock del cliente `anthropic` |
| Integración (opcional) | 1 test con fixture de imagen real, marcado `slow`, skip si no hay binario Tesseract |

### Entregable Fase 4
- [x] Celery worker + beat operativos contra Redis
- [x] OCR pipeline para PDFs e imágenes (Office → skipped)
- [x] `Document.ocr_status` con observabilidad del pipeline
- [x] Documentos buscables por su contenido interno (OCR → search_vector automático)
- [x] `cleanup_orphan_blobs` cerrando la deuda de Fase 2 (con período de gracia)
- [x] Tareas reintentables e idempotentes
- [x] (Opcional 4.4) Análisis IA de documentos con Claude API
- [x] drf-spectacular sigue en 0 errors / 0 warnings

### Pasos futuros (post-Fase 4)
- **Fase 5:** frontend, CI/CD, deploy VPS, observabilidad (Sentry), notificaciones (email en
  workflow), thumbnails. El Dockerfile de prod debe instalar `tesseract-ocr`/`poppler-utils`.
- Extracción de texto de Office (docx/xlsx) con `python-docx`/`openpyxl`.
- `django-celery-beat` para schedules editables desde el admin.
- Flower para monitoreo del worker.

---

## Fase 5 — Frontend + CI/CD + Deploy + Observabilidad + Notificaciones

**Objetivo:** cerrar el círculo del proyecto de portafolio: una SPA React que consume la
API ya construida, un pipeline de CI que protege `main`, un despliegue real con HTTPS en un
VPS, observabilidad de producción (errores + logs + health) y la primera integración de
side-effects de workflow (email al siguiente revisor). El backend está al 100% (501 tests,
99%); esta fase NO añade dominio nuevo salvo `apps/notifications` (5.7).

**Estimación global:** 6–8 semanas de calendario. ~70–90 tests nuevos (backend
notifications + health + logging; el frontend usa Vitest + Testing Library, contados aparte
como ~40–60 tests de UI). Meta de cobertura backend: mantener ≥ 95%.

**Métricas actuales (2026-06-21):** ~526 tests backend + 163 tests frontend. Cobertura backend: 95%.

**Mapa de sub-fases:**

| Sub-fase | Área | Toca backend | Toca frontend | Toca infra |
|----------|------|:---:|:---:|:---:|
| 5.1 | Frontend setup + auth — **COMPLETA (2026-06-10)** | — | ✅ | — |
| 5.2 | Frontend gestión documental — **COMPLETA** | — | ✅ | — |
| 5.3 | Frontend workflows + auditoría — **COMPLETA (2026-06-21)** | — | ✅ | — |
| 5.4 | CI/CD GitHub Actions | ✅ (config) | ✅ (build) | — |
| 5.5 | Deploy VPS (Gunicorn+Nginx+SSL) | ✅ (settings prod) | ✅ (build estático) | ✅ |
| 5.6 | Observabilidad (Sentry, logs, health) — **COMPLETA (backend)** | ✅ | ✅ | — |
| 5.7 | Notificaciones email en workflows — **COMPLETA (2026-06-10)** | ✅ (`apps/notifications`) | — | — |

### Decisiones globales de Fase 5 (cerradas — no re-discutir durante la implementación)

1. **Monorepo, dos top-levels.** El frontend vive en `frontend/` a la altura de `backend/`
   en el repo. NO se crea repo separado. *Razón:* CI/CD y deploy coordinados, un solo
   historial, coherente con el monolito.
2. **`apps/notifications` es la ÚNICA app de dominio nueva** y ya existe como skeleton
   vacío. Notificaciones se modela como dominio (BaseModel + FK a Organization), no como
   utilidad suelta. `apps/billing` NO se toca en Fase 5 (skeleton dormido, trabajo futuro).
3. **El frontend NO obtiene su propia decisión de microservicio/BFF.** Llama directo a
   `/api/v1/`. Nginx sirve el estático y hace proxy de `/api/` al backend (mismo origen en
   prod → no hay problema de CORS en prod; CORS solo se habilita en dev para Vite).
4. **Producción usa S3 real (o MinIO containerizado), nunca el MinIO de dev** con
   credenciales `minioadmin`. Las presigned URLs ya abstraen esto vía `StorageService`.
5. **El deploy es manual-asistido por script, no GitOps automático a prod.** CI corre
   lint+test+build en cada PR; el deploy a VPS es un job disparado manualmente
   (`workflow_dispatch`) o por tag, NO en cada push a `main`. *Razón:* portafolio
   self-hosted, sin staging; evita romper la demo en vivo con un merge.
6. **Migraciones en deploy: un solo proceso las corre, los demás esperan.** `migrate` se
   ejecuta en un servicio one-shot de la compose de prod con
   `depends_on ... service_completed_successfully`, NUNCA concurrentemente desde N workers
   Gunicorn.

---

### 5.1 — Frontend: setup y autenticación

**Objetivo.** Levantar el proyecto React+TS+Vite con Tailwind y shadcn/ui, establecer la
arquitectura de carpetas, el cliente HTTP con renovación automática de JWT, y el flujo de
login + layout autenticado. Es el cimiento sobre el que se montan 5.2 y 5.3; sin esto nada
más del frontend se puede construir.

#### Decisiones cerradas

1. **Estructura feature-based**, no layer-based. Cada dominio funcional
   (`features/auth`, `features/documents`, `features/folders`, `features/workflows`,
   `features/audit`, `features/search`) agrupa sus componentes, hooks, API y tipos. *Razón:*
   espeja el monolito modular del backend (cohesión por dominio); evita carpetas
   `components/` de 80 archivos. Lo transversal va en `shared/` y `lib/`.
2. **Cliente HTTP: `axios`** (no fetch nativo). *Razón:* los interceptors de request/response
   son la forma limpia de inyectar el `Authorization` header y de implementar el refresh
   automático en 401 con cola de requests pendientes — hacerlo a mano con fetch es
   código frágil reinventado.
3. **Server state con TanStack Query v5** (`@tanstack/react-query`). Estado de servidor
   (documentos, carpetas, workflows) es cache, no estado local: Query da caching,
   invalidación, refetch y polling (necesario para `ocr_status`) gratis.
4. **UI/client state con Zustand** (solo lo mínimo: sesión de auth, estado de sidebar,
   toasts). NO meter datos de servidor en Zustand.
5. **Tokens en memoria + refresh en `localStorage`** para esta fase (NO httpOnly cookies).
   *Razón:* el backend ya emite `access`+`refresh` JSON por `/auth/login/`; el flujo
   httpOnly exigiría cambiar el backend a set-cookie y manejar CSRF. Se documenta el
   trade-off de seguridad (XSS) como deuda consciente; migrar a cookies httpOnly queda para
   Fase 6. El `access` vive en memoria (Zustand), el `refresh` en `localStorage` para
   sobrevivir reload.
6. **Routing con `react-router-dom` v6.4+ (data router, `createBrowserRouter`).** Rutas
   protegidas vía un `<ProtectedRoute>` que comprueba la sesión de Zustand y redirige a
   `/login`.
7. **El envelope `{data, meta}` del backend se desenvuelve en una capa de cliente**
   (`unwrap()` en `lib/api-client.ts`), de modo que los hooks reciben ya `data`. Los
   errores `{error: {code, message, details}}` se normalizan a una clase `ApiError`.
8. **Validación de formularios con `react-hook-form` + `zod`.** El schema zod del login y
   del upload refleja las reglas del backend (tamaño, tipo) para fallar en cliente antes de
   gastar una request.

#### Estructura de carpetas (frontend/)

```
frontend/
  index.html
  package.json
  vite.config.ts
  tsconfig.json
  tailwind.config.ts
  postcss.config.js
  components.json                       # config de shadcn/ui
  .env.development                      # VITE_API_BASE_URL=http://localhost:8000/api/v1
  .env.production                       # VITE_API_BASE_URL=/api/v1  (mismo origen vía Nginx)
  src/
    main.tsx                            # bootstrap: QueryClientProvider + RouterProvider
    App.tsx
    routes.tsx                          # createBrowserRouter, rutas públicas/protegidas
    lib/
      api-client.ts                     # axios instance + interceptors + unwrap + ApiError
      query-client.ts                   # QueryClient con defaults
      utils.ts                          # cn() de shadcn
    shared/
      components/                       # ProtectedRoute, AppLayout, Sidebar, Header, ...
      components/ui/                    # shadcn/ui generados (button, input, dialog, ...)
      hooks/                            # useDebounce, usePagination, ...
      types/                            # tipos API compartidos (Envelope, Meta, ApiError)
    features/
      auth/
        api.ts                          # login, refresh, logout, me
        store.ts                        # useAuthStore (Zustand): access en memoria, role, org
        hooks.ts                        # useLogin, useLogout, useMe (TanStack mutations/queries)
        components/LoginForm.tsx
        pages/LoginPage.tsx
        types.ts
```

#### Piezas a implementar

```
frontend/  (scaffolding via: npm create vite@latest frontend -- --template react-ts)
frontend/src/lib/api-client.ts          ← axios + refresh interceptor (cola de 401)
frontend/src/features/auth/store.ts      ← useAuthStore
frontend/src/features/auth/api.ts         ← /auth/login, /refresh, /logout, /me
frontend/src/features/auth/hooks.ts        ← useLogin, useMe (TanStack Query)
frontend/src/features/auth/pages/LoginPage.tsx
frontend/src/shared/components/ProtectedRoute.tsx
frontend/src/shared/components/AppLayout.tsx   ← grid: Sidebar + Header + <Outlet/>
frontend/src/shared/components/Sidebar.tsx      ← nav por rol (RBAC en UI: oculta lo no permitido)
frontend/src/shared/components/Header.tsx        ← user menu, logout
frontend/src/routes.tsx
frontend/src/features/auth/__tests__/         ← tests de store + interceptor (Vitest)
```

Componentes shadcn/ui a generar en 5.1: `button`, `input`, `label`, `form`, `card`,
`sonner` (toasts), `avatar`, `dropdown-menu`, `skeleton`.

#### Dependencias externas (npm)

```
react ^18.3, react-dom ^18.3, typescript ^5.6, vite ^5.4
@vitejs/plugin-react ^4.3
tailwindcss ^3.4, postcss, autoprefixer
react-router-dom ^6.26
axios ^1.7
@tanstack/react-query ^5.59
zustand ^5.0
react-hook-form ^7.53, zod ^3.23, @hookform/resolvers ^3.9
clsx, tailwind-merge, class-variance-authority, lucide-react   (deps de shadcn/ui)
# dev: vitest ^2.1, @testing-library/react ^16, @testing-library/jest-dom, jsdom, msw ^2.4
```

Backend: añadir `django-cors-headers` (~4.4) a `requirements.txt`, habilitado SOLO en
`development.py` con `CORS_ALLOWED_ORIGINS=["http://localhost:5173"]` (puerto Vite). En prod
NO se usa (mismo origen).

#### DoD — ✅ COMPLETADO (2026-06-10)

- [x] `frontend/` scaffolding corriendo: `npm run dev` sirve en `localhost:5173`.
- [x] Tailwind + shadcn/ui operativos (componentes con estilos Slate).
- [x] `api-client.ts`: inyecta `Authorization: Bearer`, y ante 401 refresca el token y
      reintenta la request original una sola vez; si el refresh falla → logout + redirect.
      Cola `isRefreshing + failedQueue` garantiza exactamente 1 refresh para N 401 concurrentes.
- [x] Login funcional contra `/api/v1/auth/login/` (backend en dev); guarda tokens.
- [x] `<ProtectedRoute>` redirige a `/login` si no hay sesión; restauración silenciosa desde
      `refreshToken` en `localStorage`. El `AppLayout` (sidebar + header) se muestra autenticado.
- [x] Logout llama `/auth/logout/` (blacklist) y limpia el estado.
- [x] CORS habilitado en `development.py`; `manage.py check` limpio; suite backend sigue
      verde tras añadir `django-cors-headers`.
- [x] Tests Vitest del store de auth (12 tests) y del interceptor de refresh (10 tests,
      incluyendo test del queue pattern concurrente). Total: 22 tests frontend en verde.
- [x] `npm run build` → 0 errores TypeScript, 0 warnings.

#### Commits sugeridos

```
chore(frontend): scaffold React+TS+Vite with Tailwind and shadcn/ui
chore(backend): add django-cors-headers enabled in development only
feat(frontend): add axios client with JWT refresh interceptor
feat(frontend): add auth store, login page and protected routing
feat(frontend): add authenticated app layout (sidebar + header)
test(frontend): add tests for auth store and refresh interceptor
```

#### Auditoría post-implementación (2026-06-15)

Revisión completa del código de 5.1 y 5.7 antes de avanzar a 5.2. Se encontraron y
corrigieron 5 hallazgos (1 HIGH, 4 IMPORTANT):

**1. [HIGH] Rehidratación de perfil en `ProtectedRoute`** (commit `f9d4eff`)
Al recargar la página, el bootstrap solo restauraba el `accessToken` pero no llamaba a
`/auth/me/` → `user` permanecía `undefined` en Zustand → `Header` sin iniciales, `Sidebar`
sin ítems con `allowedRoles`. Fix: bootstrap secuencial `refreshToken()` → `setAccessToken()`
→ `getMe()` → `setUser()`; si `getMe()` falla → `logout()`. Skeleton cubre todo el proceso.
Decisión cerrada #33 (ver CLAUDE.md §17).
Tests nuevos (+5): `ProtectedRoute.test.tsx`.

**2. [IMPORTANT] `Promise.reject` faltante en interceptor 401** (commit `f9d4eff`)
Si `originalRequest` era falsy en el response interceptor, el handler podía resolver con
`undefined` en lugar de rechazar. Fix: `return Promise.reject(parseApiError(error))`
como fallback explícito.

**3. [IMPORTANT] Doble envío concurrente en `_send` de notificaciones** (commit `cb0654d`)
Guard `if notification.status == SENT` leía sin `select_for_update` → dos workers concurrentes
podían ambos pasar el guard y enviar el mismo email. Fix: claim atómico
`UPDATE WHERE status IN (pending, failed)` + comprobación de `rowcount`. Solo el worker con
`rowcount == 1` procede al SMTP. Decisión cerrada #34 (ver CLAUDE.md §17).
Tests nuevos (+2): `test_send_concurrent_claim_sends_once`, `test_send_failure_releases_claim_for_retry`.

**4. [IMPORTANT] Mutaciones fallidas silenciosas** (commit `f9d4eff`)
`<Toaster>` montado pero sin handler global → fallos de mutación invisibles para el usuario.
Fix: `MutationCache({ onError })` en `query-client.ts`; `meta.suppressGlobalToast: true`
para mutaciones con UI de error inline. Decisión cerrada #35 (ver CLAUDE.md §17).
Tests nuevos (+2): `query-client.test.ts`.

**5. [IMPORTANT] Narrowing inseguro de `ApiError` en `LoginForm`** (commit `f9d4eff`)
Double cast `as ApiError` → si el error no era `ApiError`, accedía a `.code`/`.status`
con resultado `undefined` silencioso. Fix: `instanceof ApiError` con import de valor.
Tests nuevos (+5): `LoginForm.test.tsx`.

**Tests de rollback de workflow → notificaciones** (commit `cb0654d`)
Añadidos en `test_workflow_notifications.py`: `test_cancel_workflow_sends_no_notification`
y `test_notification_not_sent_on_rollback` (verifica que `on_commit` no dispara si la
transacción hace rollback).

**Métricas tras auditoría:** frontend 22 → 34 tests Vitest (+12). Backend ~522 → ~526 (+4).
TypeScript 0 errores. black/isort/flake8 limpios.

---

### 5.2 — Frontend: gestión documental

**Objetivo.** La parte central de la app: navegar carpetas, listar y ver documentos, subir
archivos con drag & drop y progreso, ver el estado de OCR y buscar por contenido (FTS). Es
lo que un recruiter abre primero. Depende enteramente de 5.1.

#### Decisiones cerradas

1. **Upload con `react-dropzone`** + `axios` `onUploadProgress`. La validación
   client-side (tipo MIME por extensión + tamaño ≤ 50 MB) replica
   `ALLOWED_UPLOAD_MIME_TYPES`/`MAX_UPLOAD_SIZE` del backend vía un schema zod en
   `features/documents/validation.ts`. El backend sigue siendo la autoridad (valida por
   magic bytes); la validación de cliente es UX, no seguridad.
2. **`ocr_status` se muestra con un badge** (pending=gris, processing=azul pulsante,
   completed=verde, failed=rojo, skipped=neutro). En la **vista de detalle** se hace
   **polling con TanStack Query `refetchInterval`** mientras el status sea
   `pending`/`processing` (se detiene al llegar a un estado terminal). NO se implementan
   websockets en Fase 5 (over-engineering para portafolio).
3. **Folder browser es una vista de un solo nivel con breadcrumb**, no un árbol lateral
   recursivo. *Razón:* el endpoint `/folders/{id}/children/` + `/folders/{id}/documents/`
   ya da exactamente esto; un árbol completo exigiría cargar todo o lazy-load complejo.
   Reevaluable.
4. **Descarga vía presigned URL.** El click en "descargar" llama
   `GET /documents/{id}/download/`, recibe `{url, expires_in}` y hace
   `window.open(url)` — el navegador baja directo de MinIO/S3. El frontend nunca
   streamea binario.
5. **Búsqueda global en el Header** (input con `useDebounce` de 300 ms) que navega a
   `/search?q=...`. Resultados paginados reutilizando el mismo `DocumentCard` que la lista.
   Usa `GET /api/v1/search/`.
6. **Paginación de servidor, no scroll infinito.** Componente `<Pagination>` de shadcn
   consumiendo `meta.page`/`meta.total_pages`/`meta.next`.

#### Piezas a implementar

```
frontend/src/features/folders/
  api.ts          ← list, getById, children, documentsInFolder, create, rename, move, delete
  hooks.ts        ← useFolders, useFolderChildren, useCreateFolder, ...
  components/      ← FolderBreadcrumb, FolderCard, CreateFolderDialog
  pages/FolderBrowserPage.tsx
  types.ts
frontend/src/features/documents/
  api.ts          ← list, getById, upload, uploadVersion, updateMetadata, delete, download, reprocessOcr
  hooks.ts        ← useDocuments, useDocument(polling OCR), useUploadDocument, ...
  validation.ts   ← zod schema (tipo + tamaño) compartido
  components/      ← DocumentCard, DocumentUploadDropzone, OcrStatusBadge,
                     DocumentVersionList, DocumentMetadataForm
  pages/DocumentListPage.tsx
  pages/DocumentDetailPage.tsx
  types.ts
frontend/src/features/search/
  api.ts, hooks.ts, pages/SearchPage.tsx
frontend/src/features/dashboard/
  pages/DashboardPage.tsx   ← documentos recientes + stats (cuenta por status, conteo OCR)
frontend/src/shared/components/Pagination.tsx
```

Componentes shadcn/ui adicionales: `dialog`, `badge`, `table`, `tabs`, `progress`,
`tooltip`, `select`, `breadcrumb`, `pagination`, `alert-dialog` (confirmar delete).

#### Dependencias externas (npm)

```
react-dropzone ^14.2
date-fns ^4.1           # formateo de timestamps ISO 8601
```

#### DoD

- [ ] Dashboard muestra documentos recientes y conteos por status.
- [ ] Folder browser navega carpetas con breadcrumb; crear/renombrar/borrar carpeta funciona.
- [ ] Document list paginada con filtros por status y carpeta.
- [ ] Upload drag & drop con barra de progreso real; rechaza en cliente tipo/tamaño inválido
      antes de enviar; el backend confirma con 201.
- [ ] Document detail: metadata editable, lista de versiones, subir nueva versión, descargar
      vía presigned URL, badge de `ocr_status` con polling que para en estado terminal,
      botón "reprocesar OCR" (Editor+).
- [ ] Búsqueda global desde el header con debounce; página de resultados paginada.
- [ ] La UI oculta acciones de escritura para roles `viewer`/`auditor` (RBAC en UI; el
      backend sigue siendo la autoridad real).
- [ ] Tests Vitest de: validación de upload (zod), `OcrStatusBadge`, hook de polling.

#### Mejoras post-fase (2026-07-01)

- **`FileTypeBadge`** (`features/documents/components/FileTypeBadge.tsx`): badge coloreado
  que mapea `document.mime_type` a una etiqueta corta (PDF=rojo, imágenes=azul cielo,
  DOCX=índigo, XLSX/CSV=esmeralda, PPTX=naranja, TXT/desconocido=gris). Cubre tipos MIME
  largos de Office (e.g. `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
  → "DOCX"). Se renderiza en `DocumentCard` junto a los badges de status y OCR.
- **Fix overflow en `DocumentCard`** (`features/documents/components/DocumentCard.tsx`):
  añadidos `overflow-hidden` en `<Card>` y `min-w-0 flex-1` en el contenedor interno
  para completar la cadena de truncado. Los nombres de archivo largos ahora se cortan con
  `…` en lugar de desbordar el borde de la tarjeta.

#### Commits sugeridos

```
feat(frontend): add folder browser with breadcrumb navigation
feat(frontend): add document list and detail pages
feat(frontend): add drag-and-drop upload with client validation and progress
feat(frontend): add OCR status badge with detail polling
feat(frontend): add global search and results page
feat(frontend): add dashboard with recent documents and stats
test(frontend): add tests for upload validation and OCR polling
```

---

### 5.3 — Frontend: workflows y auditoría

**Objetivo.** Exponer en la UI el motor de workflows (templates, ejecuciones, avanzar/
aprobar/rechazar) y la consola de auditoría filtrable. Cierra la cobertura de la API en el
frontend. Opcionalmente, el panel de análisis IA. Depende de 5.1 y 5.2.

#### Decisiones cerradas

1. **El builder de templates es un formulario de pasos dinámico** (`useFieldArray` de
   react-hook-form): añadir/quitar pasos, cada uno con `name`, `order` (auto), `required_role`
   (select de roles), `is_final` (checkbox). Validación zod: exactamente un `is_final`,
   orders consecutivos — mismas reglas que `create_template` del backend.
2. **La acción de avanzar paso usa un `<AlertDialog>`** con select de acción
   (`approved`/`rejected`/`commented`) y textarea de comentario → `POST .../advance/`. El
   frontend NO decide si el usuario tiene el rol del paso; manda la request y muestra el 403
   del backend como toast si no le corresponde (el backend es la autoridad).
3. **La auditoría es una tabla server-side filtrable** (`action`, `entity_type`,
   `entity_id`, `user`, `created_after`/`created_before`) reutilizando los query params de
   `django-filter` ya existentes. Solo visible para `auditor`/`org_admin`/`super_admin` (la
   ruta se oculta del sidebar y se protege; el backend devuelve 403 igualmente).
4. **El panel de IA (opcional) dispara `POST /documents/{id}/analyze/`** y, como es async
   (202), hace polling de `GET /documents/{id}/` hasta que aparezca `metadata.ai_analysis`,
   mostrando summary/entities/suggested_category. Si el backend devuelve 503
   (`AI_SERVICE_UNAVAILABLE`), la UI muestra "Análisis IA no habilitado" y oculta el botón.

#### Piezas a implementar

```
frontend/src/features/workflows/
  api.ts          ← templates CRUD, executions list, start, advance, logs
  hooks.ts
  components/     ← WorkflowTemplateForm (useFieldArray), WorkflowStepEditor,
                    ExecutionStatusBadge, AdvanceStepDialog, WorkflowStepLogTimeline
  pages/WorkflowTemplatesPage.tsx
  pages/WorkflowTemplateDetailPage.tsx
  pages/WorkflowExecutionsPage.tsx
  pages/WorkflowExecutionDetailPage.tsx
  types.ts
frontend/src/features/audit/
  api.ts, hooks.ts
  components/AuditLogFilters.tsx, AuditLogTable.tsx
  pages/AuditLogPage.tsx
  types.ts
frontend/src/features/documents/components/AiAnalysisPanel.tsx   (opcional)
```

Componentes shadcn/ui adicionales: `textarea`, `checkbox`, `popover`, `calendar`
(date range para auditoría), `accordion`, `separator`.

#### Dependencias externas (npm)

Ninguna nueva más allá de las de 5.1/5.2 (el date picker usa `calendar` de shadcn + date-fns).

#### DoD — ✅ COMPLETADO (2026-06-21)

- [x] Listar/crear/ver templates de workflow con el builder de pasos dinámico; validación
      de "exactamente un paso final" y orders consecutivos en cliente.
- [x] Listar ejecuciones con filtro por estado/documento; ver detalle con timeline de logs.
- [x] Avanzar paso (approve/reject/comment) desde la UI; el 403 por rol incorrecto se
      muestra como toast.
- [x] Iniciar workflow sobre un documento desde su detalle (Editor+).
- [x] Consola de auditoría con tabla filtrable por acción/entidad/usuario/rango de fechas;
      visible solo para roles autorizados.
- [x] (Opcional) Panel de IA: dispara análisis, hace polling y muestra el resultado; oculto
      si el backend responde 503.
- [x] Tests Vitest del `WorkflowTemplateForm` (validación de pasos) y de los filtros de
      auditoría.

**Métricas 5.3:** 163 tests frontend (89 preexistentes + 74 nuevos en 5.3). Backend ~526 sin cambios.

**Deuda conocida (no bloqueante):**
- Páginas de lista de templates/ejecuciones muestran solo la primera página (backend soporta paginación; componente `<Pagination>` listo; aplazado).
- Bundle ~790KB sin code-splitting; se optimiza en 5.5.

#### Commits sugeridos

```
feat(frontend): add workflow templates pages with dynamic step builder
feat(frontend): add workflow executions list, detail and advance dialog
feat(frontend): add audit log console with server-side filters
feat(frontend): add AI analysis panel (optional, hidden when disabled)
test(frontend): add tests for workflow template form and audit filters
```

---

### 5.4 — CI/CD con GitHub Actions

**Objetivo.** Un pipeline que en cada PR garantice que el backend pasa lint+tests contra
PostgreSQL real y que el frontend compila y pasa sus tests, de modo que `main` nunca reciba
código roto. El deploy se separa en un workflow manual (ver 5.5).

#### Decisiones cerradas

1. **Dos jobs paralelos: `backend` y `frontend`.** No se bloquean entre sí; ambos deben
   pasar para mergear (branch protection en `main` exige ambos checks).
2. **El job backend levanta PostgreSQL 16 y Redis 7 como `services` del runner** (no
   docker-compose). *Razón crítica:* CLAUDE.md §6 y §11 exigen tests contra PostgreSQL
   real, NUNCA SQLite. Se usa `DJANGO_SETTINGS_MODULE=config.settings.test` apuntando a la
   DB `test_saasvault_db` del service. `CELERY_TASK_ALWAYS_EAGER=True` evita necesitar un
   worker en CI. MinIO NO se levanta: los tests de storage están mockeados (decisión de
   Fase 2).
3. **`libmagic1`, `tesseract-ocr`, `tesseract-ocr-spa`, `poppler-utils` se instalan con
   `apt` en el runner** antes de pytest. *Razón:* `python-magic` y el OCR los requieren; sin
   ellos la colección de tests falla en import. (Los unit tests de OCR mockean el motor,
   pero el import de `pytesseract`/`pdf2image` necesita los binarios presentes para no
   romper otras suites — instalar es lo más simple y robusto.)
4. **Cobertura: `pytest --cov` con `--cov-fail-under=95`.** El pipeline FALLA si la
   cobertura baja del umbral. Se sube el reporte a **Codecov** (gratis para repos públicos,
   badge directo).
5. **Triggers:** `on: pull_request` hacia `main` y `develop`, y `on: push` a `develop`. El
   push a `main` NO dispara deploy automático (decisión global #5). El deploy es un workflow
   aparte con `workflow_dispatch`.
6. **Secrets de CI mínimos.** Las credenciales de la DB de test son del service del runner
   (no secretos reales). Solo se necesita `CODECOV_TOKEN` (y para repos públicos ni eso). Se
   usa un `.env.ci` generado en el step, no el `.env` real.
7. **Caching:** `actions/setup-python` con `cache: pip` y `actions/setup-node` con
   `cache: npm` para acelerar.

#### Piezas a implementar

```
.github/workflows/ci.yml          ← jobs: backend (lint+test+cov), frontend (lint+typecheck+test+build)
.github/workflows/deploy.yml       ← workflow_dispatch (ver 5.5): SSH al VPS y redeploy
backend/pyproject.toml             ← asegurar addopts con --cov y --cov-fail-under=95 (si no están)
frontend/package.json              ← scripts: lint (eslint), typecheck (tsc --noEmit), test (vitest run), build (tsc && vite build)
README.md                          ← badge de CI + badge de cobertura (Codecov)
```

Esqueleto del job backend (referencia, no copiar literal):

```yaml
jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env: { POSTGRES_DB: test_saasvault_db, POSTGRES_USER: saasvault_user, POSTGRES_PASSWORD: ci_pass }
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U saasvault_user" --health-interval 10s
          --health-timeout 5s --health-retries 5
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.13", cache: pip }
      - run: sudo apt-get update && sudo apt-get install -y libmagic1 tesseract-ocr tesseract-ocr-spa poppler-utils
      - run: pip install -r backend/requirements.txt
      - run: black --check . && isort --check-only . && flake8 .
        working-directory: backend
      - run: pytest --cov --cov-fail-under=95 --cov-report=xml
        working-directory: backend
        env:
          DJANGO_SETTINGS_MODULE: config.settings.test
          DB_HOST: localhost
          # ... resto de env de DB/redis apuntando a los services
      - uses: codecov/codecov-action@v4
```

#### Dependencias externas

```
GitHub Actions: actions/checkout@v4, setup-python@v5, setup-node@v4, codecov/codecov-action@v4
npm (dev): eslint ^9, @typescript-eslint/*, eslint-plugin-react-hooks
```

#### DoD

- [x] `ci.yml` corre en cada PR a `main`/`develop`; ambos jobs (backend, frontend) en verde.
- [x] Backend testea contra PostgreSQL 16 + Redis 7 reales como services del runner.
- [x] Lint backend (black/isort/flake8) y frontend (eslint + `tsc --noEmit`) como gate.
- [x] El pipeline falla si la cobertura baja de 95%.
- [x] `vite build` produce el bundle de producción sin errores de tipos.
- [ ] Branch protection en `main` exige los dos checks verdes antes de mergear.
- [x] Badges de CI y cobertura visibles en el README.

#### Entregable 5.4 — COMPLETADO (2026-06-29)
- [x] ci.yml con jobs paralelos backend + frontend en verde
- [x] Backend testea contra PostgreSQL 16 + Redis 7 reales como services del runner
- [x] Lint backend (black/isort/flake8) y frontend (eslint + tsc --noEmit) como gate
- [x] pytest -m "not integration" con gate --cov-fail-under=95 (addopts)
- [x] vite build sin errores de tipos
- [x] deploy.yml scaffold para Fase 5.5
- [x] Badges CI + Codecov en README
- [ ] Branch protection en main — pendiente (requiere primer run verde en GitHub)

#### Commits sugeridos

```
ci: add GitHub Actions pipeline (backend tests on real Postgres, frontend build)
ci: enforce 95% coverage gate and upload to Codecov
chore(frontend): add eslint, typecheck and test npm scripts
docs: add CI and coverage badges to README
```

---

### 5.5 — Deploy en VPS (producción)

**Objetivo.** Poner la app accesible públicamente con HTTPS: Nginx como reverse proxy +
servidor del estático del frontend, Gunicorn sirviendo Django, worker y beat de Celery,
PostgreSQL/Redis y storage. Una compose de producción distinta de la de dev.

#### Decisiones cerradas

1. **VPS Ubuntu 22.04 (Hetzner CX22 o DigitalOcean, ~5–6 USD/mes), Docker + Compose.**
2. **`docker-compose.prod.yml` separado** del `docker-compose.yml` de dev. Servicios:
   `nginx`, `web` (Gunicorn+Django), `worker` (Celery), `beat` (Celery beat), `postgres`,
   `redis`, `minio`, y un servicio one-shot `migrate`. El `web` NO corre migraciones.
3. **Un Dockerfile multi-stage para el backend** (`backend/Dockerfile`): stage builder
   instala deps de build, stage runtime instala los binarios apt
   (`libmagic1 tesseract-ocr tesseract-ocr-spa poppler-utils`), copia el venv, corre como
   usuario no-root, `CMD` = gunicorn. El mismo image lo usan `web`, `worker`, `beat` y
   `migrate` (cambia el `command`).
4. **El frontend se compila en su propio `frontend/Dockerfile` multi-stage** (build stage
   Node → artefactos `dist/` copiados al contexto del servicio nginx). Un solo Nginx sirve
   estático + proxy.
5. **Nginx**: sirve `/` (SPA, con `try_files ... /index.html` para el router del cliente) y
   hace `proxy_pass` de `/api/`, `/admin/`, `/static/` (Django admin) al `web:8000`.
   Certbot/Let's Encrypt para SSL. HTTP→HTTPS redirect. Mismo origen → sin CORS en prod.
6. **`config/settings/production.py` endurecido:** `DEBUG=False`,
   `ALLOWED_HOSTS` desde env, `SECURE_SSL_REDIRECT=True`, `SECURE_HSTS_SECONDS`,
   `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE=True`, `SECURE_PROXY_SSL_HEADER`
   (porque está detrás de Nginx), `CONN_MAX_AGE=60`, JWT access de 15 min (vs 60 en dev),
   storage apuntando a S3/MinIO de prod. Todo vía `python-decouple`, NADA hardcodeado.
7. **Migraciones seguras (decisión global #6):** el servicio `migrate` corre
   `python manage.py migrate --noinput` y termina; `web`/`worker`/`beat` dependen de él
   (`depends_on: migrate: condition: service_completed_successfully`). Para columnas NOT
   NULL en tablas grandes se mantiene el patrón de 3 migraciones (CLAUDE.md §6); no aplica a
   ninguna migración existente.
8. **Backup de DB básico:** un servicio/cron `pg_dump` diario comprimido a un volumen (o a
   un bucket S3 con `aws s3 cp`), con retención de 7 días. Script `scripts/backup_db.sh`
   documentado. Restore documentado en README. (Backups gestionados/PITR = trabajo futuro.)
9. **`collectstatic` para el admin de Django** se corre en el entrypoint del `migrate`
   (one-shot), sirviendo `/static/` desde Nginx.

#### Piezas a implementar

```
backend/Dockerfile                     ← multi-stage; runtime con tesseract/poppler/libmagic; gunicorn
backend/entrypoint.sh                   ← opcional: collectstatic + arranque (sin migrate en web)
frontend/Dockerfile                     ← multi-stage node build → dist/
docker-compose.prod.yml                 ← nginx, web, worker, beat, postgres, redis, minio, migrate
nginx/nginx.conf                         ← (dir ya existe) SPA + proxy /api /admin /static; SSL; HTTP→HTTPS
backend/.env.production.example          ← plantilla de env de prod (sin secretos reales)
scripts/backup_db.sh                     ← pg_dump diario comprimido + retención
scripts/deploy.sh                        ← pull, build, migrate one-shot, up -d, prune (idempotente)
.github/workflows/deploy.yml             ← workflow_dispatch: SSH al VPS → scripts/deploy.sh
README.md                                 ← sección "Deploy" (provisión VPS, DNS, certbot, env)
```

Variables de entorno de producción (qué cambia respecto a dev):

```
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<secreto fuerte real>
ALLOWED_HOSTS=saasvault.tudominio.com
DB_HOST=postgres            # nombre del servicio en la compose
DB_PASSWORD=<fuerte>
REDIS_URL=redis://redis:6379/0
# Storage: S3 real o MinIO de prod (NUNCA minioadmin/minioadmin)
AWS_ACCESS_KEY_ID=<real>  AWS_SECRET_ACCESS_KEY=<real>
AWS_STORAGE_BUCKET_NAME=saasvault-prod  AWS_S3_ENDPOINT_URL=<S3 o MinIO prod>
JWT_ACCESS_LIFETIME_MIN=15
SENTRY_DSN=<de 5.6>
ORPHAN_BLOB_GRACE_HOURS=24
# Email (de 5.7): EMAIL_BACKEND, SENDGRID/SMTP creds
```

#### Dependencias externas

```
pip: gunicorn (~23.0)
sistema (en el VPS): docker, docker compose, certbot (vía contenedor o host)
infra: dominio + registro DNS A → IP del VPS; cuenta S3 o MinIO de prod
```

#### DoD

#### Entregable 5.5 — COMPLETADO (2026-06-29)
- [x] `backend/Dockerfile` multi-stage con tesseract/poppler/libmagic; usuario no-root
- [x] `frontend/Dockerfile` con build Node → nginx:stable-alpine
- [x] `docker-compose.prod.yml` con 8 servicios y migrate one-shot
- [x] Nginx: SPA fallback, proxy /api/ /admin/ /static/, HTTPS self-signed, 50m upload limit
- [x] `production.py`: `SECURE_PROXY_SSL_HEADER`, `CONN_MAX_AGE`, `DEBUG=False`, cookies seguras
- [x] `scripts/deploy.sh` idempotente; `scripts/backup_db.sh` con retención 7 días
- [x] `deploy.yml` con SSH dispatch (appleboy/ssh-action)
- [x] `docs/deploy-guide.md`: guía educativa completa (10 secciones)
- [ ] Deploy en VPS real — pendiente de provisionar servidor
- [ ] Secrets VPS en GitHub Actions — pendiente

#### Commits sugeridos

```
chore(backend): add gunicorn and multi-stage Dockerfile with OCR system deps
chore(frontend): add multi-stage Dockerfile producing production bundle
feat(deploy): add docker-compose.prod.yml with web/worker/beat/migrate services
feat(deploy): add Nginx reverse proxy config with SPA fallback and TLS
feat(deploy): harden production settings (HTTPS, secure cookies, proxy header)
feat(deploy): add db backup and idempotent deploy scripts
ci: add manual deploy workflow (workflow_dispatch over SSH)
docs: document VPS provisioning, DNS, certbot and production env
```

---

### 5.6 — Observabilidad

**Objetivo.** Saber qué pasa en producción: errores capturados con contexto (Sentry, back y
front), logs estructurados en JSON, y un health check que verifique DB, Redis y storage para
monitoreo externo / load balancer.

#### Decisiones cerradas

1. **Sentry en backend vía `sentry-sdk[django]`** con `DjangoIntegration` +
   `CeleryIntegration`. DSN por env (`SENTRY_DSN`, vacío = desactivado, igual que la feature
   IA). `traces_sample_rate` bajo (0.1) para performance sin coste. `send_default_pii=False`
   (no filtrar datos de tenant a Sentry). Se inicializa SOLO en `production.py`.
2. **Sentry en frontend vía `@sentry/react`** con DSN por env (`VITE_SENTRY_DSN`). Captura
   errores de render (ErrorBoundary) y de las mutaciones. Solo activo en el build de prod.
3. **`scrubbing` de datos sensibles:** se configura `before_send` para no enviar el
   `Authorization` header ni el body de `/auth/`. *Razón:* CLAUDE.md §10/§16 — nunca exponer
   credenciales; Sentry es un tercero.
4. **Logging estructurado JSON en producción** con `python-json-logger`. En dev sigue el
   formato legible actual. Cada log lleva, cuando hay request, `organization_id`, `user_id`,
   `request_id` (un filtro de logging que lee del contexto del middleware de tenant). NUNCA
   `print()` (CLAUDE.md §16). El `JSONFormatter` se añade al `LOGGING` de `production.py`;
   `base.py` ya tiene logging configurado.
5. **Health check en `apps/core`** (no es dominio, es infraestructura): un service ligero
   que hace `SELECT 1` (DB), `PING` (Redis) y `head_bucket` (storage), con timeout corto.
   Endpoint `GET /api/v1/health/` **público (AllowAny)** y **NO auditado** (lo llama el load
   balancer/uptime monitor sin token). Devuelve `200` si todo ok, `503` si algún componente
   falla, con `{data: {database, redis, storage}}` por componente. NO usa el envelope de
   error estándar para el 503 (es un health check, no un error de negocio) — devuelve el
   detalle por componente. Documentar esta excepción al envelope.
6. **El health check NO cuenta para el aislamiento de tenant** porque no toca datos de
   dominio (solo conectividad). Excepción justificada a "todo recibe organization", como
   `cleanup_orphan_blobs`.

#### Piezas a implementar

```
backend/requirements.txt                 ← sentry-sdk[django], python-json-logger
config/settings/production.py             ← sentry_sdk.init(...) + LOGGING con JSONFormatter
config/settings/base.py                    ← (si hace falta) filtro de logging request-context
apps/core/services/health_service.py        ← NUEVO: check_health() -> dict (db, redis, storage)
apps/core/api/health_view.py                  ← NUEVO: HealthCheckView (AllowAny, GET)
config/api_urls.py                              ← path("health/", HealthCheckView.as_view())
apps/core/logging.py                             ← JSONFormatter + RequestContextFilter
apps/core/tests/test_health.py                    ← NUEVO (~6 tests)
frontend/src/lib/sentry.ts                          ← init @sentry/react (prod only)
frontend/src/shared/components/ErrorBoundary.tsx
```

Contrato del health service:

```python
# apps/core/services/health_service.py
def check_health() -> dict:
    """System-wide connectivity check (db, redis, storage). Tenant-agnostic:
    no request, no organization (it runs before/without auth). Returns a dict
    {"database": bool, "redis": bool, "storage": bool}. Never raises."""
```

#### Dependencias externas

```
pip: sentry-sdk[django] (~2.14), python-json-logger (~2.0)
npm: @sentry/react ^8.30
infra: cuenta Sentry (free tier) → 2 DSN (backend, frontend)
```

#### DoD

- [x] `GET /api/v1/health/` devuelve 200 con `{database, redis, storage}` cuando todo está
      sano; 503 si algún componente falla; público y no auditado.
- [x] Sentry backend captura una excepción no manejada en prod con contexto (sin PII, sin
      Authorization header); desactivado si `SENTRY_DSN` vacío.
- [ ] Sentry frontend captura un error de render vía ErrorBoundary; desactivado sin DSN.
      *(pendiente: parte frontend se implementa en 5.1)*
- [x] Logs en JSON en producción con `organization_id`/`user_id`/`request_id` cuando aplica;
      formato legible en dev.
- [x] Tests del health service (db/redis/storage ok → 200; cada componente caído → 503) y de
      que el endpoint no requiere auth ni genera audit log.

#### Commits sugeridos

```
feat(core): add health check endpoint (db, redis, storage)
feat(observability): add structured JSON logging with request context in production
chore(observability): integrate Sentry in Django and Celery (DSN-gated)
feat(frontend): add Sentry and error boundary (production only)
test(core): add tests for health check service and endpoint
```

---

### 5.7 — Notificaciones por email en workflows

**Objetivo.** El primer side-effect real del motor de workflows: cuando una ejecución avanza
a un nuevo paso, notificar por email al/los usuario(s) que deben actuar (los del
`required_role` del nuevo paso). Cierra el placeholder de Fase 3.2 (decisión #5: "config/
actions JSONB reservado para notificaciones de Fase 4/5") y de Fase 4 (notificaciones
diferidas a Fase 5).

#### Decisiones cerradas

1. **`apps/notifications` se modela como dominio** (existe como skeleton). Modelo
   `Notification(BaseModel)` con FK obligatoria a `Organization`, `recipient` (FK User),
   `channel` (`email` por ahora; choices extensible), `subject`, `body`, `status`
   (`pending`/`sent`/`failed`), `sent_at`, `metadata` (JSONB: p.ej.
   `{"execution_id", "step_id"}`). *Razón:* tener registro auditable de qué se notificó a
   quién; no es solo "mandar un email y olvidar".
2. **El envío va en una tarea Celery** (`apps/notifications/tasks/notification_tasks.py`),
   disparada vía `transaction.on_commit` desde `workflow_service.advance_step`/
   `start_workflow` — NUNCA bloquea el request (CLAUDE.md §6, §12). La tarea es fina y
   delega en `notification_service`.
3. **El destinatario del nuevo paso** se resuelve por rol: los usuarios vivos de la
   organización cuyo `role == nuevo_step.required_role`. Se notifica al `required_role`
   exacto del paso (NO se spamea a org_admin/super_admin por su override). Un selector
   nuevo en `apps/notifications` resuelve los destinatarios filtrando por `organization`
   (tenant-safe).
4. **`workflow_service` NO importa el envío de email directamente**; encola el evento
   llamando a `notification_service.notify_step_assigned(...)` que crea el `Notification`
   (status `pending`) y programa la task. *Razón:* desacoplar el motor de workflow del
   detalle de transporte (email hoy, in-app/push mañana). El acoplamiento es vía service,
   no vía import del backend de email.
5. **`EMAIL_BACKEND` por entorno:** dev → `console.EmailBackend` (imprime el email en la
   terminal, cero credenciales); test → `locmem` (Django lo testea en `mail.outbox`);
   producción → SMTP de SendGrid (`smtp.sendgrid.net`, API key por env). Todo por
   `python-decouple`; NADA hardcodeado.
6. **Template HTML básico** en `apps/notifications/templates/notifications/` renderizado
   con `django.template` (`render_to_string`), con versión texto plano de fallback
   (`EmailMultiAlternatives`). Branding mínimo, link al documento/ejecución.
7. **Idempotencia y reintentos:** la task usa `autoretry_for` con el error transitorio de
   SMTP, `max_retries` desde settings. Marcar `Notification.status=sent` solo tras envío
   exitoso; si falla definitivamente → `failed` (observable). No reenviar una notificación
   ya `sent` (guard en el service).
8. **NO se notifica en reject/cancel/complete en Fase 5** (solo "te asignaron un paso").
   Notificar al iniciador en estados terminales = mejora incremental futura, para no
   inflar el alcance.

#### Piezas a implementar

```
config/settings/base.py / production.py     ← EMAIL_BACKEND + SMTP/SendGrid por entorno; DEFAULT_FROM_EMAIL
config/settings/test.py                       ← EMAIL_BACKEND = locmem
backend/.env.example / .env.production.example ← vars de email (SENDGRID_API_KEY, EMAIL_HOST, ...)
apps/notifications/apps.py + registro en INSTALLED_APPS
apps/notifications/models/notification.py      ← Notification(BaseModel) + índices (org, recipient, status)
apps/notifications/services/notification_service.py  ← notify_step_assigned(), _send(notification)
apps/notifications/selectors/notification_selector.py ← get_recipients_for_role(organization, role)
apps/notifications/tasks/notification_tasks.py        ← send_notification (fina → service)
apps/notifications/templates/notifications/step_assigned.html (+ .txt)
apps/workflows/services/workflow_service.py     ← on_commit hooks en start_workflow / advance_step
apps/notifications/tests/test_notification_service.py  ← (~8)
apps/notifications/tests/test_notification_tasks.py     ← (~2)
apps/workflows/tests/test_workflow_service.py            ← +tests: avanzar paso encola notificación
```

Índices de `Notification`:

```
idx_notifications_org_recipient   (organization, recipient)
idx_notifications_org_status      (organization, status)
```

#### Dependencias externas

```
pip: ninguna nueva obligatoria (Django email + smtplib bastan; SendGrid se usa vía SMTP).
     Opcional: sendgrid (~6.11) si se prefiere la API HTTP sobre SMTP — NO requerido.
infra: cuenta SendGrid (free 100 emails/día) + dominio verificado (SPF/DKIM) para que no
       caiga en spam. En dev/CI no se necesita: console/locmem backend.
```

#### DoD — ✅ COMPLETADO (2026-06-10)

- [x] Modelo `Notification` (BaseModel, FK org obligatoria, índices compuestos
      `idx_notifications_org_recipient` e `idx_notifications_org_status`); migración 0001.
- [x] `notification_service.notify_step_assigned` crea el `Notification` y programa la task
      vía `on_commit`; `_send` usa SMTP → `TransientError` en caso de fallo de red.
- [x] Selector tenant-safe `get_recipients_for_role(organization, role)` que resuelve
      destinatarios filtrando por rol dentro de la org.
- [x] `workflow_service.advance_step`/`start_workflow` encolan la notificación al entrar a un
      nuevo paso, vía `transaction.on_commit`. Lazy import para evitar circular imports.
- [x] `EMAIL_BACKEND` por entorno: console (dev), locmem (test), SMTP/SendGrid (prod).
      `DEFAULT_FROM_EMAIL`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, credenciales por env.
- [x] La task `send_notification` usa `autoretry_for=(TransientError,)` y marca `failed`
      ante fallo permanente; idempotente (no reenvía notificación `sent`).
- [x] Tests: 21 nuevos (selector: 5, service: 8, tasks: 2, workflow_notifications: 6).
      Cubre destinatario correcto por rol, tenant isolation, `mail.outbox`, on_commit.
- [x] `apps.notifications` registrada en `INSTALLED_APPS` (base.py).
- [x] drf-spectacular sigue en 0 errors / 0 warnings.

#### Commits sugeridos

```
chore(notifications): register app and configure EMAIL_BACKEND per environment
feat(notifications): add Notification model with tenant FK and indexes
feat(notifications): add notification_service and recipient selector
feat(notifications): add HTML email template and send task with retries
feat(workflows): notify next-step reviewers on workflow advance (on_commit)
test(notifications): add tests for service, recipients, tenant isolation and email
test(workflows): assert step advance enqueues a notification
```

---

### Orden de implementación recomendado

```
5.1 (frontend setup+auth)  ─┬─▶ 5.2 (frontend docs)  ─┬─▶ 5.3 (frontend wf+audit)
                            │                          │
5.7 (notificaciones email) ─┘  (backend, independiente del frontend; puede ir en paralelo)
                                                       │
5.4 (CI/CD) ◀──────────────────────────────────────────  (necesita que exista frontend/ para el job de build)
   │
   └─▶ 5.6 (observabilidad: health + logs + Sentry)  ─▶ 5.5 (deploy VPS)
```

Justificación del orden:
- **5.1 es el cimiento del frontend** — 5.2 y 5.3 no existen sin él.
- **5.7 (notificaciones) es backend puro e independiente**; conviene hacerlo temprano o en
  paralelo al frontend para no acoplar calendarios. Cierra deuda de Fase 3/4.
- **5.4 (CI) necesita que `frontend/` exista** (al menos el scaffold de 5.1) para el job de
  build; idealmente se monta apenas terminado 5.1 para proteger todo lo demás.
- **5.6 antes que 5.5**: el health check y los settings de logging/Sentry son insumo del
  deploy (Nginx hace health check, prod necesita Sentry y JSON logs). Desplegar sin
  observabilidad es desplegar a ciegas.
- **5.5 (deploy) es el último** porque consume todo lo anterior: imágenes con el frontend
  buildeado, settings de prod endurecidos, health check para el proxy, email SMTP real.

### Riesgos principales (top 3 por impacto)

1. **Refresh de JWT con requests concurrentes (5.1).** Si N requests reciben 401 a la vez,
   sin una cola se disparan N refresh simultáneos → el `refresh` rotativo se invalida y se
   desloguea al usuario. **Mitigación:** el interceptor mantiene una sola promesa de refresh
   en vuelo y encola las requests fallidas hasta que resuelva; test explícito de este caso.
2. **Deploy/migraciones concurrentes corrompen el arranque (5.5).** Si `web`, `worker` y
   `beat` arrancan a la vez y todos corren `migrate`, hay race conditions y locks.
   **Mitigación:** servicio `migrate` one-shot con `depends_on ... service_completed_successfully`
   (decisión global #6); `web/worker/beat` jamás migran.
3. **Emails de notificación marcados como spam o credenciales filtradas (5.7).** SendGrid sin
   SPF/DKIM cae en spam; una API key en el repo es un incidente de seguridad.
   **Mitigación:** dominio verificado en SendGrid; key SOLO por env (`python-decouple`,
   CLAUDE.md §10); `before_send` de Sentry y scrubbing de logs para no filtrar el contenido
   del email ni la key; console/locmem backend en dev/CI.

### Lo que explícitamente queda FUERA de Fase 5 (Fase 6+)

- **Tokens en cookies httpOnly** (Fase 5 usa memoria+localStorage; migración consciente).
- **Notificaciones in-app / websockets / push**; y notificar en reject/cancel/complete
  (Fase 5 solo "paso asignado" por email).
- **Thumbnails / previews de documentos** (diferido desde Fase 4).
- **Extracción de texto de Office (docx/xlsx)** con `python-docx`/`openpyxl`.
- **`django-celery-beat`** (schedules editables desde admin) y **Flower** (monitoreo worker).
- **Prometheus + Grafana / métricas** (Sentry cubre errores+performance básica en Fase 5).
- **Staging environment y deploy GitOps automático a prod** (Fase 5 hace deploy manual
  `workflow_dispatch`).
- **`apps/billing`** (skeleton dormido).
- **Backups gestionados / PITR** (Fase 5 hace `pg_dump` diario básico).
- **i18n del frontend, dark mode, tests E2E (Playwright/Cypress)** (Fase 5 cubre unit/
  component con Vitest).

---

## Fase 6 — Mejoras post-portafolio

**Objetivo:** el proyecto ya está "completo" como portafolio (Fases 0–5, backend + frontend +
CI/CD + deploy + observabilidad básica). Fase 6 NO cierra un producto: es un backlog priorizado
de mejoras donde cada sub-fase demuestra una competencia de ingeniería distinta y cierra deuda
técnica consciente registrada en Fase 5. A diferencia de las fases anteriores, **Fase 6 no es
secuencial-obligatoria**: cada sub-fase es un incremento independiente, elegible por su valor de
portafolio en el momento. Se implementan de a una, con tests en verde antes de avanzar (regla
general #1).

**Estimación global:** indefinida (backlog). Cada sub-fase estima su propia complejidad (S/M/L).
Meta de cobertura backend: mantener ≥ 95% (gate de CI de Fase 5.4). El frontend suma tests Vitest;
6.5 introduce E2E (Playwright), contados aparte.

**Métricas de partida (fin de Fase 5, 2026-07-01):** ~526 tests backend (95% cobertura) + 169
tests frontend. Todo el CI en verde. Apps de dominio activas: core, organizations, authentication,
permissions, audit, documents, workflows, search, notifications (billing dormido).

**Invariantes que Fase 6 respeta sin excepción (CLAUDE.md §2–16):** NUNCA microservicios; separación
models/services/selectors/api; toda entidad de dominio nueva hereda `BaseModel` + FK obligatoria a
`Organization`; selectors reciben `organization` explícito; auditoría desde services; soft delete en
entidades críticas; `transaction.atomic()` en services multi-tabla; side-effects vía
`transaction.on_commit`; prevención de N+1; índices compuestos con `organization` primero; tests
contra PostgreSQL real con test explícito de aislamiento de tenant.

**Mapa de sub-fases (deuda que cierra + skill que demuestra):**

| Sub-fase | Área | Cierra deuda | Skill de portafolio | Toca BE | Toca FE | Toca infra | Compl. |
|----------|------|--------------|---------------------|:---:|:---:|:---:|:---:|
| 6.1 | JWT en cookies httpOnly | #28 | Seguridad de auth / XSS-CSRF | ✅ | ✅ | — | M |
| 6.2 | Enriquecimiento documental (thumbnails + texto Office) | Diferidos #3, #4 | Pipeline async de media | ✅ | ✅ | — | M |
| 6.3 | Notificaciones in-app en tiempo real | #34, diferido notif. | Realtime (SSE) + entrega exactly-once | ✅ | ✅ | — | L |
| 6.4 | Observabilidad avanzada | Diferidos #5, #6 | SRE / métricas / monitoreo | ✅ | — | ✅ | M |
| 6.5 | Madurez de frontend (paginación, i18n, dark mode, E2E) | #38, diferidos i18n/dark/E2E | Frontend profesional + E2E | — | ✅ | — | M |
| 6.6 | `apps/billing` — planes, suscripciones y cuotas | Skeleton dormido | Modelado de dominio SaaS + Stripe | ✅ | ✅ | — | L |
| 6.7 | Staging + GitOps + backups gestionados/PITR | Diferidos #7, #9 | DevOps / SRE / DR | ✅ | ✅ | ✅ | L |

### Decisiones globales de Fase 6 (cerradas — no re-discutir durante la implementación)

1. **Cada sub-fase es un incremento independiente y mergeable por sí solo.** No hay "gran refactor"
   ni rediseño transversal. Se prefiere evolución incremental sobre big-bang (principio de diseño
   del proyecto).
2. **Ninguna sub-fase relaja las reglas de CLAUDE.md.** Si una mejora exigiera romper una invariante
   (p. ej. query sin filtro de tenant, lógica en view), se rediseña o se descarta. La única excepción
   tenant-agnóstica permitida sigue siendo la ya justificada (`cleanup_orphan_blobs`, decisión #21);
   Fase 6 no añade excepciones nuevas salvo que se documenten como decisión cerrada explícita.
3. **`apps/billing` es la ÚNICA app de dominio nueva de Fase 6** (6.6). El resto extiende apps
   existentes. No se crean apps por conveniencia.
4. **Sin websockets si SSE resuelve el caso.** El realtime de 6.3 se resuelve con la herramienta más
   simple capaz de cumplir el requisito real (server→client unidireccional). WebSockets/Channels solo
   si aparece un caso bidireccional real, que hoy no existe.
5. **El backend sigue siendo la única autoridad de RBAC y de cuotas.** El frontend puede añadir hints
   de UX (6.5), pero jamás reemplaza la validación del backend (respeta decisión #36).

---

### 6.1 — JWT en cookies httpOnly (endurecimiento de autenticación)

**Objetivo.** Migrar el almacenamiento de tokens desde `accessToken` en memoria + `refreshToken` en
`localStorage` (decisión #28) a un esquema resistente a XSS: refresh token en cookie `HttpOnly`
`Secure` `SameSite`, cerrando el trade-off de seguridad documentado como deuda de Fase 6.

**Motivación.** Un XSS hoy puede robar el `refreshToken` de `localStorage` y mantener sesión
indefinida. Es la deuda de seguridad de mayor severidad del proyecto y una mejora que cualquier
revisor senior busca en un SaaS.

**Decisiones arquitectónicas:**

1. **¿Qué token va en cookie?** Solo el **refresh** en cookie `HttpOnly Secure SameSite=Strict`,
   path acotado al endpoint de refresh/logout; el **access** sigue en memoria (Zustand). *Razón:*
   minimiza superficie CSRF (el access no viaja como cookie ambiental en cada request; se manda en
   `Authorization: Bearer`), y el refresh —que es el objetivo valioso del XSS— queda inaccesible a JS.
   Alternativa evaluada: ambos tokens en cookie → obliga a protección CSRF en TODOS los endpoints
   mutantes; se descarta por mayor superficie.
2. **Protección CSRF del endpoint de refresh.** `SameSite=Strict` + patrón double-submit token
   (cookie no-HttpOnly + header `X-CSRF-Token`) en el POST de refresh y logout.
3. **Rotación y blacklist.** El refresh rotativo + blacklist (ya activos, SimpleJWT) se mantienen; el
   nuevo refresh se re-emite como cookie en cada rotación. Logout invalida en blacklist **y** borra la
   cookie (`Set-Cookie` expirado) desde el backend.
4. **CORS/entornos.** En prod Nginx sirve mismo origen (sin CORS). En dev (Vite:5173 ≠ API:8000) el
   proxy `/api` de Vite dev-server es un **prerrequisito duro, no opcional**: sin él, `SameSite=Strict`
   no entrega la cookie en el flujo cross-origin de dev (Vite:5173 vs API:8000) y el refresh nunca
   llegaría al backend. Es la primera tarea de frontend de esta sub-fase, no un detalle de conveniencia.
5. **`LogoutView` y access expirado.** Hoy `LogoutView` exige `IsAuthenticated`; con un access de vida
   corta, un logout con el access ya expirado fallaría con 401 antes de poder invalidar el refresh. Al
   migrar a cookie, el logout debe poder leer el refresh directamente de la cookie y operar aun con el
   access vencido — ajustar el permiso a `AllowAny` cuando la identidad del refresh viaja por cookie
   (la validez la sigue dando el propio refresh + su blacklist, no el access).

**Plan de ejecución (tareas concretas)** *(validado 2026-07-03 contra el código real; detalle a nivel
de archivo/tarea para la implementación)*:

Backend:
1. `backend/config/settings/base.py` — settings de cookie vía decouple: `AUTH_REFRESH_COOKIE_ENABLED`
   (flag), `AUTH_REFRESH_COOKIE_NAME` (default `sv_refresh`), `..._PATH` (acotado a `/api/v1/auth/`),
   `..._SAMESITE` (`Strict`), `..._SECURE`, `..._HTTPONLY`; nombre de cookie CSRF double-submit
   (`sv_csrf`).
2. `backend/apps/authentication/api/cookies.py` (nuevo) — helpers HTTP puros: `set_refresh_cookie`,
   `clear_refresh_cookie`, `issue_csrf_token`, `validate_csrf` (double-submit).
3. `backend/apps/authentication/api/views.py` — `LoginView` setea cookies y deja de exponer el refresh
   en el body (con el flag activado); `TokenRefreshView` lee el refresh de la cookie (fallback a body
   durante el rollout), valida CSRF, rota y re-setea la cookie; `LogoutView` pasa a `AllowAny`, lee la
   cookie, valida CSRF, invalida en blacklist y borra la cookie.
4. `backend/apps/authentication/api/serializers.py` — `refresh` opcional en `RefreshSerializer`/
   `LogoutSerializer`.
5. `backend/apps/authentication/tests/test_auth_cookie.py` (nuevo).

Frontend:
6. `frontend/vite.config.ts` — `server.proxy` de `/api` → backend (prerrequisito, primera tarea de
   frontend).
7. `frontend/src/lib/api-client.ts` — `withCredentials: true`; el interceptor deja de leer `localStorage`
   para el refresh, llama a `/auth/refresh/` sin body, adjunta el header `X-CSRF-Token`; conserva la
   cola `isRefreshing`/`failedQueue` (decisión #29).
8. `frontend/src/features/auth/store.ts` — deja de persistir/borrar `refreshToken` de `localStorage`.
9. `frontend/src/features/auth/api.ts` — `logout()` sin `refresh` en el body.
10. `frontend/src/shared/components/ProtectedRoute.tsx` — el bootstrap (decisión #33) deja de leer
    `localStorage`, confía en la cookie.
11. `frontend/src/features/auth/__tests__/interceptor.test.ts` — reescribir los casos que usaban
    `localStorage.setItem('refreshToken', ...)`.

Tests: backend — cookie `HttpOnly`+`Secure`+`SameSite` en login, body sin refresh, refresh con/sin
cookie, CSRF ausente/incorrecto → 403, logout invalida blacklist + borra cookie, aislamiento de tenant,
flag apagado = comportamiento legacy. Frontend — N×401 concurrentes → 1 solo refresh vía cookie, sin
acceso a `localStorage`, header CSRF presente.

Commits sugeridos (conventional commits, uno por subtarea):
1. `feat(auth): add refresh-cookie settings and feature flag`
2. `feat(auth): set/read/clear httpOnly refresh cookie in auth views`
3. `feat(auth): add CSRF double-submit protection to refresh and logout`
4. `test(auth): cover cookie login/refresh/logout and tenant isolation`
5. `feat(frontend): add Vite dev proxy for same-origin API`
6. `refactor(frontend): stop persisting refresh token in localStorage`
7. `feat(frontend): send refresh via cookie and CSRF header in interceptor`
8. `test(frontend): update interceptor tests for cookie-based refresh`

**Entregables:**
- Backend: vistas custom de `login`/`refresh`/`logout` que setean/leen/borran la cookie (subclases de
  las de SimpleJWT; lógica en `auth_service`, view solo orquesta). Settings de cookie por entorno
  (`python-decouple`). Middleware/util que lee el refresh de cookie.
- Frontend: `api-client.ts` deja de leer/escribir `refreshToken` de `localStorage`; el interceptor de
  refresh (cola `isRefreshing`+`failedQueue`, decisión #29) llama al endpoint confiando en la cookie;
  `useAuthStore` deja de persistir el refresh. Manejo del CSRF token.
- Tests: backend — login setea cookie `HttpOnly`; refresh sin cookie → 401; refresh con cookie válida
  rota y re-setea; logout borra cookie + blacklist; aislamiento (cookie de org A no da acceso a org B).
  Frontend — cola de refresh sigue garantizando 1 solo refresh para N 401 concurrentes vía cookie.

**Complejidad:** M. **Riesgo:** medio — rollout con feature-flag recomendado.

---

### 6.2 — Enriquecimiento documental: thumbnails + extracción de texto Office

**Objetivo.** Extender el pipeline async de documentos (Celery, endurecido en Fase 4) con: (a)
generación de thumbnail/preview y (b) extracción de texto de ficheros Office (docx/xlsx) para
alimentar la búsqueda.

**Motivación.** Thumbnails dan un salto visual inmediato en la demo. La extracción Office cierra el
hueco de OCR de Fase 4 (decisión #12: Office → `ocr_status=skipped`), haciendo documentos ofimáticos
buscables por su contenido.

**Decisiones arquitectónicas:**

1. **Almacenamiento del thumbnail.** Objeto derivado en el mismo storage (MinIO/S3) vía
   `StorageService`. Columnas reales `thumbnail_status` (pending/processing/ready/skipped/failed) y
   `thumbnail_key` en `Document` — patrón `ocr_status` (decisión #13). Una sola migración.
2. **Formatos que generan thumbnail.** PDF (primera página vía `pdf2image`, ya instalado) e imágenes
   (`Pillow`). Office/otros → `skipped`.
3. **Extracción Office.** Extender `ocr_service` (no crear service nuevo) con handlers
   `python-docx`/`openpyxl`. Resultado escrito en `ocr_content` con `save(update_fields=["ocr_content"])`,
   disparando el signal FTS (decisión #14). Elimina el `skipped` para Office; actualiza la decisión #12.
4. **Task separada para thumbnail.** `generate_thumbnail(document_id)` — autoretry con `TransientError`,
   encolada desde `document_service.create_document` vía `transaction.on_commit`. Lógica en
   `thumbnail_service` (CLAUDE.md §12). La extracción Office va dentro del `process_ocr` existente.

**Entregables:**
- Backend: migración `thumbnail_status`/`thumbnail_key`; `thumbnail_service`; task `generate_thumbnail`;
  handlers docx/xlsx en `ocr_service`; endpoint `POST /documents/{id}/regenerate-thumbnail/` (202);
  `thumbnail_key` como presigned URL read-only en `DocumentSerializer`. `cleanup_orphan_blobs` extendido
  para blobs de thumbnail.
- Frontend: `DocumentCard`/`DocumentListPage` con miniatura (fallback a `FileTypeBadge`);
  `ThumbnailStatusBadge` con polling; preview ampliado en `DocumentDetailPage`.
- Tests: genera thumbnail PDF/imagen; Office → skipped thumbnail pero texto extraído y buscable;
  failure → `failed`; aislamiento de tenant; `cleanup` no borra thumbnails vivos.

**Complejidad:** M. **Dependencias externas:** `Pillow`, `python-docx`, `openpyxl` (pip).

---

### 6.3 — Notificaciones in-app en tiempo real + entrega exactly-once

**Objetivo.** Sumar canal `in_app` al subsistema de notificaciones (Fase 5.7, hoy solo email), con
entrega en tiempo real al frontend, ampliar los eventos notificados (reject/cancel/complete) y saldar
la deuda exactly-once (decisión #34).

**Motivación.** Diferenciador visual más fuerte: realtime UX + mensajería robusta. Cierra las deudas
del canal in-app diferido, eventos de workflow adicionales y la semántica at-least-once (#34).

**Decisiones arquitectónicas:**

1. **Transporte realtime: SSE.** El caso es estrictamente server→client; SSE funciona sobre HTTP/1.1,
   atraviesa Nginx con `proxy_buffering off`, no requiere ASGI/Django Channels. WebSockets/Channels se
   descartan (sobre-ingeniería para flujo unidireccional — decisión global #4).
2. **Modelo de datos.** Extender `Notification` existente con `read_at` (nullable) y ampliar `channel`
   choices con `in_app`. Choice `processing` para exactly-once. Índice parcial
   `idx_notifications_org_recipient_unread` con `condition=Q(read_at__isnull=True)`.
3. **Exactly-once (#34).** Estado `processing` + sweep task Beat que re-encola notificaciones colgadas
   en `processing` más de N minutos. Ciclo: pending → processing → sent con timeout. Requiere migración
   (nuevo choice) + task nueva.
4. **Eventos ampliados.** `workflow_service` emite notificaciones en reject/cancel/complete vía
   `transaction.on_commit` (patrón Fase 5.7). Un `notification_service.notify_*` por evento.
5. **Autorización del stream SSE.** Autenticación por JWT (Bearer); filtro siempre por
   `request.organization` + `request.user`. Aislamiento de tenant en el canal realtime = requisito de
   seguridad; se testea explícitamente.

**Entregables:**
- Backend: migración `Notification` (nuevos choices, `read_at`, índice parcial); `notification_service`
  canal in-app + eventos reject/cancel/complete; sweep task Beat; endpoints `GET /api/v1/notifications/`
  (lista paginada con `unread_count` en `meta`), `POST /api/v1/notifications/{id}/read/`,
  `POST /api/v1/notifications/read-all/`, `GET /api/v1/notifications/stream/` (SSE).
- Frontend: `NotificationBell` en Header con badge; hook `useNotifications` + suscripción SSE;
  `NotificationsPage`; toasts para eventos entrantes; reconexión con backoff del `EventSource`.
- Tests: notificación in-app en cada evento de workflow; `unread_count` correcto; aislamiento de tenant
  en lista y stream SSE; sweep re-encola `processing` colgadas; no reenvía `sent`; on_commit.

**Complejidad:** L. **Riesgo:** medio-alto — SSE detrás de Nginx requiere `proxy_buffering off` +
timeouts largos. Documentar en `nginx.conf`. Considerar worker async/gthread dedicado para el endpoint
SSE o límite de conexiones concurrentes.

---

### 6.4 — Observabilidad avanzada (métricas + scheduler editable + monitoreo de workers)

**Objetivo.** Elevar la observabilidad de Fase 5.6 (Sentry + JSON logs + health check) a métricas
cuantitativas (Prometheus + Grafana), schedules editables desde el admin (`django-celery-beat`) y
monitoreo de la cola Celery (Flower).

**Motivación.** Demuestra madurez de SRE: "¿cuánto, cuán rápido, cuánta cola?" en vez de solo "¿falló
algo?". Cierra los diferidos #5 y #6 de Fase 5.

**Decisiones arquitectónicas:**

1. **Instrumentación.** `django-prometheus` para métricas HTTP/DB automáticas + métricas de negocio
   custom emitidas **desde los services** (no desde views), coherente con "auditoría desde services".
   Endpoint `/metrics` protegido, no público.
2. **Sin label `organization_id` en métricas custom.** Cardinalidad alta = anti-patrón en Prometheus
   y potencial fuga de forma de datos por tenant. Métricas agregadas a nivel plataforma; el desglose
   por tenant vive en la auditoría/DB.
3. **Scheduler editable.** Migrar de `CELERY_BEAT_SCHEDULE` estático (decisión #17) a
   `django-celery-beat` (`DatabaseScheduler`). Migración de datos que siembra los schedules actuales.
   Documenta el cambio de la decisión #17.
4. **Flower** detrás de Nginx con auth básica, no expuesto públicamente sin protección.
5. **Grafana.** Dashboards versionados como JSON en el repo (`ops/grafana/`).

**Entregables:**
- Backend: `django-prometheus` + middleware; helper de métricas custom en services; `/metrics`
  protegido; `django-celery-beat` con `DatabaseScheduler` + migración de siembra.
- Infra: servicios `prometheus`, `grafana`, `flower` en compose de prod; `prometheus.yml`; dashboards
  JSON; rutas protegidas en `nginx.conf`.
- Docs: `docs/observability.md` (qué métrica significa qué, cómo leer los dashboards).
- Tests: `/metrics` expone contadores custom; no público sin auth; service incrementa el contador
  correcto; schedules sembrados existen tras migrar.

**Complejidad:** M. **Dependencias externas:** `django-prometheus`, `django-celery-beat`, `flower`
(pip); imágenes `prom/prometheus`, `grafana/grafana` (infra).

---

### 6.5 — Madurez de frontend: paginación, i18n, dark mode y E2E

**Objetivo.** Cerrar los pendientes de calidad del frontend: paginación en listas de workflows
(decisión #38), internacionalización, modo oscuro y suite E2E (Playwright).

**Motivación.** Convierte el frontend de "funcional" a "profesional". La suite E2E protege los flujos
críticos end-to-end que los tests unitarios no cubren.

**Decisiones arquitectónicas:**

1. **Paginación (#38).** Conectar `<Pagination>` en `WorkflowTemplatesPage`/`WorkflowExecutionsPage`
   al backend usando `meta.count/next/previous/page/page_size` del envelope. Trabajo pequeño de cierre.
2. **i18n.** `react-i18next` con `es`/`en` como locales iniciales; extraer strings a catálogos.
3. **Dark mode.** La estrategia `class` de Tailwind (`darkMode: ['class']`) **ya está declarada** en
   `tailwind.config.js` — la base existe. Lo que falta es el toggle, los tokens de tema de shadcn/ui
   (CSS variables) y aplicar las clases `dark:` en los componentes; toggle persistido en `localStorage`
   con respeto a `prefers-color-scheme`.
4. **E2E.** Playwright. Job separado en CI que levanta backend + frontend (compose) y corre flujos
   críticos: login, upload, búsqueda, avanzar workflow, auditoría, notificación in-app. Job paralelo
   a unit, no bloqueante (más lento/frágil).
5. **Hints de RBAC en UI (#36).** Opcional y solo como UX-hint (deshabilitar/ocultar botones). El
   backend sigue siendo la única autoridad (decisión #36 respetada).
6. **Code-splitting del frontend (deuda no capturada antes de Fase 6, validada 2026-07-03).** Hoy el
   bundle es 100% síncrono (0 usos de `React.lazy`/`Suspense` en el código). División por ruta con
   `React.lazy`/`Suspense` y, si el análisis del bundle lo justifica, `manualChunks` en la config de
   Vite. Relevante porque 6.6 (billing) y 6.3 (SSE) seguirán agregando peso al bundle.

**Entregables:**
- Frontend: `<Pagination>` conectado en listas de workflows; `react-i18next` + catálogos; dark mode
  toggle; code-splitting por ruta (`React.lazy`/`Suspense`, `manualChunks` en Vite si aplica); suite
  Playwright con flujos críticos; (opcional) helpers de hint RBAC en `shared/lib/roles`.
- CI: job `e2e` en `ci.yml`; artefactos de trazas en fallo.
- Tests: Vitest — interacciones de paginación, cambio de idioma, toggle de tema; Playwright — flujos e2e.

**Complejidad:** M. **Dependencias externas:** `react-i18next`, `i18next` (npm); `@playwright/test` (npm).
**Nota:** i18n del backend (mensajes de error localizados) queda FUERA de 6.5.

---

### 6.6 — `apps/billing` — planes, suscripciones y cuotas por organización

**Objetivo.** Construir `apps/billing` desde cero y modelar el corazón monetario de un SaaS: catálogo
de planes, suscripción por organización, cuotas/límites por plan y enforcement en los services de
dominio, con integración de pagos (Stripe) en modo test.

**Precisión (validado 2026-07-03):** `apps/billing` **no** es un "skeleton dormido" con estructura
interna — hoy es un paquete Python **vacío**: solo contiene `__init__.py`, sin `apps.py`, sin
`models/`/`services/`/`api/`, y ni siquiera está registrado en `INSTALLED_APPS`. 6.6 requiere
scaffolding completo desde cero (misma estructura obligatoria de CLAUDE.md §2: `models/`, `services/`,
`selectors/`, `api/`, `permissions/`, `tasks/`, `tests/`, `admin.py`, `apps.py`), no "despertar" nada
existente.

**Motivación.** Mayor valor de portafolio de Fase 6: modelado de dominio SaaS real, enforcement
transversal de límites multi-tenant e integración con un proveedor de pagos.

**Decisiones arquitectónicas:**

1. **Modelado:**
   - `Plan` = catálogo global (nombre, precio, límites: `max_documents`, `max_storage_bytes`,
     `max_users`, flags de features). **Sin FK a `Organization`** — es raíz de catálogo, no dato de
     tenant. Excepción documentada como decisión cerrada (análoga a `organizations`).
   - `Subscription(BaseModel)` **CON FK obligatoria a `Organization`** (una activa por org), `plan`,
     `status` (trialing/active/past_due/canceled), `current_period_end`, `stripe_customer_id`,
     `stripe_subscription_id`. Soft delete.
   - `Invoice(BaseModel)` con FK org (snapshot; detalle vive en Stripe).
   - Uso/cuota calculado con **selectors** (`count`/`sum` de documentos/storage por org), no contador
     denormalizado — evita drift. Optimización lazy si `EXPLAIN ANALYZE` lo requiere.
2. **Enforcement de cuotas en services.** `document_service.create_document` consulta
   `quota_service.assert_can_create_document(org)` antes de crear. Excede cuota →
   `ApplicationError` tipado (`QUOTA_EXCEEDED`, 402/403) con envelope estándar. NUNCA en views.
3. **Integración Stripe.** Modo test (claves por `python-decouple`). Webhooks verifican firma;
   delegan en `billing_service`. Procesamiento idempotente por `stripe_event_id`. El webhook es la
   única entrada a estados privilegiados de `Subscription` (patrón decisión #8).
4. **Auditoría.** Todo cambio de plan/suscripción/estado genera `AuditLog` desde el service.

**Entregables:**
- Backend: modelos `Plan`, `Subscription`, `Invoice` + migraciones; `billing_service`
  (suscribir, cambiar plan, procesar webhook); `quota_service` (assert_* de cuotas);
  `billing_selector` (uso por org, tenant-safe); endpoints `GET /api/v1/billing/subscription/`,
  `GET /api/v1/billing/usage/`, `POST /api/v1/billing/checkout-session/`,
  `POST /api/v1/billing/webhook/` (firma verificada, sin auth JWT). Enforcement en
  `document_service` (y donde aplique).
- Frontend: `BillingPage` (plan actual, uso vs. límites con barras de progreso, upgrade);
  banners de "cerca del límite"/"límite alcanzado"; integración Stripe Checkout.
- Tests: cuota bloquea creación al exceder límite; aislamiento de tenant en uso y suscripción;
  webhook idempotente; firma inválida → rechazo; cambio de plan audita; `transaction.atomic`.

**Complejidad:** L. **Dependencias externas:** `stripe` (pip); cuenta Stripe modo test.
**Riesgo:** medio — verificación de firma y idempotencia de webhooks son requisitos de seguridad
no negociables.

---

### 6.7 — Staging + GitOps + backups gestionados / PITR

**Objetivo.** Profesionalizar la operación: entorno de **staging** que espeja prod, deploy
**GitOps automático a staging** en cada merge a `main` (prod sigue manual, decisión Fase 5.5),
y backups gestionados con capacidad de **Point-In-Time Recovery**.

**Motivación.** Demuestra DevOps/SRE y disaster recovery: de "hago un dump y rezo" a "puedo
restaurar a cualquier minuto y valido restauraciones". Cierra los diferidos #7 y #9 de Fase 5.

**Decisiones arquitectónicas:**

1. **Staging.** Misma imagen y `docker-compose.prod.yml` parametrizado por `.env.staging`; datos
   sintéticos, jamás datos reales de prod.
2. **GitOps.** Merge a `main` con CI verde → deploy automático a staging. Prod permanece en
   `workflow_dispatch` manual (para no romper la demo en vivo). Promoción staging→prod por
   tag/dispatch.
3. **PITR.** `pgBackRest` (o `WAL-G`) para backup full + WAL archiving → PITR, almacenado en
   S3/objeto. Alternativa `pg_dump` mejorado: más simple pero sin PITR. Se recomienda pgBackRest
   por el valor de portafolio.
4. **Validación de restauración.** Job programado que restaura el último backup en entorno efímero y
   corre smoke test — "un backup no probado no es un backup".

**Entregables:**
- Infra: `.env.staging.example`; compose parametrizado; `deploy.yml` con job de staging automático +
  promoción manual a prod; configuración `pgBackRest`/`WAL-G` + bucket de backups; nginx de staging.
- Ops: script/job de validación de restauración; `docs/disaster-recovery.md` (runbook DR).
- Validación: pipeline de staging despliega en verde; restauración PITR end-to-end probada en el job
  de validación.

**Complejidad:** L. **Dependencias externas:** `pgBackRest` o `WAL-G`; bucket S3/objeto para WAL;
segundo entorno (staging VPS o mismo VPS con red separada).

---

**Validado 2026-07-03:** el backlog de Fase 6 fue auditado contra el estado real del código; las 7
sub-fases siguen vigentes sin invalidaciones. Sub-fase recomendada para empezar: **6.1** (cero
dependencias, cierra la deuda de seguridad de mayor severidad, sin migraciones).

---

### Orden de implementación recomendado

Fase 6 es un backlog: el orden es una guía por dependencias, riesgo y valor de portafolio.

```
6.1 (cookies httpOnly)  ──▶  6.2 (enriquecimiento docs)  ──▶  6.3 (notif. realtime)  ──▶  6.6 (billing)
   (seguridad, bajo riesgo)      (extiende pipeline Fase 4)       (diferenciador UX)         (dominio nuevo)
        │                              │                               │                          │
        └──────────────┬───────────────┘                               │                          │
                       ▼                                               ▼                          │
                6.4 (observabilidad)  ◀── conviene antes de billing (medir cuotas/pagos)          │
                       │                                                                           │
                       └──────────────▶  6.5 (madurez frontend)  ◀───────────────────────────────┘
                                                    │
                                                    └──▶  6.7 (staging + GitOps + PITR)
```

**Justificación:**
- **6.1 primero:** cierra la deuda de seguridad de mayor severidad (#28) antes de exponer más
  superficie. Independiente y con feature-flag de rollout.
- **6.2 temprano:** payoff visual inmediato; reutiliza el pipeline Celery de Fase 4; no depende de
  nada nuevo.
- **6.3 antes de 6.6:** la mensajería madura (exactly-once) que billing querrá usar para avisos de
  pago/cuota ya estará lista.
- **6.4 antes de 6.6:** medir es prerequisito para operar billing con confianza (tasas de webhook,
  latencias, cola).
- **6.6 en la segunda mitad:** se beneficia de observabilidad (6.4) y mensajería madura (6.3).
- **6.5 interleaveable:** la paginación (deuda pequeña) puede ir antes; E2E idealmente después de
  que billing y notificaciones realtime existan para cubrir esos flujos.
- **6.7 al final (capstone):** staging y PITR consumen todo lo anterior; tiene sentido cuando hay
  algo estable y valioso que proteger.

### Riesgos principales

1. **Migración de tokens rompe la sesión de todos los usuarios (6.1).** Un error en la cookie de
   refresh o CSRF deja al frontend sin poder renovar sesión. **Mitigación:** feature-flag, tests
   exhaustivos del interceptor y del ciclo login/refresh/logout, verificar que la cola de refresh
   (decisión #29) sigue garantizando un solo refresh para N 401 concurrentes.
2. **Stream SSE agota los workers de Gunicorn (6.3).** Conexiones long-lived en workers sync bloquean
   el pool. **Mitigación:** worker async/gthread dedicado o límite de conexiones; `proxy_buffering off`
   + timeouts en Nginx; degradación a polling como fallback; test de aislamiento de tenant en el canal.
3. **Webhooks de billing no verificados o no idempotentes corrompen el estado de suscripción (6.6).**
   **Mitigación:** verificación obligatoria de firma de Stripe; procesamiento idempotente por
   `stripe_event_id`; el webhook como única vía privilegiada a estados de `Subscription` (patrón
   decisión #8); auditoría de todo cambio.

### Lo que explícitamente queda FUERA de Fase 6 (Fase 7+ o descartado)

- **Microservicios / división del monolito** — decisión permanente (CLAUDE.md §2). Nunca.
- **Schemas de PostgreSQL separados por tenant** — aislamiento por `organization_id` en schema
  compartido (CLAUDE.md §6). No se re-abre.
- **Búsqueda con stemming o motor externo (Elasticsearch/OpenSearch)** — la FTS de PostgreSQL
  (decisión #11) se mantiene.
- **WebSockets bidireccionales / colaboración en tiempo real tipo Google Docs** — el realtime de 6.3
  es unidireccional (SSE); WebSockets solo si aparece un caso bidireccional real.
- **i18n del backend (mensajes de error localizados) y RTL** — 6.5 es i18n de UI.
- **Multi-región / alta disponibilidad activo-activo / autoscaling** — single-VPS con staging (6.7).
- **App móvil nativa / PWA offline** — fuera de alcance.
- **SSO empresarial (SAML/OIDC), MFA/TOTP** — Fase 7 potencial.
- **Data warehouse / analítica por tenant / reporting BI** — las métricas de 6.4 son operativas
  (Prometheus agregado), no analítica de negocio.

---

## Reglas generales para Claude Code en cada fase

1. **Completar tests antes de avanzar** — no iniciar fase siguiente con tests en rojo
2. **Un commit por subtarea** — no acumular todo en un solo commit gigante
3. **Revisar EXPLAIN ANALYZE** al agregar índices — verificar que se usan
4. **Documentar decisiones no obvias** — comentario breve en el código si algo no es evidente
5. **Verificar aislamiento de tenant en cada feature** — test explícito de que org A no ve datos de org B
6. **Consultar este documento** antes de empezar cualquier nueva tarea

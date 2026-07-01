# CLAUDE.md — SasVault Project Context

## 1. ¿Qué es SasVault?

SasVault es una plataforma SaaS empresarial de gestión documental y automatización de workflows. **Proyecto de portafolio profesional** — demostrar dominio de Django, PostgreSQL avanzado, REST profesional, multi-tenancy, seguridad, testing, Docker.

Inspiración: Google Drive + Notion + DocuWare, orientado a empresas.

## 2. Arquitectura — Reglas absolutas

**NUNCA proponer o implementar microservicios.** Monolito modular desacoplado por dominio. Decisión permanente.

### Separación de responsabilidades — OBLIGATORIO

```
apps/
  {nombre_app}/
    models/          ← Solo persistencia. Sin lógica de negocio.
    services/        ← TODA la lógica de negocio. Nunca en views ni models.
    selectors/       ← TODAS las consultas complejas a DB. Nunca en views.
    api/
      views.py       ← Solo orquesta: llama services/selectors, retorna respuesta.
      serializers.py ← Solo serialización/validación de entrada.
      urls.py        ← Solo registro de rutas.
    permissions/     ← Clases de permiso DRF.
    tasks/           ← Solo tareas Celery.
    tests/           ← Tests de la app.
    admin.py
    apps.py
```

### Regla de oro services vs views

```python
#  CORRECTO — La view solo orquesta
class DocumentUploadView(APIView):
    def post(self, request):
        serializer = DocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = document_service.create_document(
            organization=request.organization,
            user=request.user,
            **serializer.validated_data
        )
        return Response(DocumentSerializer(document).data, status=201)

#  INCORRECTO — Lógica de negocio en la view
class DocumentUploadView(APIView):
    def post(self, request):
        file = request.FILES['file']
        checksum = hashlib.sha256(file.read()).hexdigest()
        document = Document.objects.create(...)  # NUNCA directo desde view
        send_mail(...)  # NUNCA desde view
```

## 3. Stack tecnológico

| Capa | Tecnología | Versión |
|------|-----------|---------|
| Lenguaje | Python | 3.13.x |
| Framework | Django | 5.1.x |
| API | Django REST Framework | 3.15.x |
| Auth | djangorestframework-simplejwt | 5.3.x |
| Base de datos | PostgreSQL | 16 |
| Cache / Broker | Redis | 7 |
| Queue | Celery | 5.4.x |
| Storage (dev) | MinIO | latest |
| Storage (prod) | AWS S3 | — |
| Server | Gunicorn + Nginx | — |
| Frontend | React + TypeScript + Vite + Tailwind + shadcn/ui | — |
| Testing | pytest + pytest-django + factory-boy | — |
| Linting | black + isort + flake8 | — |
| Containers | Docker + Docker Compose | — |
| Env vars | python-decouple | — |

## 4. Multi-tenancy — Regla crítica

**TODA entidad principal debe tener `organization` como FK obligatoria.**

Aislamiento por `organization_id` en cada tabla (shared schema). Sin schemas separados.

```python
# ✅ Todo modelo principal debe verse así
class Document(BaseModel):
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='documents'
    )
```

**Middleware:** inyecta `request.organization` en cada request autenticado. Services y selectors SIEMPRE reciben `organization` como parámetro explícito.

```python
#  CORRECTO
def get_documents(organization, user, filters=None):
    return Document.objects.filter(organization=organization, ...)

#  INCORRECTO
def get_documents():
    return Document.objects.all()
```

## 5. Modelo base — BaseModel

**TODOS los modelos deben heredar de `BaseModel`**, nunca de `models.Model`.

```python
# apps/core/models/base.py
class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)  # Soft delete

    class Meta:
        abstract = True
```

### Soft Delete — OBLIGATORIO en entidades críticas

Entidades críticas: `Document`, `DocumentVersion`, `Folder`, `Workflow`, `AuditLog`, `User`.

**NUNCA usar `.delete()` directo.** Usar el servicio de soft delete.

```python
#  CORRECTO
document_service.soft_delete(document, deleted_by=request.user)

#  INCORRECTO
document.delete()
```

## 6. Convenciones de base de datos

### Motor y estrategia de multi-tenancy

- **Motor:** PostgreSQL 16 — único soportado. Aprovechar JSONB, full-text search, GIN/BRIN, arrays, CTEs, window functions. NO SQLite ni MySQL.
- **Multi-tenancy:** schema único compartido. Aislamiento por `organization_id`. NO schemas separados por tenant.
- **Tests:** corren contra PostgreSQL real (DB `test_saasvault_db`), no SQLite en memoria.
- **Implicación crítica:** query sin filtro por organization = vulnerabilidad de seguridad grave.

### Categorías de tablas

| Categoría | FK a Organization | Ejemplos |
|-----------|-------------------|----------|
| Django/Framework | — | `django_*`, `token_blacklist_*` |
| Raíz del tenant | NO | `organizations` |
| Dominio del negocio | **SÍ, obligatoria** | `documents`, `folders`, `workflows`, todo lo demás |

### Nombrado

- **Tablas:** snake_case plural. Siempre `db_table` explícito en `Meta`.
- **FK en Python:** nombre semántico en singular (`organization`, `folder`, `created_by`). NO `organization_id` en código.
- **Para FK a User:** nombres por rol (`created_by`, `uploaded_by`, `approved_by`).
- **Índices:** `idx_{tabla}_{campo1}[_{campo2}...]`. Parciales: sufijo descriptivo `idx_documents_org_status_alive`.
- **Constraints:** `uq_{tabla}_{campos}`, `chk_{tabla}_{regla}`.

### Estrategia de índices — obligatoria

1. Toda FK a `Organization` lleva índice.
2. Toda combinación usada en `filter()` o `order_by()` → índice compuesto, no índices separados.
3. Orden en el índice compuesto: primero el más selectivo (típicamente `organization`).
4. Verificar con `EXPLAIN ANALYZE`. Un índice no usado solo agrega costo.
5. NO agregar índices "por si acaso".

```python
class Meta:
    db_table = "documents"
    indexes = [
        models.Index(fields=["organization", "status"], name="idx_documents_org_status"),
        models.Index(fields=["organization", "-created_at"], name="idx_documents_org_created"),
        models.Index(fields=["organization", "checksum"], name="idx_documents_org_checksum"),
        GinIndex(fields=["search_vector"], name="idx_documents_search_vector"),
    ]
```

**Índice parcial para soft delete (tablas grandes):**

```python
models.Index(
    fields=["organization", "status"],
    name="idx_documents_org_status_alive",
    condition=Q(deleted_at__isnull=True),
)
```

### Prevención de N+1 — OBLIGATORIO en selectors

```python
#  INCORRECTO — N+1 al serializar
def get_documents(organization):
    return Document.objects.filter(organization=organization)

#  CORRECTO
def get_documents(organization):
    return (
        Document.objects
        .filter(organization=organization)
        .select_related("folder", "created_by")
        .prefetch_related("tags", "versions")
    )
```

| Tipo de relación | Método |
|------------------|--------|
| ForeignKey, OneToOne (hacia adelante) | `select_related` |
| Reverse ForeignKey, ManyToMany | `prefetch_related` |

### Soft delete — implicaciones para queries

`BaseModel.objects` ya filtra `deleted_at IS NULL`. NO repetir el filtro en cada selector.
- Registros eliminados (admin/auditoría): `Model.all_objects`.
- Uniques con soft delete: `UniqueConstraint` con `condition=Q(deleted_at__isnull=True)`.

```python
class Meta:
    constraints = [
        models.UniqueConstraint(
            fields=["organization", "slug"],
            condition=Q(deleted_at__isnull=True),
            name="uq_documents_org_slug_alive",
        )
    ]
```

### JSONB

**Usar para:** configuración dinámica por tenant, metadata flexible, snapshots de auditoría, resultados de procesamiento async.

**NO usar para:** datos filtrados en queries frecuentes, relaciones (FKs), listas que crecen indefinidamente, datos sensibles a auditar columna por columna.

```python
metadata = models.JSONField(default=dict, blank=True)  # SIEMPRE default=dict, nunca None
```

### Transacciones

Todo service que modifica más de una tabla DEBE usar `transaction.atomic()`.

```python
def create_document(organization, user, file, **data) -> Document:
    with transaction.atomic():
        document = Document.objects.create(organization=organization, ...)
        DocumentVersion.objects.create(document=document, version_number=1, ...)
        audit_service.log(organization, user, document, AuditAction.CREATE, ...)
    return document
```

- NO envolver lecturas en transacciones.
- NO `commit`/`rollback` manuales — siempre context manager.
- Tareas Celery con side-effects van DESPUÉS del commit: `transaction.on_commit(lambda: task.delay(...))`.

### Migraciones

- Revisar SIEMPRE la migración generada antes de aplicarla.
- NUNCA modificar migraciones ya aplicadas. Crear migración correctiva nueva.
- Nombrar descriptivamente: `makemigrations --name add_document_search_vector`.
- Zero-downtime: para columnas NOT NULL en tablas grandes → 3 migraciones (nullable → backfill → NOT NULL).
- `RunPython` siempre con `reverse_code`.

### Checklist obligatorio antes de mergear con DB

- [ ] Modelo nuevo hereda de `BaseModel` y tiene FK a `Organization`
- [ ] Selector recibe `organization` como parámetro explícito y filtra por él
- [ ] Índice en `organization_id` o compuesto que lo incluya como primer campo
- [ ] Selectors que devuelven listas declaran `select_related`/`prefetch_related`
- [ ] Test explícito de aislamiento (dos orgs, org A no ve datos de org B)
- [ ] Services multi-tabla usan `transaction.atomic()`
- [ ] Migración revisada manualmente
- [ ] Para queries críticas: `EXPLAIN ANALYZE` muestra uso de índice

## 7. API REST — Convenciones

URL base: `/api/v1/`

### Formato de respuesta — SIEMPRE este envelope

```json
{ "data": { ... }, "meta": {} }

{ "data": [ ... ], "meta": { "count": 100, "next": "...", "previous": null, "page": 1, "page_size": 20 } }

{ "error": { "code": "DOCUMENT_NOT_FOUND", "message": "...", "details": {} } }
```

### Códigos HTTP

| Situación | Código |
|-----------|--------|
| GET exitoso | 200 |
| POST exitoso (creación) | 201 |
| PATCH/PUT exitoso | 200 |
| DELETE exitoso | 204 |
| Validación fallida | 400 |
| No autenticado | 401 |
| Sin permiso | 403 |
| No encontrado | 404 |
| Error de servidor | 500 |

## 8. Autenticación y permisos

### JWT
- Access token: 15 min (prod) / 60 min (dev). Refresh: 7 días, rotating. Blacklist activado.
- Claims: `organization_id`, `role`, `email`.

### RBAC — Roles
```python
class UserRole(models.TextChoices):
    SUPER_ADMIN = 'super_admin'
    ORG_ADMIN = 'org_admin'
    SUPERVISOR = 'supervisor'
    EDITOR = 'editor'
    VIEWER = 'viewer'
    AUDITOR = 'auditor'
```

### Permission classes (apps/permissions/) — nunca lógica ad-hoc en views
```python
IsOrganizationMember   # user.organization == request.organization
HasRole                # class factory: user.role in roles
IsDocumentOwner
CanViewDocument / CanEditDocument / CanDeleteDocument / CanApproveDocument
```

## 9. Auditoría — Crítico

**TODO evento importante debe generar un AuditLog.**

Eventos a auditar: login/logout/refresh, CRUD de documentos, cambios de permisos, cambios de estado en workflows, cambios de config de org, accesos denegados.

Auditoría desde **services**, nunca desde views.

```python
#  CORRECTO — desde el service
def update_document(organization, user, document, **data):
    old_values = DocumentSerializer(document).data
    document = _apply_changes(document, data)
    audit_service.log(
        organization=organization, user=user, entity=document,
        action=AuditAction.UPDATE,
        old_values=old_values, new_values=DocumentSerializer(document).data,
    )
    return document
```

## 10. Variables de entorno

**NUNCA hardcodear credenciales, URLs, keys o configuración sensible.** Usar `python-decouple`.

```python
from decouple import config
SECRET_KEY = config('DJANGO_SECRET_KEY')
DEBUG = config('DJANGO_DEBUG', default=False, cast=bool)
```

`.env` en `.gitignore`. `.env.example` en el repo.

## 11. Testing — Obligatorio

**Todo código nuevo debe tener tests.**

- `pytest` + `pytest-django` + `factory-boy`. NO usar fixtures de Django.
- Tests contra PostgreSQL real. Si falla con `connection refused` en `localhost:5432` → infra apagada.

### Qué testear siempre
1. Happy path del service
2. Casos de error (wrong org, missing permission, invalid data)
3. Aislamiento de tenant (una org no accede a datos de otra)
4. Endpoints de API (status codes, formato de respuesta)
5. Permisos (autenticado vs no autenticado, rol correcto vs incorrecto)

## 12. Tareas Celery

Definidas en `apps/{app}/tasks/`. Nunca lógica de negocio dentro — llamar a services.

```python
#  CORRECTO
@shared_task
def process_document_ocr(document_id: str):
    document = Document.objects.get(id=document_id)
    ocr_service.process(document)

#  INCORRECTO — lógica directa en la task
@shared_task
def process_document_ocr(document_id: str):
    document = Document.objects.get(id=document_id)
    text = pytesseract.image_to_string(...)
    document.ocr_content = text
    document.save()
```

## 13. Settings en capas

```
backend/config/settings/
  base.py         ← Configuración común
  development.py  ← DEBUG=True, etc.
  test.py         ← Para pytest
  production.py   ← Producción
```

## 14. Código — Reglas de estilo

- black (88 chars), isort (profile black)
- Type hints obligatorios en signatures de services y selectors
- Docstrings en services y selectors (una línea)
- Comentarios solo cuando el código no se explica solo
- Nombres descriptivos en inglés

```python
#  CORRECTO
def get_documents_by_folder(
    organization: Organization,
    folder: Folder,
    user: User,
    include_deleted: bool = False,
) -> QuerySet:
    """Return documents inside a folder visible to the given user."""
    ...

#  INCORRECTO
def get_docs(org, f, u, d=False):
    return Document.objects.filter(org=org, folder=f)
```

## 15. Git — Convenciones de commits

### Conventional Commits (obligatorio)

```
feat: add document version history endpoint
fix: correct tenant isolation in document selector
chore: update dependencies
test: add tests for document upload service
docs: update API conventions
refactor: extract file validation to dedicated service
perf: add composite index on documents table
```

### Estrategia de ramas

```
main          ← Solo código listo para producción
develop       ← Integración de features
feature/{name} ← Una feature por rama
fix/{name}    ← Corrección de bugs
```

## 16. Lo que NUNCA hacer

- Lógica de negocio en views
- Queries directas a DB desde views
- Hardcodear credenciales, URL o secrets
- Eliminar físicamente entidades críticas sin soft delete
- Crear modelos sin heredar de `BaseModel`
- Crear modelos de entidades principales sin `organization` FK
- Omitir tests para lógica de negocio nueva
- Mezclar settings de entornos
- Guardar archivos binarios en PostgreSQL
- Commits con mensajes como "fix", "update", "changes"
- Proponer microservicios
- Usar `print()` (usar `logging`)
- Modificar migraciones ya aplicadas

## 17. Estado actual del proyecto

**Fase actual:** Fases de portafolio COMPLETAS (0–5). 5.1, 5.2, 5.3, 5.4, 5.5 y 5.7 COMPLETAS (5.5 completada 2026-06-29); siguiente: Fase 6 (mejoras post-portafolio).

**Completado:**
- Fase 0 — Setup: WSL2, Docker Compose (PG16+Redis7+MinIO), pre-commit hooks, .env.example
- Fase 1.1 — Django + settings 4 capas
- Fase 1.2 — Core app: BaseModel, SoftDeleteManager, ApplicationError, StandardPagination
- Fase 1.3 — Organizations: modelo, service, selector, API, tests
- Fase 1.4 — Authentication: User custom (AbstractBaseUser), JWT (organization_id/role/email), OrganizationTenantMiddleware
- Fase 1.5 — RBAC: IsOrganizationMember, HasRole (factory), IsOrgAdmin, IsSuperAdmin
- Fase 1.6 — Gestión de usuarios dentro de la organización
- Fase 2.0 — Skeletons de `apps/audit` y `apps/documents`; constantes MAX_UPLOAD_SIZE/ALLOWED_UPLOAD_MIME_TYPES; `config/celery.py`
- Fase 2.1 — `AuditLog` inmutable (BigAutoField, NO hereda BaseModel, append-only)
- Fase 2.2 — Modelos `Folder`, `Document`, `DocumentVersion` con índices compuestos, GIN, UniqueConstraints condicionales
- Fase 2.3 — `FileValidator` (magic bytes, SHA-256, 50MB); `StorageService` (boto3/MinIO, presigned URLs)
- Fase 2.4 — `FolderService` (create/rename/move con detección de ciclos, soft delete); `FolderSelector`
- Fase 2.5 — `DocumentService` (create atómico + OCR stub on_commit; versioning; status lock draft↔under_review; soft delete); `DocumentSelector`
- Fase 2.6 — REST endpoints `/api/v1/folders/` y `/api/v1/documents/` con RBAC, envelope, paginación
- Fase 3.1 — `AuditLogSelector`, `AuditLogFilter` (django-filter), API solo-lectura `GET /api/v1/audit-logs/`
- Fase 3.2 — Motor de Workflows: `WorkflowTemplate`, `WorkflowStep`, `WorkflowExecution`, `WorkflowStepLog`; `workflow_service`; API `/api/v1/workflows/`
- Fase 3.3 — Full-Text Search: signal `post_save` → `search_vector` pesos A/B/C/D; `SearchSelector`; `GET /api/v1/search/`
- Auditoría Fase 3 — race condition → UniqueConstraint parcial + IntegrityError→409; `select_for_update`; paginación consistente
- drf-spectacular: 0 errors / 0 warnings; Swagger `/api/docs/`, Redoc `/api/redoc/`
- Fase 4.0 — Pre-flight Celery: deps (`pytesseract`, `pdf2image`); `StorageService.download_file()`; settings OCR/Celery
- Fase 4.1 — `TransientError`; `process_ocr` con `autoretry_for`, `retry_backoff`
- Fase 4.2 — `Document.ocr_status` (columna real, migración); `ocr_service.process()` real (imagen/PDF/office→skipped); endpoint `POST /documents/{id}/reprocess-ocr/`
- Fase 4.3 — `cleanup_orphan_blobs` Beat diaria 03:00 UTC; `StorageService.list_objects()` paginado; período de gracia 24h
- Fase 4.4 — `ai_service.analyze()` con Claude Haiku + prompt caching; feature-flag `ANTHROPIC_API_KEY`; `POST /documents/{id}/analyze/` (202 async)
- Auditoría Fase 4 — errores SDK Anthropic → `TransientError`; `reprocess_ocr` resetea `ocr_status=PENDING`; `max_retries=3` inline
- Fase 5.6 — `GET /api/v1/health/` (público, sin envelope); `health_service` (DB/Redis/MinIO); `RequestContextFilter`; Sentry gateado por `SENTRY_DSN`
- Fase 5.1 — Frontend: Vite+React+TS+Tailwind+shadcn/ui; `api-client.ts` (Bearer + cola de refresh `isRefreshing+failedQueue`); `useAuthStore` Zustand; `LoginForm`, `ProtectedRoute`, `AppLayout`+`Sidebar`+`Header`; 22 tests Vitest
- Fase 5.7 — `apps/notifications`: `Notification(BaseModel)` con FK org; `notification_service.notify_step_assigned`; `get_recipients_for_role`; task `send_notification` (autoretry); `workflow_service` encola via `transaction.on_commit` (lazy import); 21 tests nuevos
- Auditoría Fase 5 (2026-06-15) — rehidratación de perfil en `ProtectedRoute`; `Promise.reject` en interceptor 401; claim atómico en `_send` de notificaciones; toasts globales via `MutationCache`; narrowing seguro de `ApiError`; tests de rollback de on_commit
- Fase 5.2 — Frontend gestión documental: `FolderBrowserPage`, `DocumentListPage`, `DocumentDetailPage`, upload drag&drop con progreso, `OcrStatusBadge` con polling, `SearchPage`, `DashboardPage`; `react-dropzone`; `date-fns`
- Fase 5.3 (2026-06-21) — Frontend workflows + auditoría: `WorkflowTemplateForm` (`useFieldArray`, validación zod), `AdvanceStepDialog` (`AlertDialog` + select acción + textarea), `ExecutionStatusBadge`, `WorkflowStepLogTimeline` (`formatDistanceToNow`); `AuditLogFilters`, `AuditLogTable`, `AuditLogPage`; `DocumentDetailPage` pestaña "Análisis IA" con polling; shadcn: `textarea`, `checkbox`, `separator`, `accordion`; rutas `/workflows`, `/workflows/templates/:id`, `/workflows/executions`, `/workflows/executions/:id`, `/audit-logs`; 74 tests Vitest nuevos
- Fase 5.4 (2026-06-29) — CI/CD GitHub Actions: `.github/workflows/ci.yml` (jobs paralelos backend+frontend; PG16+Redis7 como runner services; lint+pytest -m "not integration"+Codecov; gate 95% en addopts; eslint+tsc --noEmit+vitest+vite build); `.github/workflows/deploy.yml` (scaffold `workflow_dispatch` para 5.5); `pyproject.toml` `--cov-fail-under=95`; script `typecheck` en `frontend/package.json`; badges CI+Codecov en README
- Fase 5.5 (2026-06-29) — Deploy producción: `backend/Dockerfile` multi-stage (builder→runtime; libmagic1+tesseract+poppler; collectstatic como root+chown→appuser); `frontend/Dockerfile` multi-stage (Node 20 Alpine→nginx:stable-alpine; `VITE_API_BASE_URL=/api/v1`); `docker-compose.prod.yml` 8 servicios (`migrate` one-shot + web+worker+beat+nginx+postgres+redis+minio); `nginx/nginx.conf` (HTTP→HTTPS 301, TLS 1.2/1.3, SPA fallback, proxy /api/ /admin/ /static/, `client_max_body_size 50m`); `production.py` `SECURE_PROXY_SSL_HEADER`+`CONN_MAX_AGE=60`; `scripts/deploy.sh` idempotente; `scripts/backup_db.sh` (pg_dump comprimido, retención 7 días, escritura atómica); `deploy.yml` actualizado con `appleboy/ssh-action@v1.2.0`; `docs/deploy-guide.md` guía educativa 10 secciones
- Features 2026-06-30 — Asignación de carpetas: `GET /api/v1/folders/tree/` (lista plana de carpetas de la org); `PATCH /documents/{id}/` acepta `folder_id` (UUID o null); sentinel `FOLDER_UNSET` en `document_service`; selector de carpetas en pestaña "Editar metadata" de `DocumentDetailPage`
- Features 2026-06-30 — Workflow desde documento: `POST /api/v1/documents/{id}/start-workflow/` (document_id en URL, valida ejecución activa → 409 `WORKFLOW_ALREADY_ACTIVE`); botón "Iniciar workflow" en header del documento (condicionado a `canWrite && plantillas.length > 0`); `StartWorkflowDialog` con selector de plantilla; navega a la ejecución al confirmar
- Features 2026-06-30 — Upload desde carpeta: botón "Subir documento" en `FolderBrowserPage` (condicionado a `canWrite && !isRoot`); pre-asigna `folder_id`; invalida `['folders']` en `useUploadDocument.onSuccess`

**Métricas (2026-06-30):** ~526 tests backend (495 normales + 27 `@pytest.mark.integration` + ~4 nuevos) + 169 tests frontend. Cobertura backend: 95%.

**Apps activas:** `apps.core`, `apps.organizations`, `apps.authentication`, `apps.permissions`, `apps.audit`, `apps.documents`, `apps.workflows`, `apps.search`, `apps.notifications`

**Decisiones de diseño cerradas (no re-discutir):**

1. `AuditLog` usa `BigAutoField` (no UUID), NO hereda `BaseModel` — inmutable, append-only.
2. Tests de `StorageService`: mockeados (normal) + integración real MinIO (`@pytest.mark.integration`).
3. `Document.status`: `draft↔under_review` manual; `approved`/`rejected` SOLO vía `WorkflowExecution`.
4. `process_ocr` implementada con cuerpo real en Fase 4.2. Ya no es stub.
5. Blob en MinIO NO se borra al soft-delete. `cleanup_orphan_blobs` lo maneja (Fase 4.3).
6. API de auditoría solo-lectura; leer audit logs NO genera audit log.
7. Modelos de workflows heredan `BaseModel` (no el patrón inmutable de AuditLog).
8. `workflow_service` escribe `Document.status` directamente (`_set_document_status`) — ÚNICA vía privilegiada a `approved`/`rejected`.
9. Una sola ejecución activa por documento. Respaldado por `UniqueConstraint` parcial `uq_wf_exec_one_active_per_document`.
10. `config`/`actions` (JSONB en template/step) se persisten pero NO se interpretan.
11. FTS usa `config="simple"` (sin stemming). Signal `post_save` reconstruye `search_vector` solo si cambia campo de texto.
12. OCR cubre solo PDF + imágenes. Office → `ocr_status=skipped`. `ocr_content` se expone en `DocumentSerializer` (read-only) y se muestra en `DocumentDetailPage` como pestaña condicional (solo si tiene contenido).
13. `ocr_status` es columna real (no JSONB). Default `pending`. Sin re-OCR masivo.
14. OCR alimenta búsqueda automáticamente: `save(update_fields=["ocr_content"])` dispara signal FTS.
15. Tareas llaman a services (CLAUDE.md §12). `process_ocr` fina, lógica en `ocr_service`.
16. `cleanup_orphan_blobs` mira `Document` Y `DocumentVersion`; período de gracia 24h.
17. Dev corre worker+beat en venv. `CELERY_BEAT_SCHEDULE` estático.
18. OCR completion auditado con `UPDATE` + `metadata={"via":"ocr"}` (sin nuevo enum).
19. IA (4.4) opcional; Haiku 4.5; prompt caching; `ANTHROPIC_API_KEY` vacía → 503.
20. Dependencias 4.0: `pip` (`pytesseract`, `pdf2image`) + `apt` (`tesseract-ocr tesseract-ocr-spa poppler-utils`).
21. `cleanup_orphan_blobs` es tenant-agnóstico (excepción justificada). Observabilidad por `logger.info`.
22. IA feature-off por defecto. Resultado en `metadata["ai_analysis"]`. Endpoint async 202.
23. Post-auditoría Fase 4: errores SDK Anthropic → `TransientError`; `reprocess_ocr` resetea `ocr_status=PENDING`; `max_retries=3` inline.
24. `GET /api/v1/health/` es la única excepción al envelope `{data,meta}` (compatibilidad con health checkers externos). `authentication_classes=[]`.
25. Health check no se audita.
26. Sentry gateado por `SENTRY_DSN` vacío. `send_default_pii=False`. Scrubbing de `Authorization` header y bodies de `/auth/`.
27. JSON logging solo en `production.py`. `RequestContextFilter` inyecta `organization_id`/`user_id`/`request_id`.
28. `accessToken` en memoria (Zustand), `refreshToken` en `localStorage`. Trade-off XSS documentado; migrar a httpOnly cookies = Fase 6.
29. Cola de refresh (`isRefreshing+failedQueue`): garantiza exactamente 1 refresh para N 401 concurrentes.
30. `apps/notifications` es app de dominio (BaseModel + FK org). `workflow_service` la importa lazy para evitar importaciones circulares.
31. Notificaciones solo al rol exacto del paso (`required_role`). Solo en "paso asignado". Reject/cancel/complete = futuro.
32. SMTP errors → `TransientError` → `autoretry`. Notificación `sent` no se reenvía. Fallo definitivo → `status=failed`.
33. Rehidratación de perfil en `ProtectedRoute` usa `getMe()` imperativo (opción A, no `useMe()` hook). Motivo: el bootstrap es un flujo secuencial; un hook declarativo introduce race condition con el flag `restorationAttempted`. Skeleton cubre token + perfil antes de renderizar `<Outlet>`.
34. Idempotencia de `_send` en notificaciones: claim atómico `UPDATE WHERE status IN (pending, failed)` + `rowcount`. Semántica at-least-once. Sin estado `processing` (evita migración + sweep task). Si se requiere exactly-once estricto → deuda técnica: introducir `processing` + sweep.
35. Toast global de errores de mutación vía `MutationCache.onError` en `query-client.ts`. Las mutaciones con UI de error inline propia usan `meta: { suppressGlobalToast: true }`. Las queries no tienen handler global de error.
36. `AdvanceStepDialog` (frontend, 5.3): el cliente no valida el rol del usuario antes de mostrar el botón de avance — manda la request y muestra el 403 del backend como toast. El backend es la autoridad de RBAC; la UI nunca duplica esa lógica.
37. Polling de `useWorkflowExecution` cada 5s mientras `status in (pending, in_progress)`; se detiene al llegar a estado terminal. Mismo patrón que `ocr_status` en 5.2. Sin websockets (over-engineering para portafolio).
38. Paginación en listas de workflows (templates/executions) aplazada: las páginas de lista muestran solo la primera página. El componente `<Pagination>` y el soporte de backend ya existen; pendiente de conectar. Deuda anotada para 5.4/5.5.
39. `FOLDER_UNSET = object()` sentinel en `document_service`: distingue "campo `folder_id` ausente del PATCH" de "usuario quiere mover a raíz (`folder=null`)". Sin sentinel, cualquier PATCH que no incluya `folder_id` movería el documento a la raíz.
40. Endpoint `POST /documents/{id}/start-workflow/` vive en `documents/api/views.py` (no en workflows). Convención: cada `urls.py` importa solo views de su propia app. La dependencia cruzada `documents.views → workflows.services` es legítima en la capa de orquestación (una view puede llamar services de otro dominio).

**Próximo paso:** Proyecto completado en sus fases de portafolio (Fases 0–5). Ver `docs/phase-plan.md` §'Lo que queda FUERA de Fase 5' para mejoras de Fase 6+.

## 18. Cómo correr el proyecto localmente

```bash
source backend/.venv/bin/activate
docker compose up -d
cd backend && python manage.py runserver
pytest
celery -A config.celery worker --loglevel=info
```

## 19. Archivos importantes

| Archivo | Propósito |
|---------|-----------|
| `CLAUDE.md` | Este archivo |
| `docker-compose.yml` | Servicios de infraestructura local |
| `backend/.env` | Variables de entorno (NO en git) |
| `backend/.env.example` | Template de variables |
| `backend/requirements.txt` | Dependencias Python |
| `backend/pyproject.toml` | Config black/isort |
| `backend/.flake8` | Config flake8 |
| `.pre-commit-config.yaml` | Hooks de calidad |
| `docs/phase-plan.md` | Plan de desarrollo por fases |
| `docs/api-conventions.md` | Convenciones REST detalladas |
| `docs/coding-patterns.md` | Patrones de código |
| `docs/database-conventions.md` | Convenciones de base de datos |

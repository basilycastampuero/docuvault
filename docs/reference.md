# SasVault — Referencia Técnica Exhaustiva

Diccionario de consulta rápida: qué existe, dónde, qué recibe y qué devuelve.
Última actualización: 2026-07-01.

---

## Índice

1. [Backend — Modelos](#1-backend--modelos)
2. [Backend — Services](#2-backend--services)
3. [Backend — Selectors](#3-backend--selectors)
4. [Backend — API Endpoints](#4-backend--api-endpoints)
5. [Backend — Serializers](#5-backend--serializers)
6. [Backend — Enums y Constantes](#6-backend--enums-y-constantes)
7. [Frontend — Tipos TypeScript](#7-frontend--tipos-typescript)
8. [Frontend — API Client Functions](#8-frontend--api-client-functions)
9. [Frontend — Hooks (TanStack Query)](#9-frontend--hooks-tanstack-query)
10. [Frontend — Componentes Clave](#10-frontend--componentes-clave)
11. [Frontend — Stores (Zustand)](#11-frontend--stores-zustand)
12. [Contrato Frontend-Backend](#12-contrato-frontend-backend)

---

## 1. Backend — Modelos

### BaseModel

**Path:** `backend/apps/core/models/base.py`
**Herencia:** `models.Model` (abstracto)
**Managers:** `objects` (SoftDeleteManager — excluye `deleted_at IS NOT NULL`), `all_objects` (AllObjectsManager — incluye todos)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | `UUIDField` | PK, `default=uuid.uuid4`, no editable |
| `created_at` | `DateTimeField` | `auto_now_add=True` |
| `updated_at` | `DateTimeField` | `auto_now=True` |
| `deleted_at` | `DateTimeField` | nullable, `db_index=True` — soft delete |

Métodos: `.soft_delete()`, `.restore()`, `.is_deleted` (property).

---

### Organization

**App:** `organizations` | **Path:** `backend/apps/organizations/models/organization.py`
**Hereda:** `BaseModel`

| Campo | Tipo | Notas |
|---|---|---|
| `name` | `CharField(255)` | |
| `slug` | `SlugField(100)` | unique |
| `is_active` | `BooleanField` | default `True` |
| `settings` | `JSONField` | default `{}` — configuración por tenant |

---

### User

**App:** `authentication` | **Path:** `backend/apps/authentication/models/user.py`
**Hereda:** `BaseModel`, `AbstractBaseUser`, `PermissionsMixin`
**`USERNAME_FIELD`:** `email`

| Campo | Tipo | Notas |
|---|---|---|
| `email` | `EmailField` | unique |
| `first_name` | `CharField(150)` | blank |
| `last_name` | `CharField(150)` | blank |
| `organization` | `FK → Organization` | nullable, `SET_NULL` |
| `role` | `CharField(20)` | choices `UserRole`, default `viewer` |
| `is_active` | `BooleanField` | default `True` |
| `is_staff` | `BooleanField` | default `False` |

Propiedad: `full_name` → `"{first_name} {last_name}".strip() or email`.

---

### Folder

**App:** `documents` | **Path:** `backend/apps/documents/models/folder.py`
**Hereda:** `BaseModel`

| Campo | Tipo | Notas |
|---|---|---|
| `organization` | `FK → Organization` | CASCADE |
| `name` | `CharField(255)` | |
| `parent` | `FK → self` | nullable, `SET_NULL`=no, `CASCADE` — carpeta padre |
| `owner` | `FK → User` | PROTECT |

Constraint: `uq_folders_org_parent_name_alive` — único nombre por carpeta padre mientras no esté eliminado.

---

### Document

**App:** `documents` | **Path:** `backend/apps/documents/models/document.py`
**Hereda:** `BaseModel`

| Campo | Tipo | Notas |
|---|---|---|
| `organization` | `FK → Organization` | CASCADE |
| `folder` | `FK → Folder` | nullable, `SET_NULL` |
| `name` | `CharField(255)` | |
| `description` | `TextField` | blank |
| `mime_type` | `CharField(120)` | |
| `file_size` | `PositiveBigIntegerField` | bytes |
| `checksum` | `CharField(64)` | SHA-256 hexdigest |
| `storage_path` | `CharField(500)` | clave en MinIO/S3 |
| `status` | `CharField(20)` | choices `DocumentStatus`, default `draft` |
| `version` | `PositiveIntegerField` | default `1` |
| `created_by` | `FK → User` | PROTECT |
| `tags` | `ArrayField(CharField(50))` | default `[]`, GIN index |
| `metadata` | `JSONField` | default `{}`, GIN index. Clave `"ai_analysis"` contiene resultado IA. |
| `ocr_content` | `TextField` | blank — texto extraído por OCR |
| `ocr_status` | `CharField(20)` | choices `OcrStatus`, default `pending` |
| `search_vector` | `SearchVectorField` | nullable, GIN index |

Constraint: `uq_documents_org_folder_name_alive` — único nombre por carpeta mientras no esté eliminado.

**`metadata["ai_analysis"]`** estructura esperada:
```json
{
  "summary": "...",
  "entities": { "dates": [], "amounts": [], "names": [] },
  "suggested_category": "...",
  "ai_analysis_at": "ISO8601"
}
```

---

### DocumentVersion

**App:** `documents` | **Path:** `backend/apps/documents/models/document_version.py`
**Hereda:** `BaseModel`

| Campo | Tipo | Notas |
|---|---|---|
| `document` | `FK → Document` | CASCADE |
| `version_number` | `PositiveIntegerField` | |
| `storage_path` | `CharField(500)` | |
| `file_size` | `PositiveBigIntegerField` | bytes |
| `checksum` | `CharField(64)` | SHA-256 |
| `mime_type` | `CharField(120)` | |
| `created_by` | `FK → User` | PROTECT |
| `change_description` | `CharField(500)` | blank |

Ordering: `-version_number`.

---

### WorkflowTemplate

**App:** `workflows` | **Path:** `backend/apps/workflows/models/template.py`
**Hereda:** `BaseModel`

| Campo | Tipo | Notas |
|---|---|---|
| `organization` | `FK → Organization` | CASCADE |
| `name` | `CharField(255)` | |
| `description` | `TextField` | blank |
| `is_active` | `BooleanField` | default `True` |
| `config` | `JSONField` | default `{}` — no interpretado, reservado |

---

### WorkflowStep

**App:** `workflows` | **Path:** `backend/apps/workflows/models/template.py`
**Hereda:** `BaseModel`

| Campo | Tipo | Notas |
|---|---|---|
| `template` | `FK → WorkflowTemplate` | CASCADE |
| `name` | `CharField(255)` | |
| `order` | `PositiveIntegerField` | único por template (constraint parcial) |
| `required_role` | `CharField(20)` | choices `UserRole` |
| `is_final` | `BooleanField` | default `False` — exactamente uno por template |
| `actions` | `JSONField` | default `{}` — no interpretado, reservado |

Ordering: `order`.

---

### WorkflowExecution

**App:** `workflows` | **Path:** `backend/apps/workflows/models/execution.py`
**Hereda:** `BaseModel`

| Campo | Tipo | Notas |
|---|---|---|
| `organization` | `FK → Organization` | CASCADE |
| `template` | `FK → WorkflowTemplate` | PROTECT |
| `document` | `FK → Document` | CASCADE |
| `current_step` | `FK → WorkflowStep` | nullable, `SET_NULL` |
| `status` | `CharField(20)` | choices `WorkflowStatus`, default `pending` |
| `started_by` | `FK → User` | PROTECT |
| `started_at` | `DateTimeField` | nullable |
| `completed_at` | `DateTimeField` | nullable |

Constraint: `uq_wf_exec_one_active_per_document` — solo una ejecución activa (pending/in_progress) por documento.

---

### WorkflowStepLog

**App:** `workflows` | **Path:** `backend/apps/workflows/models/execution.py`
**Hereda:** `BaseModel`

| Campo | Tipo | Notas |
|---|---|---|
| `execution` | `FK → WorkflowExecution` | CASCADE |
| `step` | `FK → WorkflowStep` | PROTECT |
| `action` | `CharField(20)` | choices `WorkflowStepAction` |
| `performed_by` | `FK → User` | PROTECT |
| `comment` | `TextField` | blank |

Ordering: `created_at`.

---

### AuditLog

**App:** `audit` | **Path:** `backend/apps/audit/models/audit_log.py`
**Hereda:** `models.Model` (NO hereda `BaseModel`, no tiene `deleted_at`, no tiene UUID pk)
**Inmutable:** `.save()` con pk existente lanza `RuntimeError`. `.delete()` lanza `RuntimeError`.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | `BigAutoField` | PK auto-incremental |
| `organization` | `FK → Organization` | CASCADE, `db_index=True` |
| `user` | `FK → User` | nullable, `SET_NULL` |
| `entity_type` | `CharField(64)` | ej. `"document"`, `"folder"`, `"workflow_execution"` |
| `entity_id` | `CharField(64)` | UUID como string |
| `action` | `CharField(32)` | choices `AuditAction` |
| `old_values` | `JSONField` | default `{}` |
| `new_values` | `JSONField` | default `{}` |
| `ip_address` | `GenericIPAddressField` | nullable |
| `user_agent` | `CharField(255)` | blank |
| `metadata` | `JSONField` | default `{}` |
| `created_at` | `DateTimeField` | `auto_now_add=True` |

---

### Notification

**App:** `notifications` | **Path:** `backend/apps/notifications/models/notification.py`
**Hereda:** `BaseModel`

| Campo | Tipo | Notas |
|---|---|---|
| `organization` | `FK → Organization` | CASCADE |
| `recipient` | `FK → User` | PROTECT |
| `channel` | `CharField(20)` | choices `NotificationChannel`, default `email` |
| `subject` | `CharField(255)` | |
| `body` | `TextField` | plain-text |
| `status` | `CharField(20)` | choices `NotificationStatus`, default `pending` |
| `sent_at` | `DateTimeField` | nullable |
| `metadata` | `JSONField` | default `{}` — incluye `execution_id`, `step_id` |

---

## 2. Backend — Services

Todos los services reciben `organization` y `user` como primeros parámetros explícitos. Los que modifican más de una tabla usan `@transaction.atomic`.

### `audit_service.log`

**Path:** `backend/apps/audit/services/audit_service.py`

| Parámetro | Tipo |
|---|---|
| `organization` | `Organization` |
| `user` | `User \| None` |
| `entity_type` | `str` |
| `entity_id` | `str` |
| `action` | `AuditAction \| str` |
| `old_values` | `dict \| None` |
| `new_values` | `dict \| None` |
| `request` | `HttpRequest \| None` |
| `metadata` | `dict \| None` |

**Retorna:** `AuditLog`
**Side effects:** persiste una fila inmutable en `audit_logs`.

---

### `document_service` — `backend/apps/documents/services/document_service.py`

#### `create_document`
| Parámetro | Tipo |
|---|---|
| `organization` | `Organization` |
| `user` | `User` |
| `file` | `IO[bytes]` |
| `name` | `str` |
| `folder` | `Folder \| None` |
| `description` | `str` |
| `tags` | `list[str] \| None` |

**Retorna:** `Document`
**Side effects:** valida el archivo (magic bytes + SHA-256 + tamaño), sube a MinIO/S3, crea `DocumentVersion` v1, escribe `AuditLog` CREATE, encola `process_ocr.delay` via `on_commit`.
**Excepciones:** `PermissionDenied` si la carpeta no pertenece a la organización.

#### `upload_new_version`
| Parámetro | Tipo |
|---|---|
| `organization` | `Organization` |
| `user` | `User` |
| `document` | `Document` |
| `file` | `IO[bytes]` |
| `change_description` | `str` |

**Retorna:** `Document` (actualizado con nueva versión)
**Side effects:** sube el archivo, crea `DocumentVersion`, escribe `AuditLog` UPDATE, incrementa `document.version`.

#### `update_document_metadata`
| Parámetro | Tipo |
|---|---|
| `organization` | `Organization` |
| `user` | `User` |
| `document` | `Document` |
| `name` | `str \| None` |
| `description` | `str \| None` |
| `tags` | `list[str] \| None` |
| `folder_id` | `UUID \| None \| FOLDER_UNSET` |

**Retorna:** `Document`
**Side effects:** escribe `AuditLog` UPDATE si hay cambios.
**Nota:** `folder_id=FOLDER_UNSET` (sentinel `object()`) = "no tocar carpeta". `folder_id=None` = mover a raíz.

#### `change_document_status`
| Parámetro | Tipo |
|---|---|
| `organization` | `Organization` |
| `user` | `User` |
| `document` | `Document` |
| `new_status` | `DocumentStatus` |

**Retorna:** `Document`
**Side effects:** escribe `AuditLog` STATUS_CHANGE.
**Excepciones:** `ConflictError(code="INVALID_STATUS_TRANSITION")` — solo permite `draft ↔ under_review`. `approved`/`rejected` son exclusivos del engine de workflows.

#### `reprocess_ocr`
**Parámetros:** `organization, user, document`
**Retorna:** `Document` (con `ocr_status=pending`)
**Side effects:** resetea `ocr_status`, escribe `AuditLog`, encola `process_ocr.delay` via `on_commit`.

#### `request_ai_analysis`
**Parámetros:** `organization, user, document`
**Retorna:** `Document` (sin cambios — el resultado llega async en `metadata["ai_analysis"]`)
**Side effects:** encola `analyze_document.delay` via `on_commit`.
**Excepciones:** `AIServiceUnavailableError` si `ANTHROPIC_API_KEY` no está configurada; `ConflictError(code="AI_NO_CONTENT")` si el documento no tiene `ocr_content`.

#### `soft_delete_document`
**Parámetros:** `organization, user, document`
**Retorna:** `None`
**Side effects:** soft-delete, escribe `AuditLog` DELETE. El blob en MinIO NO se elimina (lo limpia `cleanup_orphan_blobs`).

---

### `folder_service` — `backend/apps/documents/services/folder_service.py`

#### `create_folder`
**Parámetros:** `organization, owner: User, name: str, parent: Folder | None`
**Retorna:** `Folder`
**Side effects:** `AuditLog` CREATE.
**Excepciones:** `PermissionDenied` si `parent` no pertenece a la org.

#### `rename_folder`
**Parámetros:** `organization, user, folder, new_name: str`
**Retorna:** `Folder`
**Side effects:** `AuditLog` UPDATE.

#### `move_folder`
**Parámetros:** `organization, user, folder, new_parent: Folder | None`
**Retorna:** `Folder`
**Side effects:** `AuditLog` UPDATE.
**Excepciones:** `PermissionDenied` si `new_parent` no es de la org; `ValidationError(code="FOLDER_CYCLE")` si se crea un ciclo.

#### `soft_delete_folder`
**Parámetros:** `organization, user, folder`
**Retorna:** `None`
**Side effects:** `AuditLog` DELETE.
**Excepciones:** `ConflictError` si la carpeta tiene subcarpetas o documentos vivos.

---

### `workflow_service` — `backend/apps/workflows/services/workflow_service.py`

#### `create_template`
**Parámetros:** `organization, user, name: str, description: str, steps: list[dict], config: dict | None`
**Retorna:** `WorkflowTemplate`
**Side effects:** crea `WorkflowStep` por cada paso, `AuditLog` CREATE.
**Excepciones:** `ValidationError(code="WORKFLOW_NO_STEPS" | "WORKFLOW_DUPLICATE_ORDER" | "WORKFLOW_FINAL_STEP")`.

**Estructura de cada paso en `steps`:**
```python
{"name": str, "order": int, "required_role": UserRole, "is_final": bool, "actions": dict}
```

#### `update_template`
**Parámetros:** `organization, user, template, name, description, is_active`
**Retorna:** `WorkflowTemplate`
**Side effects:** `AuditLog` UPDATE.

#### `soft_delete_template`
**Parámetros:** `organization, user, template`
**Retorna:** `None`
**Excepciones:** `ConflictError(code="WORKFLOW_TEMPLATE_IN_USE")` si hay ejecuciones activas.

#### `start_workflow`
**Parámetros:** `organization, user, document: Document, template: WorkflowTemplate`
**Retorna:** `WorkflowExecution`
**Side effects:** crea `WorkflowExecution` (status `in_progress`), mueve documento a `under_review` via `_set_document_status`, `AuditLog` CREATE, notifica rol del primer paso via `on_commit`.
**Excepciones:** `PermissionDenied`, `ConflictError(code="WORKFLOW_ALREADY_ACTIVE" | "WORKFLOW_TEMPLATE_INACTIVE" | "WORKFLOW_NO_STEPS")`.

#### `advance_step`
**Parámetros:** `organization, user, execution, action: WorkflowStepAction, comment: str`
**Retorna:** `WorkflowExecution`
**Side effects:** crea `WorkflowStepLog`, actualiza `current_step` o cierra ejecución, cambia `Document.status` via `_set_document_status`, `AuditLog` STATUS_CHANGE.
Usa `select_for_update` para evitar doble-avance concurrente.
**Excepciones:** `PermissionDenied` (rol incorrecto), `ConflictError(code="WORKFLOW_NOT_IN_PROGRESS" | "WORKFLOW_NO_CURRENT_STEP")`.

Roles que pueden actuar en cualquier paso independientemente del `required_role`: `org_admin`, `super_admin`.

#### `cancel_workflow`
**Parámetros:** `organization, user, execution`
**Retorna:** `WorkflowExecution` (status `cancelled`)
**Side effects:** retorna documento a `draft`, `AuditLog` STATUS_CHANGE.
**Excepciones:** `PermissionDenied` (solo el iniciador o admin pueden cancelar).

---

### `notification_service` — `backend/apps/notifications/services/notification_service.py`

#### `notify_step_assigned`
**Parámetros:** `organization, execution: WorkflowExecution, step: WorkflowStep`
**Retorna:** `None`
**Side effects:** crea `Notification` para cada usuario con el `required_role` del paso, encola `send_notification.delay` via `on_commit`. Llamado exclusivamente desde `workflow_service`.

---

### `auth_service` — `backend/apps/authentication/services/auth_service.py`

#### `login`
**Parámetros:** `email: str, password: str`
**Retorna:** `dict` con `{"access": str, "refresh": str, "user": User}`
**Excepciones:** `ValidationError(code="INVALID_CREDENTIALS" | "ACCOUNT_DISABLED")`.

#### `logout`
**Parámetros:** `refresh_token: str`
**Retorna:** `None`
**Side effects:** blacklistea el token en `token_blacklist`.

#### `refresh_token_pair`
**Parámetros:** `refresh_token: str`
**Retorna:** `{"access": str, "refresh": str}`

---

## 3. Backend — Selectors

### `document_selector` — `backend/apps/documents/selectors/document_selector.py`

| Función | Parámetros | Retorno | Relaciones precargadas |
|---|---|---|---|
| `get_document_by_id` | `organization, document_id` | `Document` | `folder`, `created_by` |
| `get_documents` | `organization, folder=None, status=None, tags=None, search=None` | `QuerySet[Document]` | `folder`, `created_by` |
| `get_document_versions` | `organization, document` | `QuerySet[DocumentVersion]` | `created_by` |

`get_document_by_id` lanza `NotFound` si no existe en la org.

---

### `folder_selector` — `backend/apps/documents/selectors/folder_selector.py`

| Función | Parámetros | Retorno | Relaciones precargadas |
|---|---|---|---|
| `get_folder_by_id` | `organization, folder_id` | `Folder` | `owner`, `parent` |
| `get_root_folders` | `organization` | `QuerySet[Folder]` (parent=null) | `owner` |
| `get_children` | `organization, folder` | `QuerySet[Folder]` | `owner` |
| `get_folder_tree` | `organization` | `QuerySet[Folder]` (todos, sin filtrar) | `owner` |

---

### `workflow_selector` — `backend/apps/workflows/selectors/workflow_selector.py`

| Función | Parámetros | Retorno | Relaciones precargadas |
|---|---|---|---|
| `get_templates` | `organization` | `QuerySet[WorkflowTemplate]` | `steps` (prefetch) |
| `get_template_by_id` | `organization, template_id` | `WorkflowTemplate` | `steps` (prefetch) |
| `get_executions` | `organization, document=None, status=None` | `QuerySet[WorkflowExecution]` | `template`, `document`, `current_step`, `started_by` |
| `get_execution_by_id` | `organization, execution_id` | `WorkflowExecution` | `template`, `document`, `current_step`, `started_by` |
| `get_step_logs` | `organization, execution` | `QuerySet[WorkflowStepLog]` | `step`, `performed_by` |

---

### `audit_log_selector` — `backend/apps/audit/selectors/audit_log_selector.py`

| Función | Parámetros | Retorno | Relaciones precargadas |
|---|---|---|---|
| `get_logs` | `organization` | `QuerySet[AuditLog]` (newest first) | `user` |
| `get_log_by_id` | `organization, log_id: int` | `AuditLog` | `user` |

---

### `search_selector` — `backend/apps/search/selectors/search_selector.py`

| Función | Parámetros | Retorno |
|---|---|---|
| `search_documents` | `organization, query: str, folder=None, status=None` | `QuerySet[Document]` anotado con `rank: float` |

Usa `SearchQuery(config="simple", search_type="websearch")` sobre `search_vector` (GIN index).

---

## 4. Backend — API Endpoints

URL base: `/api/v1/`
Todas las respuestas siguen el envelope `{"data": ..., "meta": {...}}` excepto el health check y los errores.

### Autenticación (`/auth/`)

| Método | URL | Permisos | Request body | Response `data` |
|---|---|---|---|---|
| `POST` | `/auth/login/` | `AllowAny` | `{email, password}` | `{access, refresh, user: UserSerializer}` |
| `POST` | `/auth/logout/` | `IsAuthenticated` | `{refresh}` | — (204) |
| `POST` | `/auth/refresh/` | `AllowAny` | `{refresh}` | `{access, refresh}` |
| `GET` | `/auth/me/` | `IsAuthenticated` | — | `UserSerializer` |

**Errores comunes:** `INVALID_CREDENTIALS` (400), `ACCOUNT_DISABLED` (400), `TOKEN_NOT_VALID` (401).

---

### Usuarios (`/users/`)

| Método | URL | Permisos | Request body | Response `data` |
|---|---|---|---|---|
| `GET` | `/users/` | `IsOrganizationMember` | — | `UserSerializer[]` paginado |
| `POST` | `/users/` | `IsOrganizationMember + IsOrgAdmin` | `UserCreateSerializer` | `UserSerializer` (201) |
| `GET` | `/users/{user_id}/` | `IsOrganizationMember` | — | `UserSerializer` |
| `PATCH` | `/users/{user_id}/` | `IsOrgAdmin` | `UserUpdateSerializer` | `UserSerializer` |
| `DELETE` | `/users/{user_id}/` | `IsOrgAdmin` | — | — (204, desactiva el usuario) |

---

### Carpetas (`/folders/`)

| Método | URL | Permisos | Request body | Response `data` |
|---|---|---|---|---|
| `GET` | `/folders/` | `IsOrganizationMember` | — | `FolderSerializer[]` (carpetas raíz) |
| `POST` | `/folders/` | `IsOrganizationMember + editor+` | `FolderCreateSerializer` | `FolderSerializer` (201) |
| `GET` | `/folders/tree/` | `IsOrganizationMember` | — | `FolderSerializer[]` (todas las carpetas, planas) |
| `GET` | `/folders/{id}/` | `IsOrganizationMember` | — | `FolderSerializer` |
| `PATCH` | `/folders/{id}/` | `IsOrganizationMember + editor+` | `FolderUpdateSerializer` | `FolderSerializer` |
| `DELETE` | `/folders/{id}/` | `IsOrganizationMember + editor+` | — | — (204) |
| `GET` | `/folders/{id}/children/` | `IsOrganizationMember` | — | `FolderSerializer[]` |
| `GET` | `/folders/{id}/documents/` | `IsOrganizationMember` | — | `DocumentSerializer[]` paginado |

**Roles "editor+":** `org_admin`, `supervisor`, `editor`.
**Errores:** `NOT_FOUND` (404), `CONFLICT` (400 si tiene hijos/documentos al borrar), `FOLDER_CYCLE` (400).

---

### Documentos (`/documents/`)

| Método | URL | Permisos | Request body / Params | Response `data` |
|---|---|---|---|---|
| `GET` | `/documents/` | `IsOrganizationMember` | `?status=, ?search=` | `DocumentSerializer[]` paginado |
| `POST` | `/documents/` | `editor+` | multipart: `DocumentUploadSerializer` | `DocumentSerializer` (201) |
| `GET` | `/documents/{id}/` | `IsOrganizationMember` | — | `DocumentSerializer` |
| `PATCH` | `/documents/{id}/` | `editor+` | `DocumentMetadataUpdateSerializer` | `DocumentSerializer` |
| `DELETE` | `/documents/{id}/` | `editor+` | — | — (204) |
| `GET` | `/documents/{id}/download/` | `IsOrganizationMember` | — | `{url: string}` (presigned URL) |
| `GET` | `/documents/{id}/versions/` | `IsOrganizationMember` | — | `DocumentVersionSerializer[]` |
| `POST` | `/documents/{id}/versions/` | `editor+` | multipart: `DocumentVersionUploadSerializer` | `DocumentSerializer` (201) |
| `POST` | `/documents/{id}/reprocess-ocr/` | `editor+` | — | `DocumentSerializer` (202) |
| `POST` | `/documents/{id}/analyze/` | `editor+` | — | `DocumentSerializer` (202) |
| `POST` | `/documents/{id}/start-workflow/` | `editor+` | `{template_id: UUID}` | `WorkflowExecutionSerializer` (201) |

**Errores:** `NOT_FOUND` (404), `INVALID_STATUS_TRANSITION` (409), `WORKFLOW_ALREADY_ACTIVE` (409), `AI_NO_CONTENT` (409), `AI_SERVICE_UNAVAILABLE` (503).

---

### Workflows (`/workflows/`)

| Método | URL | Permisos | Request body / Params | Response `data` |
|---|---|---|---|---|
| `GET` | `/workflows/templates/` | `IsOrganizationMember` | — | `WorkflowTemplateSerializer[]` paginado |
| `POST` | `/workflows/templates/` | `org_admin+` | `WorkflowTemplateCreateSerializer` | `WorkflowTemplateSerializer` (201) |
| `GET` | `/workflows/templates/{id}/` | `IsOrganizationMember` | — | `WorkflowTemplateSerializer` |
| `PATCH` | `/workflows/templates/{id}/` | `org_admin+` | `WorkflowTemplateUpdateSerializer` | `WorkflowTemplateSerializer` |
| `DELETE` | `/workflows/templates/{id}/` | `org_admin+` | — | — (204) |
| `GET` | `/workflows/executions/` | `IsOrganizationMember` | `?document=UUID, ?status=` | `WorkflowExecutionSerializer[]` paginado |
| `POST` | `/workflows/executions/` | `editor+` | `WorkflowStartSerializer` | `WorkflowExecutionSerializer` (201) |
| `GET` | `/workflows/executions/{id}/` | `IsOrganizationMember` | — | `WorkflowExecutionSerializer` |
| `POST` | `/workflows/executions/{id}/advance/` | `IsOrganizationMember` (rol validado en service) | `WorkflowAdvanceSerializer` | `WorkflowExecutionSerializer` |
| `GET` | `/workflows/executions/{id}/logs/` | `IsOrganizationMember` | — | `WorkflowStepLogSerializer[]` paginado |

**Errores:** `WORKFLOW_ALREADY_ACTIVE` (409), `WORKFLOW_NOT_IN_PROGRESS` (409), `WORKFLOW_TEMPLATE_IN_USE` (409), `WORKFLOW_NO_STEPS` (400), `WORKFLOW_FINAL_STEP` (400), `PERMISSION_DENIED` (403).

---

### Audit Logs (`/audit-logs/`)

| Método | URL | Permisos | Params | Response `data` |
|---|---|---|---|---|
| `GET` | `/audit-logs/` | `IsOrganizationMember + CanReadAuditLogs` | `?action, ?entity_type, ?entity_id, ?user_email, ?created_after, ?created_before` | `AuditLogSerializer[]` paginado |
| `GET` | `/audit-logs/{id}/` | `IsOrganizationMember + CanReadAuditLogs` | — | `AuditLogSerializer` |

**Roles con `CanReadAuditLogs`:** `org_admin`, `super_admin`, `auditor`.

---

### Búsqueda (`/search/`)

| Método | URL | Permisos | Params | Response `data` |
|---|---|---|---|---|
| `GET` | `/search/` | `IsOrganizationMember` | `?q (min 2)`, `?folder`, `?status` | `SearchResultSerializer[]` paginado |

---

### Organizaciones (`/organizations/`)

ViewSet (SimpleRouter). `GET /`, `POST /`, `GET /{id}/`, `PATCH /{id}/`, `DELETE /{id}/`.
**Requiere `SUPER_ADMIN`** para crear/eliminar.

---

### Health Check (`/health/`)

| Método | URL | Permisos | Response |
|---|---|---|---|
| `GET` | `/health/` | `AllowAny` (sin autenticación JWT) | `{"status": "ok"\|"degraded", "components": {"database": "ok"\|"error", "redis": "ok"\|"error", "storage": "ok"\|"error"}}` |

**No usa el envelope `{data, meta}`** — excepción documentada (decisión #24).
HTTP 200 si todo `ok`, 503 si hay al menos un componente en `error`.

---

### Paginación

La paginación estándar aplica a todos los listados. El frontend recibe:

```json
{
  "data": [...],
  "meta": {
    "count": 100,
    "next": "http://...?page=3",
    "previous": "http://...?page=1",
    "page": 2,
    "page_size": 20
  }
}
```

Query params: `?page=N&page_size=N`.

---

## 5. Backend — Serializers

### `UserSerializer`
**Path:** `backend/apps/authentication/api/serializers.py`
Todos los campos son `read_only`.

| Campo | Tipo |
|---|---|
| `id` | UUID |
| `email` | string |
| `first_name` | string |
| `last_name` | string |
| `role` | string (`UserRole`) |
| `organization_id` | UUID |
| `is_active` | bool |
| `created_at` | datetime |

---

### `FolderSerializer`
**Path:** `backend/apps/documents/api/serializers.py`

| Campo | Tipo | R/W |
|---|---|---|
| `id` | UUID | read-only |
| `name` | string | writable |
| `parent` | UUID \| null | writable |
| `owner_email` | string | read-only (computed) |
| `created_at` | datetime | read-only |
| `updated_at` | datetime | read-only |

---

### `DocumentSerializer`
**Path:** `backend/apps/documents/api/serializers.py`

| Campo | Tipo | R/W |
|---|---|---|
| `id` | UUID | read-only |
| `name` | string | writable |
| `description` | string | writable |
| `mime_type` | string | read-only |
| `file_size` | int (bytes) | read-only |
| `checksum` | string | read-only |
| `status` | DocumentStatus | writable (`draft`, `under_review` solo) |
| `ocr_status` | OcrStatus | read-only |
| `ocr_content` | string | read-only |
| `version` | int | read-only |
| `tags` | string[] | writable |
| `metadata` | object | writable (JSON libre; `ai_analysis` escrito por sistema) |
| `folder` | UUID \| null | writable |
| `folder_name` | string \| null | read-only (computed) |
| `created_by_email` | string | read-only |
| `created_at` | datetime | read-only |
| `updated_at` | datetime | read-only |

---

### `DocumentVersionSerializer`
**Path:** `backend/apps/documents/api/serializers.py`
Todos los campos son `read_only`.

| Campo | Tipo |
|---|---|
| `id` | UUID |
| `version_number` | int |
| `file_size` | int |
| `checksum` | string |
| `mime_type` | string |
| `change_description` | string |
| `created_by_email` | string |
| `created_at` | datetime |

---

### `WorkflowTemplateSerializer`
**Path:** `backend/apps/workflows/api/serializers.py`
Todos los campos son `read_only`.

| Campo | Tipo |
|---|---|
| `id` | UUID |
| `name` | string |
| `description` | string |
| `is_active` | bool |
| `config` | object |
| `steps` | `WorkflowStepSerializer[]` |
| `created_at` | datetime |
| `updated_at` | datetime |

---

### `WorkflowStepSerializer`
| Campo | Tipo |
|---|---|
| `id` | UUID |
| `name` | string |
| `order` | int |
| `required_role` | string (`UserRole`) |
| `is_final` | bool |
| `actions` | object |

---

### `WorkflowExecutionSerializer`
**Path:** `backend/apps/workflows/api/serializers.py`
Todos los campos son `read_only`.

| Campo | Tipo |
|---|---|
| `id` | UUID |
| `template` | UUID |
| `template_name` | string |
| `document` | UUID |
| `document_name` | string |
| `current_step` | `WorkflowStepSerializer \| null` |
| `status` | `WorkflowStatus` |
| `started_by_email` | string |
| `started_at` | datetime \| null |
| `completed_at` | datetime \| null |
| `created_at` | datetime |

---

### `WorkflowStepLogSerializer`
| Campo | Tipo |
|---|---|
| `id` | UUID |
| `step_name` | string |
| `step_order` | int |
| `action` | `WorkflowStepAction` |
| `performed_by_email` | string |
| `comment` | string |
| `created_at` | datetime |

---

### `AuditLogSerializer`
**Path:** `backend/apps/audit/api/serializers.py`
Todos los campos son `read_only`.

| Campo | Tipo |
|---|---|
| `id` | int (BigAutoField) |
| `user` | `{id: UUID, email: str} \| null` |
| `entity_type` | string |
| `entity_id` | string |
| `action` | `AuditAction` |
| `old_values` | object |
| `new_values` | object |
| `ip_address` | string \| null |
| `user_agent` | string |
| `metadata` | object |
| `created_at` | datetime |

---

### `SearchResultSerializer`
**Path:** `backend/apps/search/api/serializers.py`
Igual que `DocumentSerializer` pero sin `checksum`, `ocr_content` y `metadata`. Añade:

| Campo | Tipo |
|---|---|
| `rank` | float (SearchRank anotado) |

---

## 6. Backend — Enums y Constantes

### `UserRole` (`backend/apps/authentication/models/user.py`)

| Valor | Label |
|---|---|
| `super_admin` | Super Admin |
| `org_admin` | Organization Admin |
| `supervisor` | Supervisor |
| `editor` | Editor |
| `viewer` | Viewer |
| `auditor` | Auditor |

---

### `DocumentStatus` (`backend/apps/documents/models/document.py`)

| Valor | Label | Transición manual |
|---|---|---|
| `draft` | Draft | ↔ `under_review` |
| `under_review` | Under Review | ↔ `draft` |
| `approved` | Approved | solo via workflow |
| `rejected` | Rejected | solo via workflow |
| `archived` | Archived | — (sin endpoint activo) |

---

### `OcrStatus` (`backend/apps/documents/models/document.py`)

| Valor | Significado |
|---|---|
| `pending` | En cola (default al crear) |
| `processing` | Worker activo |
| `completed` | OCR exitoso |
| `failed` | Error (reintentable) |
| `skipped` | Tipo de archivo no soportado (office) |

---

### `WorkflowStatus` (`backend/apps/workflows/models/enums.py`)

| Valor | Terminal |
|---|---|
| `pending` | no |
| `in_progress` | no |
| `completed` | sí |
| `rejected` | sí |
| `cancelled` | sí |

---

### `WorkflowStepAction` (`backend/apps/workflows/models/enums.py`)

| Valor | Efecto |
|---|---|
| `approved` | Avanza al siguiente paso o completa la ejecución |
| `rejected` | Termina la ejecución en `rejected` |
| `commented` | Solo registra comentario, no avanza |

---

### `AuditAction` (`backend/apps/audit/models/audit_log.py`)

`create`, `update`, `delete`, `restore`, `view`, `download`, `status_change`, `login`, `logout`, `permission_denied`

---

### `NotificationChannel` / `NotificationStatus` (`backend/apps/notifications/models/notification.py`)

- **Channel:** `email` (único activo)
- **Status:** `pending`, `sent`, `failed`

---

### Constantes de archivo (`backend/apps/documents/storage/file_validator.py`)

| Constante | Valor |
|---|---|
| `MAX_UPLOAD_SIZE` | `50 * 1024 * 1024` (50 MB) |
| `ALLOWED_UPLOAD_MIME_TYPES` | `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, `application/msword`, `application/vnd.ms-excel`, `image/jpeg`, `image/png`, `application/zip` |

---

### Excepciones de aplicación (`backend/apps/core/exceptions.py`)

| Clase | HTTP | Código por defecto |
|---|---|---|
| `ApplicationError` | 400 | `ERROR` |
| `PermissionDenied` | 403 | `PERMISSION_DENIED` |
| `NotFound` | 404 | `NOT_FOUND` |
| `ValidationError` | 400 | `VALIDATION_ERROR` |
| `ConflictError` | 409 | `CONFLICT` |
| `AIServiceUnavailableError` | 503 | `AI_SERVICE_UNAVAILABLE` |
| `TransientError` | — | No llega al HTTP layer — señal interna Celery retry |

---

## 7. Frontend — Tipos TypeScript

**Path principal:** `frontend/src/shared/types/index.ts`

### Envelope types

```typescript
Envelope<T>          { data: T; meta: Record<string, unknown> }
PaginatedMeta        { count, next, previous, page, page_size }
PaginatedEnvelope<T> { data: T[]; meta: PaginatedMeta }
ApiErrorBody         { error: { code, message, details } }
ApiError (class)     extends Error { code, details, status }
```

---

### `Folder`
**Producido por:** `GET /folders/`, `/folders/tree/`, `/folders/{id}/`

| Propiedad | Tipo |
|---|---|
| `id` | `string` (UUID) |
| `name` | `string` |
| `parent` | `string \| null` (UUID del padre) |
| `owner_email` | `string` |
| `created_at` | `string` (ISO8601) |
| `updated_at` | `string` (ISO8601) |

---

### `Document`
**Producido por:** todos los endpoints de documentos

| Propiedad | Tipo | Notas |
|---|---|---|
| `id` | `string` | UUID |
| `name` | `string` | |
| `description` | `string` | |
| `mime_type` | `string` | |
| `file_size` | `number` | bytes |
| `checksum` | `string` | |
| `status` | `DocumentStatus` | |
| `version` | `number` | |
| `ocr_status` | `OcrStatus` | |
| `ocr_content` | `string` | |
| `tags` | `string[]` | |
| `metadata` | `Record<string, unknown>` | `metadata.ai_analysis` contiene resultado IA |
| `folder` | `string \| null` | UUID de carpeta |
| `folder_name` | `string \| null` | |
| `created_by_email` | `string` | |
| `created_at` | `string` | |
| `updated_at` | `string` | |

---

### `SearchResult`
```typescript
Omit<Document, 'checksum' | 'metadata' | 'ocr_content'> & { rank: number }
```

---

### `DocumentVersion`

| Propiedad | Tipo |
|---|---|
| `id` | `string` |
| `version_number` | `number` |
| `file_size` | `number` |
| `mime_type` | `string` |
| `checksum` | `string` |
| `created_by_email` | `string` |
| `change_description` | `string` |
| `created_at` | `string` |

---

### `UserProfile`
**Producido por:** `GET /auth/me/`

| Propiedad | Tipo |
|---|---|
| `id` | `string` |
| `email` | `string` |
| `first_name` | `string` |
| `last_name` | `string` |
| `role` | `UserRole` |
| `organization_id` | `string` |
| `organization_name` | `string` |
| `is_active` | `boolean` |

---

### `WorkflowTemplate`

| Propiedad | Tipo |
|---|---|
| `id` | `string` |
| `name` | `string` |
| `description` | `string` |
| `is_active` | `boolean` |
| `config` | `Record<string, unknown>` |
| `steps` | `WorkflowStep[]` |
| `organization` | `string` |
| `created_at` | `string` |
| `updated_at` | `string` |

### `WorkflowStep`

| Propiedad | Tipo |
|---|---|
| `id` | `string` |
| `name` | `string` |
| `order` | `number` |
| `required_role` | `UserRole` |
| `is_final` | `boolean` |
| `actions` | `Record<string, unknown>` |

---

### `WorkflowExecution`

| Propiedad | Tipo |
|---|---|
| `id` | `string` |
| `template` | `string` (UUID) |
| `template_name` | `string` |
| `document` | `string` (UUID) |
| `document_name` | `string` |
| `current_step` | `WorkflowStep \| null` |
| `status` | `WorkflowStatus` |
| `started_by_email` | `string` |
| `started_at` | `string \| null` |
| `completed_at` | `string \| null` |
| `created_at` | `string` |

---

### `WorkflowStepLog`

| Propiedad | Tipo |
|---|---|
| `id` | `string` |
| `step_name` | `string` |
| `step_order` | `number` |
| `action` | `WorkflowStepAction` |
| `performed_by_email` | `string` |
| `comment` | `string` |
| `created_at` | `string` |

---

### `AuditLog`

| Propiedad | Tipo |
|---|---|
| `id` | `number` (BigAutoField) |
| `user` | `{ id: string; email: string } \| null` |
| `entity_type` | `string` |
| `entity_id` | `string` |
| `action` | `AuditAction` |
| `old_values` | `Record<string, unknown>` |
| `new_values` | `Record<string, unknown>` |
| `ip_address` | `string \| null` |
| `user_agent` | `string` |
| `metadata` | `Record<string, unknown>` |
| `created_at` | `string` |

---

### Union types

```typescript
OcrStatus       = 'pending' | 'processing' | 'completed' | 'failed' | 'skipped'
DocumentStatus  = 'draft' | 'under_review' | 'approved' | 'rejected' | 'archived'
UserRole        = 'super_admin' | 'org_admin' | 'supervisor' | 'editor' | 'viewer' | 'auditor'
WorkflowStatus  = 'pending' | 'in_progress' | 'completed' | 'rejected' | 'cancelled'
WorkflowStepAction = 'approved' | 'rejected' | 'commented'
AuditAction     = 'create' | 'update' | 'delete' | 'view' | 'download' | 'login' | 'logout' | 'restore' | 'status_change'
```

---

### Tipos locales de auth (`frontend/src/features/auth/types.ts`)

```typescript
LoginCredentials { email: string; password: string }
TokenPair        { access: string; refresh: string }
RefreshResponse  { access: string; refresh: string }
```

---

## 8. Frontend — API Client Functions

### Cliente base
**Path:** `frontend/src/lib/api-client.ts`

- `apiClient` — instancia Axios con `baseURL = VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'`
- Interceptor request: inyecta `Authorization: Bearer {accessToken}` desde Zustand
- Interceptor response: cola de refresh (`isRefreshing + failedQueue`) — un solo refresh para N 401 concurrentes; en fallo redirige a `/login`
- `unwrap<T>(response)` → `T` — desenvuelve `{data: Envelope<T>}`
- `unwrapPaginated<T>(response)` → `{ items: T[]; meta: PaginatedMeta }` — desenvuelve `PaginatedEnvelope<T>`
- `parseApiError(error)` → `ApiError` — normaliza errores Axios al formato `ApiError`

---

### `auth/api.ts` — `frontend/src/features/auth/api.ts`

| Función | Parámetros | Retorno | Endpoint |
|---|---|---|---|
| `login` | `LoginCredentials` | `Promise<TokenPair>` | `POST /auth/login/` |
| `logout` | `refreshToken: string` | `Promise<void>` | `POST /auth/logout/` |
| `refreshToken` | `refresh: string` | `Promise<RefreshResponse>` | `POST /auth/refresh/` |
| `getMe` | — | `Promise<UserProfile>` | `GET /auth/me/` |

---

### `documents/api.ts` — `frontend/src/features/documents/api.ts`

Objeto `documentsApi`:

| Función | Parámetros | Retorno | Endpoint |
|---|---|---|---|
| `list` | `ListDocumentsParams?` | `Promise<{items: Document[]; meta}>` | `GET /documents/` |
| `getById` | `id: string` | `Promise<Document>` | `GET /documents/{id}/` |
| `upload` | `UploadDocumentData` | `Promise<Document>` | `POST /documents/` (multipart) |
| `update` | `id, UpdateDocumentData` | `Promise<Document>` | `PATCH /documents/{id}/` |
| `delete` | `id: string` | `Promise<void>` | `DELETE /documents/{id}/` |
| `getDownloadUrl` | `id: string` | `Promise<string>` | `GET /documents/{id}/download/` |
| `getVersions` | `id, page=1` | `Promise<{items: DocumentVersion[]; meta}>` | `GET /documents/{id}/versions/` |
| `uploadVersion` | `id, UploadVersionData` | `Promise<DocumentVersion>` | `POST /documents/{id}/versions/` (multipart) |
| `reprocessOcr` | `id: string` | `Promise<void>` | `POST /documents/{id}/reprocess-ocr/` |
| `requestAiAnalysis` | `id: string` | `Promise<void>` | `POST /documents/{id}/analyze/` |

Objeto `foldersApi` (en `documents/api.ts`):

| Función | Parámetros | Retorno | Endpoint |
|---|---|---|---|
| `getTree` | — | `Promise<Folder[]>` | `GET /folders/tree/` |

**Tipos de parámetros:**
```typescript
ListDocumentsParams  { folder_id?, status?, page?, page_size? }
UploadDocumentData   { file: File, name, folder_id?, description?, tags?, onUploadProgress? }
UpdateDocumentData   { name?, description?, tags?, folder_id?: string | null }
UploadVersionData    { file: File, change_description?, onUploadProgress? }
```

---

### `folders/api.ts` — `frontend/src/features/folders/api.ts`

Objeto `foldersApi`:

| Función | Parámetros | Retorno | Endpoint |
|---|---|---|---|
| `list` | — | `Promise<{items: Folder[]; meta}>` | `GET /folders/` |
| `getById` | `id: string` | `Promise<Folder>` | `GET /folders/{id}/` |
| `create` | `CreateFolderData` | `Promise<Folder>` | `POST /folders/` |
| `rename` | `id, RenameFolderData` | `Promise<Folder>` | `PATCH /folders/{id}/` |
| `delete` | `id: string` | `Promise<void>` | `DELETE /folders/{id}/` |
| `getChildren` | `id, page=1` | `Promise<{items: Folder[]; meta}>` | `GET /folders/{id}/children/` |
| `getDocuments` | `id, page=1` | `Promise<{items: Document[]; meta}>` | `GET /folders/{id}/documents/` |

```typescript
CreateFolderData  { name: string; parent_id?: string }
RenameFolderData  { name: string }
```

---

### `workflows/api.ts` — `frontend/src/features/workflows/api.ts`

Objeto `workflowsApi.templates`:

| Función | Parámetros | Retorno | Endpoint |
|---|---|---|---|
| `list` | `ListTemplatesParams?` | `Promise<{items, meta}>` | `GET /workflows/templates/` |
| `getById` | `id` | `Promise<WorkflowTemplate>` | `GET /workflows/templates/{id}/` |
| `create` | `CreateTemplateData` | `Promise<WorkflowTemplate>` | `POST /workflows/templates/` |
| `update` | `id, UpdateTemplateData` | `Promise<WorkflowTemplate>` | `PATCH /workflows/templates/{id}/` |
| `delete` | `id` | `Promise<void>` | `DELETE /workflows/templates/{id}/` |

Objeto `workflowsApi.executions`:

| Función | Parámetros | Retorno | Endpoint |
|---|---|---|---|
| `list` | `ListExecutionsParams?` | `Promise<{items, meta}>` | `GET /workflows/executions/` |
| `getById` | `id` | `Promise<WorkflowExecution>` | `GET /workflows/executions/{id}/` |
| `start` | `StartExecutionData` | `Promise<WorkflowExecution>` | `POST /workflows/executions/` |
| `advance` | `id, AdvanceStepData` | `Promise<WorkflowExecution>` | `POST /workflows/executions/{id}/advance/` |
| `startFromDocument` | `documentId, {template_id}` | `Promise<WorkflowExecution>` | `POST /documents/{id}/start-workflow/` |
| `getLogs` | `id, page=1` | `Promise<{items: WorkflowStepLog[], meta}>` | `GET /workflows/executions/{id}/logs/` |

```typescript
CreateTemplateData     { name, description?, steps: CreateTemplateStepData[] }
CreateTemplateStepData { name, order, required_role: UserRole, is_final, actions }
UpdateTemplateData     { name?, description?, is_active? }
StartExecutionData     { document_id: string, template_id: string }
AdvanceStepData        { action: WorkflowStepAction, comment?: string }
```

---

### `audit/api.ts` — `frontend/src/features/audit/api.ts`

Objeto `auditApi`:

| Función | Parámetros | Retorno | Endpoint |
|---|---|---|---|
| `list` | `ListAuditLogsParams?` | `Promise<{items: AuditLog[], meta}>` | `GET /audit-logs/` |

```typescript
ListAuditLogsParams { action?, entity_type?, entity_id?, user_email?, created_after?, created_before?, page? }
```

---

### `search/api.ts` — `frontend/src/features/search/api.ts`

Objeto `searchApi`:

| Función | Parámetros | Retorno | Endpoint |
|---|---|---|---|
| `search` | `query: string, page=1` | `Promise<{items: SearchResult[], meta}>` | `GET /search/` |

---

## 9. Frontend — Hooks (TanStack Query)

### `features/auth/hooks.ts`

| Hook | Parámetros | Retorno | Query key |
|---|---|---|---|
| `useLogin` | — | `UseMutationResult<void, ApiError, LoginCredentials>` | — |
| `useLogout` | — | `UseMutationResult<void, ApiError, void>` | — |
| `useMe` | — | `UseQueryResult<UserProfile>` | `['auth', 'me']` |

`useLogin` es una mutación: llama `login()` → guarda tokens → llama `getMe()` → navega a `/`.
`useLogout` vacía Zustand y localStorage y navega a `/login`.

---

### `features/documents/hooks.ts`

**Query keys:**
```typescript
documentKeys.all              = ['documents']
documentKeys.list(params)     = ['documents', 'list', params]
documentKeys.detail(id)       = ['documents', id]
documentKeys.versions(id,page)= ['documents', id, 'versions', page]
folderKeys.tree               = ['folders', 'tree']
```

| Hook | Parámetros | Retorno |
|---|---|---|
| `useDocuments` | `params: ListDocumentsParams` | `UseQueryResult<{items, meta}>` |
| `useDocument` | `id: string, pollForAi=false` | `UseQueryResult<Document>` — polling 3s mientras OCR activo (cap ~2min) o AI en curso |
| `useDocumentVersions` | `id, page=1` | `UseQueryResult<{items, meta}>` |
| `useFolderTree` | — | `UseQueryResult<Folder[]>` |
| `useUploadDocument` | — | `{ mutation: UseMutationResult, uploadProgress: number }` |
| `useUpdateDocument` | — | `UseMutationResult<Document, ApiError, {id, data}>` |
| `useDeleteDocument` | — | `UseMutationResult<void, ApiError, string>` |
| `useDownloadDocument` | — | `UseMutationResult` — abre URL en `_blank` on success |
| `useUploadVersion` | `documentId: string` | `{ mutation, uploadProgress }` |
| `useReprocessOcr` | — | `UseMutationResult<void, ApiError, string>` |
| `useRequestAiAnalysis` | — | `UseMutationResult` — `meta.suppressGlobalToast: true` |

---

### `features/folders/hooks.ts`

**Query keys:**
```typescript
folderKeys.all              = ['folders']
folderKeys.list()           = ['folders', 'list']
folderKeys.detail(id)       = ['folders', id]
folderKeys.children(id,pg)  = ['folders', id, 'children', pg]
folderKeys.documents(id,pg) = ['folders', id, 'documents', pg]
```

| Hook | Parámetros | Retorno |
|---|---|---|
| `useFolders` | — | `UseQueryResult<{items, meta}>` |
| `useFolder` | `id` | `UseQueryResult<Folder>` |
| `useFolderChildren` | `id, page=1` | `UseQueryResult<{items, meta}>` |
| `useFolderDocuments` | `id, page=1` | `UseQueryResult<{items, meta}>` |
| `useCreateFolder` | — | `UseMutationResult<Folder, ApiError, CreateFolderData>` |
| `useRenameFolder` | — | `UseMutationResult<Folder, ApiError, {id, data}>` |
| `useDeleteFolder` | — | `UseMutationResult<void, ApiError, string>` |

---

### `features/workflows/hooks.ts`

**Query keys:**
```typescript
workflowKeys.templateList(params)    = ['workflows', 'templates', 'list', params]
workflowKeys.templateDetail(id)      = ['workflows', 'templates', id]
workflowKeys.executionList(params)   = ['workflows', 'executions', 'list', params]
workflowKeys.executionDetail(id)     = ['workflows', 'executions', id]
workflowKeys.executionLogs(id, pg)   = ['workflows', 'executions', id, 'logs', pg]
```

| Hook | Parámetros | Retorno |
|---|---|---|
| `useWorkflowTemplates` | `params?` | `UseQueryResult<{items, meta}>` |
| `useWorkflowTemplate` | `id` | `UseQueryResult<WorkflowTemplate>` |
| `useCreateWorkflowTemplate` | — | `UseMutationResult<WorkflowTemplate, ...>` |
| `useUpdateWorkflowTemplate` | — | `UseMutationResult<WorkflowTemplate, ..., {id, data}>` |
| `useDeleteWorkflowTemplate` | — | `UseMutationResult<void, ..., string>` |
| `useWorkflowExecutions` | `params?` | `UseQueryResult<{items, meta}>` |
| `useWorkflowExecution` | `id` | `UseQueryResult<WorkflowExecution>` — polling 5s mientras activo (cap ~4min) |
| `useStartWorkflowExecution` | — | `UseMutationResult<WorkflowExecution, ..., StartExecutionData>` |
| `useStartWorkflowFromDocument` | — | `UseMutationResult` — `meta.suppressGlobalToast: true` |
| `useAdvanceWorkflowStep` | — | `UseMutationResult<WorkflowExecution, ..., {id, data}>` |
| `useWorkflowExecutionLogs` | `id, page=1` | `UseQueryResult<{items, meta}>` |

---

### `features/audit/hooks.ts`

| Hook | Parámetros | Retorno | Query key |
|---|---|---|---|
| `useAuditLogs` | `params?, options?` | `UseQueryResult<{items, meta}>` | `['audit-logs', 'list', params]` |

---

### `features/search/hooks.ts`

| Hook | Parámetros | Retorno | Query key |
|---|---|---|---|
| `useSearch` | `query: string, page=1` | `UseQueryResult<{items, meta}>` | `['search', query, page]` |

`enabled` solo si `query.trim().length > 0`.

---

## 10. Frontend — Componentes Clave

### `ProtectedRoute`
**Path:** `frontend/src/shared/components/ProtectedRoute.tsx`
**Props:** ninguna
**Descripción:** Guarda las rutas autenticadas. Al montar, si existe `refreshToken` en localStorage pero no hay `accessToken+user` en Zustand, ejecuta bootstrap secuencial (refresh → getMe). Muestra Skeleton durante el proceso. Redirige a `/login` si no hay token.

---

### `OcrStatusBadge`
**Path:** `frontend/src/features/documents/components/OcrStatusBadge.tsx`
**Props:** `{ status: OcrStatus }`
**Descripción:** Badge visual para el estado OCR de un documento con colores diferenciados. Animación pulse para `processing`.

---

### `ExecutionStatusBadge`
**Path:** `frontend/src/features/workflows/components/ExecutionStatusBadge.tsx`
**Props:** `{ status: WorkflowStatus }`
**Descripción:** Badge visual para el estado de una ejecución de workflow.

---

### `DocumentUploadDropzone`
**Path:** `frontend/src/features/documents/components/DocumentUploadDropzone.tsx`
**Props:**
```typescript
{ open: boolean; folderId?: string; onOpenChange: (open: boolean) => void }
```
**Descripción:** Dialog con drag-and-drop (`react-dropzone`), validación de tipo/tamaño, formulario de nombre/descripción/tags, barra de progreso de upload. Usa `useUploadDocument`.

---

### `AdvanceStepDialog`
**Path:** `frontend/src/features/workflows/components/AdvanceStepDialog.tsx`
**Props:**
```typescript
{ open: boolean; isPending: boolean; onOpenChange: (open: boolean) => void; onSubmit: (data: AdvanceStepData) => void }
```
**Descripción:** AlertDialog con selector de acción (`approved | rejected | commented`) y textarea de comentario (obligatorio solo para `commented`). Validación zod inline. El frontend no valida RBAC — lo delega al backend (decision #36).

---

### `StartWorkflowDialog`
**Path:** `frontend/src/features/workflows/components/StartWorkflowDialog.tsx`
**Props:**
```typescript
{ documentId: string; open: boolean; onOpenChange: (open: boolean) => void }
```
**Descripción:** Dialog para iniciar un workflow desde un documento. Muestra selector de plantillas activas, maneja inline el error `WORKFLOW_ALREADY_ACTIVE`, navega a la ejecución creada on success.

---

### `WorkflowTemplateForm`
**Path:** `frontend/src/features/workflows/components/WorkflowTemplateForm.tsx`
**Props:**
```typescript
{ defaultValues?, onSubmit: (values: TemplateFormValues) => void; isPending: boolean; submitLabel? }
```
**Descripción:** Formulario de creación/edición de plantillas con `useFieldArray` para los pasos. Validación: exactamente un paso `is_final`, todos los pasos con nombre y rol. Tipo `TemplateFormValues` exportado.

---

### `Pagination`
**Path:** `frontend/src/shared/components/Pagination.tsx`
**Descripción:** Componente genérico de paginación. Usa `PaginatedMeta` del backend.

---

### `AppLayout` / `Sidebar` / `Header`
**Path:** `frontend/src/shared/components/`
**Descripción:** Layout principal de la app. `Sidebar` contiene navegación principal. `Header` muestra usuario actual (de `useAuthStore`) y botón de logout.

---

## 11. Frontend — Stores (Zustand)

### `useAuthStore`
**Path:** `frontend/src/features/auth/store.ts`

**Estado:**

| Campo | Tipo | Notas |
|---|---|---|
| `accessToken` | `string \| null` | En memoria (no persiste entre recargas) |
| `user` | `UserProfile \| null` | Perfil del usuario autenticado |

**Actions:**

| Acción | Firma | Efecto |
|---|---|---|
| `setAccessToken` | `(token: string) => void` | Guarda token en Zustand |
| `setUser` | `(user: UserProfile) => void` | Guarda perfil en Zustand |
| `logout` | `() => void` | Limpia `accessToken` + `user` + `localStorage.refreshToken` |

**Nota:** `refreshToken` se almacena en `localStorage` (fuera del store). Tradeoff XSS documentado — migrar a httpOnly cookies es deuda técnica Fase 6 (decisión #28).

---

## 12. Contrato Frontend-Backend

| Hook / Función frontend | Método + Endpoint | Request type | Response `data` type |
|---|---|---|---|
| `login` | `POST /auth/login/` | `LoginCredentials` | `TokenPair + user: UserProfile` |
| `logout` | `POST /auth/logout/` | `{refresh: string}` | — |
| `refreshToken` | `POST /auth/refresh/` | `{refresh: string}` | `{access, refresh}` |
| `getMe` / `useMe` | `GET /auth/me/` | — | `UserProfile` |
| `useFolders` | `GET /folders/` | — | `Folder[]` paginado |
| `useFolderTree` / `foldersApi.getTree` | `GET /folders/tree/` | — | `Folder[]` |
| `useFolder` | `GET /folders/{id}/` | — | `Folder` |
| `useCreateFolder` | `POST /folders/` | `CreateFolderData` | `Folder` |
| `useRenameFolder` | `PATCH /folders/{id}/` | `RenameFolderData` | `Folder` |
| `useDeleteFolder` | `DELETE /folders/{id}/` | — | — (204) |
| `useFolderChildren` | `GET /folders/{id}/children/` | — | `Folder[]` paginado |
| `useFolderDocuments` | `GET /folders/{id}/documents/` | — | `Document[]` paginado |
| `useDocuments` | `GET /documents/` | `ListDocumentsParams` | `Document[]` paginado |
| `useDocument` | `GET /documents/{id}/` | — | `Document` |
| `useUploadDocument` | `POST /documents/` | `FormData (UploadDocumentData)` | `Document` |
| `useUpdateDocument` | `PATCH /documents/{id}/` | `UpdateDocumentData` | `Document` |
| `useDeleteDocument` | `DELETE /documents/{id}/` | — | — (204) |
| `useDownloadDocument` | `GET /documents/{id}/download/` | — | `{url: string}` |
| `useDocumentVersions` | `GET /documents/{id}/versions/` | — | `DocumentVersion[]` |
| `useUploadVersion` | `POST /documents/{id}/versions/` | `FormData (UploadVersionData)` | `DocumentVersion` |
| `useReprocessOcr` | `POST /documents/{id}/reprocess-ocr/` | — | `Document` (202) |
| `useRequestAiAnalysis` | `POST /documents/{id}/analyze/` | — | `Document` (202) |
| `useStartWorkflowFromDocument` | `POST /documents/{id}/start-workflow/` | `{template_id: string}` | `WorkflowExecution` |
| `useWorkflowTemplates` | `GET /workflows/templates/` | `ListTemplatesParams` | `WorkflowTemplate[]` paginado |
| `useWorkflowTemplate` | `GET /workflows/templates/{id}/` | — | `WorkflowTemplate` |
| `useCreateWorkflowTemplate` | `POST /workflows/templates/` | `CreateTemplateData` | `WorkflowTemplate` |
| `useUpdateWorkflowTemplate` | `PATCH /workflows/templates/{id}/` | `UpdateTemplateData` | `WorkflowTemplate` |
| `useDeleteWorkflowTemplate` | `DELETE /workflows/templates/{id}/` | — | — (204) |
| `useWorkflowExecutions` | `GET /workflows/executions/` | `ListExecutionsParams` | `WorkflowExecution[]` paginado |
| `useWorkflowExecution` | `GET /workflows/executions/{id}/` | — | `WorkflowExecution` |
| `useStartWorkflowExecution` | `POST /workflows/executions/` | `StartExecutionData` | `WorkflowExecution` |
| `useAdvanceWorkflowStep` | `POST /workflows/executions/{id}/advance/` | `AdvanceStepData` | `WorkflowExecution` |
| `useWorkflowExecutionLogs` | `GET /workflows/executions/{id}/logs/` | — | `WorkflowStepLog[]` paginado |
| `useAuditLogs` | `GET /audit-logs/` | `ListAuditLogsParams` | `AuditLog[]` paginado |
| `useSearch` | `GET /search/` | `{q, page}` | `SearchResult[]` paginado |

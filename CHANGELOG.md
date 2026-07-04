# Changelog

Todos los cambios notables de este proyecto están documentados aquí.
Formato basado en [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

---

## [6.1] — 2026-07-03

Fase 6.1: refresh token JWT migrado de `localStorage` a cookie httpOnly con protección CSRF.

### Security
- `76f6dc5` Refresh token de JWT ya no viaja en el body de `/auth/login/` ni se persiste en `localStorage`: ahora vive en cookie `HttpOnly Secure SameSite=Strict` (`sv_refresh`), inaccesible a JavaScript y por lo tanto a XSS
- `76f6dc5` Protección CSRF double-submit en `/auth/refresh/` y `/auth/logout/`: cookie no-HttpOnly `sv_csrf` + header `X-CSRF-Token`, comparados con `secrets.compare_digest`
- `76f6dc5` `LogoutView` pasa de `IsAuthenticated` a `AllowAny`: la identidad válida para cerrar sesión la da el refresh (vía cookie) + su blacklist, no un `access` que puede haber expirado
- `76f6dc5` Rollout controlado por feature-flag `AUTH_REFRESH_COOKIE_ENABLED` (activado por defecto, con fallback a leer el refresh del body si no hay cookie)
- `b2ac8e9` Frontend deja de leer/escribir `refreshToken` en `localStorage`; `api-client.ts` usa `withCredentials: true` y adjunta `X-CSRF-Token` automáticamente en refresh/logout
- `b2ac8e9` Proxy `/api` de Vite (`vite.config.ts`) para same-origin en dev, prerrequisito de `SameSite=Strict`

### Added
- `0e978eb` Tests backend (`test_auth_cookie.py`): cookie de login, refresh con/sin cookie, CSRF ausente/incorrecto, aislamiento de tenant, flag desactivado = comportamiento legado
- `6701bc8` Tests frontend actualizados para el flujo de cookie: interceptor, store y bootstrap de `ProtectedRoute` sin dependencia de `localStorage`
- Creado `frontend/.env.example` (gap detectado durante esta sub-fase; no existía)

### Changed
- Documentado el uso relativo de `VITE_API_BASE_URL=/api/v1` en dev (antes absoluto a `localhost:8000`), requerido para que el proxy de Vite entregue la cookie same-origin

---

## [post-5.5] — 2026-07-01

Correcciones y mejoras de calidad tras las pruebas post-portafolio.

### Added
- `bf343b6` Componente `FileTypeBadge` para mostrar el tipo MIME del documento con icono y color en las tarjetas

### Fixed
- `545a6c8` Crash en `SearchPage`: `ocr_status` añadido a `SearchResultSerializer`; fallback defensivo en `OcrStatusBadge` para valores desconocidos
- `545a6c8` Tipo `SearchResult` redefinido como `Omit<Document,...> & { rank }` para reflejar el shape real del endpoint de búsqueda (antes era `Document[]` completo)
- `545a6c8` Entidades de análisis IA siempre invisibles: tipo `AiAnalysis.entities` corregido a `{dates, amounts, names}` (el frontend lo tipaba como `string[]`)
- `76f0f8f` Patrón `lib/` demasiado amplio en `.gitignore` sustituido por `backend/lib/` y `backend/lib64/` para no ignorar `frontend/src/shared/lib/`

### Changed
- `c8e6033` `ExecutionStatusBadge` añade fallback para status de workflow no conocidos por el cliente (mismo patrón que `OcrStatusBadge`)
- `c8e6033` `WRITE_ROLES` y `START_ROLES` centralizados en `frontend/src/shared/lib/roles.ts`; eliminadas 8 declaraciones locales duplicadas
- `c8e6033` Polling de OCR se detiene tras 40 intentos (~2 min); polling de workflow tras 48 intentos (~4 min)
- `c8e6033` Tipo de retorno de `getVersions` corregido a `Partial<PaginatedMeta>` (el endpoint devuelve `meta: {}` vacío, no un meta paginado)
- `c8e6033` Código muerto del módulo de auditoría frontend eliminado: `auditApi.getById`, `useAuditLog` y `auditKeys.detail`

---

## [post-5.5-features] — 2026-06-30

Funcionalidades y correcciones añadidas durante la sesión de testing post-portafolio.

### Added
- `d90b01d` Acción "Iniciar workflow" en la cabecera de `DocumentDetailPage` con `StartWorkflowDialog` y selector de plantilla; navega a la ejecución al confirmar
- `d90b01d` Endpoint `POST /api/v1/documents/{id}/start-workflow/`; devuelve 409 si el documento ya tiene una ejecución activa
- `cc78fa8` Asignación de carpeta desde la pestaña "Editar metadata" de un documento; `PATCH /documents/{id}/` acepta `folder_id` (UUID o `null` para mover a raíz)
- `cc78fa8` `GET /api/v1/folders/tree/` que devuelve la lista plana de carpetas de la organización para el selector de carpetas
- `74e9c5b` Pestaña "Contenido OCR" restaurada en `DocumentDetailPage`; visible solo cuando `ocr_content` tiene texto (campo expuesto como `read_only` en `DocumentSerializer`)
- `0f5da56` Botón "Subir documento" en `FolderBrowserPage` condicionado a rol con permiso de escritura y carpeta no raíz; pre-asigna `folder_id`

### Fixed
- `35a7517` **Crítico:** `refreshToken()` no desenvolvía el envelope; siempre devolvía `access: undefined` causando que la sesión nunca se restaurara tras recarga de página
- `35a7517` **Crítico:** Interceptor 401 accedía a `data.access` directo en lugar de `envelope.data.access`
- `35a7517` **Crítico:** Token de refresh rotativo (`ROTATE_REFRESH_TOKENS=True`) descartado silenciosamente; el token anterior quedaba blacklisteado causando logout tras 60 min de sesión
- `1aa4f04` Tipos TypeScript de `WorkflowExecution` y `WorkflowStepLog` corregidos: campos planos del serializer (`template_name`, `started_by_email`, `step_name`) en lugar de objetos anidados que causaban crash en runtime
- `263a28e` Tipos TypeScript de `Document` y `Folder` alineados con la respuesta real del backend (`created_by_email`, `folder_name`, `folder` como UUID en lugar de objeto)
- `43e8380` Formulario de upload retenía el `folder_id` de la carpeta anterior al navegar; corregido con `key={id}` en `DocumentUploadDropzone` para forzar remount
- `c403a56` Crash en `WorkflowTemplateForm`: `<FormLabel>` usado fuera de `<FormField>` (requiere contexto React) reemplazado por `<label>` HTML estándar
- `e16f183` `NaN` como número total de páginas en `DocumentVersionList` (el endpoint devuelve `meta: {}` vacío)
- `e16f183` Campo de UUID manual en `WorkflowExecutionsPage` reemplazado por selector de documentos con búsqueda

---

## [5.5] — 2026-06-29

Fase 5.5: Deploy en producción.

### Added
- `88ad4d1` `backend/Dockerfile` multi-stage: builder instala dependencias Python + libmagic + Tesseract + Poppler; runtime ejecuta como `appuser` no-root; `collectstatic` durante el build como root para evitar errores de permisos
- `88ad4d1` `frontend/Dockerfile` multi-stage: Node 20 Alpine para el build de Vite; Nginx stable-alpine para servir el SPA; `VITE_API_BASE_URL=/api/v1` fijado en tiempo de build
- `88ad4d1` `docker-compose.prod.yml` con 8 servicios: `migrate` (one-shot), `web`, `worker`, `beat`, `nginx`, `postgres`, `redis`, `minio`
- `88ad4d1` `nginx/nginx.conf`: redirección HTTP→HTTPS, TLS 1.2/1.3, proxy a `/api/` `/admin/` `/static/`, fallback SPA, `client_max_body_size 50m`
- `88ad4d1` `scripts/deploy.sh` idempotente: pull, build, migrate y restart sin downtime
- `88ad4d1` `scripts/backup_db.sh`: `pg_dump` comprimido, retención de 7 días, escritura atómica (temp → `mv`)
- `88ad4d1` `docs/deploy-guide.md`: guía educativa con 10 secciones (requisitos VPS, variables de entorno, SSL, operaciones de mantenimiento)

---

## [5.4] — 2026-06-29

Fase 5.4: CI/CD con GitHub Actions.

### Added
- `81438bb` Pipeline CI (`.github/workflows/ci.yml`): jobs paralelos de backend y frontend; PostgreSQL 16 y Redis 7 como runner services
- `81438bb` Job backend: `flake8` + `black` + `pytest -m "not integration"` (tests de integración con MinIO excluidos) + informe de cobertura a Codecov
- `81438bb` Job frontend: `eslint` + `tsc --noEmit` + `vitest` + `vite build`
- `81438bb` Workflow `deploy.yml` scaffold para disparo manual (`workflow_dispatch`) apuntando al servidor de producción
- `81438bb` Badges de estado CI y cobertura Codecov en `README.md`

### Fixed
- `c69c22b` Seis hallazgos del post-review de Fase 5.3: filtro de auditoría enviaba email al backend que esperaba UUID; fechas "hasta" excluían eventos del día seleccionado; polling de análisis IA sin estado terminal de fallo; `WorkflowStepLogTimeline` sin fallback para acciones desconocidas; `WorkflowTemplateForm` podía entrar en loop de reset con objeto inline; query de auditoría se ejecutaba antes de verificar el rol del usuario

### Changed
- `81438bb` Gate de cobertura mínima al 95% en `pyproject.toml` (`--cov-fail-under=95`; `--cov=apps`)
- `81438bb` Script `typecheck` (`tsc --noEmit`) añadido a `frontend/package.json`

---

## [5.3] — 2026-06-21

Fase 5.3: Frontend de workflows, auditoría y análisis IA.

### Added
- `8aa9ec5` `WorkflowTemplateForm` con `useFieldArray` de react-hook-form y validación Zod para crear/editar plantillas de workflow con pasos dinámicos
- `8aa9ec5` `AdvanceStepDialog` (`AlertDialog` + select de acción + textarea de comentario) para aprobar/rechazar/completar pasos
- `8aa9ec5` `ExecutionStatusBadge` y `WorkflowStepLogTimeline` con tiempos relativos (`formatDistanceToNow`)
- `8aa9ec5` `AuditLogPage` con `AuditLogFilters` (rango de fechas, tipo de entidad, acción, email) y `AuditLogTable` paginada
- `8aa9ec5` Pestaña "Análisis IA" en `DocumentDetailPage` con polling hasta obtener resultado o error; botón "Reintentar" si la tarea Celery falla
- `8aa9ec5` Rutas `/workflows`, `/workflows/templates/:id`, `/workflows/executions`, `/workflows/executions/:id`, `/audit-logs`
- `f352b8d` Componentes shadcn/ui añadidos: `textarea`, `checkbox`, `separator`, `accordion`

---

## [5.2] — 2026-06-19

Fase 5.2: Frontend de gestión documental.

### Added
- `acad851` `FolderBrowserPage` con navegación jerárquica de carpetas, creación y eliminación
- `acad851` `DocumentListPage` con filtros por carpeta, estado y texto
- `acad851` `DocumentDetailPage` con pestañas de metadata, versiones, contenido OCR y edición
- `acad851` Upload de documentos con drag-and-drop (`react-dropzone`), barra de progreso y validación client-side de tipo MIME y tamaño
- `acad851` `OcrStatusBadge` con polling automático mientras el documento está en estado `pending` o `processing`
- `acad851` `SearchPage` con búsqueda full-text y resaltado de resultado por campo
- `acad851` `DashboardPage` con estadísticas de documentos, carpetas y workflows de la organización
- `fecd040` Dependencias añadidas: `react-dropzone`, `date-fns` y nuevos componentes shadcn/ui

---

## [5.1 + 5.7] — 2026-06-10 a 2026-06-15

Fase 5.1: Scaffold React + autenticación. Fase 5.7: Notificaciones. Auditoría de ambas fases.

### Added
- `1c96655` Scaffold frontend: React 18 + TypeScript + Vite + Tailwind CSS + shadcn/ui
- `1c96655` `api-client.ts` con cola de refresh concurrente (`isRefreshing + failedQueue`) que garantiza exactamente 1 refresh para N requests 401 simultáneas
- `1c96655` Store de autenticación Zustand con `accessToken` en memoria y `refreshToken` en `localStorage`
- `1c96655` `LoginForm`, `ProtectedRoute` (bootstrap secuencial de sesión), `AppLayout`, `Sidebar`, `Header`
- `b69d4dc` App `notifications`: modelo `Notification` con FK a organización; `notification_service.notify_step_assigned`; tarea Celery `send_notification` con autoretry sobre `TransientError` (SMTP)
- `b69d4dc` `workflow_service` encola notificaciones al asignar pasos via `transaction.on_commit` (import lazy para evitar ciclos)

### Fixed
- `f9d4eff` Perfil de usuario no rehidratado tras recarga de página: bootstrap secuencial `refresh → setAccessToken → getMe → setUser` en `ProtectedRoute`
- `f9d4eff` `Promise.reject` faltante como fallback en el interceptor 401 (podía resolver con `undefined` silenciosamente)
- `f9d4eff` Errores de mutación completamente invisibles: toast global implementado via `MutationCache.onError`; mutaciones con UI de error propia usan `meta: { suppressGlobalToast: true }`
- `f9d4eff` Narrowing inseguro de `ApiError` con double cast (`as ApiError`) corregido a `instanceof ApiError`
- `cb0654d` Doble envío concurrente de notificaciones: claim atómico `UPDATE WHERE status IN (pending, failed)` con comprobación de `rowcount`; solo el worker con `rowcount == 1` procede al envío SMTP

---

## [5.6] — 2026-06-04

Fase 5.6: Health check, Sentry y logging estructurado.

### Added
- `168af6d` Endpoint `GET /api/v1/health/` público (sin envelope, sin autenticación) con chequeo de conectividad de PostgreSQL, Redis y MinIO
- `168af6d` Integración Sentry gateada por variable `SENTRY_DSN`: sin configuración en dev por defecto; `send_default_pii=False`; scrubbing de cabecera `Authorization` y bodies de `/auth/`
- `168af6d` JSON logging solo en `production.py`; `RequestContextFilter` que inyecta `organization_id`, `user_id` y `request_id` en cada log

---

## [4.x] — 2026-06-02 a 2026-06-04

Fase 4: Pipeline OCR async, tarea de limpieza de blobs y análisis IA con Claude API.

### Added
- `478de86` Campo `ocr_status` en el modelo `Document` con cinco estados: `pending`, `processing`, `done`, `failed`, `skipped`; migración incluida
- `73a0392` Clase `TransientError` en `apps/core` para señalar fallos recuperables y activar el autoretry de Celery
- `93ff0f4` `StorageService.download_file()` para descargar blobs de MinIO como stream hacia el worker de OCR
- `3f798b8` Pipeline OCR completo en `ocr_service.process()`: PDF (pdf2image + pytesseract), imágenes (pytesseract directo), Office → `ocr_status=skipped`; resultado escribe en `ocr_content` y dispara la señal FTS
- `81a9e17` Endpoint `POST /documents/{id}/reprocess-ocr/` para reiniciar el pipeline OCR de un documento existente
- `05a6a79` Tarea Beat diaria `cleanup_orphan_blobs` a las 03:00 UTC: lista blobs en MinIO, cruza con `Document` y `DocumentVersion`, borra los que llevan más de 24h sin referencia
- `6500c6e` Análisis de documentos con Claude Haiku 3 + prompt caching; feature-flag: sin `ANTHROPIC_API_KEY` → 503; resultado almacenado en `metadata["ai_analysis"]`; endpoint asíncrono `POST /documents/{id}/analyze/` responde 202
- `2b8052c` Dependencias OCR añadidas: `pytesseract`, `pdf2image` (Python) + `tesseract-ocr`, `tesseract-ocr-spa`, `poppler-utils` (sistema)

### Fixed
- `341f21b` Errores recuperables del SDK Anthropic (`RateLimitError`, `APITimeoutError`, `APIConnectionError`) no mapeados a `TransientError`; la tarea fallaba permanentemente sin reintentar
- `341f21b` `reprocess_ocr` no reseteaba `ocr_status=PENDING` antes de encolar: el usuario veía el documento en estado `failed` sin indicación de que estaba en cola
- `341f21b` `max_retries=3` establecido inline en los decoradores `@shared_task` (antes dependía del setting global, impidiendo overrides en tests)

### Changed
- `d9dd585` Tarea `process_ocr` robustecida: política de reintentos exponencial (`autoretry_for=TransientError`, `retry_backoff=True`); lógica delegada a `ocr_service` (la tarea solo despacha)

---

## [3.x] — 2026-05-29 a 2026-05-31

Fase 3: API de auditoría, motor de workflows y búsqueda full-text.

### Added
- `9279819` API de auditoría de solo lectura `GET /api/v1/audit-logs/` con filtros por fecha, usuario (email), entidad, tipo de entidad y acción; accesible solo a `org_admin`, `super_admin` y `auditor`
- `b80a43e` Motor de workflows completo: modelos `WorkflowTemplate`, `WorkflowStep`, `WorkflowExecution`, `WorkflowStepLog`; `workflow_service` con `start`, `advance_step`, `cancel`; API REST `/api/v1/workflows/`
- `ec691d9` Búsqueda full-text PostgreSQL: señal `post_save` reconstruye `search_vector` (pesos A/B/C/D por campo); índice GIN; endpoint `GET /api/v1/search/` con ranking por relevancia
- `108fd52` Tests de integración reales para `StorageService` contra MinIO (`@pytest.mark.integration`)

### Fixed
- `c9258ea` Race condition en `start_workflow`: `UniqueConstraint` parcial `uq_wf_exec_one_active_per_document` en PostgreSQL como barrera definitiva; `IntegrityError` mapeado a `ConflictError (409)`
- `c9258ea` Doble-avance concurrente en `advance_step`: `select_for_update(of=("self",))` para lock de fila durante la transacción
- `c9258ea` Señal FTS reconstruía `search_vector` en cada `save()` aunque solo cambiara `status`: ahora compara campos de texto antes de proceder

### Changed
- `6162e74` Listados de templates y logs de workflow ahora paginan con `StandardPagination` (antes devolvían listas completas con `meta: {}`)

---

## [2.x] — 2026-05-28

Fase 2: Core de gestión documental.

### Added
- `41159af` Modelos `Folder`, `Document`, `DocumentVersion` con índices compuestos (org+status, org+created_at), índice GIN en `search_vector` y `UniqueConstraint` condicionales para soft delete
- `41159af` `FileValidator`: validación por magic bytes (python-magic), checksum SHA-256, límite de 50 MB y lista blanca de tipos MIME
- `41159af` `StorageService`: integración con MinIO/S3 via boto3, upload/delete de blobs, generación de presigned URLs
- `41159af` `FolderService`: create/rename/move con detección de ciclos de carpetas; soft delete propagado a documentos hijos
- `41159af` `DocumentService`: upload atómico en `transaction.atomic()` (documento + versión 1 + audit log + stub OCR via `on_commit`); transición de estado `draft↔under_review`; soft delete
- `41159af` REST endpoints `GET|POST /api/v1/folders/` y `GET|POST /api/v1/documents/` con RBAC por rol, envelope estándar y paginación
- `41159af` Modelo `AuditLog` inmutable: `BigAutoField` (no UUID), sin herencia de `BaseModel`, append-only

---

## [1.x] — 2026-05-25 a 2026-05-27

Fase 1: Fundamentos del backend (Django, multi-tenancy, auth, RBAC, usuarios).

### Added
- `869766d` Settings en 4 capas: `base.py`, `development.py`, `test.py`, `production.py`
- `61024a8` App `core`: `BaseModel` (UUID primary key, `created_at`, `updated_at`, `deleted_at`), `SoftDeleteManager`, manejador global de excepciones con envelope de error
- `26b0dc3` App `organizations`: modelo `Organization`, `organization_service`, `organization_selector`, REST API `GET|POST /api/v1/organizations/`
- `2414c0d` App `authentication`: `User` custom basado en `AbstractBaseUser`; JWT con claims `organization_id`, `role`, `email`; refresh token rotativo con blacklist; `OrganizationTenantMiddleware` que inyecta `request.organization` en cada request autenticado
- `b8928eb` RBAC: `IsOrganizationMember`, `HasRole` (class factory), `IsOrgAdmin`, `IsSuperAdmin` en `apps/permissions/`
- `801d34f` Gestión de usuarios dentro de la organización: invitar, listar, activar/desactivar, cambiar rol
- `2e5184f` `StandardPagination` con envelope `{data: [...], meta: {count, page, page_size, next, previous}}`; documentación OpenAPI interactiva en `/api/docs/` (Swagger) y `/api/redoc/`

### Changed
- `54b0319` `BaseModel.deleted_at` añade `db_index=True` para acelerar las queries de soft delete (`WHERE deleted_at IS NULL`)

---

## [0.x] — 2026-05-09

Setup inicial del proyecto.

### Added
- `c36cfc1` Setup inicial: WSL2, Docker Compose con PostgreSQL 16, Redis 7 y MinIO; pre-commit hooks (`black`, `isort`, `flake8`); `.env.example` con todas las variables de entorno requeridas

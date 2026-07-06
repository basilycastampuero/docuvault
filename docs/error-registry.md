# SasVault — Registro de Errores del Proyecto

> Registro factual cronológico de todos los errores cometidos durante el desarrollo,
> con causa raíz y solución aplicada. Extraído de la BITACORA, CLAUDE.md y las
> auditorías de cada fase.
>
> Uso principal: referencia histórica y fuente para `docs/ai-agent-guide.md`.
> Última actualización: 2026-07-06. Errores registrados: ERR-001 a ERR-070.

---

## Índice por categoría

| Categoría | Errores |
|---|---|
| `TYPE_CONTRACT` | ERR-005, ERR-019, ERR-020, ERR-022, ERR-023, ERR-025, ERR-037, ERR-038, ERR-039, ERR-040, ERR-041, ERR-044, ERR-046, ERR-047, ERR-048, ERR-049, ERR-050, ERR-062, ERR-064, ERR-065, ERR-066, ERR-067, ERR-070 |
| `REACT_STATE` | ERR-015, ERR-016, ERR-021, ERR-026, ERR-045, ERR-059 |
| `ASYNC_CELERY` | ERR-008, ERR-009, ERR-012, ERR-013, ERR-014, ERR-017, ERR-018, ERR-063 |
| `ENVELOPE` | ERR-010, ERR-039, ERR-040, ERR-041, ERR-042 |
| `MIGRATION` | ERR-002, ERR-006, ERR-043 |
| `DEPENDENCY` | ERR-004, ERR-028, ERR-029, ERR-030, ERR-031, ERR-033, ERR-034, ERR-035, ERR-036, ERR-055 |
| `POLLING` | ERR-024, ERR-052 |
| `ESLINT_CONFIG` | ERR-057, ERR-058 |
| `DEAD_CODE` | ERR-003, ERR-007, ERR-032, ERR-051, ERR-053, ERR-060 |
| `GITIGNORE` | ERR-001, ERR-056, ERR-061 |
| `RBAC` | ERR-027 |
| `N_PLUS_1` | ERR-011 |
| `SOFT_DELETE` | ERR-006 |
| `UI_OVERFLOW` | ERR-054 |
| `TEST_QUALITY` | ERR-068 |

---

## Fase 0–1: Setup y correcciones iniciales (pre Fase 2)

---

## ERR-001: `backend/.env` trackeado en git desde el commit inicial

| Campo | Valor |
|---|---|
| Fecha | N/D (pre Fase 2) |
| Fase | Fase 0 |
| Severidad | ALTA |
| Categoría | `GITIGNORE` |
| Archivo(s) afectado(s) | `backend/.env`, `.gitignore` |

**Descripción:** El archivo `backend/.env` (con credenciales de desarrollo: `minioadmin`/`minioadmin`) se incluyó en el primer commit y quedó trackeado en el historial de git.

**Causa raíz:** El `.gitignore` no fue configurado antes de hacer el primer `git add .`. El archivo `.env` con placeholders genéricos se añadió sin pensar que contendría credenciales reales.

**Solución aplicada:** `git rm --cached backend/.env` para dejar de trackear el archivo sin borrarlo del disco. Actualización del `.gitignore` para incluir `backend/.env`.

**Commit de corrección:** `dae4199`

---

## ERR-002: Falta `db_index=True` en `BaseModel.deleted_at`

| Campo | Valor |
|---|---|
| Fecha | N/D (pre Fase 2) |
| Fase | Fase 1.2 |
| Severidad | MEDIA |
| Categoría | `MIGRATION` |
| Archivo(s) afectado(s) | `backend/apps/core/models/base.py` |

**Descripción:** `CLAUDE.md §6` documentaba `db_index=True` en el campo `deleted_at`, pero el modelo real no lo tenía. Las queries de soft delete (`WHERE deleted_at IS NULL`) hacían full table scan en lugar de usar índice.

**Causa raíz:** El modelo se implementó sin respetar exactamente la especificación de `CLAUDE.md`. La discrepancia no se detectó en los tests iniciales porque los volúmenes de datos en tests son pequeños.

**Solución aplicada:** Se añadió `db_index=True` al campo `deleted_at` en `BaseModel`; se generaron migraciones correctivas en las apps `authentication` y `organizations`.

**Commit de corrección:** `54b0319`

---

## ERR-003: `StandardPagination` referenciada en `CLAUDE.md` pero no implementada

| Campo | Valor |
|---|---|
| Fecha | N/D (pre Fase 2) |
| Fase | Fase 1.2 |
| Severidad | MEDIA |
| Categoría | `DEAD_CODE` |
| Archivo(s) afectado(s) | `backend/apps/core/pagination.py` (inexistente) |

**Descripción:** `CLAUDE.md §7` especificaba el formato de envelope `{data: [...], meta: {count, page, page_size, total_pages, next, previous}}`, pero la clase `StandardPagination` no existía. Los endpoints de lista no usaban paginación consistente.

**Causa raíz:** La documentación del proyecto se escribió antes de implementar la funcionalidad. No hubo verificación de que el código corresponde a lo documentado.

**Solución aplicada:** Se creó `apps/core/pagination.py` con la clase `StandardPagination` que implementa el envelope completo.

**Commit de corrección:** `2e5184f`

---

## ERR-004: `drf-spectacular` en `base.py` pero no en `requirements.txt`

| Campo | Valor |
|---|---|
| Fecha | N/D (pre Fase 2) |
| Fase | Fase 1.2 |
| Severidad | MEDIA |
| Categoría | `DEPENDENCY` |
| Archivo(s) afectado(s) | `backend/requirements.txt`, `backend/config/settings/base.py` |

**Descripción:** `base.py` referenciaba la configuración de `drf-spectacular` (endpoints `/api/schema/`, `/api/docs/`) y las views estaban decoradas con `@extend_schema`, pero el paquete no estaba instalado ni en `requirements.txt`.

**Causa raíz:** La configuración se escribió anticipando la dependencia sin instalarla. El error no rompía el arranque de Django porque la importación estaba dentro de bloques `INSTALLED_APPS` y no a nivel de módulo.

**Solución aplicada:** `pip install drf-spectacular==0.27.2`, añadido a `requirements.txt`; decoradores `@extend_schema` añadidos a todas las views existentes.

**Commit de corrección:** `2e5184f`

---

## ERR-005: Nombres de tabla erróneos en `docs/database-conventions.md`

| Campo | Valor |
|---|---|
| Fecha | N/D (pre Fase 2) |
| Fase | Fase 1.3 |
| Severidad | BAJA |
| Categoría | `TYPE_CONTRACT` |
| Archivo(s) afectado(s) | `docs/database-conventions.md` |

**Descripción:** El documento de convenciones usaba los nombres auto-generados de Django (`organizations_organization`, `auth_user`) en lugar de los nombres reales definidos con `db_table` (`organizations`, `users`). El esquema del modelo `User` tampoco incluía los campos `role` y `organization_id`.

**Causa raíz:** La documentación se redactó antes de que el modelo estuviera implementado con sus metadatos finales.

**Solución aplicada:** Corrección del documento para reflejar los nombres reales. Se marcó `CLAUDE.md §6` como fuente autoritativa en caso de conflicto.

**Commit de corrección:** `e6db851`

---

## ERR-006: `BaseModel.soft_delete()` omitía `updated_at` en `update_fields`

| Campo | Valor |
|---|---|
| Fecha | N/D (pre Fase 2) |
| Fase | Fase 1.2 |
| Severidad | MEDIA |
| Categoría | `SOFT_DELETE`, `MIGRATION` |
| Archivo(s) afectado(s) | `backend/apps/core/models/base.py` |

**Descripción:** El método `soft_delete()` del patrón de código documentado llamaba a `save(update_fields=["deleted_at"])`. Con `auto_now=True` en `updated_at`, Django solo actualiza ese campo si está incluido explícitamente en `update_fields`. Los registros marcados como soft-deleted no actualizaban su `updated_at`.

**Causa raíz:** El comportamiento de `auto_now=True` con `update_fields` es no obvio: el campo se omite si no está en la lista, incluso aunque sea `auto_now`.

**Solución aplicada:** Corrección en `docs/coding-patterns.md` y en el modelo: `save(update_fields=["deleted_at", "updated_at"])`.

**Commit de corrección:** `dae4199`

---

## ERR-007: `docs/coding-patterns.md` usaba `DocuVaultException` en lugar de `ApplicationError`

| Campo | Valor |
|---|---|
| Fecha | N/D (pre Fase 2) |
| Fase | Fase 1.2 |
| Severidad | BAJA |
| Categoría | `DEAD_CODE` |
| Archivo(s) afectado(s) | `docs/coding-patterns.md` |

**Descripción:** El documento de patrones de código mostraba ejemplos con una clase `DocuVaultException` y un exception handler simplificado que no correspondía a la implementación real (`ApplicationError` con subclases `PermissionDenied`, `ValidationError.details`, `ConflictError`, pasthrough DRF).

**Causa raíz:** El documento se redactó con un nombre de excepción provisional antes de decidir la jerarquía de excepciones real.

**Solución aplicada:** Actualización del documento con la jerarquía real de excepciones y el handler completo.

**Commit de corrección:** `dae4199`

---

## Fase 3: Auditoría de workflows y FTS (2026-05-31)

---

## ERR-008: Race condition en `start_workflow` — verificación de ejecución activa no atómica

| Campo | Valor |
|---|---|
| Fecha | 2026-05-31 |
| Fase | Fase 3.2 |
| Severidad | CRÍTICA |
| Categoría | `ASYNC_CELERY` |
| Archivo(s) afectado(s) | `backend/apps/workflows/services/workflow_service.py`, `backend/apps/workflows/models/execution.py` |

**Descripción:** La regla "solo una ejecución activa por documento" se verificaba con `.exists()` antes de crear la ejecución. Dos requests concurrentes podían superar la verificación simultáneamente y crear dos ejecuciones activas para el mismo documento.

**Causa raíz:** La verificación en código no es atómica: existe una ventana de tiempo entre el `SELECT (exists)` y el `INSERT` donde otro proceso puede hacer lo mismo.

**Solución aplicada:** `UniqueConstraint` parcial `uq_wf_exec_one_active_per_document` sobre `(document)` `WHERE status IN (pending, in_progress) AND deleted_at IS NULL` en la base de datos. El código atrapa `IntegrityError` y lo convierte en `ConflictError(409)`. El `.exists()` se mantiene como fast-path para devolver un error amigable antes de llegar al constraint.

**Commit de corrección:** `c9258ea`

---

## ERR-009: Doble-avance concurrente en `advance_step` — sin lock de fila

| Campo | Valor |
|---|---|
| Fecha | 2026-05-31 |
| Fase | Fase 3.2 |
| Severidad | ALTA |
| Categoría | `ASYNC_CELERY` |
| Archivo(s) afectado(s) | `backend/apps/workflows/services/workflow_service.py` |

**Descripción:** Dos aprobadores podían leer simultáneamente que una ejecución estaba `IN_PROGRESS` y ejecutar `advance_step` al mismo tiempo, avanzando el workflow dos pasos en lugar de uno.

**Causa raíz:** No había exclusión mutua al leer y modificar el estado de la ejecución dentro de la transacción.

**Solución aplicada:** `select_for_update(of=("self",))` al re-fetchear la ejecución dentro de `advance_step`. Se usa `of=("self",)` porque la FK `current_step` puede ser `NULL` y PostgreSQL no permite `FOR UPDATE` sobre el lado nullable de un outer join.

**Commit de corrección:** `c9258ea`

---

## ERR-010: Paginación inconsistente — templates y logs de workflow no paginaban

| Campo | Valor |
|---|---|
| Fecha | 2026-05-31 |
| Fase | Fase 3.2 |
| Severidad | MEDIA |
| Categoría | `ENVELOPE` |
| Archivo(s) afectado(s) | `backend/apps/workflows/api/views.py` |

**Descripción:** `GET /workflows/templates/` y `GET /workflows/executions/{id}/logs/` devolvían listas completas sin paginar con `meta: {}`, violando la especificación de `CLAUDE.md §7` que requiere paginación estándar en todos los listados.

**Causa raíz:** Los endpoints se implementaron sin aplicar `StandardPagination`, a diferencia del resto de la API.

**Solución aplicada:** Añadido `StandardPagination` a ambos endpoints.

**Commit de corrección:** `6162e74`

---

## ERR-011: `search_vector` reconstruido en cada `save()`, incluso para cambios de solo status

| Campo | Valor |
|---|---|
| Fecha | 2026-05-31 |
| Fase | Fase 3.3 |
| Severidad | MEDIA |
| Categoría | `N_PLUS_1` |
| Archivo(s) afectado(s) | `backend/apps/search/signals.py` |

**Descripción:** El signal `post_save` que reconstruye `search_vector` se disparaba en cada guardado de `Document`, incluyendo operaciones que solo cambian `status`, `version` o `storage_path`. Esto generaba write-amplification innecesaria en la tabla de FTS.

**Causa raíz:** El signal no verificaba si algún campo de texto relevante había cambiado antes de recalcular el vector.

**Solución aplicada:** El signal compara los campos de texto modificados (`name`, `description`, `tags`, `ocr_content`) antes de proceder. Un `save(update_fields=["status"])` no dispara la reconstrucción.

**Commit de corrección:** `c9258ea`

---

## Fase 4: Auditoría de Celery/OCR/IA (2026-06-04)

---

## ERR-012: Errores del SDK Anthropic no mapeados a `TransientError`

| Campo | Valor |
|---|---|
| Fecha | 2026-06-04 |
| Fase | Fase 4.4 |
| Severidad | ALTA |
| Categoría | `ASYNC_CELERY` |
| Archivo(s) afectado(s) | `backend/apps/documents/services/ai_service.py` |

**Descripción:** Las excepciones `RateLimitError`, `APITimeoutError` y `APIConnectionError` del SDK `anthropic` no se mapeaban a `TransientError`. Estos errores son recuperables pero el mecanismo de autoretry de Celery solo reintenta ante `TransientError`, con lo que la tarea fallaba permanentemente por errores de red o rate limit sin reintentar.

**Causa raíz:** El mapeo de errores específicos del SDK a la señal interna de reintento fue omitido en la implementación inicial.

**Solución aplicada:** Bloque `except` que captura los tres tipos de error del SDK Anthropic y los envuelve en `TransientError`.

**Commit de corrección:** Auditoría Fase 4 (2026-06-04)

---

## ERR-013: `reprocess_ocr` no reseteaba `ocr_status=PENDING` antes del `on_commit`

| Campo | Valor |
|---|---|
| Fecha | 2026-06-04 |
| Fase | Fase 4.2 |
| Severidad | MEDIA |
| Categoría | `ASYNC_CELERY` |
| Archivo(s) afectado(s) | `backend/apps/documents/services/document_service.py` |

**Descripción:** `document_service.reprocess_ocr` encolaba `process_ocr.delay` via `on_commit` pero no reseteaba `ocr_status` a `PENDING` antes. El usuario veía el documento en estado `failed` hasta que el worker terminara, sin indicación de que el reprocesamiento estaba en curso.

**Causa raíz:** El reseteo del status como señal visual de "en cola" fue omitido.

**Solución aplicada:** Se añadió `document.ocr_status = OcrStatus.PENDING; document.save(update_fields=["ocr_status"])` antes del `on_commit`.

**Commit de corrección:** Auditoría Fase 4 (2026-06-04)

---

## ERR-014: `max_retries` no configurado inline en decoradores de tareas

| Campo | Valor |
|---|---|
| Fecha | 2026-06-04 |
| Fase | Fase 4.1 |
| Severidad | BAJA |
| Categoría | `ASYNC_CELERY` |
| Archivo(s) afectado(s) | `backend/apps/documents/tasks/document_tasks.py` |

**Descripción:** Los decoradores `@shared_task` de las tareas Celery usaban `settings.CELERY_TASK_MAX_RETRIES` en `retry_kwargs`, pero la documentación de Celery recomienda establecer `max_retries` directamente en el decorador para evitar ambigüedades con el argumento `max_retries` de `self.retry()`.

**Causa raíz:** Diseño inicial demasiado genérico que dependía del setting global en lugar de ser explícito por tarea.

**Solución aplicada:** `max_retries=3` establecido explícitamente inline en cada decorador de tarea.

**Commit de corrección:** Auditoría Fase 4 (2026-06-04)

---

## Fase 5.1/5.7: Auditoría de frontend y notificaciones (2026-06-15)

---

## ERR-015: Perfil de usuario no se rehidrataba tras silent refresh en `ProtectedRoute`

| Campo | Valor |
|---|---|
| Fecha | 2026-06-15 |
| Fase | Fase 5.1 |
| Severidad | ALTA |
| Categoría | `REACT_STATE` |
| Archivo(s) afectado(s) | `frontend/src/shared/components/ProtectedRoute.tsx` |

**Descripción:** Al recargar la página, `ProtectedRoute` restauraba el `accessToken` usando el `refreshToken` del `localStorage`, pero no llamaba a `/auth/me/` para restaurar el objeto `user` en el store Zustand. `Header` mostraba iniciales `?` en el avatar; `Sidebar` ocultaba ítems con `allowedRoles` porque `userRole` era `undefined`.

**Causa raíz:** El bootstrap de sesión se implementó como un flujo de dos pasos (`refresh → setAccessToken`) olvidando el tercer paso necesario (`getMe → setUser`). El skeleton de carga no cubría el bootstrap completo.

**Solución aplicada:** Bootstrap secuencial en `useEffect`: `refreshToken()` → `setAccessToken(access)` → `getMe()` → `setUser(profile)`. Si `getMe()` falla → `logout()`. El skeleton cubre todo el proceso antes de renderizar `<Outlet>`.

**Commit de corrección:** `f9d4eff`

---

## ERR-016: `Promise.reject` faltante como fallback en el interceptor 401

| Campo | Valor |
|---|---|
| Fecha | 2026-06-15 |
| Fase | Fase 5.1 |
| Severidad | ALTA |
| Categoría | `REACT_STATE` |
| Archivo(s) afectado(s) | `frontend/src/lib/api-client.ts` |

**Descripción:** En el response interceptor, si el refresh tenía éxito pero `originalRequest` era falsy, no había un `return Promise.reject(...)` explícito. El handler podía resolver con `undefined`, convirtiendo silenciosamente un error en una respuesta exitosa vacía.

**Causa raíz:** Rama de código defensiva no completada — faltaba el `else` explícito de rechazo.

**Solución aplicada:** Añadido `return Promise.reject(parseApiError(error))` como fallback explícito en la rama donde `originalRequest` es falsy.

**Commit de corrección:** `f9d4eff`

---

## ERR-017: Doble envío concurrente de notificaciones — guard sin lock atómico

| Campo | Valor |
|---|---|
| Fecha | 2026-06-15 |
| Fase | Fase 5.7 |
| Severidad | ALTA |
| Categoría | `ASYNC_CELERY` |
| Archivo(s) afectado(s) | `backend/apps/notifications/services/notification_service.py` |

**Descripción:** El guard de idempotencia leía `notification.status` y continuaba solo si era `PENDING`. Sin `select_for_update`, dos workers Celery procesando la misma tarea (re-entrega, pod duplicado) podían leer ambos `PENDING`, pasar el guard y enviar el mismo email dos veces.

**Causa raíz:** La verificación de condición y la actualización de estado no son atómicas sin un lock de fila explícito.

**Solución aplicada:** Claim atómico vía `UPDATE WHERE status IN ('pending', 'failed')` con comprobación de `rowcount`. Solo el worker con `rowcount == 1` procede al envío SMTP. El lock no persiste durante el I/O externo (conexión SMTP).

**Commit de corrección:** `cb0654d`

---

## ERR-018: Fallos de mutación silenciosos — sin toast global de errores

| Campo | Valor |
|---|---|
| Fecha | 2026-06-15 |
| Fase | Fase 5.1 |
| Severidad | MEDIA |
| Categoría | `ASYNC_CELERY` |
| Archivo(s) afectado(s) | `frontend/src/lib/query-client.ts` |

**Descripción:** El componente `<Toaster>` de Sonner estaba montado en el layout, pero ninguna mutación de TanStack Query lo usaba. Un fallo de mutación (ej: subir un documento y recibir 400) era completamente invisible para el usuario salvo que esa mutación específica tuviera manejo de error inline.

**Causa raíz:** El `QueryClient` se configuró sin un handler global de error para mutaciones. La expectativa era que cada mutación gestionaría su propio error, pero esto no fue sistemático.

**Solución aplicada:** `MutationCache({ onError })` global en `query-client.ts` que dispara `toast.error(parseApiError(e).message)` para cualquier mutación fallida. Las mutaciones con UI de error inline usan `meta: { suppressGlobalToast: true }` para optar por no usar el toast global.

**Commit de corrección:** `f9d4eff`

---

## ERR-019: Narrowing inseguro de `ApiError` con double cast en `LoginForm`

| Campo | Valor |
|---|---|
| Fecha | 2026-06-15 |
| Fase | Fase 5.1 |
| Severidad | MEDIA |
| Categoría | `TYPE_CONTRACT` |
| Archivo(s) afectado(s) | `frontend/src/features/auth/components/LoginForm.tsx` |

**Descripción:** El código usaba `loginMutation.error as ApiError` (double cast de TypeScript) para acceder a `.code` y `.status`. Si el error no era una instancia de `ApiError` (ej: error de red sin respuesta), estas propiedades eran `undefined` silenciosamente en lugar de mostrar el error real.

**Causa raíz:** El cast `as SomeType` en TypeScript elimina la comprobación de tipos pero no garantiza nada en tiempo de ejecución. La confusión entre "tipo de import" y "valor de import" llevó a no usar `instanceof`.

**Solución aplicada:** `instanceof ApiError` con `import { ApiError }` (import de valor, no `import type`) que permite la comprobación en tiempo de ejecución.

**Commit de corrección:** `f9d4eff`

---

## Fase 5.2: Gestión documental frontend

---

## ERR-020: `ocr_content` no incluido en `DocumentSerializer.fields`

| Campo | Valor |
|---|---|
| Fecha | 2026-06-22 (aprox.) |
| Fase | Fase 5.2 |
| Severidad | ALTA |
| Categoría | `TYPE_CONTRACT` |
| Archivo(s) afectado(s) | `backend/apps/documents/api/serializers.py` |

**Descripción:** El campo `ocr_content` existía en el modelo `Document` y era rellenado por el pipeline OCR (Fase 4), pero no estaba declarado en `DocumentSerializer.fields`. La API no lo devolvía. La pestaña "Contenido OCR" del frontend nunca recibía contenido y fue eliminada al asumir que el campo no existía.

**Causa raíz:** Omisión al definir los fields del serializer. El campo del modelo y la lógica que lo rellena existían, pero se olvidó exponerlo en la capa API.

**Solución aplicada:** `ocr_content` añadido como campo `read_only=True` en `DocumentSerializer`. La pestaña "Contenido OCR" fue restaurada en `DocumentDetailPage` con renderizado condicional (solo si `document.ocr_content` tiene texto).

**Commit de corrección:** `7d34ea8`

---

## ERR-021: `folder_id` incorrecto al navegar entre carpetas — `defaultValues` inmutables en react-hook-form

| Campo | Valor |
|---|---|
| Fecha | 2026-06-30 |
| Fase | Fase 5.2 |
| Severidad | ALTA |
| Categoría | `REACT_STATE` |
| Archivo(s) afectado(s) | `frontend/src/features/documents/pages/FolderBrowserPage.tsx`, `frontend/src/features/documents/components/DocumentUploadDropzone.tsx` |

**Descripción:** Al subir un documento desde una carpeta vacía, `folder_id` usaba el valor de la carpeta anterior. `react-hook-form` lee `defaultValues` solo en el mount inicial del componente; si el componente no se desmonta al cambiar de carpeta, el formulario retiene el `folderId` de la primera carpeta visitada.

**Causa raíz:** Incomprensión del ciclo de vida de react-hook-form: los `defaultValues` son "frozen" en el mount. Navegar entre carpetas cambia la prop `folderId`, pero como el componente `DocumentUploadDropzone` no se desmonta, el formulario no se reinicializa.

**Solución aplicada:** `key={id}` en `<DocumentUploadDropzone>` donde `id` es el ID de la carpeta actual. React desmonta y remonta el componente al cambiar la key, forzando la reinicialización del formulario con el `folderId` correcto.

**Commit de corrección:** `43e8380`

---

## Fase 5.3 post-testing: Auditoría de workflows/audit UI (2026-06-29)

---

## ERR-022: Filtro de auditoría enviaba email pero backend esperaba UUID

| Campo | Valor |
|---|---|
| Fecha | 2026-06-29 |
| Fase | Fase 5.3 |
| Severidad | MEDIA |
| Categoría | `TYPE_CONTRACT` |
| Archivo(s) afectado(s) | `frontend/src/features/audit/components/AuditLogFilters.tsx`, `backend/apps/audit/api/filters.py` |

**Descripción:** `AuditLogFilters.tsx` enviaba el email del usuario como query param `user`, pero `AuditLogFilter` del backend declaraba ese campo como `UUIDFilter(field_name="user_id")`. Un email no es un UUID válido: `django-filter` descartaba el valor silenciosamente y la tabla aparecía vacía sin ningún mensaje de error.

**Causa raíz:** El tipo del parámetro en el filtro del backend (`UUIDFilter`) no coincidía con lo que el frontend enviaba (string de email). La falla era silenciosa en lugar de devolver un error de validación.

**Solución aplicada:** Se añadió `user_email = CharFilter(field_name="user__email", lookup_expr="iexact")` al `AuditLogFilter` del backend. En el frontend se renombró el campo `user` → `user_email` en el formulario, la llamada a API y los hooks.

---

## ERR-023: Filtro "Hasta" excluía todos los eventos del día seleccionado

| Campo | Valor |
|---|---|
| Fecha | 2026-06-29 |
| Fase | Fase 5.3 |
| Severidad | MEDIA |
| Categoría | `TYPE_CONTRACT` |
| Archivo(s) afectado(s) | `frontend/src/features/audit/components/AuditLogFilters.tsx` |

**Descripción:** `new Date("2026-06-29").toISOString()` produce `"2026-06-29T00:00:00.000Z"`. Con `lookup_expr="lte"` en `created_at`, el filtro "Hasta" solo devolvía registros hasta medianoche UTC del día seleccionado, excluyendo prácticamente todos los eventos del propio día. El problema se amplificaba en zonas horarias fuera de UTC.

**Causa raíz:** No se tuvo en cuenta que `new Date(dateString)` interpreta la fecha como inicio del día en UTC, no como el final del día. Para un filtro "hasta fin de día" se necesita `endOfDay()`.

**Solución aplicada:** Para `created_before` se aplica `endOfDay(parseISO(value)).toISOString()` de `date-fns` antes de serializar. `created_after` no cambia (empezar desde inicio del día es correcto).

---

## ERR-024: Polling del análisis IA sin estado terminal para fallos permanentes de Celery

| Campo | Valor |
|---|---|
| Fecha | 2026-06-29 |
| Fase | Fase 5.3 |
| Severidad | MEDIA |
| Categoría | `POLLING` |
| Archivo(s) afectado(s) | `backend/apps/documents/tasks/document_tasks.py`, `frontend/src/features/documents/hooks.ts`, `frontend/src/features/documents/pages/DocumentDetailPage.tsx` |

**Descripción:** Al solicitar análisis IA, el frontend iniciaba polling cada 3 segundos mientras `!metadata?.ai_analysis`. Si la tarea Celery agotaba sus reintentos y fallaba permanentemente (sin escribir nada en `metadata`), la condición de parada nunca se cumplía. Spinner eterno y requests infinitos mientras el tab permaneciera abierto.

**Causa raíz:** El backend no escribía ningún marcador de fallo al agotar reintentos; el frontend no tenía un estado terminal de "fallo". El contrato de polling asumía que siempre terminaría con éxito.

**Solución aplicada:** El backend escribe `metadata["ai_analysis"] = {"status": "failed", "error": "..."}` al agotar reintentos. El frontend para el polling cuando `aiAnalysis` existe (tanto éxito como fallo). `DocumentDetailPage` detecta `status === 'failed'` y muestra el error con botón "Reintentar".

---

## ERR-025: `WorkflowStepLogTimeline` reventaba ante una acción desconocida

| Campo | Valor |
|---|---|
| Fecha | 2026-06-29 |
| Fase | Fase 5.3 |
| Severidad | BAJA |
| Categoría | `TYPE_CONTRACT` |
| Archivo(s) afectado(s) | `frontend/src/features/workflows/components/WorkflowStepLogTimeline.tsx` |

**Descripción:** `ACTION_CONFIG[log.action]` sin fallback: si el backend añade en el futuro un nuevo valor de `action` no conocido por el cliente, `config` es `undefined` y el acceso a sus propiedades tumba toda la línea de tiempo.

**Causa raíz:** Acceso a objeto de configuración sin verificar que la clave existe.

**Solución aplicada:** Fallback explícito `?? { label: action, Icon: Circle, className: 'text-gray-500 bg-gray-50' }` antes del destructuring.

---

## ERR-026: `WorkflowTemplateForm` podía entrar en loop de reset

| Campo | Valor |
|---|---|
| Fecha | 2026-06-29 |
| Fase | Fase 5.3 |
| Severidad | BAJA |
| Categoría | `REACT_STATE` |
| Archivo(s) afectado(s) | `frontend/src/features/workflows/components/WorkflowTemplateForm.tsx` |

**Descripción:** El `useEffect` que llama `form.reset(defaultValues)` tenía `defaultValues` (prop) como dependencia. Si un componente padre pasara un objeto inline `defaultValues={{ ... }}`, la referencia cambiaría en cada render del padre → `form.reset` se ejecutaría en cada render → pérdida del input del usuario mientras escribe.

**Causa raíz:** Los objetos creados inline en JSX tienen nueva referencia en cada render. El array de dependencias del `useEffect` compara por referencia, no por valor.

**Solución aplicada:** `useRef(defaultValues)` para capturar el valor inicial una sola vez, ignorando cambios de referencia subsiguientes.

---

## ERR-027: Query de auditoría se ejecutaba sin verificar rol del usuario

| Campo | Valor |
|---|---|
| Fecha | 2026-06-29 |
| Fase | Fase 5.3 |
| Severidad | BAJA |
| Categoría | `RBAC` |
| Archivo(s) afectado(s) | `frontend/src/features/audit/hooks.ts`, `frontend/src/features/audit/pages/AuditLogPage.tsx` |

**Descripción:** `useAuditLogs` se ejecutaba incondicionalmente antes del chequeo de rol. El backend devolvía 403 (sin fuga de datos), pero era un request innecesario. Con TanStack Query retrying automáticamente, podía generar múltiples 403 consecutivos.

**Causa raíz:** No se pasó la prop `enabled` al hook para condicionarlo al rol del usuario.

**Solución aplicada:** `useAuditLogs` acepta `options?: { enabled?: boolean }` y lo pasa a TanStack Query. En `AuditLogPage` se pasa `enabled: !!role && ALLOWED_ROLES.includes(role)`.

---

## Fase 5.5: Deploy en producción (2026-06-29)

---

## ERR-028: `VITE_API_BASE_URL` no configurado en el Dockerfile del frontend

| Campo | Valor |
|---|---|
| Fecha | 2026-06-29 |
| Fase | Fase 5.5 |
| Severidad | CRÍTICA |
| Categoría | `DEPENDENCY` |
| Archivo(s) afectado(s) | `frontend/Dockerfile` |

**Descripción:** El Dockerfile del frontend ejecutaba `npm run build` sin pasar `VITE_API_BASE_URL`. Vite reemplaza las variables de entorno en tiempo de build, no en runtime. El bundle de producción hardcodeaba `http://localhost:8000/api/v1` (el fallback de `.env.development`), haciendo que todas las llamadas a la API fallaran en el servidor.

**Causa raíz:** Desconocimiento de cómo Vite maneja las variables de entorno `VITE_*`: se inyectan en el bundle durante el build, no se leen del entorno en runtime como en Node.js.

**Solución aplicada:** `ARG VITE_API_BASE_URL=/api/v1` + `ENV VITE_API_BASE_URL=/api/v1` en el Dockerfile, antes del paso `RUN npm run build`.

---

## ERR-029: Credenciales en `docker-compose.prod.yml` con interpolación `${...}` resolvían vacías

| Campo | Valor |
|---|---|
| Fecha | 2026-06-29 |
| Fase | Fase 5.5 |
| Severidad | CRÍTICA |
| Categoría | `DEPENDENCY` |
| Archivo(s) afectado(s) | `docker-compose.prod.yml` |

**Descripción:** Las credenciales de PostgreSQL y MinIO usaban la sintaxis `${POSTGRES_PASSWORD}` e `${MINIO_ROOT_PASSWORD}` en el compose. Si las variables de entorno del shell del operador no estaban exportadas, Docker Compose las resolvía como strings vacíos silenciosamente, iniciando los servicios con contraseñas vacías.

**Causa raíz:** Docker Compose interpola variables del entorno del shell en tiempo de lectura del archivo. Si la variable no existe en el entorno, la sustituye por string vacío sin advertencia.

**Solución aplicada:** Se usó `env_file` con los nombres nativos de cada imagen (`POSTGRES_PASSWORD`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`) en lugar de interpolación `${...}`.

---

## ERR-030: `collectstatic` falla con `PermissionError` al correr como usuario no-root

| Campo | Valor |
|---|---|
| Fecha | 2026-06-29 |
| Fase | Fase 5.5 |
| Severidad | CRÍTICA |
| Categoría | `DEPENDENCY` |
| Archivo(s) afectado(s) | `backend/Dockerfile` |

**Descripción:** El Dockerfile ejecutaba `collectstatic` en el entrypoint como `appuser` (usuario no-root). El directorio `staticfiles/` era propiedad de `root` durante el build. `collectstatic` lanzaba `PermissionError` al intentar escribir.

**Causa raíz:** El script de entrypoint corría comandos de Django que requieren escribir en el filesystem antes de transferir la propiedad al usuario de runtime.

**Solución aplicada:** `collectstatic` se ejecuta durante el build (como `root`, antes del `USER appuser`), seguido de `chown -R appuser:appuser /app`. Los archivos estáticos quedan horneados en la imagen con la propiedad correcta.

---

## ERR-031: Nginx `client_max_body_size 1m` por defecto bloqueaba todos los uploads

| Campo | Valor |
|---|---|
| Fecha | 2026-06-29 |
| Fase | Fase 5.5 |
| Severidad | CRÍTICA |
| Categoría | `DEPENDENCY` |
| Archivo(s) afectado(s) | `nginx/nginx.conf` |

**Descripción:** El límite por defecto de Nginx para el cuerpo de las requests es 1 MB. El proyecto permite uploads de hasta 50 MB (`MAX_UPLOAD_SIZE` en `CLAUDE.md §3`). Todos los uploads mayores a 1 MB recibían `413 Request Entity Too Large` del proxy antes de llegar al backend Django.

**Causa raíz:** El valor por defecto de Nginx no fue sobreescrito explícitamente. El comportamiento de producción (detrás de Nginx) difiere del de desarrollo (Django directamente).

**Solución aplicada:** `client_max_body_size 50m;` añadido al bloque `server` del `nginx.conf`.

---

## ERR-032: `deploy.sh` ejecutaba las migraciones dos veces

| Campo | Valor |
|---|---|
| Fecha | 2026-06-29 |
| Fase | Fase 5.5 |
| Severidad | MEDIA |
| Categoría | `DEAD_CODE` |
| Archivo(s) afectado(s) | `scripts/deploy.sh` |

**Descripción:** El script `deploy.sh` ejecutaba explícitamente `docker compose run --rm migrate` Y también levantaba el compose completo que ya incluye un servicio `migrate` one-shot con `depends_on: service_completed_successfully`. Las migraciones corrían dos veces por deploy.

**Causa raíz:** El servicio `migrate` del compose fue añadido como solución permanente, pero el script de deploy mantenía también el comando manual de la etapa anterior.

**Solución aplicada:** Eliminado `docker compose run --rm migrate` duplicado del script. El servicio `migrate` del compose es suficiente.

---

## ERR-033: `backup_db.sh` no cargaba credenciales de `.env.production`

| Campo | Valor |
|---|---|
| Fecha | 2026-06-29 |
| Fase | Fase 5.5 |
| Severidad | MEDIA |
| Categoría | `DEPENDENCY` |
| Archivo(s) afectado(s) | `scripts/backup_db.sh` |

**Descripción:** El script de backup ejecutaba `pg_dump` asumiendo que las variables de entorno de la DB estaban disponibles en el shell, pero no cargaba el archivo `.env.production`. En un contexto de cron job o shell limpio, las variables no estaban disponibles y el dump fallaba.

**Causa raíz:** Variables de entorno asumidas como presentes sin cargarlas explícitamente.

**Solución aplicada:** El script carga `.env.production` al inicio. Se añadió escritura atómica (escribe a `.tmp` y hace `mv` al final) para evitar dumps parciales en caso de corte.

---

## Fase 5.4: CI/CD con GitHub Actions (2026-06-29)

---

## ERR-034: Tests de integración no excluidos del pipeline CI

| Campo | Valor |
|---|---|
| Fecha | 2026-06-29 |
| Fase | Fase 5.4 |
| Severidad | CRÍTICA |
| Categoría | `DEPENDENCY` |
| Archivo(s) afectado(s) | `.github/workflows/ci.yml` |

**Descripción:** El comando `pytest` en CI no excluía los tests marcados con `@pytest.mark.integration`. Los tests de integración requieren un servidor MinIO real que no está disponible en el runner de GitHub Actions. Sin la exclusión, el pipeline habría fallado desde el primer run con errores de conexión a MinIO.

**Causa raíz:** Los tests de integración se añadieron con su marker, pero la invocación de pytest en CI no fue actualizada para excluirlos.

**Solución aplicada:** `pytest -m "not integration"` en el workflow de CI.

---

## ERR-035: Push a `main` no incluido en los triggers del workflow CI

| Campo | Valor |
|---|---|
| Fecha | 2026-06-29 |
| Fase | Fase 5.4 |
| Severidad | MEDIA |
| Categoría | `DEPENDENCY` |
| Archivo(s) afectado(s) | `.github/workflows/ci.yml` |

**Descripción:** El workflow CI solo tenía trigger `pull_request`. Los badges de cobertura y CI del README mostraban "no status" porque el workflow nunca había corrido en la rama `main`.

**Causa raíz:** El trigger `push: branches: [main, develop]` fue omitido al crear el workflow.

**Solución aplicada:** Añadido `push: branches: [main, develop]` a los triggers.

---

## ERR-036: Flag `--cov` desnudo en pytest diluía el porcentaje de cobertura

| Campo | Valor |
|---|---|
| Fecha | 2026-06-29 |
| Fase | Fase 5.4 |
| Severidad | MEDIA |
| Categoría | `DEPENDENCY` |
| Archivo(s) afectado(s) | `backend/pyproject.toml` |

**Descripción:** `addopts` tenía `--cov` sin argumento de ruta, lo que medía la cobertura del árbol completo del proyecto (incluyendo `venv`, `migrations`, `tests/`) en lugar de solo `apps/`. El porcentaje resultante era artificialmente bajo y no representativo.

**Causa raíz:** El flag `--cov` sin ruta tiene un comportamiento diferente al esperado: mide todo el código ejecutable encontrado, no solo el código de la aplicación.

**Solución aplicada:** Cambiado a `--cov=apps` en `addopts`.

---

## Sesión de testing post 5.3: Type mismatches TypeScript (2026-06-30)

---

## ERR-037: `WorkflowExecution` y `WorkflowStepLog` tipados con objetos anidados pero API devuelve campos planos

| Campo | Valor |
|---|---|
| Fecha | 2026-06-30 |
| Fase | Fase 5.3 |
| Severidad | ALTA |
| Categoría | `TYPE_CONTRACT` |
| Archivo(s) afectado(s) | `frontend/src/shared/types/index.ts`, `frontend/src/features/workflows/pages/WorkflowExecutionsPage.tsx`, `frontend/src/features/workflows/pages/WorkflowExecutionDetailPage.tsx`, `frontend/src/features/workflows/components/WorkflowStepLogTimeline.tsx` |

**Descripción:** Los tipos TypeScript declaraban `template: { id, name }`, `started_by: { id, email }`, `step: { id, name, order }` como objetos anidados. El serializer devuelve campos planos: `template_name`, `started_by_email`, `step_name`, `step_order`, `performed_by_email`. Crash en runtime al acceder a propiedades de `undefined`.

**Causa raíz:** Los tipos TypeScript se redactaron en base a como se esperaba que fuera la respuesta, sin verificar contra la respuesta real del backend. El serializer `WorkflowExecutionSerializer` usa `SerializerMethodField` para campos compuestos que devuelve strings, no objetos anidados.

**Solución aplicada:** Corrección de tipos e interfaces en `shared/types/index.ts` para reflejar la respuesta real. Actualización de todos los accesos en los tres componentes afectados.

---

## ERR-038: `Document.created_by` tipado como objeto pero API devuelve string plano

| Campo | Valor |
|---|---|
| Fecha | 2026-06-30 |
| Fase | Fase 5.2 |
| Severidad | ALTA |
| Categoría | `TYPE_CONTRACT` |
| Archivo(s) afectado(s) | `frontend/src/shared/types/index.ts`, `frontend/src/features/documents/pages/DocumentDetailPage.tsx`, `frontend/src/features/documents/components/DocumentVersionList.tsx` |

**Descripción:** El tipo `Document` declaraba `created_by: { id: string; email: string }`, `folder: { id, name } | null`, y campos inexistentes `storage_path`/`ocr_content`. El backend devuelve `created_by_email: string`, `folder: string | null` (UUID) y `folder_name: string | null` separado. Crash: `Cannot read properties of undefined (reading 'email')`.

**Causa raíz:** Mismo patrón que ERR-037: tipos escritos antes de verificar la respuesta real. TypeScript no detectó el error porque algunos componentes inferían el tipo sin anotación explícita (path resuelto como `any`).

**Solución aplicada:** Interfaces `Document`, `DocumentVersion` y `Folder` en `shared/types/index.ts` corregidas para reflejar la respuesta real del backend. Regla extraída: siempre verificar con `curl` o DevTools Network antes de tipar una respuesta de API.

---

## Auth envelope bugs (2026-06-30)

---

## ERR-039: `refreshToken()` no desenvolvía el envelope — devolvía `{data, meta}` en lugar de `{access, refresh}`

| Campo | Valor |
|---|---|
| Fecha | 2026-06-30 |
| Fase | Fase 5.1 |
| Severidad | CRÍTICA |
| Categoría | `ENVELOPE` |
| Archivo(s) afectado(s) | `frontend/src/features/auth/api.ts` |

**Descripción:** La función `refreshToken()` usaba `response.data` directamente, pero la respuesta del backend está envuelta en el envelope `{data: {access, refresh}, meta: {}}`. Devolvía el envelope completo en lugar del payload. `access` era siempre `undefined`. La sesión nunca se restauraba tras una recarga de página.

**Causa raíz:** Solo `login()` y `getMe()` usaban el helper `unwrap()`. El autor de `refreshToken()` no siguió el mismo patrón sin darse cuenta de que todos los endpoints del proyecto usan el envelope.

**Solución aplicada:** `refreshToken()` usa `Envelope<RefreshResponse>` como tipo de respuesta y `unwrap(response)` para desenvolver.

**Commit de corrección:** (sesión 2026-06-30)

---

## ERR-040: Interceptor 401 no desenvolvía el envelope — `access` era siempre `undefined`

| Campo | Valor |
|---|---|
| Fecha | 2026-06-30 |
| Fase | Fase 5.1 |
| Severidad | CRÍTICA |
| Categoría | `ENVELOPE` |
| Archivo(s) afectado(s) | `frontend/src/lib/api-client.ts` |

**Descripción:** El interceptor de respuesta accedía a `data.access` directamente, pero la respuesta de `/auth/refresh/` estaba envuelta. `data` era `{data: {access, refresh}, meta: {}}`, así que `data.access` era `undefined`. El interceptor actualizaba el store con `undefined`, la request reintentada volvía a fallar con 401, y el flag `_retry` forzaba el logout.

**Causa raíz:** El interceptor fue implementado independientemente de las funciones de API, y el autor no conocía el convenio de envelope del proyecto.

**Solución aplicada:** El interceptor navega hasta el payload interno: `envelope.data.access` / `envelope.data.refresh`.

**Commit de corrección:** (sesión 2026-06-30)

---

## ERR-041: Refresh token rotativo no persistido tras refresh silencioso

| Campo | Valor |
|---|---|
| Fecha | 2026-06-30 |
| Fase | Fase 5.1 |
| Severidad | CRÍTICA |
| Categoría | `ENVELOPE` |
| Archivo(s) afectado(s) | `frontend/src/lib/api-client.ts`, `frontend/src/shared/components/ProtectedRoute.tsx` |

**Descripción:** Con `ROTATE_REFRESH_TOKENS=True` + `BLACKLIST_AFTER_ROTATION=True`, cada respuesta de `/auth/refresh/` incluye un nuevo refresh token y blacklistea el anterior. El interceptor y el bootstrap de `ProtectedRoute` guardaban el nuevo `access` pero descartaban silenciosamente el nuevo `refresh`. Tras 60 minutos, el interceptor intentaba usar el refresh original (ya blacklisteado) → `400/401` → logout involuntario. Solo reproducible en sesiones largas.

**Causa raíz:** El tipo `RefreshResponse` solo tenía `access: string`, por lo que el campo `refresh` de la respuesta no era visible a nivel de tipos. Se ignoró el nuevo refresh token sin darse cuenta.

**Solución aplicada:** `RefreshResponse` añade `refresh: string`. El interceptor persiste `newRefresh` en `localStorage`. `ProtectedRoute` también persiste el nuevo refresh en el bootstrap.

**Commit de corrección:** (sesión 2026-06-30)

---

## ERR-042: Fixtures de tests para `/auth/refresh/` no usaban el envelope — bug enmascarado

| Campo | Valor |
|---|---|
| Fecha | 2026-06-30 |
| Fase | Fase 5.1 |
| Severidad | ALTA |
| Categoría | `ENVELOPE` |
| Archivo(s) afectado(s) | `frontend/src/features/auth/__tests__/interceptor.test.ts`, `frontend/src/shared/components/__tests__/ProtectedRoute.test.tsx` |

**Descripción:** Los handlers MSW mockeaban `/auth/refresh/` devolviendo `{ access: '...' }` (formato plano sin envelope). Los tests pasaban aunque el código de producción estuviera roto frente al backend real, que devuelve `{data: {access, refresh}, meta: {}}`.

**Causa raíz:** Los mocks de test fueron escritos con el formato "esperado" en lugar del formato real del backend. Los tests pasaban porque el mock devolvía exactamente lo que el código roto asumía recibir.

**Solución aplicada:** Actualización de los 5 handlers MSW en `interceptor.test.ts` y el fixture `REFRESH_RESPONSE` en `ProtectedRoute.test.tsx` al formato envelope correcto.

**Commit de corrección:** (sesión 2026-06-30)

---

## Workflow/notification bugs (2026-06-30)

---

## ERR-043: Migración `notifications.0001` no aplicada — 500 en `start-workflow`

| Campo | Valor |
|---|---|
| Fecha | 2026-06-30 |
| Fase | Fase 5.7 |
| Severidad | CRÍTICA |
| Categoría | `MIGRATION` |
| Archivo(s) afectado(s) | `backend/apps/notifications/migrations/0001_initial.py` |

**Descripción:** `POST /api/v1/documents/{id}/start-workflow/` devolvía 500 con error de tabla `notifications_notification` no existente. La migración de la nueva app `notifications` (Fase 5.7) no había sido aplicada al entorno de desarrollo.

**Causa raíz:** La app `notifications` fue implementada y sus tests corrieron con la DB de test (que aplica las migraciones automáticamente), pero el entorno de desarrollo no ejecutó `python manage.py migrate notifications` tras la implementación.

**Solución aplicada:** `python manage.py migrate notifications` (sin cambios de código).

---

## ERR-044: `DocumentVersionList` calculaba `Math.ceil(undefined/undefined)` = NaN

| Campo | Valor |
|---|---|
| Fecha | 2026-06-30 |
| Fase | Fase 5.2 |
| Severidad | MEDIA |
| Categoría | `TYPE_CONTRACT` |
| Archivo(s) afectado(s) | `frontend/src/features/documents/components/DocumentVersionList.tsx` |

**Descripción:** El endpoint `GET /documents/{id}/versions/` devuelve `"meta": {}` (vacío, sin paginación). El componente calculaba `Math.ceil(total_count / page_size)` directamente sobre los valores de `meta`, que eran `undefined`. Resultado: número total de páginas = NaN.

**Causa raíz:** El tipo del retorno de `getVersions` estaba declarado como `PaginatedMeta` (garantizando `count` y `page_size`), pero el endpoint real devuelve `meta: {}`.

**Solución aplicada:** Desestructuración defensiva con fallback a `1` para el total de páginas. El tipo del retorno corregido a `Partial<PaginatedMeta>`.

---

## ERR-045: `<FormLabel>` usado fuera de `<FormField>` — crash en WorkflowTemplateForm

| Campo | Valor |
|---|---|
| Fecha | 2026-06-30 |
| Fase | Fase 5.3 |
| Severidad | ALTA |
| Categoría | `REACT_STATE` |
| Archivo(s) afectado(s) | `frontend/src/features/workflows/components/WorkflowTemplateForm.tsx` |

**Descripción:** `WorkflowTemplateForm.tsx` usaba `<FormLabel>` de shadcn/ui como título visual de la sección de pasos, fuera de cualquier `<FormField>`. El componente `FormLabel` llama internamente a `useFormField()`, que lee un contexto React (`FormFieldContext`) que solo existe dentro del render prop de `<FormField>`. Error: `"useFormField should be used within <FormField>"`.

**Causa raíz:** `<FormLabel>` de shadcn/ui no es un elemento HTML puro sino un componente de contexto. Su uso fuera de `<FormField>` no está prohibido por TypeScript pero falla en runtime.

**Solución aplicada:** Reemplazado por `<label>` HTML estándar para títulos visuales de sección fuera de campos de formulario.

**Commit de corrección:** (sesión 2026-06-30)

---

## Post-testing final: auditorías 2026-07-01

---

## ERR-046: `ocr_status` ausente de `SearchResultSerializer.fields` — crash en SearchPage

| Campo | Valor |
|---|---|
| Fecha | 2026-07-01 |
| Fase | Fase 5.2 / 3.3 |
| Severidad | ALTA |
| Categoría | `TYPE_CONTRACT` |
| Archivo(s) afectado(s) | `backend/apps/search/api/serializers.py`, `frontend/src/features/documents/components/OcrStatusBadge.tsx` |

**Descripción:** `SearchResultSerializer` no incluía `ocr_status` en sus `fields`. `DocumentCard` pasaba `document.ocr_status` (siempre `undefined`) al `OcrStatusBadge`. `CONFIG[undefined]` es `undefined`; el destructuring de `label` lanzaba `TypeError` y la `SearchPage` mostraba pantalla en blanco.

**Causa raíz:** `SearchResultSerializer` se implementó como un subconjunto de `DocumentSerializer` pero `ocr_status` se añadió a `DocumentSerializer` en Fase 4.2 sin actualizar el serializer de búsqueda.

**Solución aplicada:** `ocr_status` añadido a `SearchResultSerializer.fields`. Fallback defensivo `CONFIG[status] ?? { label: ..., className: ... }` en `OcrStatusBadge` para status desconocidos.

---

## ERR-047: Tipo `SearchResult` declarado como `Document[]` en lugar de shape real

| Campo | Valor |
|---|---|
| Fecha | 2026-07-01 |
| Fase | Fase 5.2 |
| Severidad | MEDIA |
| Categoría | `TYPE_CONTRACT` |
| Archivo(s) afectado(s) | `frontend/src/shared/types/index.ts`, `frontend/src/features/search/api.ts` |

**Descripción:** `searchApi.search` tipaba los resultados como `Document[]` completo, pero el serializer devuelve un shape parcial (sin `checksum`, `metadata`, `ocr_content`) más el campo extra `rank`. Falsedad de tipos que podría causar accesos silenciosos a `undefined`.

**Causa raíz:** El tipo fue creado reutilizando `Document` por conveniencia sin modelar las diferencias.

**Solución aplicada:** Nueva interfaz `SearchResult extends Omit<Document, 'checksum'|'metadata'|'ocr_content'> & { rank: number }` en `shared/types/index.ts`.

---

## ERR-048: AI `entities` tipado como `string[]` pero backend devuelve objeto `{dates, amounts, names}`

| Campo | Valor |
|---|---|
| Fecha | 2026-07-01 |
| Fase | Fase 5.3 |
| Severidad | MEDIA |
| Categoría | `TYPE_CONTRACT` |
| Archivo(s) afectado(s) | `frontend/src/shared/types/index.ts`, `frontend/src/features/documents/pages/DocumentDetailPage.tsx` |

**Descripción:** La pestaña "Análisis IA" mostraba resumen y categoría pero nunca las entidades detectadas. El backend almacena `entities: { dates: [], amounts: [], names: [] }` (objeto con tres listas), pero el frontend tipaba `entities?: string[]`. La guarda `analysis.entities.length > 0` evaluaba `undefined > 0 = false` y silenciaba el bloque.

**Causa raíz:** El tipo fue escrito sin consultar la estructura real de `metadata["ai_analysis"]` definida en `docs/reference.md` y en `ai_service.py`.

**Solución aplicada:** `AiAnalysis.entities` corregido al tipo objeto real `{dates: string[], amounts: string[], names: string[]}`. Rendering actualizado para aplanar las tres listas en badges.

---

## ERR-049: `ExecutionStatusBadge` sin fallback en status desconocido

| Campo | Valor |
|---|---|
| Fecha | 2026-07-01 |
| Fase | Fase 5.3 |
| Severidad | BAJA |
| Categoría | `TYPE_CONTRACT` |
| Archivo(s) afectado(s) | `frontend/src/features/workflows/components/ExecutionStatusBadge.tsx` |

**Descripción:** `CONFIG[status]` sin fallback: si el backend añade un nuevo valor de `WorkflowStatus` no conocido por el cliente, `config` es `undefined` y el destructuring falla en runtime.

**Causa raíz:** Omisión del patrón defensivo aplicado en el mismo PR a `OcrStatusBadge` (ERR-046).

**Solución aplicada:** Fallback `?? { label: status, className: 'text-gray-500 bg-gray-50' }`.

---

## ERR-050: `getVersions` tipada con `PaginatedMeta` en lugar de `Partial<PaginatedMeta>`

| Campo | Valor |
|---|---|
| Fecha | 2026-07-01 |
| Fase | Fase 5.2 |
| Severidad | BAJA |
| Categoría | `TYPE_CONTRACT` |
| Archivo(s) afectado(s) | `frontend/src/features/documents/api.ts` |

**Descripción:** El tipo de retorno declaraba `meta: PaginatedMeta` (garantizando `count`, `next`, `page`, `page_size`), pero el endpoint real devuelve `"meta": {}` vacío. El tipo creaba una falsa seguridad.

**Causa raíz:** El tipo fue copiado del patrón general de paginación sin verificar si ese endpoint específico realmente pagina.

**Solución aplicada:** Tipo corregido a `meta: Partial<PaginatedMeta>`.

---

## ERR-051: `WRITE_ROLES` duplicado en 8 lugares del frontend

| Campo | Valor |
|---|---|
| Fecha | 2026-07-01 |
| Fase | Fase 5.1–5.3 |
| Severidad | BAJA |
| Categoría | `DEAD_CODE` |
| Archivo(s) afectado(s) | Múltiples archivos en `frontend/src/features/` |

**Descripción:** La constante que define los roles con permiso de escritura (`['editor', 'supervisor', 'org_admin', 'super_admin']`) estaba declarada como variable local en 8 componentes distintos. Si la política de roles cambiaba, habría que actualizar 8 lugares.

**Causa raíz:** Cada componente declaraba la constante inline por conveniencia sin crear un módulo compartido.

**Solución aplicada:** Creado `frontend/src/shared/lib/roles.ts` con `WRITE_ROLES`, `START_ROLES` y el helper `canWrite()`. Reemplazadas las 8 declaraciones locales.

---

## ERR-052: Polling de OCR y workflow sin cota máxima de iteraciones

| Campo | Valor |
|---|---|
| Fecha | 2026-07-01 |
| Fase | Fase 5.2–5.3 |
| Severidad | MEDIA |
| Categoría | `POLLING` |
| Archivo(s) afectado(s) | `frontend/src/features/documents/hooks.ts`, `frontend/src/features/workflows/hooks.ts` |

**Descripción:** `useDocument` hacía polling cada 3 segundos mientras `ocr_status` fuera `pending` o `processing`. `useWorkflowExecution` cada 5 segundos mientras el status fuera no terminal. Si el worker Celery moría sin escribir un estado terminal, el polling corría indefinidamente mientras el tab permaneciera abierto.

**Causa raíz:** El polling tenía condición de parada basada en el estado del objeto, pero no tenía límite de intentos como red de seguridad.

**Solución aplicada:** `useDocument` detiene el polling tras 40 intentos (~2 minutos). `useWorkflowExecution` tras 48 intentos (~4 minutos). Se loguea un warning en consola al alcanzar el tope.

---

## ERR-053: Código muerto en el módulo de auditoría del frontend

| Campo | Valor |
|---|---|
| Fecha | 2026-07-01 |
| Fase | Fase 5.3 |
| Severidad | BAJA |
| Categoría | `DEAD_CODE` |
| Archivo(s) afectado(s) | `frontend/src/features/audit/api.ts`, `frontend/src/features/audit/hooks.ts` |

**Descripción:** `auditApi.getById`, `useAuditLog` (hook de detalle) y `auditKeys.detail` existían pero nunca fueron consumidos por ningún componente. El backend expone `GET /audit-logs/{id}/` pero el frontend nunca lo usó.

**Causa raíz:** Se implementaron las funciones "por si acaso" siguiendo el patrón CRUD completo, sin verificar si el frontend realmente tenía una vista de detalle de audit log.

**Solución aplicada:** Eliminados los tres artefactos.

---

## ERR-054: Overflow de texto en `DocumentCard` — nombres de archivo muy largos

| Campo | Valor |
|---|---|
| Fecha | 2026-07-01 |
| Fase | Fase 5.2 |
| Severidad | BAJA |
| Categoría | `UI_OVERFLOW` |
| Archivo(s) afectado(s) | `frontend/src/features/documents/components/DocumentCard.tsx` |

**Descripción:** Los nombres de archivo muy largos desbordaban los bordes de la tarjeta de documento. La clase `truncate` en el texto no tenía efecto porque el contenedor flex padre no limitaba el tamaño mínimo del item.

**Causa raíz:** En un contenedor flex, un ítem no se encoge más allá de su contenido mínimo a menos que tenga `min-w-0`. Sin `min-w-0 flex-1`, el `truncate` (que requiere `overflow: hidden`) no funciona porque el contenedor crece con el contenido en lugar de recortarlo.

**Solución aplicada:** `overflow-hidden` en el elemento `<Card>` externo + `min-w-0 flex-1` en el contenedor flex interno. El `truncate` ya existía en el `<p>` del nombre.

---

## ERR-055: PostgreSQL FTS tokeniza palabras unidas por guión bajo como token único

| Campo | Valor |
|---|---|
| Fecha | 2026-05-31 |
| Fase | Fase 3.3 |
| Severidad | MEDIA |
| Categoría | `DEPENDENCY` |
| Archivo(s) afectado(s) | Tests de FTS en `backend/apps/search/tests/` |

**Descripción:** Tests de FTS fallaban porque los documentos de prueba usaban nombres como `"annual_report.pdf"`. PostgreSQL con `config="simple"` tokeniza `annual_report` como un único token (no como dos palabras separadas). Buscar `"annual"` no encontraba el documento.

**Causa raíz:** El tokenizador de PostgreSQL FTS considera el guión bajo como parte de un token, no como separador de palabras. Comportamiento no obvio para quien espera que `annual_report` sea tokenizado como `annual` + `report`.

**Solución aplicada:** Los tests usan nombres con espacios naturales (`"annual report"`). La documentación del proyecto advierte este comportamiento. No se cambió el tokenizador (`simple` es intencional para corpus multi-idioma).

---

## Post-portafolio: correcciones post-5.5 (2026-07-01)

---

## ERR-056: Patrón `lib/` demasiado amplio en `.gitignore` — ignoraba `frontend/src/shared/lib/`

| Campo | Valor |
|---|---|
| Fecha | 2026-07-01 |
| Fase | Post-Fase 5.5 |
| Severidad | MEDIA |
| Categoría | `GITIGNORE` |
| Archivo(s) afectado(s) | `.gitignore`, `frontend/src/shared/lib/roles.ts` |

**Descripción:** El `.gitignore` raíz contenía el patrón `lib/` (heredado de la plantilla Python de gitignore), que ignora cualquier directorio llamado `lib` en toda la jerarquía del proyecto. Al crear `frontend/src/shared/lib/roles.ts` (centralización de `WRITE_ROLES` en Fase post-5.5), git marcaba `frontend/src/shared/lib/` como directorio ignorado. El archivo fue incluido correctamente en el commit mediante `git add` explícito, pero cualquier archivo nuevo creado dentro de `frontend/src/shared/lib/` habría sido silenciosamente omitido de `git status` como si no existiera.

**Causa raíz:** El patrón `lib/` de la plantilla estándar de Python `.gitignore` fue copiado sin adaptar su alcance. Su intención original es ignorar el directorio `lib/` del entorno virtual Python (que vive en `backend/lib/`), no directorios `lib/` arbitrarios dentro del código fuente del frontend.

**Solución aplicada:** `lib/` sustituido por `backend/lib/` y `lib64/` por `backend/lib64/` en el `.gitignore` raíz, limitando el patrón exclusivamente al subdirectorio backend donde reside el virtualenv Python.

**Commit de corrección:** `76f0f8f`

---

## ERR-057: `react-refresh/only-export-components` en archivos generados por shadcn/ui

| Campo | Valor |
|---|---|
| Fecha | 2026-07-01 |
| Fase | Post-portafolio / CI |
| Severidad | MEDIA |
| Categoría | `ESLINT_CONFIG` |
| Archivo(s) afectado(s) | `frontend/src/components/ui/badge.tsx:36`, `button.tsx:56`, `form.tsx:170` |

**Descripción:** El job `frontend / Lint` del CI falló porque los archivos shadcn/ui exportan constantes de variantes (`buttonVariants`, `badgeVariants`, `FormFieldContext`) en el mismo módulo que componentes React. La regla `react-refresh/only-export-components` del plugin de Vite lo reporta como error porque mezclar exportaciones de componentes y no-componentes en el mismo archivo puede interferir con Hot Module Replacement.

**Causa raíz:** Los archivos de shadcn/ui son generados automáticamente y siguen su propia convención de diseño (export de variantes junto al componente). El `eslint.config.js` no tenía override para este directorio, por lo que la regla se aplicaba indiscriminadamente a código que no pertenece a la aplicación.

**Solución aplicada:** Override en `frontend/eslint.config.js` que deshabilita `react-refresh/only-export-components` para `src/components/ui/**/*.{ts,tsx}`.

**Commit de corrección:** `89f5e86`

---

## ERR-058: `@typescript-eslint/no-unused-vars` no reconocía la convención de prefijo `_`

| Campo | Valor |
|---|---|
| Fecha | 2026-07-01 |
| Fase | Post-portafolio / CI |
| Severidad | MEDIA |
| Categoría | `ESLINT_CONFIG` |
| Archivo(s) afectado(s) | `frontend/src/features/documents/api.ts:38` |

**Descripción:** La variable `_omit` en la destructuración `const { onUploadProgress: _omit, ...queryParams }` fue reportada como unused. El propósito era excluir `onUploadProgress` del spread `queryParams` sin consumirlo; la convención de prefijo `_` para variables intencionalmente no usadas no estaba configurada en el linter.

**Causa raíz:** El `eslint.config.js` no tenía configurado `varsIgnorePattern` en la regla `@typescript-eslint/no-unused-vars`, por lo que el prefijo `_` no se reconocía como indicador de variable descartada a propósito.

**Solución aplicada:** (1) Renombrar `_omit` a `_`. (2) Añadir `varsIgnorePattern: '^_'` a la configuración global de `@typescript-eslint/no-unused-vars` en `eslint.config.js`.

**Commit de corrección:** `89f5e86`

---

## ERR-059: `react-hooks/set-state-in-effect` en `ProtectedRoute` — patrón intencional sin suprimir

| Campo | Valor |
|---|---|
| Fecha | 2026-07-01 |
| Fase | Post-portafolio / CI |
| Severidad | MEDIA |
| Categoría | `REACT_STATE` |
| Archivo(s) afectado(s) | `frontend/src/shared/components/ProtectedRoute.tsx:28` |

**Descripción:** El React Compiler eslint plugin reportó `setRestorationAttempted(true)` como `setState` síncrono dentro de un `useEffect`. El warning es técnicamente correcto desde la perspectiva del plugin, pero el patrón es intencional: la decisión de diseño #33 requiere un bootstrap secuencial donde `getMe()` imperativo se ejecuta y setea el flag antes de renderizar `<Outlet>`. Un hook declarativo (`useMe()`) introduciría race condition con el flag `restorationAttempted`.

**Causa raíz:** El patrón de bootstrap secuencial (correcto en este contexto) no tenía directiva de supresión. Al añadir el plugin de React Compiler al CI, el warning pasó a ser error bloqueante.

**Solución aplicada:** `// eslint-disable-next-line react-hooks/set-state-in-effect` en la línea específica, con comentario explicativo que referencia la decisión de diseño #33.

**Commit de corrección:** `89f5e86`

---

## ERR-060: Directiva `eslint-disable` obsoleta en `WorkflowTemplateForm`

| Campo | Valor |
|---|---|
| Fecha | 2026-07-01 |
| Fase | Post-portafolio / CI |
| Severidad | BAJA |
| Categoría | `DEAD_CODE` |
| Archivo(s) afectado(s) | `frontend/src/features/workflows/components/WorkflowTemplateForm.tsx:94` |

**Descripción:** Un comentario `// eslint-disable-next-line react-hooks/exhaustive-deps` en la línea 94 ya no correspondía a ningún warning activo en ese punto del código. ESLint detecta las directivas que no suprimen ningún error real y las reporta como "unused directive", lo que convierte el aviso en error de CI.

**Causa raíz:** Una refactorización anterior eliminó o movió la dependencia problemática del `useEffect` sin quitar la directiva de supresión que ya había dejado de ser necesaria.

**Solución aplicada:** Eliminar la directiva obsoleta.

**Commit de corrección:** `89f5e86`

---

## CI / PR #1: Rondas 2 y 3 (2026-07-01)

---

## ERR-061: `frontend/src/lib/` nunca commiteada — 11 suites con "0 tests" en CI

| Campo | Valor |
|---|---|
| Fecha | 2026-07-01 |
| Fase | CI / PR #1 |
| Severidad | ALTA |
| Categoría | `GITIGNORE` |
| Archivo(s) afectado(s) | `frontend/src/lib/api-client.ts`, `frontend/src/lib/query-client.ts`, `frontend/src/lib/utils.ts`, `frontend/src/lib/__tests__/query-client.test.ts` |

**Descripción:** 11 suites de test reportaron "0 tests" en CI. Error: `Failed to resolve import "@/lib/utils"` / `Failed to resolve import "@/lib/api-client"`. Exit code 1. En CI el directorio `frontend/src/lib/` no existía porque nunca fue commiteado.

**Causa raíz:** El `.gitignore` original contenía el patrón `lib/` (heredado de Python), que ignoraba cualquier directorio llamado `lib` en toda la jerarquía. Cuando se corrigió a `backend/lib/` en ERR-056 (commit `76f0f8f`), el directorio `frontend/src/lib/` (que aloja el cliente HTTP, query client y utils de Tailwind) ya llevaba tiempo en "untracked files" silenciosamente y nadie lo había commiteado. Diferente de ERR-056, que era sobre `src/shared/lib/roles.ts`; este es el directorio base `src/lib/`.

**Solución aplicada:** `git add frontend/src/lib/` — 4 archivos trackeados y commiteados. Commit `387cb1a`.

---

## ERR-062: `TypeError: 'Folder' object is not subscriptable` — test con acceso de subscript sobre model instance

| Campo | Valor |
|---|---|
| Fecha | 2026-07-01 |
| Fase | CI / PR #1 |
| Severidad | MEDIA |
| Categoría | `TYPE_CONTRACT` |
| Archivo(s) afectado(s) | `backend/apps/documents/tests/test_folder_selector.py` |

**Descripción:** `TestFolderSelector::test_get_folder_tree_flat_list` fallaba con `TypeError: 'Folder' object is not subscriptable` al ejecutar `node["id"]` sobre el resultado de `get_folder_tree()`.

**Causa raíz:** El test fue escrito asumiendo que `get_folder_tree()` devuelve dicts (como haría un queryset `.values()`), usando acceso de subscript `node["id"]`. El selector devuelve model instances de Django; el acceso de subscript falla sobre una instancia.

**Solución aplicada:** Cambiar el test para usar acceso de atributo: `str(node.id)` en lugar de `node["id"]`, `str(node.parent_id)` en lugar de `node["parent_id"]`. Commit `387cb1a`.

---

## ERR-063: `celery.exceptions.Retry: TransientError('Storage unavailable')` — mock_storage incompleto con Celery eager + transaction=True

| Campo | Valor |
|---|---|
| Fecha | 2026-07-01 |
| Fase | CI / PR #1 |
| Severidad | ALTA |
| Categoría | `ASYNC_CELERY` |
| Archivo(s) afectado(s) | `backend/apps/documents/tests/test_document_service.py` (5 tests), `backend/apps/documents/tests/test_api.py` (1 test) |

**Descripción:** 6 tests fallaron con `Retry in 1s: TransientError('Storage unavailable for {document_id}')`. Los tests pasaban localmente pero fallaban en CI.

**Causa raíz:** Interacción de tres factores simultáneos: (1) `@pytest.mark.django_db(transaction=True)` → los hooks `on_commit` se disparan tras cada commit real; (2) `CELERY_TASK_ALWAYS_EAGER=True` → `process_ocr.delay()` corre síncronamente al ser llamada; (3) el fixture `mock_storage` mockeaba `StorageService` en `apps.documents.services.document_service` (para `upload_file`) pero NO en `apps.documents.services.ocr_service`, donde `process_ocr` importa un `StorageService` fresco para `download_file`. MinIO no está disponible en CI → `download_file` lanza `TransientError`. Localmente MinIO sí corre en Docker Compose y el task se ejecutaba correctamente.

**Solución aplicada:** Añadir `monkeypatch.setattr("apps.documents.services.document_service.process_ocr.delay", MagicMock())` dentro del fixture `mock_storage` en ambos archivos. El task nunca se encola en tests que solo verifican el service de documento. Commit `387cb1a`.

---

## ERR-064: `WRITE_ROLES.includes(role)` — `TS2345` en strict mode de `vite build`

| Campo | Valor |
|---|---|
| Fecha | 2026-07-01 |
| Fase | CI / PR #1 |
| Severidad | MEDIA |
| Categoría | `TYPE_CONTRACT` |
| Archivo(s) afectado(s) | `DashboardPage.tsx`, `DocumentCard.tsx`, `DocumentVersionList.tsx`, `DocumentDetailPage.tsx`, `DocumentListPage.tsx`, `FolderCard.tsx`, `FolderBrowserPage.tsx` |

**Descripción:** `TS2345: Argument of type 'UserRole' is not assignable to parameter of type '"super_admin" | "org_admin" | "supervisor" | "editor"'` en 7 archivos durante `vite build` en CI. `tsc --noEmit` local había pasado limpio.

**Causa raíz:** `WRITE_ROLES` definido con `as const` produce tipo `readonly ["super_admin", "org_admin", "supervisor", "editor"]`. `.includes()` sobre ese tipo solo acepta exactamente esas 4 strings literales. `UserRole` incluye también `"viewer"` y `"auditor"` → TypeScript en modo strict lo rechaza. `tsc --noEmit` local usa `tsconfig.json` (menos restrictivo); `vite build` usa `tsconfig.app.json` (`strict: true`).

**Solución aplicada:** Castear a `(WRITE_ROLES as readonly string[]).includes(role)` en los 7 archivos. Commit `4177596`.

---

## ERR-065: `SearchResult` pasado a `DocumentCard` que espera `Document` — `TS2739`

| Campo | Valor |
|---|---|
| Fecha | 2026-07-01 |
| Fase | CI / PR #1 |
| Severidad | MEDIA |
| Categoría | `TYPE_CONTRACT` |
| Archivo(s) afectado(s) | `frontend/src/features/search/pages/SearchPage.tsx` |

**Descripción:** `TS2739: Type 'SearchResult' is missing the following properties from type 'Document': checksum, ocr_content, metadata` en `vite build`.

**Causa raíz:** `SearchResult` extiende `Omit<Document, 'checksum'|'metadata'|'ocr_content'>`, omitiendo 3 campos que `DocumentCard` declara en su prop type `document: Document`. Aunque `DocumentCard` no accede a esos 3 campos en su render, TypeScript en modo strict los exige en la firma del componente.

**Solución aplicada:** Cast `doc as unknown as Document` en `SearchPage`. El cast es seguro porque `DocumentCard` no consume `checksum`, `ocr_content` ni `metadata`. Commit `4177596`.

---

## ERR-066: `storage_path` inexistente en tipo `Document` — fixture de test desactualizado

| Campo | Valor |
|---|---|
| Fecha | 2026-07-01 |
| Fase | CI / PR #1 |
| Severidad | BAJA |
| Categoría | `TYPE_CONTRACT` |
| Archivo(s) afectado(s) | `frontend/src/features/documents/__tests__/hooks.test.ts` |

**Descripción:** `TS2353: Object literal may only specify known properties, and 'storage_path' does not exist in type 'Document'` en `vite build`. El fixture del test contenía `storage_path: 'uploads/test.pdf'`, campo que existía en una versión anterior del tipo `Document` y fue eliminado al sincronizar los tipos con la respuesta real del backend.

**Causa raíz:** Al eliminar `storage_path` del tipo `Document` (ERR-038, 2026-06-30), el fixture del test no fue actualizado en consecuencia.

**Solución aplicada:** Eliminar `storage_path` del fixture y alinear con el tipo actual (`folder_name`, `created_by_email`). Commit `4177596`.

---

## ERR-067: `ocr_content` faltante en fixtures de tests de documentos

| Campo | Valor |
|---|---|
| Fecha | 2026-07-01 |
| Fase | CI / PR #1 |
| Severidad | BAJA |
| Categoría | `TYPE_CONTRACT` |
| Archivo(s) afectado(s) | `frontend/src/features/documents/__tests__/DocumentDetailPage.test.tsx`, `frontend/src/features/documents/__tests__/DocumentVersionList.test.tsx` |

**Descripción:** `TS2741: Property 'ocr_content' is missing in type '...' but required in type 'Document'` en `vite build`. Dos archivos de test tenían `MOCK_DOCUMENT` sin el campo `ocr_content`.

**Causa raíz:** Cuando se añadió `ocr_content: string` al tipo `Document` en la feature de 2026-06-30 (exposición del campo OCR en la API), los fixtures de estos dos tests no fueron actualizados para incluir el nuevo campo requerido.

**Solución aplicada:** Añadir `ocr_content: ''` al `MOCK_DOCUMENT` en ambos archivos. Commit `4177596`.

---

## ERR-068: Test de `ProtectedRoute` verde por una razón incorrecta (ausencia de mock de red)

| Campo | Valor |
|---|---|
| Fecha | 2026-07-03 |
| Fase | 6.1 |
| Severidad | BAJA (calidad de test, no bug de producción) |
| Categoría | `TEST_QUALITY` |
| Archivo(s) afectado(s) | `frontend/src/shared/components/__tests__/ProtectedRoute.test.tsx` |

**Descripción:** El test "sin refreshToken en localStorage → redirige a /login" pasaba en verde desde antes de Fase 6.1, pero no verificaba lo que su nombre y su intención indicaban.

**Causa raíz:** El test no configuraba ningún mock de red (ni MSW ni mock de módulo) para la llamada a `refreshToken()` que dispara `ProtectedRoute` al montar. En jsdom, esa request sin handler fallaba con un error de red genérico — y ese error caía, por coincidencia, en el mismo bloque `.catch()` que maneja un 401 real del backend, produciendo el mismo resultado observable (`Navigate` a `/login`). El test aprobaba por un camino de fallo distinto al que pretendía cubrir, no por la lógica de negocio real.

**Solución aplicada:** Detectado al reescribir la suite para el nuevo flujo de cookie httpOnly (que ya no puede decidir de antemano, mirando `localStorage`, si intentar el refresh). Se reemplazó la dependencia de comportamiento de red no configurado por mocks explícitos a nivel de módulo (`vi.mock('@/features/auth/api')` sobre `refreshToken`/`getMe`), permitiendo simular determinísticamente "cookie válida" vs. "cookie ausente/inválida" en cada caso. Commit `6701bc8`.

---

## ERR-069: `mock_storage` no cubría `generate_thumbnail.delay` — I/O real no determinista contra MinIO en tests de `create_document`

| Campo | Valor |
|---|---|
| Fecha | 2026-07-06 |
| Fase | 6.2 |
| Severidad | BAJA (aislamiento de test, no bug de producción) |
| Categoría | `ASYNC_CELERY` |
| Archivo(s) afectado(s) | `backend/apps/documents/tests/test_document_service.py` (fixture `mock_storage`) |

**Descripción:** Al añadir el segundo `transaction.on_commit(lambda: generate_thumbnail.delay(...))` en `document_service.create_document` (junto al `process_ocr.delay` ya existente), el fixture `mock_storage` —que ya mockeaba `process_ocr.delay` desde el fix de ERR-063— no mockeaba el nuevo `generate_thumbnail.delay`. Con `CELERY_TASK_ALWAYS_EAGER=True` y `django_capture_on_commit_callbacks`/`transaction=True`, la task de thumbnail se ejecutaba de verdad en algunos tests de `create_document`, intentando I/O real contra MinIO.

**Causa raíz:** Un mock que cubre una sola de las dos tasks encoladas en `on_commit` queda incompleto en cuanto se añade una segunda; el patrón es el mismo de ERR-063 pero detectado y corregido durante la escritura de los tests nuevos de Fase 6.2, antes de que llegara a producir fallos intermitentes en CI.

**Solución aplicada:** Extender el fixture `mock_storage` para mockear también `apps.documents.services.document_service.generate_thumbnail.delay` junto a `process_ocr.delay`. Pendiente de commit (sesión de Fase 6.2, 2026-07-06).

---

## ERR-070: Fixtures de tests de documentos sin `thumbnail_status`/`thumbnail_url` tras extender el tipo `Document`

| Campo | Valor |
|---|---|
| Fecha | 2026-07-06 |
| Fase | 6.2 (frontend) |
| Severidad | BAJA (detectado por `tsc`, no una falla de CI ya ocurrida) |
| Categoría | `TYPE_CONTRACT` |
| Archivo(s) afectado(s) | Fixtures `MOCK_DOCUMENT`/equivalentes en `frontend/src/features/documents/__tests__/hooks.test.ts` y `DocumentDetailPage.test.tsx` |

**Descripción:** Al añadir `thumbnail_status: ThumbnailStatus` y `thumbnail_url: string | null` como campos obligatorios del tipo `Document`, los fixtures de test existentes (construidos a mano antes de esta sesión) dejaron de tipar correctamente bajo `tsc --noEmit`. Vitest seguía en verde porque no type-checkea al ejecutar — el problema solo era visible corriendo el compilador.

**Causa raíz:** Mismo patrón que ERR-066/ERR-067 (2026-07-01): cada vez que se agrega un campo obligatorio nuevo a un tipo de contrato compartido (`Document`), todos los fixtures de test que construyen ese tipo a mano deben actualizarse en el mismo cambio. No hay un mecanismo automático (p. ej. un factory/builder de fixtures) que lo garantice.

**Solución aplicada:** Añadir `thumbnail_status`/`thumbnail_url` a los fixtures afectados durante la escritura de los tests nuevos de esta sesión, antes de que llegara a fallar en CI. Detectado proactivamente por `test-quality-engineer`, no como un fallo de pipeline ya ocurrido. Pendiente de commit (sesión de Fase 6.2 frontend, 2026-07-06). **Nota recurrente:** este es el tercer caso del mismo patrón (ERR-066, ERR-067, ERR-070) — señal de que valdría la pena introducir un factory de fixtures de `Document` en el frontend (deuda técnica anotada, no implementada).

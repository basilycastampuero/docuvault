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
> Última actualización: **Fase 6.1 (JWT en cookies httpOnly) implementada y testeada completa**
> (2026-07-03). Rama `feature/5.2-frontend-documents`.
> Proyecto de portafolio completado (Fases 0–5). Fase 6 = mejoras post-portafolio, en ejecución
> (6.1 completa, 6.2 siguiente).

---

### 2026-07-03 — Fase 6.1 implementada: refresh token de cookie httpOnly + CSRF (4 commits)

Mismo día en que se validó el backlog de Fase 6 (ver entrada siguiente, cronológicamente anterior),
se implementó y testeó por completo la sub-fase elegida para arrancar: **6.1 — JWT en cookies
httpOnly**.

**El problema que cierra.** Desde Fase 5.1 (decisión #28) el `refreshToken` vivía en
`localStorage`: cualquier XSS en la aplicación podía leerlo y mantener una sesión válida
indefinidamente, sin necesidad de robar credenciales. Es la deuda de seguridad de mayor severidad
del proyecto — el tipo de cosa que un revisor senior busca primero en un SaaS.

**La solución.** El refresh ahora viaja en una cookie `HttpOnly Secure SameSite=Strict`
(`sv_refresh`), invisible a JavaScript: un XSS ya no puede leerla. El `access` se queda en memoria
(Zustand) como antes. Como la cookie viaja automáticamente con cada request al dominio, hace falta
protección CSRF en los dos endpoints que la usan (`/auth/refresh/`, `/auth/logout/`): patrón
double-submit con una segunda cookie no-HttpOnly (`sv_csrf`) que el cliente lee y reenvía como
header `X-CSRF-Token`; el backend compara ambos valores con `secrets.compare_digest`. Todo detrás
del feature-flag `AUTH_REFRESH_COOKIE_ENABLED` (activado por defecto, con fallback a leer el
refresh del body si no hay cookie, para permitir un rollout gradual sin romper clientes viejos).

Un ajuste no anticipado en el plan original: `LogoutView` exigía `IsAuthenticated`, lo que
significa que un `access` ya expirado (típico si el usuario dejó la pestaña abierta) impediría
cerrar sesión. Se cambió a `AllowAny` — la identidad válida para hacer logout la da el propio
refresh (vía su cookie) más su blacklist, no el access. El logout quedó además deliberadamente
idempotente: si el refresh ya estaba blacklisteado o era inválido, no lanza error (solo
`logger.warning`) y de todos modos limpia la cookie.

**El prerrequisito que no era opcional: el proxy de Vite.** `SameSite=Strict` solo entrega la
cookie si la request es same-origin. En dev, Vite corre en `:5173` y Django en `:8000` — dos
orígenes distintos — así que sin un proxy la cookie de refresh nunca hubiera llegado al backend.
Se agregó `server.proxy['/api']` en `frontend/vite.config.ts` apuntando a `localhost:8000`, y con
eso `frontend/src/lib/api-client.ts` pasó a usar `withCredentials: true`. Un detalle que se
descubrió recién al integrar: el proxy solo sirve si el cliente pide URLs *relativas*
(`/api/v1/...`). `VITE_API_BASE_URL` seguía apuntando a `http://localhost:8000/api/v1` en
`.env.development` (valor heredado de Fase 5.1) — con eso las requests seguían siendo cross-origin
por más proxy que hubiera, y el ajuste no estaba en el plan de ejecución original de 6.1. Se
corrigió a `/api/v1` (mismo valor relativo que ya usaba `.env.production`). Como `.env.development`
está en `.gitignore`, el cambio no quedó versionado por sí solo — lo que sí expuso un gap real:
**`frontend/.env.example` no existía** (a diferencia de `backend/.env.example`, que CLAUDE.md §10
exige). Sin ese archivo, cualquier clon nuevo del repo no tiene forma de saber que necesita esa
variable en modo relativo para que el proxy funcione. Se creó `frontend/.env.example` como parte
de esta misma tarea de documentación.

**Un test verde por la razón equivocada.** El test de `ProtectedRoute` "sin sesión guardada →
redirige a /login" pasaba desde antes de este cambio, pero por accidente: no tenía ningún mock de
red configurado, así que en jsdom la request al backend fallaba con un error de red genérico —
y ese error caía, por coincidencia, en el mismo `.catch()` que un 401 real. El test nunca verificó
lo que decía verificar. Se detectó al reescribir la suite para el nuevo flujo (la cookie es
invisible a JS, así que el bootstrap ya no puede decidir de antemano si intentar el refresh
mirando `localStorage`: ahora siempre lo intenta, y deja que el backend responda 401 si no hay
cookie válida) y se corrigió mockeando `refreshToken`/`getMe` a nivel de módulo en lugar de
depender de comportamiento de red no configurado. Buena anécdota de que un test en verde no es
sinónimo de un test correcto.

**Resultado final:** 550 tests backend (95.62% cobertura, sube desde el ~95% de fin de Fase 5) +
174 tests frontend (sube desde 169), 0 errores de TypeScript. 4 commits: `76f6dc5` (backend),
`0e978eb` (tests backend), `b2ac8e9` (frontend), `6701bc8` (tests frontend). Detalle completo del
plan de ejecución en `docs/phase-plan.md` §6.1; decisión de diseño registrada como **#41** en
`CLAUDE.md` §17 (supera la #28).

---

### 2026-07-03 — Validación del backlog de Fase 6 y decisión de arrancar por 6.1

Se retomó el proyecto para planificar la ejecución de Fase 6. El backlog de 7 sub-fases se había
agregado a `docs/phase-plan.md` el 2026-07-01 (commit `a6a81a4`), pero nunca se validó contra el
código real tal como estaba en ese momento — se escribió como propuesta. Antes de empezar a
implementar nada, se encargó a un agente de arquitectura de software auditar cada premisa del
backlog contra el estado actual del repositorio y producir un plan de ejecución concreto para la
sub-fase de arranque.

**Resultado de la validación:** las 7 sub-fases (6.1 a 6.7) siguen vigentes — ninguna quedó
invalidada por cambios posteriores al plan. Tres hallazgos relevantes emergieron de la auditoría:

1. **`apps/billing` es un paquete vacío, no un "skeleton dormido".** Solo contiene `__init__.py`;
   no tiene `apps.py` ni está registrado en `INSTALLED_APPS`. La sub-fase 6.6 requiere scaffolding
   completo desde cero, no "despertar" una estructura existente. Se corrigió la redacción de 6.6 en
   `docs/phase-plan.md` para reflejarlo con precisión.
2. **Falta code-splitting en el frontend — deuda real no capturada antes de Fase 6.** El bundle es
   100% síncrono (0 usos de `React.lazy`/`Suspense`). Se sumó como entregable adicional de la
   sub-fase 6.5 (madurez de frontend), junto con la nota de que el dark mode ya tiene su estrategia
   `darkMode: ['class']` declarada en `tailwind.config.js` — falta el toggle y los tokens, no la base.
3. **El proxy `/api` de Vite en dev es un prerrequisito duro de 6.1, no un detalle opcional.** Sin
   él, `SameSite=Strict` no entrega la cookie de refresh en el flujo cross-origin de dev (Vite:5173
   vs API:8000). Se agregó como primera tarea de frontend en el plan de ejecución de 6.1, junto con
   una segunda precisión: `LogoutView` hoy exige `IsAuthenticated`, lo que rompería el logout con un
   access ya expirado una vez que el refresh viva en cookie — habrá que pasarlo a `AllowAny` cuando
   la identidad del refresh viaje por cookie.

**Decisión: se empieza por 6.1 (JWT en cookies httpOnly).** Es la sub-fase de mayor severidad de
seguridad del backlog (cierra la deuda XSS de la decisión #28), no tiene dependencias de otras
sub-fases y no requiere ninguna migración de base de datos — el menor riesgo de arranque con el
mayor impacto de portafolio. El agente arquitecto entregó además un plan de ejecución a nivel de
archivo/tarea/commit para 6.1, incorporado a `docs/phase-plan.md`. La implementación queda para una
sesión futura.

---

### 2026-07-01 — Mejoras UX: FileTypeBadge y fix overflow en DocumentCard (commit bf343b6)

Dos mejoras cosméticas/UX en la capa de listado de documentos, ambas en
`frontend/src/features/documents/components/`.

**FileTypeBadge (nuevo componente):** mapea `document.mime_type` a un badge coloreado con
una etiqueta corta legible (PDF=rojo, JPG/PNG/WEBP=azul cielo, DOCX=índigo,
XLSX/CSV=esmeralda, PPTX=naranja, TXT/desconocido=gris). Maneja los tipos MIME largos de
Office (e.g. `application/vnd.openxmlformats-officedocument.wordprocessingml.document` → "DOCX")
mediante un mapa de prefijos. Se renderiza en `DocumentCard` en la fila de badges junto a
`OcrStatusBadge` y el badge de status del documento.

**Fix overflow en DocumentCard:** los nombres de archivo muy largos desbordaban los bordes
de la tarjeta. Fix: `overflow-hidden` en el elemento `<Card>` más externo, y `min-w-0 flex-1`
en el contenedor flex interno. Estos dos valores completan la cadena de truncado que ya
tenía `truncate` en el `<p>` del nombre — sin `min-w-0`, un flex item no se encoge más allá
de su contenido mínimo y el truncado no tiene efecto.

**Archivos:** `FileTypeBadge.tsx` (nuevo), `DocumentCard.tsx`.

---

### 2026-07-01 — Auditoría de código frontend (post-testing)

**[ALTA] Crash SearchPage:** `SearchResultSerializer` no incluía `ocr_status` en sus `fields`. `DocumentCard` pasaba `document.ocr_status` (undefined) al badge; `CONFIG[undefined]` es `undefined` → destructuración de `label` lanzaba TypeError con pantalla en blanco. Fix: campo añadido al serializer (`backend/apps/search/api/serializers.py`) + fallback defensivo `CONFIG[status] ?? { label: ..., className: ... }` en `OcrStatusBadge.tsx`.

**[MEDIA] Tipo SearchResult:** `searchApi.search` tipaba los resultados como `Document[]` completo, pero el serializer devuelve un shape parcial (sin `checksum`, `metadata`, `ocr_content`) más el campo extra `rank`. Fix: nueva interfaz `SearchResult extends Omit<Document, 'checksum'|'metadata'|'ocr_content'> { rank: number }` en `shared/types/index.ts`; `search/api.ts` actualizado.

**[MEDIA] Entidades IA invisibles:** La pestaña "Análisis IA" mostraba resumen y categoría pero nunca las entidades detectadas. El backend almacena `entities: { dates: [], amounts: [], names: [] }` (objeto), pero el frontend lo tipaba como `entities?: string[]`; la guarda `analysis.entities.length > 0` evaluaba `undefined > 0 = false` y silenciaba el bloque. Fix: `AiAnalysis.entities` corregido al tipo objeto real; rendering actualizado para aplanar las tres listas y mostrarlas como badges (`DocumentDetailPage.tsx`).

#### Issues de baja severidad (2026-07-01)

1. **ExecutionStatusBadge fallback** — `CONFIG[status] ?? { label: ..., className: ... }` antes del destructuring. Mismo patrón que `OcrStatusBadge`. Previene crash si el backend añade un nuevo status de workflow no conocido por el cliente.
2. **`getVersions` tipo honesto** — Retorno cambiado a `Partial<PaginatedMeta>` en `documents/api.ts`, reflejando que el endpoint devuelve `"meta": {}` vacío. Elimina el asunto de falsa seguridad de tipos.
3. **WRITE_ROLES centralizado** — Creado `frontend/src/shared/lib/roles.ts` con las constantes `WRITE_ROLES`/`START_ROLES` y el helper `canWrite()`. Eliminadas 8 declaraciones locales duplicadas. Previene RBAC inconsistente en la UI si cambia la política de roles.
4. **Polling con cota máxima** — `useDocument` detiene el polling de OCR tras 40 intentos (~2 min); `useWorkflowExecution` tras 48 intentos (~4 min). Previene polling eterno si el worker Celery muere sin escribir un estado terminal.
5. **Código muerto audit eliminado** — `auditApi.getById`, `useAuditLog` y `auditKeys.detail` removidos. El backend expone el endpoint `GET /audit-logs/{id}/` pero el frontend nunca lo consumió; mantenerlo generaba deuda de tipos sin valor.

---

### 2026-07-01 — Fix ESLint CI: 5 errores bloqueaban la PR #1 (commit 89f5e86)

Al abrir `feature/5.2-frontend-documents → main` el job `frontend / Lint` del CI de GitHub
Actions falló con 5 errores de ESLint. Ninguno era lógica de negocio; todos eran
configuración de linting o directivas desactualizadas.

**ERR-A — `react-refresh/only-export-components` en archivos shadcn/ui**
`badge.tsx`, `button.tsx` y `form.tsx` exportan constantes de variantes
(`buttonVariants`, `badgeVariants`, `FormFieldContext`) junto a componentes. La regla de
Vite lo reporta porque mezclar exportaciones de componentes y no-componentes en el mismo
archivo interfiere con Hot Module Replacement. Solución: override en `eslint.config.js`
deshabilitando la regla para `src/components/ui/**/*.{ts,tsx}` — son archivos generados
por shadcn/ui, no código de la aplicación.

**ERR-B — `@typescript-eslint/no-unused-vars` — variable `_omit`**
En `documents/api.ts`, la destructuración `const { onUploadProgress: _omit, ...queryParams }`
usaba `_omit` para excluir el campo del spread. La regla no reconocía la convención de
prefijo `_` como "variable intencionalmente no usada". Solución: renombrar a `_` (nombre
mínimo) y añadir `varsIgnorePattern: '^_'` globalmente en `eslint.config.js`.

**ERR-C — `react-hooks/set-state-in-effect` en `ProtectedRoute`**
El React Compiler eslint plugin marcaba `setRestorationAttempted(true)` como `setState`
síncrono dentro de un `useEffect`. El patrón es intencional (decisión de diseño #33 —
bootstrap secuencial: `getMe()` imperativo antes de renderizar `<Outlet>`). Solución:
`// eslint-disable-next-line react-hooks/set-state-in-effect` en la línea específica.

**ERR-D — Directiva `eslint-disable` obsoleta en `WorkflowTemplateForm`**
Un `// eslint-disable-next-line react-hooks/exhaustive-deps` en la línea 94 ya no
correspondía a ningún warning activo. ESLint lo reporta como "unused directive". Solución:
eliminar la directiva.

---

### 2026-07-01 — CI Ronda 2: tests de backend fallaron + imports del frontend no commiteados (commit 387cb1a)

La segunda ronda de CI en la PR #1 expuso tres categorías de problemas distintas.

**ERR-A — `frontend/src/lib/` nunca commiteada (GITIGNORE)**

11 suites de test reportaron "0 tests" en CI. Error: `Failed to resolve import "@/lib/utils"` /
`Failed to resolve import "@/lib/api-client"`. El directorio `frontend/src/lib/` (que contiene
`api-client.ts`, `query-client.ts`, `utils.ts` y su test) estaba permanentemente en "untracked
files" — nunca se hizo `git add`. En CI el directorio no existe y todos los imports fallan con
exit code 1.

Causa raíz: el `.gitignore` original tenía el patrón `lib/` heredado de Python. Al corregirlo en
ERR-056 (commit `76f0f8f`) se restringió a `backend/lib/`, pero el directorio base `frontend/src/lib/`
(diferente de `frontend/src/shared/lib/`) nunca fue commiteado explícitamente. El patrón original
lo ignoraba silenciosamente y nadie lo detectó porque `git status` tampoco lo mostraba.

Solución: `git add frontend/src/lib/` — 4 archivos commiteados (`api-client.ts`, `query-client.ts`,
`utils.ts`, `__tests__/query-client.test.ts`).

**ERR-B — `TypeError: 'Folder' object is not subscriptable` (TYPE_CONTRACT)**

`test_folder_selector.py::TestFolderSelector::test_get_folder_tree_flat_list` fallaba porque el test
usaba acceso de subscript `node["id"]` y `node["parent_id"]`. `get_folder_tree()` devuelve model
instances de Django (no dicts), por lo que el acceso de subscript lanza `TypeError`.

Solución: acceso de atributo: `str(node.id)` y `str(node.parent_id)` en lugar de subscript. El test
asumía que el selector devolvía `.values()` (dicts) cuando en realidad devuelve queryset de instancias.

**ERR-C — `celery.exceptions.Retry: TransientError('Storage unavailable')` (ASYNC_CELERY)**

6 tests fallaron con `Retry in 1s: TransientError('Storage unavailable for {document_id}')`. Interacción
entre tres factores simultáneos:

1. Tests usan `@pytest.mark.django_db(transaction=True)` → los hooks `on_commit` se disparan tras cada
   commit real (no al final del test completo)
2. `CELERY_TASK_ALWAYS_EAGER=True` en `test.py` → `process_ocr.delay()` corre síncronamente al ser llamada
3. El fixture `mock_storage` mockeaba `StorageService` en `document_service` (para `upload_file`) pero NO
   en `ocr_service`, donde `process_ocr` importa un `StorageService` fresco para `download_file` — ese
   import nunca se mockeó

MinIO no existe como servicio en el runner de CI → `download_file` lanza `TransientError` → Celery
reintenta → el test falla.

Solución: añadir `monkeypatch.setattr("apps.documents.services.document_service.process_ocr.delay", MagicMock())`
dentro del fixture `mock_storage` en `test_document_service.py` y `test_api.py`. El task nunca se encola
en tests que solo verifican el service de documento.

Por qué no se detectó localmente: MinIO sí corre en Docker Compose durante el desarrollo. El task se ejecutaba
realmente, descargaba el archivo, y el test pasaba. En CI no hay MinIO.

---

### 2026-07-01 — CI Ronda 3: errores de TypeScript en vite build (commit 4177596)

La tercera ronda falló en el paso `vite build` del job de frontend. `tsc --noEmit` local había pasado
limpio. La diferencia clave: `vite build` usa `tsconfig.app.json` con `strict: true` más restrictivo
que el `tsconfig.json` que usa `tsc --noEmit` al correr solo.

**ERR-D — `WRITE_ROLES.includes(role)` rechazado por strict mode (TYPE_CONTRACT)**

`WRITE_ROLES` se define con `as const` → su tipo es `readonly ["super_admin", "org_admin", "supervisor",
"editor"]`. El método `.includes()` sobre ese tipo solo acepta exactamente esas 4 strings literales.
`UserRole` incluye `"viewer"` y `"auditor"` → `TS2345` en 7 archivos: `DashboardPage.tsx`,
`DocumentCard.tsx`, `DocumentVersionList.tsx`, `DocumentDetailPage.tsx`, `DocumentListPage.tsx`,
`FolderCard.tsx`, `FolderBrowserPage.tsx`.

Solución: `(WRITE_ROLES as readonly string[]).includes(role)` en los 7 archivos afectados.

**ERR-E — `SearchResult` pasado a `DocumentCard` que espera `Document` (TYPE_CONTRACT)**

`SearchResult` extiende `Omit<Document, 'checksum'|'metadata'|'ocr_content'>` — omite 3 campos que
`DocumentCard` declara en su prop type `document: Document`. Aunque `DocumentCard` no accede a esos
3 campos en su render, TypeScript los exige en la firma: `TS2739`.

Solución: `doc as unknown as Document` en `SearchPage`. El cast es seguro porque `DocumentCard`
no consume `checksum`, `ocr_content` ni `metadata`.

**ERR-F — `storage_path` inexistente en tipo `Document` — fixture de test desactualizado (TYPE_CONTRACT)**

Un fixture de `hooks.test.ts` contenía `storage_path: 'uploads/test.pdf'`, campo que existía en una
versión anterior del tipo `Document` y fue eliminado. `TS2353` en modo strict.

Solución: eliminar `storage_path` del fixture y alinear con el tipo actual (`folder_name`, `created_by_email`).

**ERR-G — `ocr_content` faltante en fixtures de tests (TYPE_CONTRACT)**

Cuando se añadió `ocr_content: string` al tipo `Document` (feature 2026-06-30), dos archivos de test
no actualizaron su `MOCK_DOCUMENT`. `TS2741: Property 'ocr_content' is missing` en modo strict.

Solución: añadir `ocr_content: ''` al `MOCK_DOCUMENT` en `DocumentDetailPage.test.tsx` y
`DocumentVersionList.test.tsx`.

**Lección transversal:** `npm run build` (usa `tsconfig.app.json`, `strict: true`) y `tsc --noEmit`
(usa `tsconfig.json`, menos restrictivo) pueden dar resultados diferentes. Siempre verificar con
`npm run build` antes de pushear una PR — si solo corre `tsc --noEmit` localmente, los errores de
strict mode solo aparecen en CI.

---

### 2026-06-30 — Bugs y mejoras en workflows
**Bug crítico:** 500 en start-workflow → migración `notifications.0001` no aplicada → `python manage.py migrate notifications` (sin cambios de código).
**Bug NaN:** `DocumentVersionList` calculaba `Math.ceil(undefined/undefined)` cuando backend devuelve `"meta": {}` → desestructuración defensiva con fallback a `1`.
**UX:** Campo UUID manual de documento en `WorkflowExecutionsPage` → reemplazado por `<Select>` con `useDocuments()`.

---

## 2026-06-30 — Feature: subir documentos desde la carpeta
**Mejora UX:** botón "Subir documento" en `FolderBrowserPage` (solo visible en carpetas específicas, no en raíz). Pre-asigna `folder_id` de la carpeta actual. Invalida `['folders']` en `useUploadDocument` para refrescar la lista de documentos de la carpeta.
**Archivos:** `hooks.ts` (invalidación), `FolderBrowserPage.tsx` (botón + dialog).

#### Fix: folder_id incorrecto al navegar entre carpetas
**Bug:** Al subir desde una carpeta vacía, `folder_id` usaba el valor de la carpeta anterior (react-hook-form lee `defaultValues` solo en el mount inicial; el componente no se desmontaba al navegar).
**Fix:** `key={id}` en `<DocumentUploadDropzone>` → React remonta al cambiar de carpeta, reinicializando el form con el `folderId` correcto.
**Commit:** `43e8380`

---

## 2026-06-30 — Fix: exponer `ocr_content` en API y UI (commit 7d34ea8)

`ocr_content` existía en el modelo `Document` (TextField) pero no estaba declarado en
`DocumentSerializer.fields`, por lo que la API no lo devolvía. En consecuencia, la pestaña
"Contenido OCR" de `DocumentDetailPage` había sido eliminada previamente al comprobar que
el campo nunca llegaba al frontend.

**Fix backend:** añadido `ocr_content` a `DocumentSerializer` (read-only).

**Fix frontend:** restaurada la pestaña "Contenido OCR" en `DocumentDetailPage`. Aparece
de forma condicional: solo si `document.ocr_content` tiene texto (documentos sin OCR o con
`ocr_status=skipped` no muestran la pestaña).

**Archivos:** `backend/apps/documents/api/serializers.py`, `frontend/src/shared/types/index.ts`,
`frontend/src/features/documents/pages/DocumentDetailPage.tsx`.

---

## 2026-06-30 — Features: asignación de carpetas y workflow desde documento (commits cc78fa8, d90b01d)

Durante la sesión de testing local se identificaron dos gaps de UX: los documentos podían crearse pero no tenían forma de asignarse a una carpeta después de la subida, y para iniciar un workflow era necesario conocer y escribir el UUID del documento a mano. Se implementaron dos features para corregirlos.

---

### Feature 1 — Asignación de carpetas (commit cc78fa8)

**Problema:** los documentos existían sueltos sin forma de moverlos a una carpeta tras la creación. Las carpetas aparecían vacías aunque hubiera documentos en el sistema.

**Solución backend:**
- Nuevo endpoint `GET /api/v1/folders/tree/` — devuelve todas las carpetas de la organización en lista plana, sin recursión, para poblar selectores de UI.
- `PATCH /api/v1/documents/{id}/` ahora acepta `folder_id` (UUID o `null` para "sin carpeta"). El service usa un sentinel `FOLDER_UNSET = object()` para distinguir "campo ausente del PATCH" de "usuario quiere mover a raíz (null)". Sin sentinel, cualquier PATCH sin `folder_id` movería el documento a raíz.

**Solución frontend:** selector de carpetas en la pestaña "Editar metadata" de `DocumentDetailPage`. Carga opciones desde `GET /folders/tree/` y envía el UUID elegido (o `null`) en el PATCH.

**Archivos:** `document_service.py`, `documents/api/serializers.py`, `documents/api/views.py`, `documents/api/urls.py`; `documents/api.ts`, `documents/hooks.ts`, `documents/validation.ts`, `documents/components/DocumentMetadataForm.tsx`, `documents/pages/DocumentDetailPage.tsx`.

---

### Feature 2 — Iniciar workflow desde el documento (commit d90b01d)

**Problema:** iniciar un workflow requería conocer el UUID del documento e introducirlo a mano en el formulario de nueva ejecución. El botón aparecía aunque no hubiera plantillas disponibles en la organización.

**Solución backend:**
- Nuevo endpoint `POST /api/v1/documents/{id}/start-workflow/` — el `document_id` va en la URL. El body solo requiere `template_id`. Valida ejecución activa existente y devuelve 409 `WORKFLOW_ALREADY_ACTIVE` si la hay. Vive en `documents/api/views.py` (no en workflows) por convención: cada `urls.py` importa solo views de su propia app; la dependencia cruzada `documents.views → workflows.services` es legítima en la capa de orquestación.

**Solución frontend:**
- Botón "Iniciar workflow" en el header de `DocumentDetailPage`. Solo se muestra si `canWrite && plantillas_activas.length > 0`.
- Nuevo componente `StartWorkflowDialog`: selector de plantilla + confirmación. Al confirmar, navega automáticamente a la página de la ejecución creada.

**Archivos:** `workflows/api/serializers.py`; `workflows/api.ts`, `workflows/hooks.ts`, `workflows/components/StartWorkflowDialog.tsx` (nuevo).

---

## 2026-06-30 — Sesión de testing local: type mismatch en workflows y documentos (commit 1aa4f04)

Sesión de prueba manual del frontend contra el backend real. Se detectaron y corrigieron 2 bugs
de tipos TypeScript y se añadieron 5 tests de regresión.

**Bug A — WorkflowExecution: crash al acceder a campos de objetos anidados.**
Los tipos `WorkflowExecution` y `WorkflowStepLog` en `shared/types/index.ts` declaraban
objetos anidados (`template: { id, name }`, `started_by: { id, email }`, `step: { id, name, order }`, etc.)
pero el API devuelve campos planos con sufijo (`template_name`, `started_by_email`, `step_name`,
`step_order`, `performed_by_email`). Afectó a `WorkflowExecutionsPage`, `WorkflowExecutionDetailPage`
y `WorkflowStepLogTimeline`. Fix: actualizar tipos + todos los accesos en los tres componentes.

**Bug B — DocumentDetailPage: crash en panel de carpeta + pestaña OCR muerta.**
El tipo `Document` declaraba `folder: { id, name }` pero el API devuelve UUID string + `folder_name`
separado → crash `Cannot read properties of undefined (reading 'id')` al abrir cualquier documento
con carpeta. Además, la pestaña "Contenido OCR" nunca se renderizaba: `ocr_content` no existe en
el serializer del backend. Fix: `document.folder.id` → `document.folder`, `document.folder.name` →
`document.folder_name`; eliminada la pestaña OCR muerta.

**Tests de regresión añadidos (5 tests, todos verdes):**
- `WorkflowTemplateForm.regression.test.tsx` — montaje sin crash cuando `<label>` sustituye `<FormLabel>` fuera de `<FormField>`
- `DocumentDetailPage.test.tsx` (2) — montaje sin crash + campo plano `created_by_email`
- `DocumentVersionList.test.tsx` (2) — mismo patrón para `version.created_by_email`

Suite total: **169/169 tests frontend** en verde.

---

## 2026-06-30 — Corrección de 3 bugs críticos en la capa de autenticación frontend

Durante una sesión de prueba local del flujo de login se detectó que el frontend se quedaba
bloqueado en la pantalla de login a pesar de que el backend respondía correctamente. Los logs
del backend mostraban el patrón:

```
POST /api/v1/auth/login/ → 200
GET  /api/v1/auth/me/    → 401
POST /api/v1/auth/refresh/ → 400
```

Se realizó un code review completo de la capa de comunicación frontend↔backend (APIs, hooks,
interceptores, manejo de tokens). Se encontraron **3 bugs críticos** de la misma raíz y 2 medios
+ 3 menores que ya estaban correctos.

---

### Causa raíz común

El endpoint `/api/v1/auth/refresh/` (como todos los endpoints del proyecto) devuelve el payload
envuelto en el envelope estándar `{data: {access, refresh}, meta: {}}`. Solo `getMe()` y
`login()` (este último ya corregido en la sesión anterior) usaban el helper `unwrap()`. Todos
los demás puntos de consumo del endpoint de refresh usaban `response.data` crudo, recibiendo el
envelope completo en lugar del payload, con lo que `access` resultaba `undefined`.

---

### Bug crítico 1 — `api.ts` — `refreshToken()` no desenvolvía el envelope

**Síntoma:** La sesión nunca se restauraba tras una recarga de página. El bootstrap de
`ProtectedRoute` fallaba silenciosamente: llamaba a `refreshToken()`, recibía `undefined` como
`access` y abortaba el flujo.

**Código roto:**
```typescript
const response = await apiClient.post<RefreshResponse>('/auth/refresh/', { refresh })
return response.data  // devolvía {data: {...}, meta: {}} en vez de {access, refresh}
```

**Fix:** tipar la respuesta como `Envelope<RefreshResponse>` y pasar por `unwrap()`:
```typescript
const response = await apiClient.post<Envelope<RefreshResponse>>('/auth/refresh/', { refresh })
return unwrap(response)
```

---

### Bug crítico 2 — `api-client.ts` — Interceptor de 401 no desenvolvía el envelope

**Síntoma:** Cualquier request cuyo access token expirara durante la sesión (sin recarga de
página) entraba en un bucle de 401: el interceptor hacía el refresh silencioso, recibía
`envelope.data.access` como `undefined`, actualizaba el store con `undefined`, la request
reintentada volvía a fallar con 401, hasta que el flag `_retry` cortaba el ciclo y se
ejecutaba el logout.

**Código roto:**
```typescript
const { data } = await axios.post<{ access: string }>(`${baseURL}/auth/refresh/`, { refresh: refreshToken })
const newAccess = data.access  // undefined — data era el envelope completo
```

**Fix:** tipar correctamente y navegar hasta el payload interno:
```typescript
const { data: envelope } = await axios.post<{
  data: { access: string; refresh: string }
}>(`${baseURL}/auth/refresh/`, { refresh: refreshToken })
const newAccess = envelope.data.access
const newRefresh = envelope.data.refresh
useAuthStore.getState().setAccessToken(newAccess)
if (newRefresh) localStorage.setItem('refreshToken', newRefresh)
```

---

### Bug crítico 3 — Refresh token rotado nunca persistido

**Contexto:** El backend tiene `ROTATE_REFRESH_TOKENS=True` + `BLACKLIST_AFTER_ROTATION=True`
(SimpleJWT). Cada respuesta de `/auth/refresh/` incluye un **nuevo** refresh token y blacklistea
el anterior.

**Síntoma:** Los primeros 60 minutos (ventana del access token en dev) todo funcionaba. Pasado
ese tiempo, el interceptor intentaba usar el refresh token original (ya blacklisteado) → el
backend devolvía 400/401 → logout involuntario. Imposible de reproducir en sesiones cortas; se
manifestaba solo en uso prolongado.

**Archivos afectados y fix:**

- `api-client.ts` — ya corregido como parte del Bug 2: el interceptor ahora persiste
  `envelope.data.refresh` en `localStorage`.
- `ProtectedRoute.tsx` — el bootstrap de sesión tampoco guardaba el nuevo refresh:
  ```typescript
  // ANTES
  refreshToken(storedRefresh).then(async ({ access }) => {
      setAccessToken(access)
      // ← el nuevo refresh token se descartaba silenciosamente

  // DESPUÉS
  refreshToken(storedRefresh).then(async ({ access, refresh: newRefresh }) => {
      setAccessToken(access)
      localStorage.setItem('refreshToken', newRefresh)
  ```
- `types.ts` — `RefreshResponse` solo tenía `access: string`. Se añadió `refresh: string`.

---

### Tests actualizados

Los fixtures MSW en la suite de tests mockeaban `/auth/refresh/` con el formato plano
`{ access: '...' }` (sin envelope), lo que hacía que los tests pasaran aunque el código de
producción estuviera roto frente al backend real. Se actualizaron al formato envelope correcto:

- `frontend/src/features/auth/__tests__/interceptor.test.ts` — 5 handlers de
  `http.post('/auth/refresh/')`.
- `frontend/src/shared/components/__tests__/ProtectedRoute.test.tsx` — fixture
  `REFRESH_RESPONSE`.

**Resultado:** 164/164 tests frontend pasando. `tsc --noEmit` sin errores.

---

### Lo que el reviewer confirmó como ya correcto

- Cola de refresh (`isRefreshing + failedQueue`): N requests con 401 simultáneos →
  exactamente 1 refresh, el resto espera en cola y se reintenta con el nuevo token.
- `parseApiError`: maneja status 0 (red error), 4xx y 5xx correctamente.
- Logout: best-effort; la sesión local se limpia siempre, independientemente de si el
  backend acepta el token de blacklist.
- `CORS_ALLOW_ALL_ORIGINS=True` en dev: intencional y documentado.
- Endpoints de documents, workflows y audit: todos usan `unwrap()` correctamente.

---

### Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `frontend/src/features/auth/types.ts` | `RefreshResponse` añade campo `refresh: string` |
| `frontend/src/features/auth/api.ts` | `refreshToken()` usa `Envelope<RefreshResponse>` + `unwrap()` |
| `frontend/src/lib/api-client.ts` | Interceptor 401 desenvuelve envelope; persiste nuevo refresh |
| `frontend/src/shared/components/ProtectedRoute.tsx` | Bootstrap persiste `newRefresh` en `localStorage` |
| `frontend/src/features/auth/__tests__/interceptor.test.ts` | 5 fixtures MSW actualizados al formato envelope |
| `frontend/src/shared/components/__tests__/ProtectedRoute.test.tsx` | Fixture `REFRESH_RESPONSE` actualizado |

---

## 2026-06-30 — Bug en WorkflowTemplateForm y pruebas de roles/permisos

Dos hallazgos de la sesión de prueba local: un crash al abrir el formulario de creación de
workflow templates, y una verificación manual completa del RBAC con tres cuentas reales.

---

### Bug: `<FormLabel>` fuera de `<FormField>` crasheaba la página de creación de template

**Síntoma:** Al navegar a `/workflows/templates` y hacer clic en "Crear template", la página
crasheaba con "Unexpected Application Error! useFormField should be used within \<FormField\>".
React Router capturaba el error en su `RenderErrorBoundary`.

**Mensaje de error clave:**
```
Error: useFormField should be used within <FormField>
    at useFormField (form.tsx:35:9)
    at form.tsx:80:32   ← FormLabel llamando useFormField internamente
```
Stack trace apuntaba a `WorkflowTemplateForm.tsx:37:40` → `FormLabel` en `form.tsx:78:53`.

**Causa raíz:** `WorkflowTemplateForm.tsx` línea 134 usaba un `<FormLabel>` de shadcn/ui como
título visual de la sección de pasos, fuera de cualquier `<FormField>`:

```tsx
// INCORRECTO — <FormLabel> fuera de <FormField>
<FormLabel className="text-sm font-medium">Pasos del workflow</FormLabel>
```

El componente `FormLabel` de shadcn/ui llama internamente a `useFormField()`, que lee un
contexto React (`FormFieldContext`) que solo existe dentro del render prop de
`<FormField name="..." render={...}>`. Fuera de ese contexto, el hook lanza.

**Fix:**
```tsx
// CORRECTO — label HTML estándar para títulos visuales de sección
<label className="text-sm font-medium">Pasos del workflow</label>
```

**Regla resultante:** `<FormLabel>` de shadcn solo se usa dentro de `<FormField render={...}>`.
Para cualquier título o etiqueta visual fuera de un campo de formulario → `<label>`, `<span>`
o `<p>` HTML puro.

**Archivo:** `frontend/src/features/workflows/components/WorkflowTemplateForm.tsx` línea 134.

---

### Pruebas de roles y permisos — verificación manual del RBAC

Se levantó la infraestructura completa (`docker compose up -d`). Health check confirmado:

```json
{"status":"ok","components":{"database":"ok","redis":"ok","storage":"ok"}}
```

Backend en `localhost:8000`, frontend Vite en `localhost:5173`. Se probaron tres cuentas.

**`basilyandree@gmail.com` — rol `super_admin`, `organization = None`**

| Endpoint | Resultado | ¿Esperado? |
|----------|-----------|------------|
| POST `/auth/login/` | ✅ 200 | ✓ |
| GET `/auth/me/` | ✅ 200 | ✓ |
| GET `/documents/` | ❌ 403 `PERMISSION_DENIED` | ✓ correcto |
| GET `/folders/` | ❌ 403 `PERMISSION_DENIED` | ✓ correcto |

El `super_admin` recibe 403 en los endpoints de dominio porque su usuario tiene
`organization=None`. `IsOrganizationMember` verifica `user.organization == request.organization`;
con `organization=None` la verificación falla. Comportamiento correcto y esperado: el
`super_admin` no es un usuario de tenant — accede al sistema vía Django Admin o endpoints de
plataforma propios, no por la API de negocio.

**`admin@acme.com` — rol `org_admin`, org: `Acme Corp`**

| Endpoint | Resultado | ¿Esperado? |
|----------|-----------|------------|
| POST `/auth/login/` | ✅ 200 | ✓ |
| GET `/documents/?page=1&page_size=6` | ✅ 200 (0 docs) | ✓ |
| GET `/folders/` | ✅ 200 (1 carpeta: "Carpeta de Acme") | ✓ |
| GET `/workflows/templates/` | ✅ 200 | ✓ |
| GET `/audit-logs/` | ✅ 200 | ✓ |
| GET `/search/?q=acme` | ✅ 200 | ✓ |
| POST `/workflows/templates/` | ✅ 201 (puede crear) | ✓ |

**`editor@acme.com` — rol `editor`, org: `Acme Corp`**

| Endpoint | Resultado | ¿Esperado? |
|----------|-----------|------------|
| POST `/auth/login/` | ✅ 200 | ✓ |
| GET `/documents/?page=1&page_size=6` | ✅ 200 (0 docs) | ✓ |
| GET `/folders/` | ✅ 200 (1 carpeta) | ✓ |
| POST `/folders/` | ✅ 201 (creó "Carpeta editor test") | ✓ |
| GET `/workflows/templates/` | ✅ 200 | ✓ |
| GET `/audit-logs/` | ❌ 403 `PERMISSION_DENIED` | ✓ correcto (solo auditor/org_admin) |
| POST `/workflows/templates/` | ❌ 403 `PERMISSION_DENIED` | ✓ correcto (solo org_admin/supervisor) |
| GET `/search/?q=acme` | ✅ 200 | ✓ |

**Conclusión:** el RBAC funciona correctamente en todos los casos verificados. Los rechazos
403 son legítimos — cada uno corresponde a una restricción de rol correctamente aplicada por
el backend, no a errores de la aplicación.

---

## 2026-06-30 — Bug: tipos TypeScript desincronizados con la API → crash en DocumentDetailPage

Al hacer clic en un documento recién subido, la página crasheaba con:

```
TypeError: Cannot read properties of undefined (reading 'email')
    at DocumentDetailPage (DocumentDetailPage.tsx:367:92)
```

---

### Cómo leer el error

El mensaje `Cannot read properties of undefined (reading 'email')` significa: se intentó hacer
`.email` sobre `undefined`. La línea 367 de `DocumentDetailPage.tsx` hacía
`document.created_by.email`, pero `document.created_by` era `undefined` porque el backend no
devuelve ese campo.

---

### Causa raíz

Los tipos TypeScript del frontend modelaban los campos de autor/propietario como objetos
anidados, pero el backend los devuelve como strings planos:

| Tipo | Campo en el tipo TS (incorrecto) | Campo real del backend (correcto) |
|------|----------------------------------|-----------------------------------|
| `Document` | `created_by: { id: string; email: string }` | `created_by_email: string` |
| `DocumentVersion` | `created_by: { id: string; email: string }` | `created_by_email: string` |
| `Folder` | `owner: { id: string; email: string }` | `owner_email: string` |

Además `Document` tenía campos inexistentes en la API (`storage_path` y `ocr_content`), y
`folder` estaba tipado como `{ id, name } | null` cuando el backend devuelve el UUID como
string o null más un campo separado `folder_name`.

TypeScript no detectó el error porque los componentes usaban el tipo sin anotación explícita
(inferencia desde el hook), y la inferencia resolvía como `any` en algunas rutas.

---

### Fix

`frontend/src/shared/types/index.ts` — interfaz `Document` corregida:

```typescript
// ANTES (incorrecto)
export interface Document {
  folder: { id: string; name: string } | null
  created_by: { id: string; email: string }
  storage_path: string
  ocr_content: string
  // ...
}

// DESPUÉS (correcto — refleja la respuesta real del backend)
export interface Document {
  folder: string | null
  folder_name: string | null
  created_by_email: string
  // storage_path y ocr_content eliminados (no existen en la API)
  // ...
}
```

`DocumentDetailPage.tsx` y `DocumentVersionList.tsx`:

```tsx
// ANTES
document.created_by.email
version.created_by.email

// DESPUÉS
document.created_by_email
version.created_by_email
```

### Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `frontend/src/shared/types/index.ts` | Interfaces `Document`, `DocumentVersion`, `Folder` corregidas para reflejar respuesta real del backend |
| `frontend/src/features/documents/pages/DocumentDetailPage.tsx` | Acceso via `created_by_email`, `folder`/`folder_name` correctos |
| `frontend/src/features/documents/components/DocumentVersionList.tsx` | Acceso via `created_by_email` |

---

### Lección

Cuando TypeScript pasa limpio pero hay crashes en runtime con `Cannot read properties of
undefined`, el problema suele ser que el tipo estaba declarado incorrectamente (no como `any`,
sino con una forma que no coincide con los datos reales). La causa más frecuente: el tipo TS se
escribe antes de verificar contra la respuesta real del backend. Verificar siempre con
`curl` o la pestaña Network de DevTools antes de tipar una respuesta de API.

---

## 2026-06-29 — Fase 5.5 completada: Deploy en VPS (Docker + Nginx + Gunicorn)

Se implementó la infraestructura completa de producción. El proyecto ahora puede desplegarse
en cualquier VPS con Docker instalado ejecutando un único script idempotente.

---

### Dockerfiles multi-stage

**`backend/Dockerfile`** — dos stages. El stage `builder` instala todas las dependencias Python
en un entorno aislado. El stage `runtime` parte de una imagen limpia, añade las dependencias de
sistema necesarias para OCR y validación de archivos (`libmagic1 tesseract-ocr tesseract-ocr-spa
poppler-utils`), ejecuta `collectstatic` como `root` durante el build (evita el `PermissionError`
que ocurría al intentarlo como usuario no-root en runtime), transfiere ownership a `appuser` vía
`chown` y ejecuta Gunicorn como usuario no-root. Variables `PYTHONUNBUFFERED=1` y
`PYTHONDONTWRITEBYTECODE=1` para logging en tiempo real y sin bytecode en la imagen.

**`frontend/Dockerfile`** — stage `build` con Node 20 Alpine ejecuta `npm run build` con
`VITE_API_BASE_URL=/api/v1` (fix crítico: sin esto el bundle hardcodeaba `localhost:5173` en
todas las llamadas a la API). Stage `serve` con `nginx:stable-alpine` sirve el `/dist` resultante.

### docker-compose.prod.yml — 8 servicios

Servicios: `migrate` (one-shot), `web` (Gunicorn), `worker` (Celery), `beat` (Celery beat),
`nginx`, `postgres:16-alpine`, `redis:7-alpine`, `minio`. Tres volúmenes nombrados:
`postgres_data`, `redis_data`, `minio_data`.

El servicio `migrate` tiene `restart: no` y los demás servicios de aplicación declaran
`depends_on: migrate: condition: service_completed_successfully` — garantiza que las migraciones
corren exactamente una vez antes de que arranque el resto. Las credenciales de postgres y minio
se pasan vía `env_file` con los nombres nativos de cada imagen (`POSTGRES_PASSWORD`,
`MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD`) en lugar de interpolación `${...}` — esto evita que
Docker Compose resuelva variables vacías silenciosamente.

### Nginx (`nginx/nginx.conf`)

- Bloque HTTP: redirige todo a HTTPS con 301 permanente.
- Bloque HTTPS: TLS 1.2/1.3 con certificado self-signed (generado por `deploy.sh` si no existe).
- `try_files $uri $uri/ /index.html` — fallback SPA para que React Router funcione correctamente.
- Proxy de `/api/`, `/admin/` y `/static/` hacia `web:8000`.
- `client_max_body_size 50m` — fix crítico: el default de 1MB bloqueaba todos los uploads de
  documentos (MAX_UPLOAD_SIZE es 50MB según CLAUDE.md §3).

### production.py

Se añadieron `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` (necesario para que
Django detecte HTTPS detrás de Nginx) y `CONN_MAX_AGE = 60` (reutilización de conexiones PG,
reduce latencia en requests frecuentes).

### Scripts de operaciones

**`scripts/deploy.sh`** — idempotente: `git pull`, genera cert self-signed si no existe,
`docker compose -f docker-compose.prod.yml build`, `up -d`. El `run --rm migrate` duplicado
fue eliminado; el compose lo maneja via `depends_on`.

**`scripts/backup_db.sh`** — carga credenciales desde `.env.production`, ejecuta `pg_dump`
comprimido, escritura atómica (escribe a `.tmp` y hace rename al final para evitar dumps
parciales en caso de corte), retención de 7 días (borra dumps más antiguos automáticamente).

### deploy.yml actualizado

`.github/workflows/deploy.yml` — ya no es un scaffold vacío. Trigger `workflow_dispatch` +
`push: branches: [main]`. Usa `appleboy/ssh-action@v1.2.0` con secrets `VPS_HOST`, `VPS_USER`,
`VPS_SSH_KEY` para conectarse al servidor y ejecutar `bash scripts/deploy.sh` de forma remota.

### docs/deploy-guide.md — guía educativa completa

Documento nuevo de 10 secciones orientado a quien nunca deployó una app en producción:
runserver vs producción, arquitectura del stack, Dockerfiles multi-stage explicados, servicios
del compose, configuración Nginx, variables de entorno de producción, SSL (self-signed vs
Let's Encrypt), cómo usar los scripts, diagnóstico de problemas comunes, y glosario de términos.

### Fixes post-revisión (4 críticos + 3 medios + 2 menores)

| Severidad | Fix |
|-----------|-----|
| Crítico | `VITE_API_BASE_URL=/api/v1` en Dockerfile frontend |
| Crítico | Credenciales postgres/minio: eliminada interpolación `${...}`, usando `env_file` con nombres nativos |
| Crítico | `collectstatic` como root en build-time + `chown` → resuelve `PermissionError` de appuser |
| Crítico | `client_max_body_size 50m` en nginx.conf (default 1MB bloqueaba uploads) |
| Medio | `staticfiles/` horneado en imagen (resuelve falta de volumen compartido entre migrate/web) |
| Medio | `deploy.sh`: eliminado `run --rm migrate` duplicado |
| Medio | `backup_db.sh`: carga `.env.production`, escritura atómica con `.tmp` |
| Menor | `PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1` en Dockerfile |
| Menor | `beat` ahora depende de `postgres: service_healthy` |

### Pendientes para completar el deploy real

- Provisionar VPS Ubuntu 22.04 + Docker.
- Configurar secrets en GitHub: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`.
- Ejecutar `bash scripts/deploy.sh` en el servidor por primera vez.
- Activar branch protection en `main` tras primer run verde del workflow de deploy.

---

## 2026-06-29 — Fase 5.4 completada: CI/CD con GitHub Actions

Se implementó el pipeline de integración continua completo. Dos jobs paralelos (backend y
frontend) se ejecutan en cada PR y push a `main`/`develop`.

---

### Pipeline de backend (`ci.yml`)

El job levanta PostgreSQL 16 y Redis 7 como **runner services** del propio runner de GitHub
Actions — sin mocks, la misma base de datos que en producción. Antes de correr la suite
instala las dependencias apt necesarias para OCR y procesamiento de archivos
(`libmagic1 tesseract-ocr tesseract-ocr-spa poppler-utils`).

El gate de calidad aplica en orden: lint (black/isort/flake8) → tests con
`pytest -m "not integration"` (los tests de integración que requieren MinIO real se excluyen
en CI; no hay servidor MinIO en el runner) → upload a Codecov. La cobertura mínima del 95%
se configura en `pyproject.toml` vía `--cov-fail-under=95` en `addopts`, de modo que el gate
aplica tanto en CI como al correr pytest localmente.

### Pipeline de frontend (`ci.yml`)

El job corre eslint, `tsc --noEmit` (se añadió el script `typecheck` a `package.json`) y
`vitest run`. El paso final ejecuta `vite build` — si hay errores de tipos que solo aparecen
en el bundle, el job falla aquí.

### Scaffold de deploy (`deploy.yml`)

Se creó `.github/workflows/deploy.yml` con trigger `workflow_dispatch` como placeholder para
la Fase 5.5 (deploy en VPS). No ejecuta pasos reales todavía.

### Fixes post-revisión aplicados

Tras una revisión del pipeline antes de mergearlo se corrigieron cuatro puntos:

1. **Crítico:** `pytest -m "not integration"` añadido — sin esto los tests de integración de
   MinIO habrían roto el job desde el primer run porque no hay servidor MinIO en CI.
2. **Medio:** push a `main` añadido a los triggers — sin esto el badge del README mostraba
   "no status" porque el workflow nunca corría en `main`.
3. **Medio:** `--cov` pelado eliminado del comando pytest (ya estaba en addopts como
   `--cov=apps`; el argumento suelto medía el árbol completo y diluía el porcentaje real).
4. **Menor:** tabla de fases y métricas del README actualizadas (~526 tests / 95%).

### Pendientes anotados

- **Codecov token** (`CODECOV_TOKEN`): necesario para repos privados. Por ahora
  `fail_ci_if_error: false` evita que el upload roto rompa el job.
- **Correr suite completa local** con `pytest -m "not integration"` para confirmar el gate
  del 95% (Docker estaba apagado durante la sesión).
- **Branch protection en `main`**: configurar en GitHub Settings tras el primer run verde.

---

## 2026-06-29 — Post-auditoría Fase 5.3: 6 hallazgos corregidos

Después de completar la Fase 5.3 (frontend de workflows, auditoría y análisis IA), se realizó
una sesión de revisión del código producido buscando bugs, inconsistencias y edge cases antes
de avanzar a la Fase 5.4. Se encontraron 6 hallazgos (3 Medio + 3 Menor) y se corrigieron todos
en la misma sesión.

---

### MEDIO #1 — Filtro de auditoría enviaba email pero el backend esperaba UUID

**Dónde:** `frontend/src/features/audit/components/AuditLogFilters.tsx`, `backend/apps/audit/api/filters.py`

**Qué pasaba:** `AuditLogFilters.tsx` enviaba el email del usuario como query param `user`, pero
`AuditLogFilter` en el backend declaraba ese campo como `UUIDFilter(field_name="user_id")`. Un
email no es un UUID válido: `django-filter` descartaba el valor silenciosamente → la tabla
aparecía vacía sin ningún mensaje de error al usuario.

**La corrección:** se añadió `user_email = CharFilter(field_name="user__email", lookup_expr="iexact")`
al `AuditLogFilter` del backend. En el frontend se renombró el campo `user` → `user_email`
en el formulario, la llamada a la API y los hooks.

**Archivos:** `backend/apps/audit/api/filters.py`, `frontend/src/features/audit/components/AuditLogFilters.tsx`, `frontend/src/features/audit/api.ts`

---

### MEDIO #2 — Filtro "Hasta" excluía todos los eventos del día seleccionado

**Dónde:** `frontend/src/features/audit/components/AuditLogFilters.tsx`

**Qué pasaba:** `new Date("2026-06-29").toISOString()` produce `"2026-06-29T00:00:00.000Z"`.
Con `lookup_expr="lte"` sobre `created_at`, el filtro solo devolvía registros hasta medianoche
UTC del día seleccionado → prácticamente ningún evento del propio día aparecía. El problema
se amplificaba para usuarios en zonas horarias fuera de UTC, produciendo un corrimiento de
día completo.

**La corrección:** para `created_before` se aplica `endOfDay(parseISO(value)).toISOString()`
de `date-fns` (ya instalado en el proyecto) antes de serializar el valor. `created_after` queda
sin cambios: empezar desde el inicio del día es el comportamiento esperado.

**Archivos:** `frontend/src/features/audit/components/AuditLogFilters.tsx`

---

### MEDIO #3 — Polling del análisis IA no terminaba si la tarea Celery fallaba definitivamente

**Dónde:** `backend/apps/documents/tasks/document_tasks.py`, `frontend/src/features/documents/hooks.ts`, `frontend/src/features/documents/pages/DocumentDetailPage.tsx`

**Qué pasaba:** al solicitar análisis, `setPollForAi(true)` iniciaba un refetch de TanStack
Query cada 3 segundos mientras `pollForAi && !metadata?.ai_analysis`. Si la tarea Celery agotaba
sus reintentos y fallaba permanentemente, el backend nunca escribía nada en `metadata` → la
condición de parada nunca se cumplía → spinner eterno y requests infinitos mientras el tab
permaneciera abierto.

**La corrección (backend):** se escribe un marcador de fallo en el handler de error de
`analyze_document` antes de re-lanzar la excepción: `metadata["ai_analysis"] = {"status": "failed", "error": "..."}`.
Se extrajo el helper `_write_ai_failure_marker(document, document_id)` para mantener la
función principal legible.

**La corrección (frontend):** la condición de polling ahora para cuando `aiAnalysis` existe,
sea éxito o fallo. En `DocumentDetailPage.tsx` se detecta `status === 'failed'` y se muestra
el error con un botón "Reintentar". El polling se reactiva si el usuario reintenta y hay una
nueva tarea en curso.

**Archivos:** `backend/apps/documents/tasks/document_tasks.py`, `frontend/src/features/documents/hooks.ts`, `frontend/src/features/documents/pages/DocumentDetailPage.tsx`

---

### MENOR #4 — `WorkflowStepLogTimeline` reventaba ante una acción desconocida

**Dónde:** `frontend/src/features/workflows/components/WorkflowStepLogTimeline.tsx`

**Qué pasaba:** `ACTION_CONFIG[log.action]` sin fallback: si el backend introduce en el futuro
un nuevo valor de `action`, `config` es `undefined` y el intento de acceder a sus propiedades
tumba toda la línea de tiempo. `AuditLogTable.tsx` ya tenía este fallback desde 5.3;
`WorkflowStepLogTimeline.tsx` no lo tenía.

**La corrección:** añadido fallback explícito `?? { label: action, Icon: Circle, className: 'text-gray-500 bg-gray-50' }`.

**Archivos:** `frontend/src/features/workflows/components/WorkflowStepLogTimeline.tsx`

---

### MENOR #5 — `WorkflowTemplateForm` podía entrar en loop de reset

**Dónde:** `frontend/src/features/workflows/components/WorkflowTemplateForm.tsx`

**Qué pasaba:** el `useEffect` que llama `form.reset(defaultValues)` tenía `defaultValues`
(prop) como dependencia. Si un componente padre futuro pasara un objeto inline
`defaultValues={{ ... }}`, la referencia cambiaría en cada render del padre → `form.reset`
en cada render → pérdida del input del usuario mientras escribe.

**La corrección:** estabilizado con `useRef(defaultValues)` para capturar el valor inicial
una sola vez y no reaccionar a cambios de referencia subsiguientes.

**Archivos:** `frontend/src/features/workflows/components/WorkflowTemplateForm.tsx`

---

### MENOR #6 — La query de auditoría se disparaba aunque el usuario no tuviera el rol

**Dónde:** `frontend/src/features/audit/hooks.ts`, `frontend/src/features/audit/pages/AuditLogPage.tsx`

**Qué pasaba:** `useAuditLogs` se ejecutaba incondicionalmente antes del chequeo de rol.
El backend devolvía 403 sin fuga de datos, pero era un request innecesario. Con TanStack
Query retrying automáticamente, podía generar varios 403 consecutivos antes de detenerse.

**La corrección:** `useAuditLogs` acepta `options?: { enabled?: boolean }` y pasa el flag
a TanStack Query. En `AuditLogPage` se pasa `enabled: !!role && ALLOWED_ROLES.includes(role)`.

**Archivos:** `frontend/src/features/audit/hooks.ts`, `frontend/src/features/audit/pages/AuditLogPage.tsx`

---

### Métricas post-auditoría

| Métrica | Antes | Después |
|---------|-------|---------|
| Tests frontend (Vitest) | 163 | 164 (+1 nuevo) |
| Tests backend (pytest) | ~526 | ~528 (+2 nuevos, pendientes de correr) |
| TypeScript errors | 0 | 0 |
| black/isort/flake8 | limpio | limpio |

Los 2 tests backend nuevos están en `test_audit_api.py` (filtro por `user_email`) y
`test_document_tasks.py` (verificación del marcador de fallo en `metadata["ai_analysis"]`).
Los tests backend no se ejecutaron en esta sesión (PostgreSQL apagado); quedan pendientes
de correr en la próxima sesión con la infra activa.

**Cobertura backend:** 95% esperada (sin variación por estos cambios).

---

### Nota de deuda técnica

Cuando el usuario presiona "Reintentar" después de un fallo del análisis IA, el marcador
de fallo anterior permanece visible durante 1-2 ciclos de polling hasta que el backend
sobreescriba `metadata["ai_analysis"]` con el resultado de la nueva tarea. Para una UX
más limpia, el endpoint `POST /documents/{id}/analyze/` podría limpiar el campo al recibir
la request — aplazado para no añadir complejidad innecesaria en esta fase.

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

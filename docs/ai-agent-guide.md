# SasVault — Guía de Anti-patrones para Agentes IA

> Este documento lista los errores cometidos realmente durante el desarrollo de SasVault,
> agrupados por patrón, con ejemplos de código incorrecto vs. correcto y explicación de
> por qué ocurren. Destinado a guiar a agentes IA (y desarrolladores) en futuras sesiones.
>
> Fuente: `docs/error-registry.md` + BITACORA.md. Fecha: 2026-07-01 (última actualización: 2026-07-03).

---

## Índice

1. [TYPE_CONTRACT — Tipos TypeScript que no reflejan la respuesta real del backend](#1-type_contract)
2. [REACT_STATE — Comportamientos de React malinterpretados](#2-react_state)
3. [MIGRATION — Migraciones omitidas o incorrectamente ordenadas](#3-migration)
4. [ENVELOPE — Respuestas de API sin desenvolver el wrapper `{data, meta}`](#4-envelope)
5. [TENANT_ISOLATION — Queries sin filtro por organization](#5-tenant_isolation)
6. [RBAC y DEAD_CODE — Permisos duplicados y código nunca usado](#6-rbac-y-dead_code)
7. [SOFT_DELETE — Comportamiento no obvio de `auto_now` y `update_fields`](#7-soft_delete)
8. [ASYNC_CELERY — Race conditions y errores en tareas asíncronas](#8-async_celery)
9. [POLLING — Polling sin cota, sin estado terminal, sin propagación de fallos](#9-polling)
10. [GITIGNORE — Archivos sensibles en el historial de git](#10-gitignore)
11. [Checklist pre-PR](#11-checklist-pre-pr)
12. [CI vs local: configuraciones divergentes](#12-ci-vs-local-configuraciones-divergentes)
13. [TEST_QUALITY — Un test en verde no es sinónimo de un test correcto](#13-test_quality--un-test-en-verde-no-es-sinónimo-de-un-test-correcto)

---

## 1. TYPE_CONTRACT

**Problema:** Los tipos TypeScript del frontend declaran una forma de la respuesta que no corresponde con lo que el serializer Django realmente devuelve.

**Síntoma:** Crash en runtime (`Cannot read properties of undefined`) o datos invisibles (fields que son `undefined` silenciosamente). TypeScript no detecta el error en compilación porque el tipo incorrecto "satisface" el código que lo consume.

**Ejemplo real — incorrecto (ERR-037, ERR-038):**

```typescript
// ❌ INCORRECTO — tipos redactados "por intuición", sin verificar la respuesta real
interface WorkflowExecution {
  id: string;
  template: { id: string; name: string };     // ← API devuelve string plano "template_name"
  started_by: { id: string; email: string };  // ← API devuelve string plano "started_by_email"
  current_step: {
    id: string;
    name: string;                              // ← API devuelve "step_name", "step_order"
    order: number;
  } | null;
}

// En el componente
<span>{execution.template.name}</span>         // ← crash: template es undefined
<span>{execution.started_by.email}</span>      // ← crash: started_by es undefined
```

```typescript
// ✅ CORRECTO — tipos verificados contra la respuesta real del serializer
interface WorkflowExecution {
  id: string;
  template_name: string;
  started_by_email: string;
  step_name: string | null;
  step_order: number | null;
  performed_by_email: string | null;
}

// En el componente
<span>{execution.template_name}</span>
<span>{execution.started_by_email}</span>
```

**Ejemplo real — incorrecto (ERR-048, ERR-047):**

```typescript
// ❌ INCORRECTO — tipo copiado de Document sin verificar el subconjunto real
type SearchResult = Document;

// ❌ INCORRECTO — tipo de entities adivinado como string[]
interface AiAnalysis {
  summary: string;
  category: string;
  entities?: string[];   // ← backend devuelve { dates, amounts, names }
}
```

```typescript
// ✅ CORRECTO
type SearchResult = Omit<Document, 'checksum' | 'metadata' | 'ocr_content'> & {
  rank: number;
};

interface AiAnalysis {
  summary: string;
  category: string;
  entities?: {
    dates: string[];
    amounts: string[];
    names: string[];
  };
}
```

**Por qué ocurre:** El agente escribe el tipo en base a cómo "debería" verse la respuesta (con objetos anidados siguiendo el modelo de Django) sin verificar que los serializers DRF usan `SerializerMethodField` con nombres planos para evitar N+1 queries.

**Cómo evitarlo:**

1. Antes de escribir un tipo TypeScript de respuesta, leer el serializer Django correspondiente en `backend/apps/{app}/api/serializers.py`. El tipo debe coincidir campo a campo con `fields` del serializer.
2. Para campos compuestos (ej: `created_by`), buscar si el serializer usa `SerializerMethodField` — si es así, el nombre del campo en la respuesta es plano (ej: `created_by_email`).
3. La guía autoritativa de todos los tipos de respuesta está en `docs/reference.md` — leerla antes de crear interfaces TypeScript.
4. Los badges y componentes que consumen un campo de un objeto de configuración (`CONFIG[value]`) siempre deben tener fallback: `CONFIG[value] ?? { label: value, className: 'text-gray-500' }`.

---

## 2. REACT_STATE

**Problema:** Comportamientos de React o de sus librerías de estado/formularios que son no obvios y llevan a bugs difíciles de reproducir.

**Síntoma:** Estado desactualizado al navegar entre rutas, formularios que conservan valores de renders anteriores, componentes que se rompen por contexto faltante, estado de autenticación inconsistente al recargar.

### 2.1 react-hook-form: `defaultValues` son inmutables post-mount

**Ejemplo real (ERR-021):**

```tsx
// ❌ INCORRECTO — el formulario conserva el folderId de la primera carpeta visitada
function FolderBrowserPage({ folderId }: { folderId: string }) {
  return (
    // Si FolderBrowserPage no se desmonta al cambiar de carpeta,
    // el formulario no re-inicializa con el nuevo folderId
    <DocumentUploadDropzone defaultFolderId={folderId} />
  );
}
```

```tsx
// ✅ CORRECTO — key fuerza remount del componente cuando cambia la carpeta
function FolderBrowserPage({ folderId }: { folderId: string }) {
  return (
    <DocumentUploadDropzone
      key={folderId}   // ← React desmonta y remonta al cambiar folderId
      defaultFolderId={folderId}
    />
  );
}
```

**Regla:** Si un componente usa `react-hook-form` y recibe una prop que debe cambiar los `defaultValues` al cambiar de entidad, añadir `key={entityId}` en el punto de uso.

### 2.2 Bootstrap de sesión: rehidratación secuencial obligatoria

**Ejemplo real (ERR-015):**

```tsx
// ❌ INCORRECTO — solo restaura el accessToken, no el perfil
useEffect(() => {
  const stored = localStorage.getItem('refreshToken');
  if (stored) {
    refreshToken(stored).then(({ access }) => {
      setAccessToken(access);
      // ← falta: llamar getMe() y setUser()
    });
  }
}, []);

// En el Header: muestra iniciales "?" porque user es undefined
```

```tsx
// ✅ CORRECTO — bootstrap secuencial completo
useEffect(() => {
  const stored = localStorage.getItem('refreshToken');
  if (!stored) { setRestorationAttempted(true); return; }

  refreshToken(stored)
    .then(({ access, refresh }) => {
      setAccessToken(access);
      localStorage.setItem('refreshToken', refresh); // persistir token rotativo
      return getMe();                                // paso 3 obligatorio
    })
    .then((profile) => setUser(profile))
    .catch(() => logout())
    .finally(() => setRestorationAttempted(true));
}, []);
```

**Regla:** El bootstrap de sesión es un flujo de tres pasos: `refreshToken` → `setAccessToken` + `persistRefresh` → `getMe` → `setUser`. Omitir cualquiera deja el estado inconsistente.

**Actualización Fase 6.1 (2026-07-03):** el ejemplo de arriba refleja el esquema anterior a 6.1
(`localStorage.getItem('refreshToken')`). Desde 6.1 el refresh token vive en una cookie `HttpOnly`
invisible a JS — ya no hay nada que leer de `localStorage` ni que persistir manualmente
(`persistRefresh` desaparece del flujo). El bootstrap ahora es: `refreshToken()` (sin argumento,
el navegador adjunta la cookie solo) → `setAccessToken` → `getMe()` → `setUser`; si no hay cookie
válida, `refreshToken()` rechaza y el `.catch()` hace `logout()`. Ver `frontend/src/shared/components/ProtectedRoute.tsx` y decisión #41 en `CLAUDE.md` §17. La lección de fondo (bootstrap secuencial de 3 pasos, nunca solo `setAccessToken`) sigue vigente.

### 2.3 `FormLabel` de shadcn/ui requiere contexto de `FormField`

**Ejemplo real (ERR-045):**

```tsx
// ❌ INCORRECTO — FormLabel llama useFormField() internamente
<section>
  <FormLabel>Pasos del workflow</FormLabel>  {/* crash: contexto FormFieldContext ausente */}
  {fields.map(...)}
</section>
```

```tsx
// ✅ CORRECTO — label HTML para títulos fuera de campos de formulario
<section>
  <label className="text-sm font-medium">Pasos del workflow</label>
  {fields.map(...)}
</section>
```

### 2.4 `useEffect` con objetos inline crea loops de render

**Ejemplo real (ERR-026):**

```tsx
// ❌ INCORRECTO — si defaultValues es un objeto inline en el padre,
// cada render del padre crea una nueva referencia → loop infinito
useEffect(() => {
  form.reset(defaultValues);
}, [defaultValues]);  // ← nueva referencia cada vez
```

```tsx
// ✅ CORRECTO — capturar el valor inicial con useRef
const initialValues = useRef(defaultValues);
useEffect(() => {
  form.reset(initialValues.current);
}, []); // ← sin dependencias: solo al mount
```

---

## 3. MIGRATION

**Problema:** Migraciones no aplicadas al entorno de desarrollo, o migraciones con bugs que no se detectan hasta producción.

**Síntoma:** `OperationalError: table does not exist` al llamar endpoints que usan una app nueva. Tests que pasan (la DB de test se recrea automáticamente) pero el entorno de dev falla.

**Ejemplo real (ERR-043):**

```
POST /api/v1/documents/{id}/start-workflow/
→ 500 Internal Server Error
→ django.db.utils.OperationalError: no such table: notifications_notification
```

**Por qué ocurre:** Los tests de pytest recrean la DB de test y aplican todas las migraciones en cada run. El entorno de desarrollo usa la DB persistente del Docker Compose, que requiere `manage.py migrate` manual tras añadir una nueva app.

**Cómo evitarlo:**

1. Al añadir una nueva app a `INSTALLED_APPS` o crear un modelo nuevo, ejecutar siempre `python manage.py migrate` en el entorno de desarrollo.
2. La secuencia correcta al implementar una nueva app es: `INSTALLED_APPS` → `makemigrations` → revisar la migración generada → `migrate` → arrancar el servidor.
3. Revisar la migración generada ANTES de aplicarla — buscar operaciones destructivas o migraciones que tocan tablas grandes sin `RunSQL` incremental.

**Ejemplo real (ERR-002) — migración correctiva por campo faltante:**

```python
# ❌ INCORRECTO — añadir db_index modificando la migración original ya aplicada
# apps/core/migrations/0001_initial.py  ← NUNCA modificar migraciones ya aplicadas

# ✅ CORRECTO — crear migración nueva
python manage.py makemigrations core --name add_deleted_at_index
# → 0002_add_deleted_at_index.py
```

**Regla:** Nunca modificar una migración ya aplicada. Siempre crear una migración correctiva nueva.

---

## 4. ENVELOPE

**Problema:** El cliente HTTP del frontend no desarrolla el wrapper `{data: {...}, meta: {...}}` que envuelve TODAS las respuestas de la API de SasVault.

**Síntoma:** Campos que son `undefined` silenciosamente. El interceptor de refresh funciona en tests pero falla en producción. El access token actualizado es siempre `undefined`.

**El contrato de la API (innegociable):**

```json
// Todas las respuestas exitosas tienen esta forma
{
  "data": { ... },    // ← el payload real está aquí
  "meta": {}
}

// Las listas tienen meta con paginación
{
  "data": [ ... ],
  "meta": { "count": 100, "page": 1, "page_size": 20, "next": "...", "previous": null }
}
```

**Ejemplo real — incorrecto (ERR-039, ERR-040):**

```typescript
// ❌ INCORRECTO — accede a response.data sin desenvolver el envelope
async function refreshToken(token: string) {
  const response = await apiClient.post('/auth/refresh/', { refresh: token });
  return response.data;  // ← response.data es {data: {access, refresh}, meta: {}}
  // access es undefined, refresh es undefined
}

// En el interceptor
const { access } = tokenResponse.data;  // ← devuelve undefined porque data es el envelope
apiClient.setToken(access);             // ← setToken(undefined)
```

```typescript
// ✅ CORRECTO — tipo explícito del envelope y helper unwrap
type Envelope<T> = { data: T; meta: Record<string, unknown> };

function unwrap<T>(response: AxiosResponse<Envelope<T>>): T {
  return response.data.data;
}

async function refreshToken(token: string): Promise<{ access: string; refresh: string }> {
  const response = await apiClient.post<Envelope<{ access: string; refresh: string }>>(
    '/auth/refresh/',
    { refresh: token }
  );
  return unwrap(response);  // ← { access: "eyJ...", refresh: "eyJ..." }
}
```

**Nota (Fase 6.1):** la firma de `refreshToken` en los ejemplos de arriba (`token: string`, retorno
`{access, refresh}`) corresponde al esquema previo a 6.1. Desde 6.1, `refreshToken()` no recibe
argumentos (el refresh viaja por cookie `HttpOnly`) y retorna solo `{access}` (el nuevo refresh se
re-setea como cookie, no vuelve en el body). La lección del envelope (`unwrap`) sigue igual.

**Ejemplo real — tests enmascaraban el bug (ERR-042):**

```typescript
// ❌ INCORRECTO — mock sin envelope: los tests pasan pero el código real está roto
server.use(
  rest.post('/auth/refresh/', (req, res, ctx) =>
    res(ctx.json({ access: 'new-token' }))  // ← falta el wrapper {data, meta}
  )
);

// ✅ CORRECTO — mock con envelope igual que el backend real
server.use(
  rest.post('/auth/refresh/', (req, res, ctx) =>
    res(ctx.json({ data: { access: 'new-token', refresh: 'new-refresh' }, meta: {} }))
  )
);
```

**Excepción:** `GET /api/v1/health/` es la única ruta que NO usa el envelope (compatibilidad con health checkers externos). Ver decisión #24 en `CLAUDE.md §17`.

**Cómo evitarlo:**

1. Toda función en `*/api.ts` que consume este backend debe tipar la respuesta como `Envelope<T>` y usar `unwrap()`.
2. Al escribir mocks MSW, copiar SIEMPRE el formato `{data: ..., meta: {}}`. Un mock que pasa sin envelope garantiza que el bug en producción no será detectado en tests.
3. El token rotativo: `ROTATE_REFRESH_TOKENS=True` significa que cada respuesta de `/auth/refresh/` incluye un nuevo `refresh` que DEBE persistirse en `localStorage`. Descartarlo causa logout forzado en 60 minutos.

---

## 5. TENANT_ISOLATION

**Problema:** Queries a la base de datos que no filtran por `organization`, exponiendo datos de un tenant a otro.

**Síntoma:** Un usuario de Org A puede leer documentos de Org B. El problema no siempre es visible en tests unitarios si los fixtures solo usan una organización.

**La regla es absoluta:** Toda query en un selector DEBE recibir `organization` como primer parámetro y filtrar por él.

**Ejemplo — incorrecto:**

```python
# ❌ INCORRECTO — devuelve documentos de TODAS las organizaciones
def get_documents_by_status(status: str) -> QuerySet:
    return Document.objects.filter(status=status)

# ❌ INCORRECTO — query en la view (nunca en la view)
class DocumentListView(APIView):
    def get(self, request):
        docs = Document.objects.filter(organization=request.organization)
        return Response({"data": DocumentSerializer(docs, many=True).data})
```

```python
# ✅ CORRECTO — selector con organization como primer parámetro explícito
def get_documents_by_status(
    organization: Organization,
    status: str,
) -> QuerySet:
    """Return documents in a given status for the organization."""
    return (
        Document.objects
        .filter(organization=organization, status=status)
        .select_related("folder", "created_by")
    )

# La view llama al selector, nunca hace la query directamente
class DocumentListView(APIView):
    def get(self, request):
        documents = document_selector.get_documents_by_status(
            organization=request.organization,
            status=request.query_params.get("status", "draft"),
        )
        return Response({"data": DocumentSerializer(documents, many=True).data})
```

**Test de aislamiento obligatorio (debe existir para cada selector nuevo):**

```python
def test_documents_are_isolated_between_organizations():
    """Una organización nunca debe ver documentos de otra."""
    org_a = OrganizationFactory()
    org_b = OrganizationFactory()
    doc_a = DocumentFactory(organization=org_a)
    doc_b = DocumentFactory(organization=org_b)

    result = get_documents_by_status(organization=org_a, status="draft")

    assert doc_a in result
    assert doc_b not in result  # ← este assert es el que importa
```

**Cómo evitarlo:**

1. Antes de escribir cualquier selector, verificar que su firma incluye `organization: Organization` como primer parámetro.
2. Buscar en el PR cualquier `.objects.filter(...)` sin `organization=organization` — es una vulnerabilidad de seguridad.
3. La excepción documentada: `cleanup_orphan_blobs` es tenant-agnóstica (ver decisión #21 en `CLAUDE.md §17`). Toda otra excepción requiere justificación explícita.

---

## 6. RBAC y DEAD_CODE

**Problema A (RBAC):** Consultas o acciones que se ejecutan antes de verificar los permisos del usuario, generando requests innecesarios (403 silenciosos) o lógica de permisos duplicada en el cliente.

**Problema B (DEAD_CODE):** Constantes de roles duplicadas en múltiples archivos y funciones de API nunca consumidas.

### 6.1 Query condicional al rol

**Ejemplo real (ERR-027):**

```typescript
// ❌ INCORRECTO — useAuditLogs corre siempre, generando 403 para roles sin acceso
function AuditLogPage() {
  const { data, isLoading } = useAuditLogs(filters);  // ← dispara aunque role=VIEWER

  if (!ALLOWED_ROLES.includes(userRole)) {
    return <NotAuthorized />;
  }
  // ...
}
```

```typescript
// ✅ CORRECTO — query condicional al rol
function AuditLogPage() {
  const { role } = useAuthStore();
  const canAccess = !!role && ALLOWED_ROLES.includes(role);
  const { data, isLoading } = useAuditLogs(filters, { enabled: canAccess });

  if (!canAccess) return <NotAuthorized />;
  // ...
}

// El hook acepta options con enabled
function useAuditLogs(filters: AuditFilters, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: auditKeys.list(filters),
    queryFn: () => auditApi.getLogs(filters),
    enabled: options?.enabled ?? true,
  });
}
```

**Regla:** La verificación de rol en el backend es la autoridad. La verificación en el frontend es UX (evitar requests inútiles), no seguridad. NUNCA duplicar la lógica de permisos del backend en el cliente.

### 6.2 Centralizar constantes de roles

**Ejemplo real (ERR-051):**

```typescript
// ❌ INCORRECTO — 8 archivos con la misma constante inline
// DocumentDetailPage.tsx
const WRITE_ROLES = ['editor', 'supervisor', 'org_admin', 'super_admin'];
// FolderBrowserPage.tsx
const WRITE_ROLES = ['editor', 'supervisor', 'org_admin', 'super_admin'];
// WorkflowExecutionsPage.tsx
const WRITE_ROLES = ['editor', 'supervisor', 'org_admin', 'super_admin'];
// ... × 5 más
```

```typescript
// ✅ CORRECTO — módulo compartido en shared/lib/roles.ts
export const WRITE_ROLES: UserRole[] = ['editor', 'supervisor', 'org_admin', 'super_admin'];
export const START_ROLES: UserRole[] = ['supervisor', 'org_admin', 'super_admin'];
export const canWrite = (role?: UserRole | null): boolean =>
  !!role && WRITE_ROLES.includes(role);
```

### 6.3 No implementar funciones que no tienen consumidor

**Ejemplo real (ERR-053):**

```typescript
// ❌ INCORRECTO — función implementada "por si acaso" sin consumidor real
// audit/api.ts
export const getAuditLogById = (id: string) => api.get(`/audit-logs/${id}/`);

// audit/hooks.ts
export const useAuditLog = (id: string) => useQuery({ ... });

// audit/keys.ts
detail: (id: string) => ['audit-logs', id] as const
```

**Regla:** No implementar el CRUD completo de un recurso si el frontend solo necesita el endpoint de lista. Los tres artefactos anteriores nunca fueron importados y fueron eliminados en la auditoría.

---

## 7. SOFT_DELETE

**Problema:** `auto_now=True` en `updated_at` no actualiza el campo si no está incluido explícitamente en `update_fields`.

**Síntoma:** Los registros soft-deleted conservan el `updated_at` anterior. Los tests de "cuándo fue eliminado" pasan porque comprueban `deleted_at`, pero auditorías que observan `updated_at` muestran datos incorrectos.

**Ejemplo real (ERR-006):**

```python
# ❌ INCORRECTO — auto_now=True no se dispara si updated_at no está en update_fields
def soft_delete(self, deleted_by=None):
    self.deleted_at = timezone.now()
    self.save(update_fields=["deleted_at"])  # ← updated_at NO se actualiza
```

```python
# ✅ CORRECTO — incluir updated_at explícitamente
def soft_delete(self, deleted_by=None):
    self.deleted_at = timezone.now()
    self.save(update_fields=["deleted_at", "updated_at"])
```

**Comportamiento de Django con `auto_now=True`:**

| Operación | ¿Actualiza `auto_now` field? |
|---|---|
| `instance.save()` | Sí |
| `instance.save(update_fields=["campo"])` sin incluir el campo auto | **No** |
| `QuerySet.update(...)` | **No** (nunca actualiza `auto_now`) |

**Cómo evitarlo:**

1. Al usar `save(update_fields=[...])`, verificar siempre si hay campos `auto_now=True` que deben actualizarse y añadirlos a la lista.
2. `BaseModel` tiene `updated_at = models.DateTimeField(auto_now=True)` — incluirlo siempre que el significado del cambio implique "este registro fue modificado".

---

## 8. ASYNC_CELERY

**Problema:** Race conditions y errores de coordinación en código asíncrono — tanto en Celery (backend) como en la cola de refresh del frontend.

### 8.1 Guard de ejecución única sin lock — race condition

**Ejemplo real (ERR-008):**

```python
# ❌ INCORRECTO — verificación no atómica: ventana entre SELECT y INSERT
def start_workflow(organization, user, document, template):
    if WorkflowExecution.objects.filter(
        document=document,
        status__in=['pending', 'in_progress']
    ).exists():
        raise ConflictError("WORKFLOW_ALREADY_ACTIVE")
    # ← VENTANA: otro request puede superar este check simultáneamente
    execution = WorkflowExecution.objects.create(...)
```

```python
# ✅ CORRECTO — constraint de DB + captura de IntegrityError
# En el modelo:
class Meta:
    constraints = [
        models.UniqueConstraint(
            fields=["document"],
            condition=Q(status__in=["pending", "in_progress"], deleted_at__isnull=True),
            name="uq_wf_exec_one_active_per_document",
        )
    ]

# En el service:
def start_workflow(organization, user, document, template):
    if WorkflowExecution.objects.filter(...).exists():
        raise ConflictError("WORKFLOW_ALREADY_ACTIVE")  # fast-path amigable
    try:
        with transaction.atomic():
            execution = WorkflowExecution.objects.create(...)
    except IntegrityError:
        raise ConflictError("WORKFLOW_ALREADY_ACTIVE")  # fallback atómico
```

### 8.2 `select_for_update` para operaciones de transición de estado

**Ejemplo real (ERR-009):**

```python
# ❌ INCORRECTO — dos workers pueden leer y avanzar el mismo paso
def advance_step(execution_id, action, user):
    execution = WorkflowExecution.objects.get(id=execution_id)  # ← sin lock
    if execution.status != 'in_progress':
        raise ValidationError("Execution is not in progress")
    _apply_transition(execution, action)  # ← dos workers pueden ejecutar esto

# ✅ CORRECTO — lock a nivel de fila con select_for_update
def advance_step(execution_id, action, user):
    with transaction.atomic():
        execution = (
            WorkflowExecution.objects
            .select_for_update(of=("self",))  # of=("self",) porque current_step puede ser NULL
            .get(id=execution_id)
        )
        if execution.status != 'in_progress':
            raise ValidationError("Execution is not in progress")
        _apply_transition(execution, action)
```

### 8.3 Mapear errores de SDKs externos a `TransientError`

**Ejemplo real (ERR-012):**

```python
# ❌ INCORRECTO — RateLimitError del SDK Anthropic no es capturado → fallo permanente
@shared_task(autoretry_for=(TransientError,), max_retries=3)
def run_ai_analysis(document_id: str):
    document = Document.objects.get(id=document_id)
    result = ai_service.analyze(document)  # ← puede lanzar anthropic.RateLimitError
    # Si lanza, la tarea falla permanentemente porque RateLimitError no es TransientError

# ✅ CORRECTO — mapeo explícito de errores recuperables a TransientError
import anthropic

def analyze(document: Document) -> dict:
    try:
        response = client.messages.create(...)
        return _parse_response(response)
    except (
        anthropic.RateLimitError,
        anthropic.APITimeoutError,
        anthropic.APIConnectionError,
    ) as e:
        raise TransientError(str(e)) from e  # ← autoretry lo reintentará
```

### 8.4 Resetear estado visual ANTES del `on_commit`

**Ejemplo real (ERR-013):**

```python
# ❌ INCORRECTO — el usuario ve "FAILED" hasta que el worker termine
def reprocess_ocr(organization, user, document):
    transaction.on_commit(lambda: process_ocr.delay(str(document.id)))

# ✅ CORRECTO — resetear a PENDING inmediatamente como señal de "en cola"
def reprocess_ocr(organization, user, document):
    document.ocr_status = OcrStatus.PENDING
    document.save(update_fields=["ocr_status", "updated_at"])  # visible de inmediato
    transaction.on_commit(lambda: process_ocr.delay(str(document.id)))
```

### 8.5 Idempotencia de notificaciones con claim atómico

**Ejemplo real (ERR-017):**

```python
# ❌ INCORRECTO — dos workers leen PENDING simultáneamente, envían dos emails
def _send(notification: Notification):
    if notification.status not in ('pending', 'failed'):  # ← no atómico
        return
    notification.status = 'sending'
    notification.save()
    _smtp_send(notification)

# ✅ CORRECTO — claim atómico: solo un worker avanza
def _send(notification: Notification):
    updated = (
        Notification.objects
        .filter(id=notification.id, status__in=('pending', 'failed'))
        .update(status='sending')
    )
    if updated == 0:
        return  # otro worker ya tomó esta notificación
    _smtp_send(notification)
```

---

## 9. POLLING

**Problema:** El polling de TanStack Query que no tiene cota máxima de iteraciones ni detecta estados terminales del backend deja requests abiertos indefinidamente cuando el worker Celery muere.

**Síntoma:** Spinner eterno en la UI. Requests cada N segundos para siempre mientras el tab permanezca abierto. No hay forma de que el usuario sepa que algo falló.

### 9.1 Siempre propagamos el fallo al objeto polleado

**Ejemplo real (ERR-024):**

```python
# ❌ INCORRECTO — si la tarea falla definitivamente, metadata["ai_analysis"] nunca se escribe
# El frontend hace polling para siempre
@shared_task(max_retries=3, autoretry_for=(TransientError,))
def run_ai_analysis(document_id: str):
    document = Document.objects.get(id=document_id)
    result = ai_service.analyze(document)
    document.metadata['ai_analysis'] = result
    document.save(update_fields=['metadata'])
    # Si las 3 tentativas fallan → la función termina sin escribir nada → polling infinito

# ✅ CORRECTO — escribir marcador de fallo al agotar reintentos
@shared_task(max_retries=3, autoretry_for=(TransientError,))
def run_ai_analysis(document_id: str):
    try:
        document = Document.objects.get(id=document_id)
        result = ai_service.analyze(document)
        document.metadata['ai_analysis'] = {'status': 'success', **result}
    except Exception as exc:
        if run_ai_analysis.request.retries >= run_ai_analysis.max_retries:
            # Fallo definitivo — escribir marcador para detener el polling
            document.metadata['ai_analysis'] = {'status': 'failed', 'error': str(exc)}
        else:
            raise  # permitir autoretry
    finally:
        document.save(update_fields=['metadata'])
```

### 9.2 Siempre definir un estado terminal en el frontend

**Ejemplo real (ERR-052, ERR-024):**

```typescript
// ❌ INCORRECTO — polling sin cota ni estado terminal de fallo
const { data: document } = useQuery({
  queryKey: documentKeys.detail(id),
  queryFn: () => fetchDocument(id),
  refetchInterval: (data) => {
    const status = data?.ocr_status;
    return status === 'pending' || status === 'processing' ? 3000 : false;
    // ← Si el worker muere sin transicionar: polling eterno
  },
});
```

```typescript
// ✅ CORRECTO — cota máxima + detección de todos los estados terminales
const pollCount = useRef(0);
const MAX_POLLS = 40; // ~2 minutos a 3s

const { data: document } = useQuery({
  queryKey: documentKeys.detail(id),
  queryFn: () => fetchDocument(id),
  refetchInterval: (data) => {
    const status = data?.ocr_status;
    const isTerminal = !['pending', 'processing'].includes(status ?? '');
    const overLimit = pollCount.current >= MAX_POLLS;

    if (isTerminal || overLimit) {
      if (overLimit) console.warn(`Polling cap reached for document ${id}`);
      return false;
    }
    pollCount.current++;
    return 3000;
  },
});
```

**Regla mnemónica:** Todo proceso asíncrono tiene exactamente dos estados terminales: éxito y fallo. El backend debe escribir ambos. El frontend debe detectar ambos y en ningún caso hacer polling infinito.

---

## 10. GITIGNORE

**Problema:** Archivos con credenciales o configuración sensible son incluidos en el historial de git antes de que `.gitignore` los excluya.

**Síntoma:** `git log --all --full-history -- backend/.env` muestra el archivo en el historial. Las credenciales se filtran incluso después de `git rm --cached`, porque permanecen en commits anteriores.

**Ejemplo real (ERR-001):**

```bash
# ❌ SECUENCIA INCORRECTA
touch backend/.env          # ← crea el archivo
echo "POSTGRES_PASSWORD=secreto" >> backend/.env
git add .                   # ← incluye backend/.env
git commit -m "initial setup"
# AHORA el .env con credenciales está en el historial para siempre

# ✅ SECUENCIA CORRECTA
touch .gitignore
echo "backend/.env" >> .gitignore   # ← proteger ANTES de crear el .env
touch backend/.env
git add .                           # ← .env no se incluye por estar en .gitignore
git commit -m "feat: initial project setup"
```

**Si ya ocurrió:** `git rm --cached backend/.env` detiene el tracking pero NO elimina el archivo del historial. Para eliminar del historial usar `git filter-repo` (requiere coordinación con el equipo). En proyectos de portafolio con credenciales de desarrollo no críticas, `git rm --cached` + `commit` + rotate de credenciales es suficiente.

**Lista obligatoria de archivos que nunca deben estar en git:**

```gitignore
# Backend
backend/.env
backend/.env.*
!backend/.env.example

# Frontend
frontend/.env
frontend/.env.local
frontend/.env.*.local

# Producción
.env.production
scripts/*.env
```

---

## 11. Checklist pre-PR

Ejecutar mentalmente antes de cada PR que toca este proyecto:

### Backend

- [ ] **Tipos en serializers:** ¿Los campos del serializer coinciden con lo que el frontend espera? Verificar especialmente `SerializerMethodField` con nombres planos.
- [ ] **Tenant isolation:** Cada nuevo selector recibe `organization` como primer parámetro y filtra por él. No hay ningún `.objects.filter()` sin `organization=organization` en selectors.
- [ ] **Migración generada:** ¿Se revisó la migración generada por `makemigrations`? ¿No modifica migraciones ya aplicadas? ¿Está nombrada descriptivamente?
- [ ] **Migración aplicada:** ¿Se ejecutó `python manage.py migrate` en el entorno de desarrollo?
- [ ] **`update_fields` + `auto_now`:** Si el código usa `save(update_fields=[...])`, ¿se incluye `updated_at` cuando debe actualizarse?
- [ ] **Celery transients:** Los errores recuperables de SDKs externos (Anthropic, SMTP, S3) se mapean a `TransientError`.
- [ ] **Estados terminales de tareas:** Si una tarea puede fallar definitivamente, ¿escribe un marcador de fallo en el objeto para que el polling del cliente pueda parar?
- [ ] **Idempotencia de efectos:** Operaciones de transición de estado usan `select_for_update` o claim atómico para evitar doble ejecución concurrente.
- [ ] **Test de aislamiento:** Para cada nuevo selector, existe un test que verifica que Org A no ve datos de Org B.

### Frontend

- [ ] **Tipos verificados contra el serializer:** Cada interfaz TypeScript de respuesta de API fue verificada contra el serializer Django real (no "por intuición"). Referencia: `docs/reference.md`.
- [ ] **Envelope desenvolvido:** Todas las llamadas a la API usan el helper `unwrap()` o acceden a `response.data.data` (no a `response.data` directamente).
- [ ] **Mocks con envelope:** Los handlers MSW en tests usan el formato `{data: ..., meta: {}}` igual que el backend real.
- [ ] **Refresh token nunca en `localStorage`/JS (Fase 6.1):** el `refresh` viaja exclusivamente en la cookie `HttpOnly` `sv_refresh`, seteada/leída/borrada por el backend. Si el código toca el interceptor de refresh o el bootstrap de sesión, verificar que no se intente leer, guardar o loguear el refresh token desde JavaScript.
- [ ] **Header CSRF en refresh/logout:** las llamadas a `/auth/refresh/` y `/auth/logout/` deben adjuntar `X-CSRF-Token` (leído de la cookie `sv_csrf` vía `getCookie()`); el backend responde 403 `CSRF_INVALID` si falta o no coincide.
- [ ] **Polling con cota:** Cualquier `refetchInterval` tiene una condición de stop por estado terminal Y un contador máximo de iteraciones.
- [ ] **`key` en componentes con `defaultValues`:** Los componentes con `react-hook-form` que cambian de entidad sin desmontarse tienen `key={entityId}`.
- [ ] **`FormLabel` solo dentro de `<FormField>`:** No hay `<FormLabel>` de shadcn/ui fuera del contexto de un `FormField`.
- [ ] **Roles centralizados:** Las constantes de roles usan `WRITE_ROLES` / `START_ROLES` de `shared/lib/roles.ts`, no declaraciones inline.
- [ ] **Sin dead code:** Las funciones de API y hooks creados tienen al menos un consumidor real en un componente.

### DevOps / CI

- [ ] **`pytest -m "not integration"`** en el pipeline CI. Los tests de integración requieren MinIO y solo corren localmente.
- [ ] **Variables de entorno de Vite en el Dockerfile:** El `ARG VITE_API_BASE_URL` está definido antes del paso `RUN npm run build`. Un bundle de producción sin esta variable apunta a `localhost:8000`.
- [ ] **`client_max_body_size`** en `nginx.conf` está configurado a `50m` (no el default de 1m).
- [ ] **`npm run build` antes de pushear:** `tsc --noEmit` y `vite build` usan configs distintas; verificar siempre con `npm run build` antes de abrir una PR.
- [ ] **`git status` antes de pushear:** verificar que no hay "untracked files" en `frontend/src/` — un directorio ignorado silenciosamente por `.gitignore` no llega a CI.

---

## 12. CI vs local: configuraciones divergentes

Esta sección documenta las diferencias entre correr el proyecto localmente y en CI que han causado fallos repetidos. Un test verde localmente puede rojo en CI por razones que no son obvias.

### 12.1 TypeScript: `tsc --noEmit` vs `vite build`

**El problema:**

```bash
# Local — pasa limpio
npx tsc --noEmit
# → 0 errors

# CI — falla
npm run build     # ejecuta: vite build
# → TS2345: Argument of type 'UserRole' is not assignable to...
```

**Por qué ocurre:**

`tsc --noEmit` usa `tsconfig.json` (configuración base, menos restrictiva). `vite build` usa `tsconfig.app.json`, que en este proyecto tiene `"strict": true`. Las diferencias de strict mode que más afectan:

| Regla | `tsconfig.json` | `tsconfig.app.json` (strict) |
|---|---|---|
| `strictNullChecks` | puede estar off | on |
| Inference en arrays `as const` | menos restrictiva | `.includes()` solo acepta literales exactos |
| Propiedades faltantes en object literals | warning | error |
| Propiedades requeridas faltantes en tipos | warning | error |

**Errores concretos de este proyecto (ERR-064 a ERR-067):**

```typescript
// ERR-064 — as const + includes
const WRITE_ROLES = ['editor', 'supervisor', 'org_admin', 'super_admin'] as const;
// ❌ WRITE_ROLES.includes(role) — TS2345 si role es UserRole (incluye 'viewer', 'auditor')
// ✅ (WRITE_ROLES as readonly string[]).includes(role)

// ERR-065 — prop type más amplio que el tipo del valor pasado
// ❌ <DocumentCard document={searchResult} /> donde SearchResult omite campos que Document requiere
// ✅ <DocumentCard document={searchResult as unknown as Document} /> (si el componente no los usa)

// ERR-066/ERR-067 — campos requeridos faltantes en fixtures de test
// ❌ const MOCK = { id: '...', name: '...' }  // sin ocr_content
// ✅ const MOCK = { id: '...', name: '...', ocr_content: '' }
```

**Regla:** Siempre verificar con `npm run build` antes de abrir una PR. Si el paso `vite build` falla en CI pero `tsc --noEmit` pasa local, la causa es casi siempre una de las diferencias de strict mode de la tabla anterior.

---

### 12.2 Tests de backend: mock_storage incompleto con Celery eager + transaction=True

**El problema:**

```
# En CI:
celery.exceptions.Retry: Retry in 1s: TransientError('Storage unavailable for {id}')
# En local: el test pasa
```

**Por qué ocurre:**

La interacción de tres configuraciones crea un comportamiento que solo aparece en CI:

```
test.py → CELERY_TASK_ALWAYS_EAGER=True
         ↓ process_ocr.delay() corre SÍNCRONAMENTE

test → django_db(transaction=True)
         ↓ on_commit() se dispara en cada COMMIT REAL

CI → MinIO no existe como servicio runner
         ↓ download_file() lanza TransientError
```

Localmente MinIO corre en Docker Compose → el task encuentra el archivo → pasa. En CI no hay MinIO → falla.

**Solución para tests que solo verifican el service (no el pipeline OCR):**

```python
@pytest.fixture
def mock_storage(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(
        "apps.documents.services.document_service.StorageService",
        lambda: mock,
    )
    # CRÍTICO: también mockear el delay del task para que on_commit no lo dispare
    monkeypatch.setattr(
        "apps.documents.services.document_service.process_ocr.delay",
        MagicMock(),
    )
    return mock
```

**Regla general:** Si un test usa `transaction=True` y el código bajo test llama a `.delay()` en un `on_commit`, el task se ejecutará síncronamente en CI si `CELERY_TASK_ALWAYS_EAGER=True`. Mockear solo el `StorageService` no es suficiente — hay que mockear también el `.delay()` del task o cada import de `StorageService` que el task usa en sus módulos propios.

---

### 12.3 Archivos no commiteados: untracked silenciosos

**El problema:**

```
# Local: los tests pasan
# CI: Failed to resolve import "@/lib/utils" — 11 suites con 0 tests
```

**Por qué ocurre:**

Un patrón en `.gitignore` puede ignorar un directorio que parece estar en el proyecto localmente porque existe en el sistema de archivos, pero nunca fue commiteado. El directorio `frontend/src/lib/` fue creado antes de que el `.gitignore` se corrigiera de `lib/` a `backend/lib/`. Durante todo ese tiempo, `git status` mostraba el directorio como ignorado (no como untracked), y el desarrollador asumió que estaba trackeado.

**Cómo detectarlo:**

```bash
# Ver todos los archivos ignorados en el repo
git ls-files --others --ignored --exclude-standard frontend/src/

# Ver estado completo incluyendo ignorados
git status --ignored frontend/src/lib/
```

---

## 13. TEST_QUALITY — Un test en verde no es sinónimo de un test correcto

**Problema:** Un test pasa, pero no por la razón que su nombre y su intención afirman — pasa porque un mock ausente o incompleto produce, por coincidencia, el mismo resultado observable que el escenario que se quería cubrir.

**Ejemplo real (ERR-068, Fase 6.1):**

```tsx
// ❌ Test que pasaba desde antes de Fase 6.1 — pero por la razón equivocada
test('sin refreshToken en localStorage → redirige a /login', async () => {
  // Sin mock de red configurado para refreshToken().
  renderProtectedRoute();
  await waitFor(() => {
    expect(screen.getByTestId('login-page')).toBeInTheDocument();
  });
});
```

**Por qué pasaba igual:** Sin un mock (MSW o de módulo) para la llamada HTTP que dispara `ProtectedRoute` al montar, jsdom hacía fallar la request con un error de red genérico — indistinguible, para el `.catch()` del componente, de un 401 real del backend. El test terminaba en el mismo estado observable (`Navigate` a `/login`) sin haber ejercitado el camino que decía probar.

```tsx
// ✅ CORRECTO — mock explícito a nivel de módulo, escenario determinístico
vi.mock('@/features/auth/api', () => ({
  refreshToken: vi.fn(),
  getMe: vi.fn(),
}))

test('cookie de refresh ausente/inválida → redirige a /login', async () => {
  vi.mocked(authApi.refreshToken).mockRejectedValue(new Error('401'))
  renderProtectedRoute()
  await waitFor(() => {
    expect(screen.getByTestId('login-page')).toBeInTheDocument()
  })
})
```

**Cómo evitarlo:**

1. Cuando un test depende de una llamada HTTP o de red, verificar explícitamente qué pasa si esa llamada NO está mockeada (¿el test seguiría pasando por una razón distinta?).
2. Preferir mocks explícitos y deterministas (mock de módulo o handler MSW con handler por defecto para rutas no cubiertas, `onUnhandledRequest: 'error'`) sobre depender de comportamiento incidental de la librería de testing.
3. Al reescribir un test por un cambio de arquitectura (como el paso de `localStorage` a cookie httpOnly en 6.1), revisar si el test viejo realmente ejercitaba el código que dice cubrir, no solo copiar su aserción final.

**Regla:** Antes de abrir cualquier PR, correr `git status` y revisar que no hay archivos en `frontend/src/` listados como "ignored" o "untracked" que deberían estar en el repo. Si un import funciona local pero falla en CI con "Failed to resolve import", el primer sospechoso es que el archivo nunca fue commiteado.

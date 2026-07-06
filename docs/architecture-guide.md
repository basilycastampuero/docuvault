# docs/architecture-guide.md — [PENDIENTE DE GENERACIÓN]

> **Estado de este archivo:** este documento **todavía no contiene la guía de arquitectura final**.
> Contiene el **prompt / especificación** que una IA (o un humano) debe seguir para generarla,
> palabra por palabra según lo que el usuario pidió y lo que se acordó en la conversación que dio
> origen a este archivo. Cuando llegue el momento de generarlo (ver "Cuándo generarlo" abajo), quien
> lo haga debe **reemplazar todo el contenido de este archivo** por el documento final — este
> preámbulo y las instrucciones dejan de ser necesarios una vez generado el contenido real.

---

## 0. Cuándo generarlo

**No generar todavía.** Al momento de escribir esta especificación (2026-07-06), el proyecto está en
Fase 6.2 (backend + frontend de thumbnails/Office ya completos, ver `CLAUDE.md` §17). Este documento
debe redactarse **cuando el proyecto esté terminado en su totalidad**, es decir, cuando `CLAUDE.md`
§17 declare completas todas las subfases de la Fase 6 (6.1, 6.2, 6.3, y cualquier otra que se agregue
después). Antes de arrancar la generación, quien la ejecute debe:

1. Leer `CLAUDE.md` §17 ("Estado actual del proyecto") y confirmar que no queda ninguna subfase de la
   Fase 6 pendiente o "en curso".
2. Si queda trabajo pendiente, **no generar el documento** — avisar al usuario y detenerse.
3. Si el usuario pide generarlo explícitamente aunque quede trabajo pendiente, generarlo igual pero
   dejar constancia al inicio del documento de qué fases quedaban abiertas en ese momento.

---

## 1. Objetivo del documento a generar

Crear `docs/architecture-guide.md` (reemplazando este contenido) como **el documento más detallado y
explicativo del proyecto para comprensión humana profunda**. Debe permitir explicar, defender o
reestructurar cualquier parte de SasVault teniendo *solo este documento a mano*, sin necesidad de
saltar a otro `.md` para entender el **por qué** de algo. La única excepción son citas puntuales a
otros documentos cuando su contenido ya es correcto y completo — para no duplicar texto — pero
incluso en esos casos la cita debe ir acompañada de suficiente contexto en el propio documento para
que el lector entienda *qué* va a encontrar allí y *por qué* importa, antes de saltar a leerlo.

**Audiencia:** debe servir tanto para un desarrollador junior (que necesita entender conceptos base:
qué es multi-tenancy, por qué soft delete, qué hace un middleware) como para uno senior (que necesita
trade-offs concretos, alternativas descartadas y deuda técnica documentada). Cuando un concepto no es
obvio para alguien sin el contexto del proyecto, explicarlo desde cero antes de entrar en el detalle
específico de SasVault.

**Extensión:** sin límite. Prioridad total a la completitud y profundidad sobre la brevedad. Es
preferible que una sección quede larga y exhaustiva a que quede corta y obligue a adivinar.

---

## 2. Principios rectores (no negociables)

1. **No tocar `docs/reference.md`.** Ese documento mantiene su naturaleza de diccionario de consulta
   rápida (tablas escaneables: qué existe, qué recibe, qué devuelve). Este documento nuevo es
   complementario, no un reemplazo — cubre el "por qué" y el "cómo fluye", no el "qué existe".
2. **Autosuficiencia.** El lector no debe necesitar abrir otro archivo para entender el razonamiento
   detrás de una decisión. Si una explicación en otro `.md` es incompleta, superficial, ambigua o
   quedó desactualizada, **no la cites tal cual** — amplíala o reescríbela directamente aquí.
3. **Citas con precisión de línea.** Toda referencia a otro documento o archivo de código debe incluir
   `documento.md § sección, líneas X-Y` (o `archivo.py:X-Y` para código). Nunca cites solo el nombre
   del archivo — el objetivo explícito de este ejercicio es que las referencias sean accionables.
4. **Verificar antes de citar, no copiar de memoria.** Los números de línea cambian con cada commit.
   Al generar este documento, **volver a grepear/leer el código y los `.md` en el momento de la
   redacción** — no reutilizar líneas citadas en conversaciones o documentos anteriores sin
   verificarlas primero. Un número de línea equivocado es peor que no tener número.
5. **Explicar con ejemplos reales del repo, no genéricos.** Cuando ilustres un patrón (ej. un service
   con `transaction.atomic()`, un hook de TanStack Query con polling), pega el fragmento real del
   código citando archivo y líneas, no un ejemplo inventado.
6. **Los "por qués" priman sobre los "qués".** `reference.md` ya cubre el qué. Este documento existe
   específicamente para el contexto, el trade-off, la alternativa descartada, el incidente que
   motivó una decisión. Si no hay un "por qué" que agregar sobre lo que ya dice `reference.md`, esa
   sección de este documento probablemente sobra o debe fusionarse con otra.
7. **Sincronizar con el estado real del código en el momento de generación**, no con lo que este
   prompt describe hoy (2026-07-06). Este prompt fue escrito en Fase 6.2; para cuando se generare el
   documento, es probable que existan Fase 6.3 y posiblemente más decisiones de diseño, endpoints,
   modelos, librerías, etc. **Todo lo listado en la sección 4 de este prompt es un piso mínimo, no
   un techo** — cubrir todo lo que exista en el proyecto al momento de generar, no solo lo enumerado
   aquí.
8. **El ángulo del "error silencioso" es obligatorio al explicar decisiones que divergen de un patrón
   establecido.** Cuando una decisión se aparta deliberadamente de un patrón que el lector esperaría
   por analogía (ej. `ThumbnailStatus` usa `"ready"` en vez de `"completed"` como `OcrStatus`), no
   basta con describir la decisión: hay que (a) dejar explícito que fue deliberada y no un descuido,
   (b) nombrar el error concreto que se comete si alguien clona el patrón "vecino" sin fijarse en la
   diferencia (ej. copiar el enum de OCR y asumir el mismo valor terminal), y (c) explicar por qué
   ese error es precisamente el tipo de cosa que un agente de IA o un dev nuevo comete al generalizar
   por analogía en vez de leer el código real. Este es el mismo ángulo que ya usa `BITACORA.md` en
   varias entradas (ver sección 3) — mantenerlo como lente recurrente, no como excepción puntual.
9. **Trade-offs cuantificados, no solo cualitativos.** Cuando una decisión se justifica por
   performance/tamaño/complejidad (ej. "PNG siempre, no JPEG condicional al formato de entrada"), no
   alcanza con nombrar la alternativa descartada — hay que dar (a) el trade-off real con números
   concretos cuando existan o se puedan estimar razonablemente (ej. "JPEG sería ~40% más liviano para
   fotografías, pero..."), (b) el problema técnico específico que la alternativa introduciría (ej. el
   canal alfa de un PNG con transparencia se convierte en fondo negro al pasar a JPEG), y (c) por qué,
   a la escala concreta del proyecto (ej. thumbnails de 400px, 20-60 KB), la complejidad de la
   alternativa "más óptima" no se justifica frente a la simplicidad de un único formato/camino para
   todo el pipeline downstream. Si no hay una cifra real medida en el proyecto, está bien estimarla,
   pero **marcarla explícitamente como estimación** ("aproximadamente", "del orden de") — nunca
   presentar un número inventado como si fuera un dato medido. La decisión #42 de `CLAUDE.md` §17
   (PNG vs JPEG en thumbnails) es el ejemplo de referencia que debe expandirse con este patrón; buscar
   el resto de decisiones de performance/tamaño/complejidad en `CLAUDE.md` §17 y aplicarles el mismo
   tratamiento.
10. **Cobertura mecánica completa de cada sistema/flujo/algoritmo — no solo anécdotas de decisiones.**
    Los principios 8 y 9 son patrones puntuales de profundidad para casos concretos donde una decisión
    diverge de algo esperado o involucra un trade-off medible. **No son el estándar completo ni un
    sustituto de él.** El requisito base, que gobierna toda la sección 4, es explicar **cada sistema,
    flujo, algoritmo, método, función y modelo relevante del proyecto de forma completa y mecánica**
    — cómo funciona paso a paso, no solo por qué se eligió — al nivel de detalle que le permita a un
    junior sin contexto previo seguir el razonamiento de principio a fin. Esto incluye explícitamente
    lo **"invisible"**: mecánica de infraestructura que nadie marcó como una decisión notable, pero
    que igual hace falta explicar para entender el proyecto en su totalidad. Ejemplos del tipo de cosa
    que entra en esta categoría (no es una lista cerrada — aplicar el mismo criterio a todo lo que se
    encuentre): cómo firma y verifica Django un JWT y qué son sus claims exactamente; cómo un índice
    GIN acelera una búsqueda `search_vector`/`tsquery` y por qué un índice B-tree normal no serviría
    para eso; qué hace mecánicamente `select_for_update` para evitar una condición de carrera en
    `advance_step`; cómo se dispara un signal `post_save` de Django y por qué corre síncrono dentro de
    la misma transacción; qué es y cómo funciona criptográficamente una URL presignada de S3/MinIO
    (qué firma, qué expira, qué pasa si se comparte); cómo funciona el algoritmo de backoff+jitter de
    Celery (`retry_backoff=True, retry_jitter=True`) y por qué el jitter evita un "thundering herd" de
    reintentos simultáneos; cómo el patrón CSRF double-submit realmente impide un ataque (qué sabe el
    atacante, qué no puede falsificar); cómo TanStack Query decide cuándo refetchear vs servir de
    caché. Cuando una sección de la 4 liste preguntas a responder, tratarlas como el piso, no el
    techo: si explicar completamente un mecanismo requiere una subsección propia con su propio
    diagrama o ejemplo de código, generarla — la extensión total del documento no tiene límite
    (sección 1).

---

## 3. Fuentes a consultar y qué extraer de cada una

Leer estos documentos **completos** (no solo el encabezado) antes de escribir, y extraer/expandir lo
siguiente de cada uno:

| Fuente | Qué contiene hoy | Qué extraer / expandir para este documento |
|---|---|---|
| `CLAUDE.md` (raíz) | Reglas absolutas de arquitectura, stack, multi-tenancy, RBAC, testing, estado del proyecto, **§17 con las decisiones de diseño cerradas numeradas** | Es la fuente principal de "por qués". Cada decisión numerada en §17 debe aparecer expandida en la sección correspondiente de este documento — no como lista plana, sino integrada en la narrativa del flujo/tecnología al que pertenece, con contexto de cuándo y por qué se tomó |
| `docs/reference.md` | Diccionario de qué existe (modelos, services, selectors, endpoints, serializers, tipos TS, hooks, componentes) | NO copiar tablas de aquí. Solo referenciarlo (`reference.md § sección`) cuando el documento nuevo necesite decir "para la firma exacta, ver reference.md". El valor de este documento nuevo es el contexto alrededor de esas firmas, no repetirlas |
| `docs/coding-patterns.md` | Patrones de código con ejemplos reales (services/selectors, transacciones, N+1, etc.), cada patrón con su "¿Por qué?" | Muy relevante — probablemente la fuente con más solapamiento directo. Verificar si sus explicaciones de "por qué" ya son suficientemente profundas; si sí, citarlas con línea; si no, expandirlas aquí |
| `docs/database-conventions.md` | Convenciones de DB expandidas desde `CLAUDE.md` §6, con SQL de referencia | Usar para la sección de modelo de datos / multi-tenancy en profundidad |
| `docs/api-conventions.md` | Convenciones REST (versionado, envelope, códigos HTTP) | Usar para la sección del contrato API / viaje de un request |
| `docs/ai-agent-guide.md` | Anti-patrones reales cometidos (TYPE_CONTRACT, REACT_STATE, MIGRATION, ENVELOPE, TENANT_ISOLATION, RBAC, SOFT_DELETE, ASYNC_CELERY, POLLING, GITIGNORE) | Resumir cada categoría con 1-2 ejemplos concretos y su lección — no hace falta repetir los ~69 errores individuales, pero sí el patrón de cada categoría |
| `docs/error-registry.md` | Registro cronológico factual de los 69 errores (ERR-001 a ERR-069) | Fuente de respaldo para `ai-agent-guide.md`; citar casos puntuales solo si aportan un "por qué" que no esté ya en `ai-agent-guide.md` |
| `docs/deploy-guide.md` | Guía educativa de despliegue a producción, ya tiene un "por qué" muy detallado (Dockerfiles multi-stage, nginx, docker-compose.prod.yml) | No reescribir esto — ya cumple el estándar de autosuficiencia. Resumir el flujo en 1-2 párrafos en la sección de CI/CD-deploy de este documento y referenciar el resto con secciones/líneas |
| `docs/git-workflow.md` | Estrategia de ramas y convenciones de commits | Resumen breve; no necesita expansión, es autoexplicativo |
| `docs/local-dev.md` | Cómo levantar el entorno local | Resumen breve con referencia; no es objeto de "por qué" |
| `docs/manual-testing.md` | Guía de pruebas manuales end-to-end | Mencionar su existencia en la sección de testing; no expandir contenido, ya es autosuficiente |
| `docs/phase-plan.md` | Plan de desarrollo por fases con checklists | Usar para entender el orden histórico de decisiones si hace falta contexto temporal ("esto se decidió en la Fase X porque...") |
| `BITACORA.md` (raíz) | Diario de desarrollo escrito para humanos: decisiones, complicaciones, flujo de agentes usado (software-architect → senior-software-engineer → test-quality-engineer → docs-manager → git-operator) y — clave — ya usa el ángulo del "error silencioso" en varias entradas (ver principio 8 de la sección 2, ej. líneas 33-37 y 98-99 sobre `ThumbnailStatus.ready`) | **Fuente primaria, no de respaldo.** Minar activamente cada entrada relevante por sub-fase: cuando una entrada ya explica el "por qué + qué error evita" con la calidad esperada, adaptar/incorporar esa prosa directamente en la sección temática correspondiente de este documento (no dejarla aislada como "contexto histórico si hace falta"), citando la entrada y fecha para trazabilidad. Cuando la explicación de `BITACORA.md` sea más breve de lo que amerita el tema, expandirla aquí sin perder el ángulo del error silencioso que ya trae |
| `CHANGELOG.md` (raíz) | Historial Keep a Changelog por fase | Usar solo si hace falta precisión de qué cambió en qué commit |
| Código fuente (`backend/`, `frontend/`) | Fuente de verdad final | Toda cita de comportamiento debe verificarse contra el código real, no asumirse de la documentación |

---

## 4. Estructura obligatoria del contenido final

Esta es la tabla de contenidos mínima. Cada sección lista las preguntas concretas que debe responder
el texto — no basta con un título y un párrafo genérico, hay que dejar sin ambigüedad qué debe cubrir
cada una. Se puede reordenar o subdividir si mejora la narrativa, pero ningún punto puede faltar.

### 4.1. Introducción y cómo leer este documento
- Qué es SasVault, en una frase, y qué NO es este documento (no es `reference.md`, no reemplaza
  `CLAUDE.md` como fuente de reglas).
- Cómo está organizado, y la convención de citas usada (formato `archivo § sección, líneas X-Y`).

### 4.2. Visión arquitectónica general
- Qué es "monolito modular" en este proyecto concretamente (no en abstracto) — qué significa que
  `apps/documents`, `apps/workflows`, etc. sean módulos dentro de un solo proceso Django.
- Por qué se descartaron microservicios explícitamente para un proyecto de portafolio (justificar con
  el objetivo del proyecto: demostrar dominio de un stack monolítico bien estructurado, no de
  orquestación distribuida).
- Diagrama (ASCII o descripción textual clara) de las capas: `models → services/selectors →
  api/views/serializers → permissions`. Explicar la regla de oro (view solo orquesta) con el ejemplo
  correcto/incorrecto ya existente en `CLAUDE.md` §2, pero expandiendo el razonamiento.

### 4.3. El viaje de un request — end to end
Elegir 1-2 requests reales representativos (ej. `POST /documents/` con upload, y `POST
/workflows/executions/{id}/advance/`) y trazar **todo el camino**, con archivo y líneas de cada salto:
- Nginx/Vite proxy (dev vs prod) → Django URL routing → middleware (`OrganizationTenantMiddleware`:
  qué hace, cómo decodifica el JWT, qué inyecta en `request.organization`, qué pasa si el usuario no
  tiene organización) → permission classes (`IsOrganizationMember` + `HasRole` inline) → view (qué
  hace y qué NO hace) → serializer (validación de entrada) → service (lógica de negocio,
  `transaction.atomic()`, side effects, auditoría, `on_commit` para tareas Celery) → selector (si
  aplica) → serializer de salida (envelope `{data, meta}`) → respuesta HTTP.
- Repetir el ejercicio para el flujo de autenticación completo (login → cookies `sv_refresh`/`sv_csrf`
  → refresh con CSRF double-submit → logout), citando `backend/apps/authentication/api/cookies.py` y
  el interceptor de axios en `frontend/src/lib/api-client.ts`.

### 4.4. Multi-tenancy en profundidad
- Qué es un "shared schema" con aislamiento por `organization_id` vs. schemas separados, y por qué se
  eligió el primero (ver `CLAUDE.md` §4 y `docs/database-conventions.md`).
- Cómo se garantiza el aislamiento en cada capa: modelo (FK obligatoria), selector (filtro explícito),
  vista (permission class), y qué pasa si alguien se salta una capa (ejemplo real del anti-patrón
  `TENANT_ISOLATION` de `ai-agent-guide.md`, con su cita).
- Por qué el middleware inyecta `request.organization` en vez de derivarlo del usuario en cada
  service/selector por separado.

### 4.5. Modelo base, soft delete y auditoría
- Por qué `BaseModel` con UUID + soft delete es el estándar, qué entidades quedan exentas
  (`AuditLog`) y por qué (inmutabilidad, append-only, no tiene sentido "borrar" una auditoría).
- Cómo funciona `SoftDeleteManager` vs `AllObjectsManager`, con ejemplo de código real.
- Por qué el borrado físico de blobs en MinIO está desacoplado del soft delete del `Document`
  (`cleanup_orphan_blobs`), y qué problema resolvía (blobs huérfanos vs. período de gracia de 24h).
- El sistema de auditoría: por qué vive en services y nunca en views, y un ejemplo real de
  `audit_service.log()` en contexto.

### 4.6. Stack tecnológico — qué se usa, dónde y por qué
Para cada tecnología/librería relevante, una subsección con: **qué problema resuelve en este
proyecto específico**, **alternativas consideradas o descartadas (si se conocen)**, y **dónde se usa**
(archivo + líneas de al menos un uso representativo). Cubrir como mínimo:
- Backend: Django, DRF, `djangorestframework-simplejwt`, PostgreSQL 16 (por qué no SQLite ni en
  tests), Redis (cache + broker), Celery (por qué async para OCR/thumbnails/IA/notificaciones),
  MinIO/boto3 (dev) vs S3 (prod), `python-decouple`, `drf-spectacular`, Sentry (gateado por
  `SENTRY_DSN`), `pytesseract`/`pdf2image` (OCR), `python-docx`/`openpyxl` (extracción Office OOXML),
  `Pillow` (thumbnails), SDK `anthropic` (análisis IA con Claude Haiku + prompt caching).
- Frontend: React + Vite + TypeScript, Tailwind + shadcn/ui, TanStack Query (por qué sobre Redux/RTK
  Query — sincronización server-state, caché, polling), Zustand (por qué sobre Context API — solo
  para `accessToken`/`user`, estado mínimo en memoria), `react-hook-form` + `zod` (formularios +
  validación), `axios` (interceptores de refresh), `react-dropzone` (upload drag&drop), `date-fns`
  (formateo de fechas).
- Testing: pytest + pytest-django + factory-boy (por qué no fixtures de Django), Vitest (frontend).
- Infra: Docker Compose, GitHub Actions, Gunicorn + Nginx.

### 4.7. Settings, configuración y variables de entorno
- Explicar el patrón de 4 capas (`base.py`, `development.py`, `test.py`, `production.py`) y por qué
  (evitar mezclar config de entornos, `CLAUDE.md` §13).
- Tabla de variables de entorno relevantes (las de `.env.example` de backend y frontend) con qué
  controla cada una y en qué archivo de settings se lee.
- Feature flags relevantes del proyecto (`AUTH_REFRESH_COOKIE_ENABLED`, `ANTHROPIC_API_KEY` como
  flag implícito, `SENTRY_DSN` como flag implícito) — qué activan y su comportamiento por defecto.

### 4.8. Testing — filosofía y convenciones
- Por qué contra PostgreSQL real y no SQLite (comportamiento de constraints/JSONB/GIN no es
  reproducible en SQLite).
- Qué se testea siempre (happy path, errores, aislamiento de tenant, permisos) y por qué ese orden.
- Cómo factory-boy reemplaza fixtures y qué gana el proyecto con eso.
- Métrica de cobertura actual y el gate de CI (`--cov-fail-under=95`).
- Referenciar `docs/manual-testing.md` para el testing manual end-to-end, sin repetir su contenido.

### 4.9. Frontend — estructura y convenciones
- Estructura de carpetas `features/{dominio}/{api,hooks,components,pages,types}` y por qué (mismo
  principio de separación de responsabilidades que el backend, adaptado a React).
- Routing: listar las rutas reales de la app (`App.tsx` o el router config) con su componente y
  protección (`ProtectedRoute`).
- Patrón de stores Zustand: por qué solo `accessToken`/`user` viven ahí y no más estado global.
- Patrón de hooks TanStack Query: query keys, invalidación, polling (OCR/thumbnail/workflow), toast
  global de errores vs `suppressGlobalToast`.
- Patrón de componentes: badges de estado (`OcrStatusBadge`, `ThumbnailStatusBadge`,
  `ExecutionStatusBadge`) como el mismo patrón repetido tres veces — explicar por qué se decidió no
  abstraerlo en un componente genérico (si esa decisión existe) o proponerlo como deuda técnica si no.

### 4.10. Flujos asíncronos completos (Celery)
Para cada pipeline async, el flujo completo con diagrama textual: qué lo dispara → qué task se
encola → qué service ejecuta → qué actualiza en DB → cómo se entera el frontend (polling):
- OCR (`process_ocr` → `ocr_service.process`) — incluir la extracción Office OOXML de Fase 6.2 y por
  qué Office legado (`.doc`/`.xls`) y `.zip` quedan en `skipped`.
- Thumbnails (`generate_thumbnail` → `thumbnail_service.generate`) — por qué solo PDF/imagen, por qué
  siempre PNG de salida (aplicar aquí el principio 9 — trade-off cuantificado JPEG vs PNG, problema
  del canal alfa, por qué la complejidad de un formato condicional no se justifica a la escala de un
  thumbnail de 400px), por qué solo la primera página de un PDF.
- Análisis IA (`analyze_document` → `ai_service.analyze`) — feature flag, prompt caching, truncado de
  input, sentinel de fallo definitivo para detener el polling del frontend.
- Notificaciones (`send_notification` → `notification_service._send`) — idempotencia con claim
  atómico, semántica at-least-once, por qué no hay estado `processing` (deuda técnica documentada).
- Limpieza de blobs huérfanos (`cleanup_orphan_blobs`) — por qué es tenant-agnóstico (única excepción
  a la regla de multi-tenancy) y por qué corre en Beat diario en vez de on-demand.

### 4.11. Búsqueda full-text
- Por qué `search_vector` con pesos A/B/C/D y `config="simple"` (sin stemming) en vez de un motor de
  búsqueda externo (Elasticsearch/Meilisearch) — trade-off de simplicidad para un portafolio.
- Cómo el signal `post_save` reconstruye el vector solo cuando cambia un campo de texto relevante.
- Cómo OCR alimenta la búsqueda automáticamente (encadenamiento `ocr_content` → signal FTS).

### 4.12. RBAC y seguridad
- Los 6 roles y su jerarquía práctica (qué puede hacer cada uno).
- Por qué las permission classes de objeto (`CanEditDocument`, etc.) NO existen como clases dedicadas
  y en su lugar se usa `HasRole(*roles)()` inline en las views — trade-off de simplicidad vs.
  DRY, y por qué el proyecto lo aceptó.
- El sistema de cookies httpOnly + CSRF double-submit de Fase 6.1: por qué se migró desde
  `localStorage`, qué vulnerabilidad cerraba (XSS robando el refresh token), cómo funciona el
  double-submit paso a paso.
- Sentry y qué datos se scrubean (`Authorization` header, bodies de `/auth/`).

### 4.13. CI/CD y despliegue (resumen navegable)
- Resumir en 1-2 páginas el pipeline de CI (jobs paralelos backend/frontend, PostgreSQL+Redis como
  servicios del runner, gates de cobertura/lint/tipos) y el pipeline de deploy (`workflow_dispatch`,
  Dockerfiles multi-stage, `docker-compose.prod.yml`, nginx, backups).
- No reescribir el detalle completo — referenciar `docs/deploy-guide.md § sección, líneas X-Y` para
  cada subtema (por qué dos stages, por qué 8 servicios, por qué TLS 1.2/1.3, etc.), ya que ese
  documento cumple el estándar de autosuficiencia por sí mismo.

### 4.14. Decisiones de diseño — el catálogo completo explicado
Tomar **todas** las decisiones numeradas en `CLAUDE.md` §17 vigentes al momento de generar este
documento (hoy son 42, probablemente más para cuando se genere) y, en vez de repetirlas como lista
plana, **integrarlas en la sección temática que les corresponda** de este documento (ej. la decisión
sobre `FOLDER_UNSET` va en la explicación del flujo de `update_document_metadata`, no en una lista
aislada). Al final de esta sección, incluir una tabla-índice que mapee cada número de decisión de
`CLAUDE.md` §17 a la sección de este documento donde fue desarrollada, para que sirva de puente entre
ambos documentos.

Para las decisiones que divergen de un patrón hermano ya establecido (mismo caso que
`ThumbnailStatus.ready` vs `OcrStatus.completed`), aplicar obligatoriamente el ángulo del "error
silencioso" del principio 8 (sección 2): deliberada-no-descuido → error concreto que previene →
por qué un agente/dev nuevo cae en él por analogía. `BITACORA.md` ya trae varias de estas listas
para minar (ver sección 3) — no limitarse a esa lista si se detectan más divergencias del mismo tipo
en el código al momento de generar.

Para las decisiones justificadas por performance/tamaño/complejidad (ej. PNG vs JPEG en thumbnails,
`config="simple"` sin stemming en FTS, cap de polling en vez de websockets), aplicar el principio 9
(sección 2): trade-off cuantificado, problema técnico concreto de la alternativa, y por qué la
complejidad extra no se justifica a la escala del proyecto. Ambos principios (8 y 9) pueden aplicarse
a la misma decisión cuando corresponda — no son mutuamente excluyentes.

### 4.15. Anti-patrones aprendidos (resumen ejecutivo)
- Resumir las categorías de `docs/ai-agent-guide.md` (TYPE_CONTRACT, REACT_STATE, MIGRATION,
  ENVELOPE, TENANT_ISOLATION, RBAC/DEAD_CODE, SOFT_DELETE, ASYNC_CELERY, POLLING, GITIGNORE, y
  cualquier categoría nueva agregada después) con 1-2 ejemplos concretos por categoría y la lección
  que deja. Referenciar `docs/ai-agent-guide.md § sección, líneas X-Y` para el detalle completo de
  cada anti-patrón.

### 4.16. Deuda técnica conocida
- Consolidar en una sola lista todas las menciones de "deuda técnica" / "pendiente" / "fuera de
  alcance" encontradas en `CLAUDE.md` §17 y en el resto de la documentación (ej. paginación de
  workflows sin conectar, thumbnail no se re-encola al subir nueva versión, notificaciones sin estado
  `processing`, `SearchPage` sin thumbnail real). Cada ítem con su razón de por qué se aceptó como
  deuda y no se resolvió.

### 4.17. Glosario
- Términos que un junior podría no conocer o que tienen un significado específico en este proyecto:
  tenant, multi-tenancy, soft delete, envelope, selector, service, presigned URL, idempotencia,
  at-least-once, feature flag, RBAC, CSRF double-submit, prompt caching, N+1, etc.

---

## 5. Formato de citas cruzadas

Usar siempre este formato exacto al referenciar otro documento o código en vez de copiar su
contenido:

```
Ver `docs/deploy-guide.md` § "Multi-stage Dockerfiles — por qué dos stages", líneas 120-165.
```

```
Ver `backend/apps/documents/services/thumbnail_service.py:45-78`.
```

Nunca usar solo el nombre del archivo sin sección/líneas. Si al momento de escribir no se puede
determinar la línea exacta (por ejemplo, porque se está describiendo un concepto disperso en todo un
archivo), decirlo explícitamente en vez de inventar un rango: "disperso en todo el archivo, ver
`archivo.py`".

---

## 6. Estilo y profundidad esperada

- Español, mismo tono que el resto de `docs/` (directo, técnico, sin relleno).
- Cada sección técnica debe poder responder a un junior que pregunta "¿pero por qué así y no de otra
  forma?" sin que el junior tenga que preguntar de nuevo.
- Usar bloques de código reales (pegados del repo, con su cita) en vez de pseudocódigo, salvo cuando
  el pseudocódigo sea estrictamente más claro para ilustrar un concepto genérico antes de aterrizarlo
  en el ejemplo real.
- Tablas para comparar alternativas (ej. "por qué Zustand y no Redux") cuando ayude a la lectura
  rápida, pero sin sacrificar la prosa explicativa alrededor.
- Diagramas: usar bloques de texto/ASCII simples (flechas `→`, cajas con `┌─┐`) para los flujos de
  request y de Celery — no depender de imágenes externas.

---

## 7. Checklist de cierre antes de dar el documento por completo

Antes de considerar terminado el documento generado, verificar:

- [ ] Cada sección de la sección 4 de este prompt está cubierta.
- [ ] Cada decisión vigente en `CLAUDE.md` §17 aparece desarrollada en alguna sección (ver tabla-índice
      de la sección 4.14).
- [ ] Cada cita a otro documento incluye sección + líneas, no solo nombre de archivo.
- [ ] Ningún número de línea fue copiado sin re-verificar contra el estado actual del repo.
- [ ] `docs/reference.md` no fue modificado como parte de esta tarea.
- [ ] El documento se puede leer de principio a fin y explicar la app completa sin abrir otro archivo,
      salvo las citas puntuales explícitas.
- [ ] Se actualizó la tabla "Archivos importantes" de `CLAUDE.md` §19 para incluir
      `docs/architecture-guide.md` (si no estaba ya listada).

---

## 8. Qué NO hacer

- No convertir `docs/reference.md` en un documento narrativo — su naturaleza de diccionario rápido no
  se toca.
- No duplicar tablas completas de `reference.md` en este documento; si hace falta mostrar una firma,
  citarla.
- No dejar afirmaciones de "por qué" sin al menos una razón concreta — si genuinamente no se conoce el
  motivo de una decisión antigua, decirlo explícitamente ("no se documentó el motivo original; se
  infiere que...") en vez de inventar una justificación.
- No generar este documento mientras queden subfases de la Fase 6 abiertas, salvo pedido explícito del
  usuario (ver sección 0).

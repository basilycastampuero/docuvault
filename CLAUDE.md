# CLAUDE.md — SasVault Project Context

> Este archivo es leído automáticamente por Claude Code al inicio de cada sesión.
> Contiene TODO el contexto necesario para trabajar en este proyecto correctamente.
> NO omitir ni ignorar ninguna sección. Leer completo antes de escribir código.

---

## 1. ¿Qué es SasVault?

SasVault es una plataforma SaaS empresarial de gestión documental y automatización de workflows. Es un **proyecto de portafolio profesional** que debe demostrar arquitectura backend seria, no un CRUD simple.

**Objetivo de portafolio:** demostrar dominio de Django, PostgreSQL avanzado, diseño REST profesional, multi-tenancy, seguridad, testing, Docker y criterio técnico de ingeniería.

Inspiración de producto: Google Drive + Notion + DocuWare, orientado a empresas.

---

## 2. Arquitectura — Reglas absolutas

### Tipo de arquitectura: Monolito Modular

**NUNCA proponer o implementar microservicios.** El proyecto es un monolito modular desacoplado por dominio. Esta es una decisión deliberada y permanente para esta etapa.

### Separación de responsabilidades — OBLIGATORIO

Cada app Django sigue esta estructura interna. **No mezclar responsabilidades bajo ningún concepto:**

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

### Regla de oro de services vs views

```python
# ✅ CORRECTO — La view solo orquesta
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

# ❌ INCORRECTO — Lógica de negocio en la view
class DocumentUploadView(APIView):
    def post(self, request):
        file = request.FILES['file']
        checksum = hashlib.sha256(file.read()).hexdigest()
        document = Document.objects.create(...)  # ← NUNCA directo desde view
        send_mail(...)  # ← NUNCA desde view
```

---

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

---

## 4. Multi-tenancy — Regla crítica

**TODA entidad principal debe tener `organization` como FK obligatoria.**

El aislamiento entre organizaciones es mediante `organization_id` en cada tabla (shared schema). No hay schemas separados por tenant.

```python
# ✅ Todo modelo principal debe verse así
class Document(BaseModel):
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='documents'
    )
    # ... resto de campos
```

**Middleware de tenant:** existe un middleware que inyecta `request.organization` en cada request autenticado. Los selectors y services SIEMPRE reciben `organization` como parámetro explícito y filtran por él. Nunca asumir organización desde contexto global.

```python
# ✅ CORRECTO
def get_documents(organization, user, filters=None):
    return Document.objects.filter(organization=organization, ...)

# ❌ INCORRECTO — nunca así
def get_documents():
    return Document.objects.all()
```

---

## 5. Modelo base — BaseModel

**TODOS los modelos deben heredar de `BaseModel`**, nunca de `models.Model` directamente.

```python
# apps/core/models/base.py
import uuid
from django.db import models

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

**NUNCA usar `.delete()` directo en estas entidades.** Usar el servicio de soft delete.

```python
# ✅ CORRECTO
document_service.soft_delete(document, deleted_by=request.user)

# ❌ INCORRECTO
document.delete()
```

---

## 6. Convenciones de base de datos

### Motor y estrategia de multi-tenancy

- **Motor:** PostgreSQL 16 — único soportado. Aprovechar features nativas: JSONB, full-text search, GIN/BRIN, arrays, CTEs, window functions. NO usar SQLite ni MySQL para ningún propósito real. Los tests también corren contra PostgreSQL real (DB `test_saasvault_db`), no SQLite en memoria.
- **Multi-tenancy:** schema único compartido. TODAS las organizaciones viven en las mismas tablas. El aislamiento se garantiza por `organization_id` en cada tabla de dominio y en cada query. NO usar schemas PostgreSQL separados por tenant. NO usar bases de datos separadas por tenant. Decisión permanente para esta etapa.
- **Implicación crítica:** una query mal escrita (sin filtro por organization) filtra datos entre tenants — vulnerabilidad de seguridad grave en SaaS empresarial. Los selectors SIEMPRE reciben `organization` como parámetro explícito y filtran por él en su query base. El middleware inyecta `request.organization` en cada request autenticado.

### Categorías de tablas

| Categoría | FK a Organization | Ejemplos |
|-----------|-------------------|----------|
| Django/Framework (no tocar) | — | `django_*`, `token_blacklist_*` |
| Raíz del tenant | NO (ella ES el tenant) | `organizations` |
| Dominio del negocio | **SÍ, obligatoria** | `documents`, `folders`, `workflows`, `audit_logs`, todo lo demás |

Toda tabla nueva del proyecto cae en "Dominio del negocio" salvo justificación documentada. La FK a `organizations` es no-nullable salvo casos extremos (logs de sistema sin user, eventos pre-autenticación).

### Nombrado

- **Tablas:** snake_case plural. Configurar SIEMPRE `db_table` explícito en `Meta` para no depender del label de la app:
  ```python
  class Meta:
      db_table = "documents"
  ```
- **Campos FK en Python:** nombre semántico del modelo en singular (`organization`, `folder`, `created_by`, `assigned_to`, `reviewed_by`). NO `organization_id` en el código — Django agrega el `_id` solo en la columna real.
- **Para FK a User:** preferir nombres por rol (`created_by`, `uploaded_by`, `approved_by`) sobre el genérico `user`.
- **Índices:** `idx_{tabla}_{campo1}[_{campo2}...]`. Para índices parciales agregar sufijo describiendo la condición: `idx_documents_org_status_alive` (filtra `deleted_at IS NULL`).
- **Constraints:** `uq_{tabla}_{campos}` para uniques compuestos, `chk_{tabla}_{regla}` para CHECK constraints.

### Estrategia de índices — obligatoria

**Reglas absolutas:**

1. Toda FK a `Organization` lleva índice — es el campo más usado en cada query del sistema.
2. Toda combinación de campos usada en `filter()` o `order_by()` lleva un **índice compuesto**, no índices separados por columna. PostgreSQL no combina índices separados de forma eficiente en tablas grandes.
3. El **orden de los campos** en el índice compuesto importa: primero el más selectivo y constante en la query (típicamente `organization`), después el que varía. Un índice `(organization, status)` sirve para queries que filtran por organization sola o por ambos; pero NO sirve para filtrar solo por status.
4. Verificar con `EXPLAIN ANALYZE` que el índice se está usando. Un índice que existe pero no se usa solo agrega costo en writes y espacio en disco.
5. NO agregar índices "por si acaso". Cada índice cuesta en cada INSERT/UPDATE.

```python
class Meta:
    db_table = "documents"
    indexes = [
        # Listado por estado dentro de una organización
        models.Index(fields=["organization", "status"], name="idx_documents_org_status"),
        # Listado cronológico dentro de una organización (DESC porque queremos los recientes primero)
        models.Index(fields=["organization", "-created_at"], name="idx_documents_org_created"),
        # Detección de duplicados por hash dentro de una org
        models.Index(fields=["organization", "checksum"], name="idx_documents_org_checksum"),
        # Full-text search (requiere django.contrib.postgres)
        GinIndex(fields=["search_vector"], name="idx_documents_search_vector"),
    ]
```

**Índice parcial para soft delete (tablas grandes):**
Cuando una tabla supera los ~100k filas y un porcentaje significativo está soft-deleted, un índice parcial mejora drásticamente las queries normales:

```python
from django.db.models import Q

models.Index(
    fields=["organization", "status"],
    name="idx_documents_org_status_alive",
    condition=Q(deleted_at__isnull=True),
)
```

### Prevención de N+1 — OBLIGATORIO en selectors

Cualquier selector que devuelva un queryset que se serializa en lista debe declarar explícitamente sus relaciones con `select_related` y `prefetch_related`. Sin esto, una respuesta de 50 documentos puede generar 150+ queries.

```python
# ❌ INCORRECTO — N+1 al serializar
def get_documents(organization):
    return Document.objects.filter(organization=organization)

# ✅ CORRECTO
def get_documents(organization):
    return (
        Document.objects
        .filter(organization=organization)
        .select_related("folder", "created_by")     # FK / OneToOne → JOIN
        .prefetch_related("tags", "versions")        # reverse FK / M2M → query extra agrupada
    )
```

| Tipo de relación | Método |
|------------------|--------|
| ForeignKey, OneToOne (hacia adelante) | `select_related` |
| Reverse ForeignKey, ManyToMany | `prefetch_related` |

### Soft delete — implicaciones para queries

`BaseModel.objects` ya filtra `deleted_at IS NULL` automáticamente. NO repetir el filtro en cada selector.

- Para acceder a registros eliminados (admin, auditoría): `Model.all_objects`.
- Para uniques que respeten soft delete: usar `UniqueConstraint` con `condition=Q(deleted_at__isnull=True)` en vez de `unique=True`. Esto permite reusar un slug/email después de eliminar el registro original.

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

**Usar JSONB para:**
- Configuración dinámica por tenant (`Organization.settings`)
- Metadata flexible que varía por instancia (`Document.metadata`, `AuditLog.metadata`)
- Snapshots de valores en auditoría (`AuditLog.old_values`, `new_values`)
- Resultados estructurados de procesamiento async (análisis IA, OCR enriquecido)

**NO usar JSONB para:**
- Datos que se filtran u ordenan en queries frecuentes → columna real con índice
- Relaciones (FKs) → tablas y FKs reales, siempre
- Listas que pueden crecer indefinidamente (historial, comments) → tabla aparte
- Datos sensibles que deben auditarse columna por columna

```python
metadata = models.JSONField(default=dict, blank=True)  # SIEMPRE default=dict, nunca None
```

**Indexar JSONB cuando se consulta frecuentemente:**

```python
from django.contrib.postgres.indexes import GinIndex

class Meta:
    indexes = [
        GinIndex(
            fields=["metadata"],
            name="idx_documents_metadata_gin",
            opclasses=["jsonb_path_ops"],  # más rápido que jsonb_ops para queries de contención
        ),
    ]
```

### Transacciones

Todo service que modifica más de una tabla DEBE envolver las operaciones en `transaction.atomic()`. La regla: si la operación falla a la mitad, la BD queda como antes de empezar.

```python
from django.db import transaction

def create_document(organization, user, file, **data) -> Document:
    with transaction.atomic():
        document = Document.objects.create(organization=organization, ...)
        DocumentVersion.objects.create(document=document, version_number=1, ...)
        audit_service.log(organization, user, document, AuditAction.CREATE, ...)
    return document
```

**Reglas:**
- NO envolver lecturas en transacciones — innecesario.
- NO usar `commit`/`rollback` manuales — siempre el context manager.
- Las tareas Celery que disparan side-effects (notificaciones, llamadas externas) van DESPUÉS del `commit`, no dentro de la transacción. Usar `transaction.on_commit(lambda: task.delay(...))`.

### Migraciones

- **Revisar SIEMPRE** la migración generada antes de aplicarla (`makemigrations` produce, `migrate` aplica). Verificar índices, defaults, on_delete, constraints.
- **NUNCA** modificar migraciones ya aplicadas en cualquier entorno. Si hay un error, crear una migración correctiva nueva.
- **Nombrar descriptivamente:** `python manage.py makemigrations --name add_document_search_vector` produce `0042_add_document_search_vector.py`, mucho mejor que `0042_auto_20260526_1830.py`.
- **Zero-downtime en producción:** evitar operaciones que bloquean tablas grandes. Para columnas nuevas NOT NULL en tablas grandes, seguir el patrón de 3 migraciones:
  1. Agregar columna como nullable
  2. Backfill async (data migration o tarea Celery)
  3. Cambiar a NOT NULL
- **Data migrations:** todo `RunPython` con `reverse_code`. Si genuinamente no es reversible, usar `migrations.RunPython.noop` y comentar por qué.

### Conexiones y performance

- `CONN_MAX_AGE = 60` reutiliza conexiones entre requests por 60s — evita overhead de TCP+auth en cada request. NO subirlo arbitrariamente: PostgreSQL tiene límite de conexiones (default 100), y con N workers × M conexiones persistentes se agota rápido.
- En producción, usar **PgBouncer** como pool externo si hay muchos workers/celery beat.
- **Objetivo de performance:** queries de listado paginado < 50ms con el dataset esperado. Profilear con `EXPLAIN ANALYZE` cualquier query del critical path antes de mergear.

### Checklist obligatorio antes de mergear una feature con DB

- [ ] Todo modelo nuevo hereda de `BaseModel` y tiene FK a `Organization` (excepto raíz)
- [ ] Todo selector recibe `organization` como parámetro explícito y filtra por él
- [ ] Hay índice en `organization_id` o compuesto que lo incluya como primer campo
- [ ] Los selectors que devuelven listas declaran `select_related`/`prefetch_related`
- [ ] Test explícito de aislamiento: crear dos orgs, verificar que org A no ve datos de org B
- [ ] Services que tocan múltiples tablas usan `transaction.atomic()`
- [ ] La migración fue revisada manualmente, no solo generada
- [ ] Para queries críticas: salida de `EXPLAIN ANALYZE` muestra uso de índice

---

## 7. API REST — Convenciones

### URL base
```
/api/v1/
```

### Estructura de URLs
```
/api/v1/auth/login/
/api/v1/auth/refresh/
/api/v1/organizations/
/api/v1/organizations/{id}/
/api/v1/documents/
/api/v1/documents/{id}/
/api/v1/documents/{id}/versions/
/api/v1/folders/
/api/v1/workflows/
/api/v1/audit-logs/
```

### Formato de respuesta — SIEMPRE este envelope

```json
// Respuesta exitosa (objeto)
{
  "data": { ... },
  "meta": {}
}

// Respuesta exitosa (lista paginada)
{
  "data": [ ... ],
  "meta": {
    "count": 100,
    "next": "http://...",
    "previous": null,
    "page": 1,
    "page_size": 20
  }
}

// Error
{
  "error": {
    "code": "DOCUMENT_NOT_FOUND",
    "message": "Document with id X does not exist",
    "details": {}
  }
}
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

### Métodos HTTP
- `GET` → lectura
- `POST` → creación
- `PATCH` → actualización parcial (preferido sobre PUT)
- `PUT` → reemplazo completo (usar solo cuando sea necesario)
- `DELETE` → eliminación (soft delete en entidades críticas)

---

## 8. Autenticación y permisos

### JWT
- Access token: vida corta (15 min en prod, 60 min en dev)
- Refresh token: vida larga (7 días), rotating
- Blacklist activado para logout real
- Claims adicionales: `organization_id`, `role`

### RBAC — Roles del sistema
```python
class UserRole(models.TextChoices):
    SUPER_ADMIN = 'super_admin'
    ORG_ADMIN = 'org_admin'
    SUPERVISOR = 'supervisor'
    EDITOR = 'editor'
    VIEWER = 'viewer'
    AUDITOR = 'auditor'
```

### Permission classes — Siempre usar estas, nunca lógica ad-hoc en views

```python
# Ejemplos de clases que deben existir en apps/permissions/
IsOrganizationMember   # Usuario pertenece a la organización del request
HasRole                # Usuario tiene al menos uno de los roles requeridos
IsDocumentOwner        # Usuario es propietario del documento
CanViewDocument        # Permiso granular de lectura
CanEditDocument        # Permiso granular de edición
CanDeleteDocument      # Permiso granular de eliminación
CanApproveDocument     # Permiso granular de aprobación
```

---

## 9. Auditoría — Crítico

**TODO evento importante debe generar un AuditLog.** Esto no es opcional.

Eventos a auditar SIEMPRE:
- Login / logout / refresh
- Creación, modificación, eliminación de documentos
- Cambios de permisos
- Cambios de estado en workflows
- Cambios de configuración de organización
- Intentos de acceso denegados

La auditoría se registra desde los **services**, nunca desde views.

```python
# ✅ CORRECTO — desde el service
def update_document(organization, user, document, **data):
    old_values = DocumentSerializer(document).data
    document = _apply_changes(document, data)
    audit_service.log(
        organization=organization,
        user=user,
        entity=document,
        action=AuditAction.UPDATE,
        old_values=old_values,
        new_values=DocumentSerializer(document).data,
    )
    return document
```

---

## 10. Variables de entorno

**NUNCA hardcodear credenciales, URLs, keys o cualquier configuración sensible.**
Usar siempre `python-decouple`:

```python
from decouple import config

SECRET_KEY = config('DJANGO_SECRET_KEY')
DEBUG = config('DJANGO_DEBUG', default=False, cast=bool)
DB_NAME = config('DB_NAME')
```

El archivo `.env` existe pero está en `.gitignore`. El archivo `.env.example` sí está en el repo.

---

## 11. Testing — Obligatorio

**Todo código nuevo debe tener tests.** No es opcional.

### Herramientas
- `pytest` + `pytest-django`
- `factory-boy` para fixtures
- NO usar `fixtures` de Django (muy frágiles)

### Convenciones de tests

```python
# Estructura de un test correcto
class TestDocumentService:
    def test_create_document_success(self, db, organization, user):
        """Should create document with correct metadata"""
        document = document_service.create_document(
            organization=organization,
            user=user,
            name="test.pdf",
            file=SimpleUploadedFile("test.pdf", b"content")
        )
        assert document.organization == organization
        assert document.created_by == user
        assert document.status == DocumentStatus.DRAFT

    def test_create_document_wrong_organization_raises(self, db, organization, other_user):
        """Should raise PermissionDenied if user not in organization"""
        with pytest.raises(PermissionDenied):
            document_service.create_document(
                organization=organization,
                user=other_user,  # usuario de otra org
                ...
            )
```

### Factories — Usar siempre

```python
# tests/factories.py
import factory
from apps.organizations.models import Organization
from apps.authentication.models import User

class OrganizationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Organization
    name = factory.Sequence(lambda n: f"Organization {n}")
    slug = factory.LazyAttribute(lambda o: o.name.lower().replace(' ', '-'))

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    organization = factory.SubFactory(OrganizationFactory)
```

### Qué testear siempre
1. Happy path del service
2. Casos de error esperados (wrong org, missing permission, invalid data)
3. Aislamiento de tenant (una org no puede acceder a datos de otra)
4. Endpoints de la API (status codes, formato de respuesta)
5. Permisos (autenticado vs no autenticado, rol correcto vs incorrecto)

---

## 12. Tareas Celery

Las tareas async se definen en `apps/{app}/tasks/`. Nunca lógica de negocio dentro de la tarea — llamar a services:

```python
# ✅ CORRECTO
@shared_task
def process_document_ocr(document_id: str):
    document = Document.objects.get(id=document_id)
    ocr_service.process(document)  # lógica en el service

# ❌ INCORRECTO — lógica directa en la task
@shared_task
def process_document_ocr(document_id: str):
    document = Document.objects.get(id=document_id)
    image = Image.open(...)
    text = pytesseract.image_to_string(...)
    document.ocr_content = text
    document.save()
```

---

## 13. Configuración Django — Settings en capas

```
backend/config/settings/
  __init__.py
  base.py         ← Configuración común a todos los entornos
  development.py  ← Configuración local (DEBUG=True, etc.)
  test.py         ← Configuración para pytest
  production.py   ← Configuración de producción
```

La variable `DJANGO_SETTINGS_MODULE` controla cuál se usa:
- Local: `config.settings.development`
- Tests: `config.settings.test`
- Prod: `config.settings.production`

---

## 14. Código — Reglas de estilo

- **Formateo:** black (línea máx 88 chars)
- **Imports:** isort con profile black
- **Type hints:** obligatorios en signatures de services y selectors
- **Docstrings:** en services y selectors, una línea describiendo qué hace
- **Comentarios:** solo cuando el código no se explica solo. No comentar lo obvio.
- **Nombres:** descriptivos en inglés. Sin abreviaturas raras.

```python
# ✅ CORRECTO
def get_documents_by_folder(
    organization: Organization,
    folder: Folder,
    user: User,
    include_deleted: bool = False,
) -> QuerySet:
    """Return documents inside a folder visible to the given user."""
    qs = Document.objects.filter(organization=organization, folder=folder)
    if not include_deleted:
        qs = qs.filter(deleted_at__isnull=True)
    return qs

# ❌ INCORRECTO
def get_docs(org, f, u, d=False):
    return Document.objects.filter(org=org, folder=f)
```

---

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
feature/{name} ← Una feature por rama (ej: feature/jwt-authentication)
fix/{name}    ← Corrección de bugs
```

### Flujo de trabajo
1. Crear rama desde `develop`: `git checkout -b feature/nombre`
2. Commits pequeños y descriptivos durante el desarrollo
3. PR hacia `develop` cuando la feature está completa con tests
4. `main` solo recibe merges de `develop` cuando hay versión estable

---

## 16. Lo que NUNCA hacer en este proyecto

- ❌ Lógica de negocio en views
- ❌ Queries directas a DB desde views (`Model.objects.filter()` en views)
- ❌ Hardcodear cualquier credencial, URL o secret
- ❌ Eliminar físicamente entidades críticas sin usar soft delete
- ❌ Crear modelos sin heredar de `BaseModel`
- ❌ Crear modelos de entidades principales sin `organization` FK
- ❌ Omitir tests para lógica de negocio nueva
- ❌ Mezclar settings de entornos
- ❌ Guardar archivos binarios en PostgreSQL
- ❌ Commits con mensajes como "fix", "update", "changes"
- ❌ Proponer microservicios
- ❌ Usar `print()` para debugging (usar `logging`)
- ❌ Modificar migraciones ya aplicadas

---

## 17. Estado actual del proyecto

**Fase actual:** Fase 4 EN CURSO. 4.0 (pre-flight) COMPLETA; siguiente: 4.1.
Fase 3 COMPLETA (3.1 + 3.2 + 3.3 + auditoría de fase).

**Completado:**
- [x] **Fase 0** — Setup completo: WSL2, Docker Compose (PG16 + Redis7 + MinIO),
      pre-commit hooks, .env.example, estructura de carpetas
- [x] **Fase 1.1** — Django + settings en 4 capas (base/development/test/production)
- [x] **Fase 1.2** — Core app: BaseModel (UUID, soft delete con `db_index` en
      `deleted_at`), SoftDeleteManager, ApplicationError + handler, StandardPagination
- [x] **Fase 1.3** — Organizations: modelo, service, selector, API, tests
- [x] **Fase 1.4** — Authentication: User custom (AbstractBaseUser),
      JWT con claims personalizados (organization_id, role, email),
      OrganizationTenantMiddleware, endpoints auth
- [x] **Fase 1.5** — RBAC: IsOrganizationMember, HasRole (class factory), IsOrgAdmin,
      IsSuperAdmin
- [x] **Fase 1.6** — Gestión de usuarios dentro de la organización
- [x] **Fase 2.0** — Skeletons de `apps/audit` y `apps/documents` registrados en
      INSTALLED_APPS; constantes `MAX_UPLOAD_SIZE` y `ALLOWED_UPLOAD_MIME_TYPES`
      en settings; `config/celery.py` wired up (necesario para `TASK_ALWAYS_EAGER`)
- [x] **Fase 2.1** — `AuditLog` inmutable (BigAutoField, NO hereda BaseModel,
      append-only), `audit_service.log()` llamado desde todos los services críticos
- [x] **Fase 2.2** — Modelos `Folder`, `Document`, `DocumentVersion` con índices
      compuestos, GIN (search_vector, metadata, tags), soft delete y UniqueConstraint
      condicionales (deleted_at IS NULL)
- [x] **Fase 2.3** — `FileValidator` (detección MIME real por magic bytes via
      python-magic, SHA-256 checksum, límite 50 MB); `StorageService` (boto3/MinIO,
      presigned URLs, `ensure_bucket`); comando `init_storage`
- [x] **Fase 2.4** — `FolderService` (create/rename/move con detección de ciclos,
      validación de tenant, soft delete con guard de hijos/documentos vivos);
      `FolderSelector` (N+1 verificado con `select_related`)
- [x] **Fase 2.5** — `DocumentService` (create con `transaction.atomic` + OCR stub
      via `transaction.on_commit`; versioning; metadata update; status lock
      draft ↔ under_review; soft delete sin borrar storage);
      `DocumentSelector` (filtros por folder/status/tags/search, N+1 verificado)
- [x] **Fase 2.6** — REST endpoints `/api/v1/folders/` y `/api/v1/documents/`
      con RBAC (Editor+ para escrituras, cualquier miembro para lecturas),
      envelope `{data, meta}`, paginación, serializers separados por operación
- [x] **Fase 3.1** — Capa de lectura de auditoría: `AuditLogSelector`,
      `AuditLogFilter` (django-filter: action, entity_type, entity_id, user, rango de
      fechas), API solo-lectura `GET /api/v1/audit-logs/` y `/{id}/` (PK entera
      `<int:log_id>`), permiso `CanReadAuditLogs` (auditor/org_admin/super_admin).
      Leer logs no se audita. POST/PATCH/DELETE → 405.
- [x] **Fase 3.2** — Motor de Workflows: modelos `WorkflowTemplate`, `WorkflowStep`,
      `WorkflowExecution`, `WorkflowStepLog` (todos BaseModel); `workflow_service`
      (create/update/soft_delete template, start, advance approve/reject/comment,
      reject, cancel); `WorkflowSelector` (N+1-safe); API `/api/v1/workflows/`
      (templates + executions + advance + logs). **Desbloquea `approved`/`rejected`
      de `Document.status`**: el workflow escribe el status directamente (el guard
      manual de `change_document_status` de Fase 2 sigue intacto). Validación de rol
      por paso en el service. Una sola ejecución activa por documento.
      `ENUM_NAME_OVERRIDES` añadido para mantener drf-spectacular en 0 warnings.
- [x] **Fase 3.3** — Full-Text Search nativo de PostgreSQL: signal `post_save` que
      puebla `Document.search_vector` con pesos A/B/C/D (name/description/tags/
      ocr_content), `config="simple"`; `SearchSelector` con `SearchQuery(websearch)`
      + `SearchRank` sobre el índice GIN; endpoint `GET /api/v1/search/?q=&folder=&status=`
      con envelope, paginación y `IsOrganizationMember`; data migration de backfill.
      `DocumentStatusEnum` añadido a `ENUM_NAME_OVERRIDES`.
- [x] **Auditoría de Fase 3** — corregidos 3 hallazgos: (1) race condition de "una
      ejecución activa por documento" → `UniqueConstraint` parcial + IntegrityError→409;
      (2) `advance_step` sin lock → `select_for_update(of=self)`; (3) listados de
      workflows sin paginar → `StandardPagination`. Ver `docs/phase-plan.md` §3.3.
- [x] drf-spectacular configurado y operativo (0 errors / 0 warnings)
- [x] Documentación API (Swagger UI en `/api/docs/`, Redoc en `/api/redoc/`)

**Métricas:** 394 tests pasando, cobertura 98% (Fase 3 completa + auditoría, 2026-05-31).
Nota: los tests requieren PostgreSQL real corriendo (`docker compose up -d`); si falla
con `connection refused` en `localhost:5432`, la infra está apagada — no es un fallo
de código.

**Apps activas en INSTALLED_APPS:**
`apps.core`, `apps.organizations`, `apps.authentication`, `apps.permissions`,
`apps.audit`, `apps.documents`, `apps.workflows`, `apps.search`

**Decisiones de diseño cerradas de Fase 2 (ya implementadas, no re-discutir):**
1. `AuditLog` usa `BigAutoField` (no UUID) y NO hereda `BaseModel` — inmutable,
   append-only, consultado cronológicamente.
2. Tests de `StorageService` son mockeados (boto3 via monkeypatch). Integración
   real con MinIO se añade en Fase 4.
3. `Document.status` acepta 5 valores pero solo `draft ↔ under_review` se permiten
   manualmente. `approved`/`rejected` se habilitan vía `WorkflowExecution` (Fase 3.2,
   ya implementado).
4. Tarea `process_ocr` existe como stub vacío; cuerpo real en Fase 4.2.
5. El blob en MinIO NO se borra al soft-delete un documento. Cleanup en Fase 4.

**Decisiones de diseño cerradas de Fase 3 (ya implementadas, no re-discutir):**
6. API de auditoría es solo-lectura; leer audit logs NO genera un audit log.
7. Modelos de workflows heredan `BaseModel` (incluido `WorkflowStepLog`); NO se
   replica el patrón inmutable de `AuditLog` — son dato de dominio.
8. `workflow_service` escribe `Document.status` directamente (helper
   `_set_document_status`), saltándose el guard manual de `change_document_status`.
   Es la ÚNICA vía privilegiada a `approved`/`rejected`. El guard manual sigue intacto.
9. Un documento solo puede tener UNA ejecución activa (`pending`/`in_progress`) a la
   vez. **Respaldado a nivel de DB** por el `UniqueConstraint` parcial
   `uq_wf_exec_one_active_per_document` (corrección de la auditoría de Fase 3); el
   `.exists()` del service queda como fast-path. El rol requerido por paso se valida en
   el service; ORG_ADMIN/SUPER_ADMIN pueden actuar sobre cualquier paso (override).
10. `config`/`actions` (JSONB en template/step) se persisten pero NO se interpretan
    hasta Fase 4 (notificaciones, side-effects automáticos).
11. **FTS usa `config="simple"`** (sin stemming) — deliberado para corpus multi-tenant
    ES/EN. El `search_vector` se reconstruye vía signal `post_save` SOLO cuando cambia
    un campo de texto (name/description/tags/ocr_content). `bulk_create` saltaría el
    signal (caveat para el OCR async de Fase 4).

**Decisiones de diseño cerradas de Fase 4 (PLANIFICADAS, aún no implementadas — ver
`docs/phase-plan.md` §4):**
12. OCR cubre **solo PDF + imágenes** (Tesseract). Office (docx/xlsx/zip) → `ocr_status =
    skipped`. Extracción de texto de Office = trabajo futuro.
13. **`ocr_status` es columna real** (CharField + choices: pending/processing/completed/
    failed/skipped), default `pending`. Sin re-OCR masivo automático de docs existentes.
14. **El OCR alimenta la búsqueda automáticamente:** `ocr_service` guarda `ocr_content`
    con `update_fields`, lo que dispara el signal de FTS y reconstruye `search_vector`.
    Sin código extra de indexación.
15. **Tareas llaman a services** (CLAUDE.md §12): `process_ocr` es fino, la lógica vive en
    `ocr_service`. Reintentos `autoretry_for=(TransientError,)`; idempotente.
16. **`cleanup_orphan_blobs`** (Beat diario) mira `Document` Y `DocumentVersion`, con
    período de gracia para no borrar uploads en vuelo. Cierra la deuda de Fase 2 (#5).
17. Dev corre worker+beat en **venv** (no docker); `CELERY_BEAT_SCHEDULE` **estático**.
18. OCR completion auditado con `UPDATE` + `metadata={"via":"ocr"}` (sin nuevo enum).
19. **IA (4.4) opcional**, Haiku 4.5, prompt caching, `ANTHROPIC_API_KEY` por env
    (feature-off si falta). Notificaciones y thumbnails → Fase 5.
20. Falta antes de empezar: `pip` (`pytesseract`, `pdf2image`) + `apt`
    (`tesseract-ocr tesseract-ocr-spa poppler-utils`) + `StorageService.download_file()`.

**4.0 (pre-flight) COMPLETA (2026-06-02, rama `feature/celery-ocr-pipeline`):** deps pip
fijadas (`pdf2image`, `pytesseract`); `StorageService.download_file()` + test; settings
OCR (`OCR_LANGUAGES`, `OCR_PDF_DPI`) y Celery (retry delay/max, `CELERY_BEAT_SCHEDULE={}`,
`CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP`); `.env.example` actualizado. Worker real
verificado contra Redis ejecutando el stub `process_ocr`. 395 tests, 99%. **Pendiente del
usuario:** instalar los binarios apt (no bloquean 4.1; requeridos para el OCR real de 4.2).

**Próximo paso:** Fase 4.1 (reintentos/idempotencia de Celery), luego 4.2 (`ocr_service` +
`ocr_status` + endpoint re-OCR), 4.3 (`cleanup_orphan_blobs`), y 4.4 IA opcional al final.
Ver `docs/phase-plan.md` §4 para el plan detallado con DoD por sub-fase.

Ver `docs/phase-plan.md` para el plan completo de desarrollo.

---

## 18. Cómo correr el proyecto localmente

```bash
# 1. Activar entorno virtual
source backend/.venv/bin/activate

# 2. Levantar servicios de infraestructura
docker compose up -d

# 3. Correr Django
cd backend
python manage.py runserver

# 4. Correr tests
pytest

# 5. Celery worker (terminal separada)
celery -A config.celery worker --loglevel=info

# 6. Verificar que servicios están sanos
docker compose ps
```

---

## 19. Archivos importantes del proyecto

| Archivo | Propósito |
|---------|-----------|
| `CLAUDE.md` | Este archivo — contexto para Claude Code |
| `docker-compose.yml` | Servicios de infraestructura local |
| `backend/.env` | Variables de entorno (NO en git) |
| `backend/.env.example` | Template de variables (SÍ en git) |
| `backend/requirements.txt` | Dependencias Python fijadas |
| `backend/pyproject.toml` | Config de black e isort |
| `backend/.flake8` | Config de flake8 |
| `.pre-commit-config.yaml` | Hooks de calidad de código |
| `docs/phase-plan.md` | Plan de desarrollo por fases |
| `docs/api-conventions.md` | Convenciones REST detalladas |
| `docs/coding-patterns.md` | Patrones de código con ejemplos |
| `docs/database-conventions.md` | Convenciones de base de datos |

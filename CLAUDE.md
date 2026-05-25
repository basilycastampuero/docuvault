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

### Nombrado
- Tablas: snake_case plural (`documents`, `audit_logs`, `workflow_steps`)
- Campos FK: `{modelo}_id` o `{modelo}` con nombre descriptivo
- Índices: `idx_{tabla}_{campo(s)}`

### Índices obligatorios
Siempre agregar índice en:
- `organization_id` en toda tabla con FK a Organization
- Campos usados frecuentemente en `filter()` o `order_by()`
- Campos usados en búsqueda (GIN para full-text)

```python
class Meta:
    indexes = [
        models.Index(fields=['organization', 'status'], name='idx_documents_org_status'),
        models.Index(fields=['organization', 'created_at'], name='idx_documents_org_created'),
    ]
```

### Campos JSONB
Usar para: metadata flexible, configuración dinámica, valores old/new en auditoría.

```python
metadata = models.JSONField(default=dict, blank=True)
```

### Migraciones
- Siempre revisar la migración generada antes de aplicar
- Nunca modificar migraciones ya aplicadas
- Nombrar migraciones descriptivamente cuando sea posible

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

**Fase actual:** 0 — Setup y configuración de entorno

**Completado:**
- [ ] Estructura de carpetas creada
- [ ] Docker Compose (PostgreSQL, Redis, MinIO)
- [ ] Pre-commit hooks configurados
- [ ] .gitignore y README profesionales
- [ ] Variables de entorno (.env / .env.example)

**Próximo paso:** Fase 1 — Inicializar Django y configurar settings en capas

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

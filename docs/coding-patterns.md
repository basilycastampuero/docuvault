# docs/coding-patterns.md — Patrones de Código SasVault

> Referencia de patrones con ejemplos concretos extraídos del código real.
> Claude Code debe seguir estos patrones en TODO el código del proyecto.

---

## 1. Patrón Services / Selectors

### ¿Por qué?

Las views en Django/DRF tienden a convertirse en el basurero de toda la lógica. Este patrón mantiene la lógica de negocio aislada, testeable y reutilizable.

- **Service:** modifica estado (escribe en DB, llama APIs, dispara tasks)
- **Selector:** solo lee (queries, filtros, agregaciones)
- **View:** orquesta (llama service/selector, serializa, retorna respuesta HTTP)

### Service — ejemplo real (`document_service.py`)

```python
# apps/documents/services/document_service.py
import logging
from typing import IO, TYPE_CHECKING

from django.db import transaction

from apps.audit.models import AuditAction
from apps.audit.services import audit_service
from apps.core.exceptions import ConflictError, PermissionDenied
from apps.documents.models import Document, DocumentStatus, DocumentVersion, Folder
from apps.documents.storage import StorageService, validate_file
from apps.documents.tasks.document_tasks import process_ocr

if TYPE_CHECKING:
    from apps.authentication.models import User
    from apps.organizations.models import Organization

logger = logging.getLogger(__name__)


@transaction.atomic
def create_document(
    organization: "Organization",
    user: "User",
    file: IO[bytes],
    name: str,
    folder: Folder | None = None,
    description: str = "",
    tags: list[str] | None = None,
) -> Document:
    """Upload a file and create a Document with its initial DocumentVersion."""
    if folder is not None and folder.organization_id != organization.pk:
        raise PermissionDenied("Folder does not belong to this organization.")

    mime_type, file_size, checksum = validate_file(file)

    doc = Document.objects.create(
        organization=organization,
        folder=folder,
        name=name,
        description=description,
        mime_type=mime_type,
        file_size=file_size,
        checksum=checksum,
        storage_path="",          # temporal hasta confirmar el upload
        status=DocumentStatus.DRAFT,
        version=1,
        created_by=user,
        tags=tags or [],
    )

    storage = StorageService()
    path = StorageService.build_storage_path(str(organization.id), str(doc.id), name)
    storage.upload_file(file, path, content_type=mime_type)
    doc.storage_path = path
    doc.save(update_fields=["storage_path", "updated_at"])

    DocumentVersion.objects.create(
        document=doc,
        version_number=1,
        storage_path=path,
        file_size=file_size,
        checksum=checksum,
        mime_type=mime_type,
        created_by=user,
        change_description="Initial version",
    )

    audit_service.log(
        organization=organization,
        user=user,
        entity_type="document",
        entity_id=str(doc.id),
        action=AuditAction.CREATE,
        new_values={"name": name, "mime_type": mime_type, "file_size": file_size},
    )

    # El task se encola DESPUÉS del commit para evitar que se procese
    # antes de que exista el registro en DB.
    transaction.on_commit(lambda: process_ocr.delay(str(doc.id)))
    return doc
```

**Regla crítica:** `transaction.on_commit()` para side-effects async. Si el task se lanzara dentro de la transacción y esta hiciera rollback, el worker intentaría procesar un documento que no existe.

### Selector — ejemplo real (`document_selector.py`)

```python
# apps/documents/selectors/document_selector.py
import uuid
from typing import TYPE_CHECKING

from apps.core.exceptions import NotFound
from apps.documents.models import Document, DocumentStatus, DocumentVersion

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from apps.organizations.models import Organization


def get_document_by_id(
    organization: "Organization", document_id: str | uuid.UUID
) -> Document:
    """Return a document by id scoped to the organization. Raises NotFound otherwise."""
    try:
        return Document.objects.select_related("folder", "created_by").get(
            id=document_id, organization=organization
        )
    except Document.DoesNotExist:
        raise NotFound(f"Document {document_id} not found.")


def get_documents(
    organization: "Organization",
    folder=None,
    status: DocumentStatus | None = None,
    tags: list[str] | None = None,
    search: str | None = None,
) -> "QuerySet[Document]":
    """Return a filtered queryset of documents for the organization."""
    qs = (
        Document.objects.filter(organization=organization)
        .select_related("folder", "created_by")  # evita N+1
        .order_by("-created_at")
    )
    if folder is not None:
        qs = qs.filter(folder=folder)
    if status is not None:
        qs = qs.filter(status=status)
    if tags:
        qs = qs.filter(tags__overlap=tags)  # ArrayField overlap
    if search:
        qs = qs.filter(name__icontains=search)  # FTS real en Fase 3.3
    return qs
```

**Regla:** todo selector que devuelve una lista debe declarar `select_related` / `prefetch_related`. Sin esto, serializar 50 documentos genera 150+ queries.

### View — ejemplo real (`views.py`)

```python
# apps/documents/api/views.py
from rest_framework.views import APIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status

from apps.core.pagination import StandardPagination
from apps.documents.api.serializers import DocumentSerializer, DocumentUploadSerializer
from apps.documents.selectors import get_document_by_id, get_documents
from apps.documents.services import document_service
from apps.permissions.permissions import IsOrganizationMember


class DocumentListCreateView(APIView):
    permission_classes = [IsOrganizationMember]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request: Request) -> Response:
        qs = get_documents(
            organization=request.organization,
            status=request.query_params.get("status"),
            search=request.query_params.get("search"),
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = DocumentSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request: Request) -> Response:
        serializer = DocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        doc = document_service.create_document(
            organization=request.organization,
            user=request.user,
            **serializer.validated_data,
        )
        return Response({"data": DocumentSerializer(doc).data}, status=status.HTTP_201_CREATED)
```

**Regla:** la view nunca llama a `Model.objects.*` directamente. Solo orquesta entre serializers, selectors y services.

---

## 2. Patrón BaseModel

El código real está en `apps/core/models/base.py`. Puntos clave:

```python
class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = SoftDeleteManager()       # excluye deleted_at IS NOT NULL (default)
    all_objects = AllObjectsManager()   # incluye todos — usar solo en admin/auditoría

    class Meta:
        abstract = True

    def soft_delete(self) -> None:
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])
```

**Reglas de uso:**
- Todo modelo de dominio hereda de `BaseModel`. Nunca de `models.Model` directamente.
- `AuditLog` es la única excepción: no hereda de `BaseModel` porque es inmutable (sin `updated_at`, sin `deleted_at`).
- Para soft delete en entidades críticas: `document_service.soft_delete_document(...)`, nunca `.delete()` directo.
- `Model.objects` ya filtra `deleted_at IS NULL`. No repetir el filtro en selectors.
- Para acceder a registros eliminados: `Model.all_objects.filter(...)`.

---

## 3. Patrón Permission Classes

```python
# apps/permissions/permissions.py
from rest_framework.permissions import BasePermission
from apps.authentication.models import UserRole


class IsOrganizationMember(BasePermission):
    """
    Requiere OrganizationTenantMiddleware (inyecta request.organization).
    Verifica que el usuario pertenezca a la organización del request.
    """
    message = "You are not a member of this organization."

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if request.organization is None:
            return False
        return request.user.organization_id == request.organization.id


def HasRole(*roles: str):
    """
    Class factory. Devuelve una clase de permiso para los roles dados.

    Uso: permission_classes = [IsOrganizationMember, HasRole(UserRole.ORG_ADMIN)]
    O en código: HasRole("org_admin", "supervisor", "editor")()
    """
    class _HasRole(BasePermission):
        required_roles = roles
        message = f"Required role: {', '.join(roles)}."

        def has_permission(self, request, view) -> bool:
            if not request.user or not request.user.is_authenticated:
                return False
            return request.user.role in self.required_roles

    _HasRole.__name__ = f"HasRole({', '.join(roles)})"
    return _HasRole


# Atajos de uso frecuente
IsSuperAdmin = HasRole(UserRole.SUPER_ADMIN)
IsOrgAdmin = HasRole(UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN)
```

**Importante:** `HasRole(...)` retorna una **clase**, no una instancia. Para usarlo fuera de `permission_classes`:

```python
# ✅ Correcto — instanciar con ()
perm = HasRole("org_admin", "editor")()
if not perm.has_permission(request, None):
    raise PermissionDenied()

# ❌ Incorrecto — HasRole(...) es una clase, no una instancia
perm = HasRole("org_admin", "editor")
perm.has_permission(request, None)  # TypeError
```

---

## 4. Patrón de Tests con factory-boy

Las factories están en `apps/{app}/tests/factories.py` de cada app. Ejemplo real:

```python
# apps/documents/tests/factories.py
import factory
from apps.authentication.tests.factories import UserFactory
from apps.documents.models import Document, DocumentStatus, DocumentVersion, Folder
from apps.organizations.tests.factories import OrganizationFactory


class FolderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Folder

    organization = factory.SubFactory(OrganizationFactory)
    name = factory.Sequence(lambda n: f"Folder {n}")
    parent = None
    owner = factory.SubFactory(UserFactory)


class DocumentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Document

    organization = factory.SubFactory(OrganizationFactory)
    name = factory.Sequence(lambda n: f"document_{n}.pdf")
    mime_type = "application/pdf"
    file_size = 1024
    checksum = factory.Sequence(lambda n: f"{'a' * 63}{n}"[:64])
    storage_path = factory.Sequence(lambda n: f"org/2026/01/{n}/file.pdf")
    status = DocumentStatus.DRAFT
    version = 1
    created_by = factory.SubFactory(UserFactory)
    tags = factory.LazyFunction(list)
    metadata = factory.LazyFunction(dict)
```

Test completo con mock de StorageService:

```python
# apps/documents/tests/test_document_service.py
import io
from unittest.mock import MagicMock, patch
import pytest

from apps.audit.models import AuditAction, AuditLog
from apps.authentication.tests.factories import UserFactory
from apps.core.exceptions import PermissionDenied
from apps.documents.models import Document, DocumentStatus, DocumentVersion
from apps.documents.services.document_service import create_document
from apps.documents.storage.storage_service import StorageService as RealStorageService
from apps.organizations.tests.factories import OrganizationFactory

PDF_HEADER = b"%PDF-1.4\n" + b"%" * 100


@pytest.fixture
def mock_storage(monkeypatch):
    """Mockea StorageService sin tocar MinIO."""
    mock_instance = MagicMock()
    mock_instance.upload_file.return_value = "org/2026/01/doc/file.pdf"
    mock_class = MagicMock()
    mock_class.return_value = mock_instance
    # Preservar el método estático — si no, build_storage_path devuelve MagicMock
    mock_class.build_storage_path = RealStorageService.build_storage_path
    monkeypatch.setattr(
        "apps.documents.services.document_service.StorageService", mock_class
    )
    return mock_instance


@pytest.mark.django_db(transaction=True)
class TestCreateDocument:
    def test_creates_document_with_version(self, mock_storage):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        doc = create_document(
            organization=org,
            user=user,
            file=io.BytesIO(PDF_HEADER + b"content"),
            name="report.pdf",
        )
        assert doc.status == DocumentStatus.DRAFT
        assert doc.version == 1
        assert DocumentVersion.objects.filter(document=doc, version_number=1).exists()

    def test_storage_failure_rolls_back_document(self, mock_storage):
        """Si storage.upload_file falla, la transacción revierte el Document."""
        mock_storage.upload_file.side_effect = RuntimeError("S3 timeout")
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        with pytest.raises(RuntimeError):
            create_document(
                organization=org,
                user=user,
                file=io.BytesIO(PDF_HEADER + b"x"),
                name="fail.pdf",
            )
        assert Document.objects.filter(organization=org).count() == 0

    def test_rejects_folder_from_other_org(self, mock_storage):
        from .factories import FolderFactory
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()
        user = UserFactory(organization=org1)
        folder = FolderFactory(organization=org2)
        with pytest.raises(PermissionDenied):
            create_document(
                organization=org1, user=user,
                file=io.BytesIO(PDF_HEADER), name="x.pdf",
                folder=folder,
            )

    def test_on_commit_dispatches_ocr(self, mock_storage):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        with patch("apps.documents.services.document_service.process_ocr.delay") as mock_delay:
            doc = create_document(
                organization=org, user=user,
                file=io.BytesIO(PDF_HEADER), name="b.pdf",
            )
            mock_delay.assert_called_once_with(str(doc.id))
```

**Notas del patrón de mock:**
- `mock_class.build_storage_path = RealStorageService.build_storage_path` es obligatorio — `MagicMock()` elimina los métodos estáticos.
- Tests con `@django_db(transaction=True)` son necesarios cuando se prueba `transaction.on_commit()`. En modo sin transacción real, `on_commit` se ejecuta inmediatamente.
- El mock se aplica sobre el **path de importación en el módulo del service** (`apps.documents.services.document_service.StorageService`), no sobre el path de definición.

---

## 5. Patrón Serializers

Dos tipos según el sentido del dato:

```python
# apps/documents/api/serializers.py
from rest_framework import serializers
from apps.documents.models import Document, DocumentStatus, DocumentVersion


class DocumentSerializer(serializers.ModelSerializer):
    """Serializer de LECTURA — para respuestas. Todos los campos son read_only."""
    folder_name = serializers.CharField(source="folder.name", read_only=True, allow_null=True)
    created_by_email = serializers.CharField(source="created_by.email", read_only=True)

    class Meta:
        model = Document
        fields = [
            "id", "name", "description", "mime_type", "file_size", "checksum",
            "status", "version", "tags", "metadata",
            "folder", "folder_name", "created_by_email",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "mime_type", "file_size", "checksum", "version",
                            "folder_name", "created_by_email", "created_at", "updated_at"]


class DocumentUploadSerializer(serializers.Serializer):
    """Serializer de ESCRITURA — solo valida entrada. No tiene Meta ni modelo."""
    file = serializers.FileField()
    name = serializers.CharField(max_length=255)
    folder_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        default=list,
    )


class DocumentMetadataUpdateSerializer(serializers.Serializer):
    """Solo expone los campos que se pueden editar manualmente en Fase 2."""
    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(allow_blank=True, required=False)
    tags = serializers.ListField(child=serializers.CharField(max_length=50), required=False)
    # Status limitado: approved/rejected requieren WorkflowExecution (Fase 3.2)
    status = serializers.ChoiceField(
        choices=[DocumentStatus.DRAFT, DocumentStatus.UNDER_REVIEW],
        required=False,
    )
```

**Regla:** separar siempre serializer de lectura (ModelSerializer) de serializer de escritura (Serializer plano). Nunca usar el mismo para ambos sentidos.

---

## 6. Patrón Celery Tasks

```python
# apps/documents/tasks/document_tasks.py
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def process_ocr(document_id: str) -> None:
    """OCR stub — body implemented in Phase 4.2."""
    logger.info("OCR stub invoked for document %s", document_id)
```

**Reglas:**
- Usar `@shared_task` (no `@app.task`): funciona con cualquier app Celery sin import circular.
- Nunca poner lógica de negocio en la tarea. Llamar a un service:
  ```python
  @shared_task
  def process_ocr(document_id: str) -> None:
      from apps.documents.services import ocr_service  # import lazy — evita ciclos
      document = Document.objects.get(id=document_id)
      ocr_service.process(document)
  ```
- Las tareas se definen en `apps/{app}/tasks/{nombre}_tasks.py`.
- Se disparan desde services vía `transaction.on_commit(lambda: task.delay(id))`.
- **NUNCA** disparar tasks directamente desde views o dentro de una transacción activa.

---

## 7. Patrón de respuesta de errores

Todas las excepciones se transforman al envelope `{error: {code, message, details}}` por `custom_exception_handler` en `apps/core/exceptions.py`.

```python
# Uso en services/selectors
from apps.core.exceptions import (
    NotFound,
    PermissionDenied,
    ValidationError,
    ConflictError,
)

# NotFound — el recurso no existe o no pertenece a la org
raise NotFound(f"Document {document_id} not found.")

# PermissionDenied — el usuario no tiene acceso
raise PermissionDenied("Folder does not belong to this organization.")

# ValidationError — entrada inválida con detalles opcionales
raise ValidationError(
    message="File type 'application/x-msdownload' is not allowed.",
    code="INVALID_MIME_TYPE",
)

# ConflictError — conflicto de estado (no se puede borrar, transición inválida)
raise ConflictError(
    message="Cannot transition from 'draft' to 'approved' manually.",
    code="INVALID_STATUS_TRANSITION",
)
```

Respuesta HTTP resultante (ejemplo NotFound):
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Document abc-123 not found.",
    "details": {}
  }
}
```

**Mapa de excepciones → HTTP:**
| Excepción | HTTP | Cuándo usar |
|-----------|------|-------------|
| `NotFound` | 404 | Recurso no existe o no pertenece a la org |
| `PermissionDenied` | 403 | Sin permisos (RBAC o tenant) |
| `ValidationError` | 400 | Datos de entrada inválidos |
| `ConflictError` | 409 | Estado incompatible (tiene hijos, status inválido) |

---

## 8. AuditLog — cómo registrar eventos

Llamar siempre desde **services**, nunca desde views.

```python
from apps.audit.models import AuditAction
from apps.audit.services import audit_service

# Crear
audit_service.log(
    organization=organization,
    user=user,
    entity_type="document",
    entity_id=str(document.id),
    action=AuditAction.CREATE,
    new_values={"name": "report.pdf", "mime_type": "application/pdf"},
)

# Actualizar con old/new values
audit_service.log(
    organization=organization,
    user=user,
    entity_type="document",
    entity_id=str(document.id),
    action=AuditAction.UPDATE,
    old_values={"name": "old.pdf"},
    new_values={"name": "new.pdf"},
)

# Con request (captura IP y user-agent)
audit_service.log(
    organization=organization,
    user=user,
    entity_type="user",
    entity_id=str(user.id),
    action=AuditAction.LOGIN,
    request=request,
)
```

**Acciones disponibles:** `CREATE`, `UPDATE`, `DELETE`, `RESTORE`, `VIEW`, `DOWNLOAD`, `STATUS_CHANGE`, `LOGIN`, `LOGOUT`, `PERMISSION_DENIED`.

**Regla:** `AuditLog` es inmutable. Nunca llamar `.save()` sobre un log existente ni `.delete()`. El modelo lanza `RuntimeError` si se intenta.

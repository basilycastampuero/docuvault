# docs/coding-patterns.md — Patrones de Código DocuVault

> Referencia de patrones con ejemplos concretos.
> Claude Code debe seguir estos patrones en TODO el código del proyecto.

---

## 1. Patrón Services / Selectors

### ¿Por qué?

Las views en Django/DRF tienden a convertirse en el basurero de toda la lógica. Este patrón mantiene la lógica de negocio aislada, testeable y reutilizable.

- **Service:** modifica estado (escribe en DB, llama APIs, dispara tasks)
- **Selector:** solo lee (queries, filtros, agregaciones)
- **View:** orquesta (llama service/selector, serializa, retorna respuesta HTTP)

### Service — estructura tipo

```python
# apps/documents/services/document_service.py
import hashlib
from typing import Optional
from django.db import transaction
from django.core.files.uploadedfile import UploadedFile

from apps.core.exceptions import ValidationError, PermissionDenied
from apps.organizations.models import Organization
from apps.authentication.models import User
from apps.documents.models import Document, DocumentVersion, DocumentStatus
from apps.audit.services import audit_service
from apps.audit.constants import AuditAction
from apps.documents.tasks import process_ocr
from apps.documents.services.storage_service import storage_service
from apps.documents.validators import validate_document_file


@transaction.atomic
def create_document(
    organization: Organization,
    user: User,
    file: UploadedFile,
    name: str,
    folder=None,
    description: str = "",
    tags: list = None,
) -> Document:
    """
    Upload a new document to the organization.
    Validates file, uploads to storage, creates DB record and first version.
    """
    # 1. Validar
    validate_document_file(file)

    # 2. Calcular checksum
    checksum = _calculate_checksum(file)

    # 3. Subir a storage
    storage_path = storage_service.upload_file(
        file=file,
        organization=organization,
        document_id=None,  # se genera en el modelo
    )

    # 4. Crear registro en DB
    document = Document.objects.create(
        organization=organization,
        created_by=user,
        folder=folder,
        name=name,
        description=description,
        mime_type=file.content_type,
        file_size=file.size,
        checksum=checksum,
        storage_path=storage_path,
        status=DocumentStatus.DRAFT,
        version=1,
        tags=tags or [],
    )

    # 5. Crear primera versión
    DocumentVersion.objects.create(
        document=document,
        version_number=1,
        storage_path=storage_path,
        file_size=file.size,
        checksum=checksum,
        created_by=user,
        change_description="Initial upload",
    )

    # 6. Disparar OCR async
    process_ocr.delay(str(document.id))

    # 7. Auditar
    audit_service.log(
        organization=organization,
        user=user,
        entity=document,
        action=AuditAction.CREATE,
    )

    return document


def _calculate_checksum(file: UploadedFile) -> str:
    """Calculate SHA256 checksum of uploaded file."""
    sha256 = hashlib.sha256()
    for chunk in file.chunks():
        sha256.update(chunk)
    file.seek(0)  # Reset file pointer after reading
    return sha256.hexdigest()
```

### Selector — estructura tipo

```python
# apps/documents/selectors/document_selector.py
from typing import Optional
from django.db.models import QuerySet
from django.contrib.postgres.search import SearchQuery, SearchRank

from apps.organizations.models import Organization
from apps.authentication.models import User
from apps.documents.models import Document, DocumentStatus


def get_documents(
    organization: Organization,
    user: User,
    folder_id: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    include_deleted: bool = False,
) -> QuerySet:
    """
    Return documents visible to user within the organization.
    Applies all filters and tenant isolation.
    """
    qs = Document.objects.filter(organization=organization)

    if not include_deleted:
        qs = qs.filter(deleted_at__isnull=True)

    if folder_id:
        qs = qs.filter(folder_id=folder_id)

    if status:
        qs = qs.filter(status=status)

    if search:
        query = SearchQuery(search, config='spanish')
        qs = (
            qs.annotate(rank=SearchRank('search_vector', query))
              .filter(search_vector=query)
              .order_by('-rank')
        )

    return qs.select_related('created_by', 'folder').order_by('-created_at')


def get_document_by_id(
    organization: Organization,
    document_id: str,
    include_deleted: bool = False,
) -> Document:
    """
    Return a single document by ID, scoped to organization.
    Raises Document.DoesNotExist if not found or wrong org.
    """
    qs = Document.objects.filter(organization=organization, id=document_id)
    if not include_deleted:
        qs = qs.filter(deleted_at__isnull=True)
    return qs.select_related('created_by', 'folder', 'organization').get()
```

### View — estructura tipo

```python
# apps/documents/api/views.py
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status

from apps.permissions.permissions import IsOrganizationMember, HasRole
from apps.authentication.constants import UserRole
from apps.documents.api.serializers import (
    DocumentSerializer,
    DocumentCreateSerializer,
    DocumentListSerializer,
)
from apps.documents.services import document_service
from apps.documents.selectors import document_selector


class DocumentListCreateView(APIView):
    permission_classes = [IsOrganizationMember]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        documents = document_selector.get_documents(
            organization=request.organization,
            user=request.user,
            folder_id=request.query_params.get('folder'),
            status=request.query_params.get('status'),
            search=request.query_params.get('q'),
        )
        serializer = DocumentListSerializer(documents, many=True)
        return Response({'data': serializer.data})

    def post(self, request):
        serializer = DocumentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        document = document_service.create_document(
            organization=request.organization,
            user=request.user,
            **serializer.validated_data,
        )
        return Response(
            {'data': DocumentSerializer(document).data},
            status=status.HTTP_201_CREATED,
        )


class DocumentDetailView(APIView):
    permission_classes = [IsOrganizationMember]

    def get_object(self, request, document_id):
        try:
            return document_selector.get_document_by_id(
                organization=request.organization,
                document_id=document_id,
            )
        except Document.DoesNotExist:
            raise NotFound(detail="Document not found")

    def get(self, request, document_id):
        document = self.get_object(request, document_id)
        return Response({'data': DocumentSerializer(document).data})

    def patch(self, request, document_id):
        document = self.get_object(request, document_id)
        serializer = DocumentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = document_service.update_document(
            organization=request.organization,
            user=request.user,
            document=document,
            **serializer.validated_data,
        )
        return Response({'data': DocumentSerializer(document).data})

    def delete(self, request, document_id):
        document = self.get_object(request, document_id)
        document_service.soft_delete_document(
            organization=request.organization,
            user=request.user,
            document=document,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
```

---

## 2. Patrón BaseModel

```python
# apps/core/models/base.py
import uuid
from django.db import models
from django.utils import timezone


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class AllObjectsManager(models.Manager):
    """Manager que incluye objetos eliminados — usar con cuidado."""
    pass


class BaseModel(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # Manager por defecto excluye soft-deleted
    objects = SoftDeleteManager()
    # Para acceder a todos los objetos incluyendo eliminados
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=['deleted_at'])

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=['deleted_at'])

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
```

---

## 3. Patrón Permission Classes

```python
# apps/permissions/permissions.py
from rest_framework.permissions import BasePermission
from apps.authentication.constants import UserRole


class IsOrganizationMember(BasePermission):
    """
    Verifica que el usuario autenticado pertenezca a la organización del request.
    Requiere que OrganizationTenantMiddleware haya inyectado request.organization.
    """
    message = "You do not have access to this organization."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not hasattr(request, 'organization'):
            return False
        return request.user.organization == request.organization


class HasRole(BasePermission):
    """
    Verifica que el usuario tenga al menos uno de los roles requeridos.
    Uso: permission_classes = [IsOrganizationMember, HasRole]
         required_roles = [UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN]
    """
    required_roles = []
    message = "You do not have the required role for this action."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        required = getattr(view, 'required_roles', self.required_roles)
        return request.user.role in required


class IsSuperAdmin(BasePermission):
    message = "Super admin access required."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == UserRole.SUPER_ADMIN
        )


class IsOrgAdmin(BasePermission):
    message = "Organization admin access required."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in [UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN]
        )
```

---

## 4. Patrón de Tests con factory-boy

```python
# backend/tests/factories.py
import factory
from factory.django import DjangoModelFactory
from django.contrib.auth.hashers import make_password

from apps.organizations.models import Organization
from apps.authentication.models import User, UserRole
from apps.documents.models import Document, DocumentStatus, Folder


class OrganizationFactory(DjangoModelFactory):
    class Meta:
        model = Organization

    name = factory.Sequence(lambda n: f"Organization {n}")
    slug = factory.LazyAttribute(lambda o: o.name.lower().replace(' ', '-'))
    is_active = True


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    password = factory.LazyFunction(lambda: make_password("testpassword123"))
    organization = factory.SubFactory(OrganizationFactory)
    role = UserRole.EDITOR
    is_active = True


class OrgAdminFactory(UserFactory):
    role = UserRole.ORG_ADMIN


class FolderFactory(DjangoModelFactory):
    class Meta:
        model = Folder

    name = factory.Sequence(lambda n: f"Folder {n}")
    organization = factory.SubFactory(OrganizationFactory)
    owner = factory.SubFactory(UserFactory)
    parent = None


class DocumentFactory(DjangoModelFactory):
    class Meta:
        model = Document

    name = factory.Sequence(lambda n: f"document_{n}.pdf")
    organization = factory.SubFactory(OrganizationFactory)
    created_by = factory.SubFactory(UserFactory)
    folder = None
    status = DocumentStatus.DRAFT
    mime_type = "application/pdf"
    file_size = 1024
    checksum = factory.Sequence(lambda n: f"checksum_{n}")
    storage_path = factory.Sequence(lambda n: f"org/2024/01/doc_{n}/file.pdf")
    version = 1
```

```python
# Ejemplo de test completo
# apps/documents/tests/test_document_service.py
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch, MagicMock

from apps.documents.services import document_service
from apps.documents.models import Document, DocumentVersion
from tests.factories import OrganizationFactory, UserFactory, FolderFactory


@pytest.mark.django_db
class TestCreateDocument:

    def test_creates_document_successfully(self):
        """Happy path: document is created with correct data"""
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        file = SimpleUploadedFile("test.pdf", b"PDF content", content_type="application/pdf")

        with patch('apps.documents.services.document_service.storage_service.upload_file') as mock_upload:
            mock_upload.return_value = "org/2024/01/test.pdf"

            with patch('apps.documents.services.document_service.process_ocr.delay'):
                document = document_service.create_document(
                    organization=org,
                    user=user,
                    file=file,
                    name="Test Document",
                )

        assert document.organization == org
        assert document.created_by == user
        assert document.name == "Test Document"
        assert document.version == 1
        assert Document.objects.filter(organization=org).count() == 1
        assert DocumentVersion.objects.filter(document=document).count() == 1

    def test_creates_first_document_version(self):
        """Should automatically create DocumentVersion on creation"""
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        file = SimpleUploadedFile("test.pdf", b"content", content_type="application/pdf")

        with patch('apps.documents.services.document_service.storage_service.upload_file') as mock_upload:
            mock_upload.return_value = "path/to/file.pdf"
            with patch('apps.documents.services.document_service.process_ocr.delay'):
                document = document_service.create_document(
                    organization=org, user=user, file=file, name="Doc"
                )

        version = DocumentVersion.objects.get(document=document)
        assert version.version_number == 1
        assert version.created_by == user

    def test_tenant_isolation(self):
        """User from org B cannot create document in org A"""
        org_a = OrganizationFactory()
        org_b = OrganizationFactory()
        user_from_b = UserFactory(organization=org_b)
        file = SimpleUploadedFile("test.pdf", b"content", content_type="application/pdf")

        with pytest.raises(Exception):  # PermissionDenied o similar
            document_service.create_document(
                organization=org_a,  # org diferente al usuario
                user=user_from_b,
                file=file,
                name="Doc",
            )

    def test_invalid_mime_type_raises(self):
        """Should reject files with invalid MIME type"""
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        # .exe no está permitido
        file = SimpleUploadedFile("malware.exe", b"MZ content", content_type="application/x-msdownload")

        with pytest.raises(Exception):  # ValidationError
            document_service.create_document(
                organization=org, user=user, file=file, name="Bad file"
            )
```

---

## 5. Patrón Serializers

```python
# apps/documents/api/serializers.py
from rest_framework import serializers
from apps.documents.models import Document


class DocumentSerializer(serializers.ModelSerializer):
    """Serializer de lectura — para respuestas de la API"""
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    folder_name = serializers.CharField(source='folder.name', read_only=True, allow_null=True)

    class Meta:
        model = Document
        fields = [
            'id', 'name', 'description', 'mime_type', 'file_size',
            'status', 'version', 'tags', 'metadata',
            'created_by_email', 'folder_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields  # Solo lectura — nunca usarlo para crear/editar


class DocumentCreateSerializer(serializers.Serializer):
    """Serializer de escritura — solo valida entrada, no toca el modelo directamente"""
    file = serializers.FileField()
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, default="", allow_blank=True)
    folder_id = serializers.UUIDField(required=False, allow_null=True)
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        default=list,
    )

    def validate_name(self, value):
        if len(value.strip()) == 0:
            raise serializers.ValidationError("Name cannot be empty.")
        return value.strip()
```

---

## 6. Patrón Celery Tasks

```python
# apps/documents/tasks/ocr_tasks.py
import logging
from celery import shared_task
from celery.exceptions import Retry

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # 60 segundos entre reintentos
    name='documents.process_ocr',
)
def process_ocr(self, document_id: str) -> None:
    """
    Async task: run OCR on a document and update its search index.
    Retries up to 3 times on failure.
    """
    from apps.documents.models import Document
    from apps.documents.services import ocr_service

    try:
        document = Document.objects.get(id=document_id)
        ocr_service.process_document(document)
        logger.info(f"OCR completed for document {document_id}")
    except Document.DoesNotExist:
        logger.error(f"Document {document_id} not found for OCR processing")
        # No retry si el documento no existe
    except Exception as exc:
        logger.warning(f"OCR failed for document {document_id}, retrying: {exc}")
        raise self.retry(exc=exc)
```

---

## 7. Patrón de respuesta de errores

```python
# apps/core/exceptions.py
from rest_framework.views import exception_handler
from rest_framework.response import Response


class DocuVaultException(Exception):
    """Base exception para el proyecto"""
    default_message = "An error occurred"
    default_code = "ERROR"
    status_code = 400

    def __init__(self, message=None, code=None):
        self.message = message or self.default_message
        self.code = code or self.default_code
        super().__init__(self.message)


class ValidationError(DocuVaultException):
    default_code = "VALIDATION_ERROR"
    status_code = 400


class PermissionDenied(DocuVaultException):
    default_code = "PERMISSION_DENIED"
    status_code = 403


class NotFound(DocuVaultException):
    default_code = "NOT_FOUND"
    status_code = 404


def custom_exception_handler(exc, context):
    """Handler global de excepciones — retorna siempre el envelope de error."""
    response = exception_handler(exc, context)

    if isinstance(exc, DocuVaultException):
        return Response(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
            status=exc.status_code,
        )

    if response is not None:
        return Response(
            {
                "error": {
                    "code": "API_ERROR",
                    "message": str(exc),
                    "details": response.data,
                }
            },
            status=response.status_code,
        )

    return response
```

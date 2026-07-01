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
    folder = None
    name = factory.Sequence(lambda n: f"document_{n}.pdf")
    description = ""
    mime_type = "application/pdf"
    file_size = 1024
    checksum = factory.Sequence(lambda n: f"{'a' * 63}{n}"[:64])
    storage_path = factory.Sequence(lambda n: f"org/2026/01/{n}/file.pdf")
    status = DocumentStatus.DRAFT
    version = 1
    created_by = factory.SubFactory(UserFactory)
    tags = factory.LazyFunction(list)
    metadata = factory.LazyFunction(dict)


class DocumentVersionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DocumentVersion

    document = factory.SubFactory(DocumentFactory)
    version_number = 1
    storage_path = factory.Sequence(lambda n: f"org/2026/01/{n}/v1/file.pdf")
    file_size = 1024
    checksum = factory.Sequence(lambda n: f"{'b' * 63}{n}"[:64])
    mime_type = "application/pdf"
    created_by = factory.SubFactory(UserFactory)
    change_description = ""

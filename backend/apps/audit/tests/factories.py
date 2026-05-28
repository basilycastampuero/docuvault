import factory

from apps.audit.models import AuditAction, AuditLog
from apps.authentication.tests.factories import UserFactory
from apps.organizations.tests.factories import OrganizationFactory


class AuditLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AuditLog

    organization = factory.SubFactory(OrganizationFactory)
    user = factory.SubFactory(UserFactory)
    entity_type = "document"
    entity_id = factory.Sequence(lambda n: str(n))
    action = AuditAction.CREATE
    old_values = factory.LazyFunction(dict)
    new_values = factory.LazyFunction(dict)

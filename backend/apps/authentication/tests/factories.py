import factory

from apps.authentication.models import User, UserRole
from apps.organizations.tests.factories import OrganizationFactory


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    organization = factory.SubFactory(OrganizationFactory)
    role = UserRole.VIEWER
    is_active = True
    password = factory.PostGenerationMethodCall("set_password", "testpass123")

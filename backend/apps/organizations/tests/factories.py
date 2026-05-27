import factory
from django.utils.text import slugify

from apps.organizations.models import Organization


class OrganizationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Organization

    name = factory.Sequence(lambda n: f"Organization {n}")
    slug = factory.LazyAttribute(lambda o: slugify(o.name))
    is_active = True
    settings = factory.LazyFunction(dict)

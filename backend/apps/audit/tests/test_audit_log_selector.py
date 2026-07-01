import pytest

from apps.audit.selectors import get_log_by_id, get_logs
from apps.audit.tests.factories import AuditLogFactory
from apps.authentication.tests.factories import UserFactory
from apps.core.exceptions import NotFound
from apps.organizations.tests.factories import OrganizationFactory


@pytest.mark.django_db
class TestGetLogs:
    def test_returns_logs_for_organization(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        AuditLogFactory(organization=org, user=user)
        AuditLogFactory(organization=org, user=user)

        qs = get_logs(organization=org)

        assert qs.count() == 2

    def test_tenant_isolation(self):
        org_a = OrganizationFactory()
        org_b = OrganizationFactory()
        user_a = UserFactory(organization=org_a)
        user_b = UserFactory(organization=org_b)
        AuditLogFactory(organization=org_a, user=user_a)
        AuditLogFactory(organization=org_b, user=user_b)

        assert get_logs(organization=org_a).count() == 1
        assert get_logs(organization=org_b).count() == 1

    def test_no_n_plus_one(self, django_assert_num_queries):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        for _ in range(5):
            AuditLogFactory(organization=org, user=user)

        with django_assert_num_queries(1):
            list(get_logs(organization=org))

    def test_ordered_newest_first(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        first = AuditLogFactory(organization=org, user=user)
        second = AuditLogFactory(organization=org, user=user)

        ids = list(get_logs(organization=org).values_list("id", flat=True))
        assert ids[0] == second.id
        assert ids[1] == first.id


@pytest.mark.django_db
class TestGetLogById:
    def test_returns_log_in_organization(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        entry = AuditLogFactory(organization=org, user=user)

        result = get_log_by_id(organization=org, log_id=entry.id)

        assert result.id == entry.id

    def test_not_found_for_other_organization(self):
        org_a = OrganizationFactory()
        org_b = OrganizationFactory()
        user_a = UserFactory(organization=org_a)
        entry = AuditLogFactory(organization=org_a, user=user_a)

        with pytest.raises(NotFound):
            get_log_by_id(organization=org_b, log_id=entry.id)

    def test_not_found_for_nonexistent_id(self):
        org = OrganizationFactory()

        with pytest.raises(NotFound):
            get_log_by_id(organization=org, log_id=999999)

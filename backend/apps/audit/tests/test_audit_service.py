import pytest

from apps.audit.models import AuditAction, AuditLog
from apps.audit.services import log
from apps.authentication.tests.factories import UserFactory
from apps.organizations.tests.factories import OrganizationFactory


@pytest.mark.django_db
class TestAuditService:
    def test_log_creates_entry(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)

        entry = log(
            organization=org,
            user=user,
            entity_type="document",
            entity_id="abc-123",
            action=AuditAction.CREATE,
            new_values={"name": "test.pdf"},
        )

        assert entry.pk is not None
        assert entry.organization == org
        assert entry.user == user
        assert entry.entity_type == "document"
        assert entry.entity_id == "abc-123"
        assert entry.action == AuditAction.CREATE
        assert entry.new_values == {"name": "test.pdf"}
        assert entry.old_values == {}

    def test_log_without_user(self):
        org = OrganizationFactory()

        entry = log(
            organization=org,
            user=None,
            entity_type="organization",
            entity_id=str(org.id),
            action=AuditAction.UPDATE,
        )

        assert entry.user is None
        assert AuditLog.objects.filter(pk=entry.pk).exists()

    def test_log_with_request(self, rf):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        request = rf.get("/", HTTP_USER_AGENT="TestAgent/1.0", REMOTE_ADDR="10.0.0.1")

        entry = log(
            organization=org,
            user=user,
            entity_type="user",
            entity_id=str(user.id),
            action=AuditAction.LOGIN,
            request=request,
        )

        assert entry.ip_address == "10.0.0.1"
        assert entry.user_agent == "TestAgent/1.0"

    def test_log_snapshots_old_and_new_values(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)

        entry = log(
            organization=org,
            user=user,
            entity_type="document",
            entity_id="doc-42",
            action=AuditAction.UPDATE,
            old_values={"name": "old.pdf"},
            new_values={"name": "new.pdf"},
        )

        assert entry.old_values == {"name": "old.pdf"}
        assert entry.new_values == {"name": "new.pdf"}

    def test_audit_log_has_no_updated_at(self):
        assert not hasattr(AuditLog, "updated_at")

    def test_audit_log_is_immutable(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        entry = log(
            organization=org,
            user=user,
            entity_type="document",
            entity_id="x",
            action=AuditAction.CREATE,
        )
        entry.action = AuditAction.DELETE
        with pytest.raises(RuntimeError):
            entry.save()

    def test_audit_log_cannot_be_deleted(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        entry = log(
            organization=org,
            user=user,
            entity_type="document",
            entity_id="y",
            action=AuditAction.CREATE,
        )
        with pytest.raises(RuntimeError):
            entry.delete()

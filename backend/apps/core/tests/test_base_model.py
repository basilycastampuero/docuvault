import uuid

from django.db import models

from apps.core.models.base import BaseModel, SoftDeleteManager


class TestBaseModelStructure:
    def test_id_is_uuid_primary_key(self):
        field = BaseModel._meta.get_field("id")
        assert isinstance(field, models.UUIDField)
        assert field.primary_key is True
        assert field.default is uuid.uuid4
        assert field.editable is False

    def test_has_created_at_auto_field(self):
        field = BaseModel._meta.get_field("created_at")
        assert isinstance(field, models.DateTimeField)
        assert field.auto_now_add is True

    def test_has_updated_at_auto_field(self):
        field = BaseModel._meta.get_field("updated_at")
        assert isinstance(field, models.DateTimeField)
        assert field.auto_now is True

    def test_has_nullable_deleted_at(self):
        field = BaseModel._meta.get_field("deleted_at")
        assert isinstance(field, models.DateTimeField)
        assert field.null is True
        assert field.blank is True

    def test_is_abstract(self):
        assert BaseModel._meta.abstract is True

    def test_default_manager_is_soft_delete(self):
        # _meta.local_managers works on abstract models; the descriptor does not
        managers = {m.name: m for m in BaseModel._meta.local_managers}
        assert "objects" in managers
        assert isinstance(managers["objects"], SoftDeleteManager)

    def test_all_objects_manager_exists(self):
        from apps.core.models.base import AllObjectsManager

        managers = {m.name: m for m in BaseModel._meta.local_managers}
        assert "all_objects" in managers
        assert isinstance(managers["all_objects"], AllObjectsManager)

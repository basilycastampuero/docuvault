import pytest

from apps.authentication.tests.factories import UserFactory
from apps.core.exceptions import NotFound
from apps.documents.selectors.folder_selector import (
    get_children,
    get_folder_by_id,
    get_folder_tree,
    get_root_folders,
)
from apps.organizations.tests.factories import OrganizationFactory

from .factories import FolderFactory


@pytest.mark.django_db
class TestFolderSelector:
    def test_get_folder_by_id(self):
        org = OrganizationFactory()
        folder = FolderFactory(organization=org)
        result = get_folder_by_id(organization=org, folder_id=folder.id)
        assert result == folder

    def test_get_folder_by_id_raises_if_not_found(self):
        org = OrganizationFactory()
        import uuid

        with pytest.raises(NotFound):
            get_folder_by_id(organization=org, folder_id=uuid.uuid4())

    def test_get_folder_by_id_raises_if_wrong_org(self):
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()
        folder = FolderFactory(organization=org2)
        with pytest.raises(NotFound):
            get_folder_by_id(organization=org1, folder_id=folder.id)

    def test_get_root_folders_excludes_children(self):
        org = OrganizationFactory()
        root = FolderFactory(organization=org)
        FolderFactory(organization=org, parent=root)
        roots = list(get_root_folders(organization=org))
        assert root in roots
        assert len(roots) == 1

    def test_get_root_folders_tenant_isolation(self):
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()
        FolderFactory(organization=org1)
        FolderFactory(organization=org2)
        assert get_root_folders(org1).count() == 1

    def test_get_root_folders_no_n_plus_one(self, django_assert_num_queries):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        for _ in range(10):
            FolderFactory(organization=org, owner=user)
        with django_assert_num_queries(1):
            list(get_root_folders(organization=org))

    def test_get_children(self):
        org = OrganizationFactory()
        parent = FolderFactory(organization=org)
        child1 = FolderFactory(organization=org, parent=parent)
        child2 = FolderFactory(organization=org, parent=parent)
        FolderFactory(organization=org)  # unrelated root
        children = list(get_children(organization=org, folder=parent))
        assert set(c.pk for c in children) == {child1.pk, child2.pk}

    def test_get_folder_tree_flat_list(self):
        org = OrganizationFactory()
        root = FolderFactory(organization=org)
        child = FolderFactory(organization=org, parent=root)
        tree = list(get_folder_tree(organization=org))
        ids = [str(node.id) for node in tree]
        assert str(root.id) in ids
        assert str(child.id) in ids
        child_node = next(n for n in tree if str(n.id) == str(child.id))
        assert str(child_node.parent_id) == str(root.id)

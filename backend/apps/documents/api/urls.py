from django.urls import path

from .views import (
    DocumentDetailView,
    DocumentDownloadView,
    DocumentListCreateView,
    DocumentVersionListView,
    FolderChildrenView,
    FolderDetailView,
    FolderDocumentsView,
    FolderListCreateView,
)

urlpatterns = [
    path("folders/", FolderListCreateView.as_view(), name="folder-list-create"),
    path("folders/<uuid:folder_id>/", FolderDetailView.as_view(), name="folder-detail"),
    path(
        "folders/<uuid:folder_id>/children/",
        FolderChildrenView.as_view(),
        name="folder-children",
    ),
    path(
        "folders/<uuid:folder_id>/documents/",
        FolderDocumentsView.as_view(),
        name="folder-documents",
    ),
    path("documents/", DocumentListCreateView.as_view(), name="document-list-create"),
    path(
        "documents/<uuid:document_id>/",
        DocumentDetailView.as_view(),
        name="document-detail",
    ),
    path(
        "documents/<uuid:document_id>/download/",
        DocumentDownloadView.as_view(),
        name="document-download",
    ),
    path(
        "documents/<uuid:document_id>/versions/",
        DocumentVersionListView.as_view(),
        name="document-versions",
    ),
]

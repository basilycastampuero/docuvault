from django.urls import path

from .views import (
    DocumentAnalyzeView,
    DocumentDetailView,
    DocumentDownloadView,
    DocumentListCreateView,
    DocumentRegenerateThumbnailView,
    DocumentReprocessOcrView,
    DocumentStartWorkflowView,
    DocumentVersionListView,
    FolderChildrenView,
    FolderDetailView,
    FolderDocumentsView,
    FolderListCreateView,
    FolderTreeView,
)

urlpatterns = [
    path("folders/", FolderListCreateView.as_view(), name="folder-list-create"),
    # `folders/tree/` MUST appear before `folders/<uuid:folder_id>/` to avoid
    # Django routing "tree" as a UUID.
    path("folders/tree/", FolderTreeView.as_view(), name="folder-tree"),
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
    path(
        "documents/<uuid:document_id>/reprocess-ocr/",
        DocumentReprocessOcrView.as_view(),
        name="document-reprocess-ocr",
    ),
    path(
        "documents/<uuid:document_id>/regenerate-thumbnail/",
        DocumentRegenerateThumbnailView.as_view(),
        name="document-regenerate-thumbnail",
    ),
    path(
        "documents/<uuid:document_id>/analyze/",
        DocumentAnalyzeView.as_view(),
        name="document-analyze",
    ),
    path(
        "documents/<uuid:document_id>/start-workflow/",
        DocumentStartWorkflowView.as_view(),
        name="document-start-workflow",
    ),
]

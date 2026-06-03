import logging

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import StandardPagination
from apps.documents.api.serializers import (
    DocumentMetadataUpdateSerializer,
    DocumentSerializer,
    DocumentUploadSerializer,
    DocumentVersionSerializer,
    DocumentVersionUploadSerializer,
    FolderCreateSerializer,
    FolderSerializer,
    FolderUpdateSerializer,
)
from apps.documents.models import DocumentStatus
from apps.documents.selectors import (
    get_children,
    get_document_by_id,
    get_document_versions,
    get_documents,
    get_folder_by_id,
    get_root_folders,
)
from apps.documents.services import document_service, folder_service
from apps.permissions.permissions import HasRole, IsOrganizationMember

logger = logging.getLogger(__name__)

_EDITOR_ROLES = ["org_admin", "supervisor", "editor"]


# ---------------------------------------------------------------------------
# Folder views
# ---------------------------------------------------------------------------


@extend_schema(tags=["Folders"])
class FolderListCreateView(APIView):
    permission_classes = [IsOrganizationMember]

    @extend_schema(summary="List root folders", responses=FolderSerializer(many=True))
    def get(self, request: Request) -> Response:
        folders = get_root_folders(organization=request.organization)
        serializer = FolderSerializer(folders, many=True)
        return Response({"data": serializer.data, "meta": {}})

    @extend_schema(
        summary="Create a folder",
        request=FolderCreateSerializer,
        responses={201: FolderSerializer},
    )
    def post(self, request: Request) -> Response:
        self._require_editor(request)
        serializer = FolderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        parent = None
        parent_id = serializer.validated_data.get("parent_id")
        if parent_id:
            parent = get_folder_by_id(
                organization=request.organization, folder_id=parent_id
            )

        folder = folder_service.create_folder(
            organization=request.organization,
            owner=request.user,
            name=serializer.validated_data["name"],
            parent=parent,
        )
        return Response(
            {"data": FolderSerializer(folder).data}, status=status.HTTP_201_CREATED
        )

    @staticmethod
    def _require_editor(request: Request) -> None:
        perm = HasRole(*_EDITOR_ROLES)()
        if not perm.has_permission(request, None):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied()


@extend_schema_view(
    get=extend_schema(
        summary="Retrieve a folder", responses=FolderSerializer, tags=["Folders"]
    ),
    patch=extend_schema(
        summary="Update a folder",
        request=FolderUpdateSerializer,
        responses=FolderSerializer,
        tags=["Folders"],
    ),
    delete=extend_schema(
        summary="Delete a folder", responses={204: None}, tags=["Folders"]
    ),
)
class FolderDetailView(APIView):
    permission_classes = [IsOrganizationMember]

    def _get_folder(self, request: Request, folder_id):
        return get_folder_by_id(organization=request.organization, folder_id=folder_id)

    def get(self, request: Request, folder_id) -> Response:
        folder = self._get_folder(request, folder_id)
        return Response({"data": FolderSerializer(folder).data})

    def patch(self, request: Request, folder_id) -> Response:
        FolderListCreateView._require_editor(request)
        folder = self._get_folder(request, folder_id)
        serializer = FolderUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if "name" in data:
            folder = folder_service.rename_folder(
                organization=request.organization,
                user=request.user,
                folder=folder,
                new_name=data["name"],
            )

        if "parent_id" in data:
            new_parent = None
            if data["parent_id"] is not None:
                new_parent = get_folder_by_id(
                    organization=request.organization, folder_id=data["parent_id"]
                )
            folder = folder_service.move_folder(
                organization=request.organization,
                user=request.user,
                folder=folder,
                new_parent=new_parent,
            )

        return Response({"data": FolderSerializer(folder).data})

    def delete(self, request: Request, folder_id) -> Response:
        FolderListCreateView._require_editor(request)
        folder = self._get_folder(request, folder_id)
        folder_service.soft_delete_folder(
            organization=request.organization, user=request.user, folder=folder
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Folders"])
class FolderChildrenView(APIView):
    permission_classes = [IsOrganizationMember]

    @extend_schema(
        summary="List children of a folder", responses=FolderSerializer(many=True)
    )
    def get(self, request: Request, folder_id) -> Response:
        folder = get_folder_by_id(
            organization=request.organization, folder_id=folder_id
        )
        children = get_children(organization=request.organization, folder=folder)
        return Response(
            {"data": FolderSerializer(children, many=True).data, "meta": {}}
        )


@extend_schema(tags=["Folders"])
class FolderDocumentsView(APIView):
    permission_classes = [IsOrganizationMember]

    @extend_schema(
        summary="List documents in a folder", responses=DocumentSerializer(many=True)
    )
    def get(self, request: Request, folder_id) -> Response:
        folder = get_folder_by_id(
            organization=request.organization, folder_id=folder_id
        )
        qs = get_documents(organization=request.organization, folder=folder)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = DocumentSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


# ---------------------------------------------------------------------------
# Document views
# ---------------------------------------------------------------------------


@extend_schema(tags=["Documents"])
class DocumentListCreateView(APIView):
    permission_classes = [IsOrganizationMember]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(summary="List documents", responses=DocumentSerializer(many=True))
    def get(self, request: Request) -> Response:
        qs = get_documents(
            organization=request.organization,
            status=request.query_params.get("status"),
            search=request.query_params.get("search"),
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = DocumentSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        summary="Upload a document",
        request={"multipart/form-data": DocumentUploadSerializer},
        responses={201: DocumentSerializer},
    )
    def post(self, request: Request) -> Response:
        FolderListCreateView._require_editor(request)
        serializer = DocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        folder = None
        if data["folder_id"]:
            folder = get_folder_by_id(
                organization=request.organization, folder_id=data["folder_id"]
            )

        doc = document_service.create_document(
            organization=request.organization,
            user=request.user,
            file=data["file"],
            name=data["name"],
            folder=folder,
            description=data["description"],
            tags=data["tags"],
        )
        return Response(
            {"data": DocumentSerializer(doc).data}, status=status.HTTP_201_CREATED
        )


@extend_schema_view(
    get=extend_schema(
        summary="Retrieve a document", responses=DocumentSerializer, tags=["Documents"]
    ),
    patch=extend_schema(
        summary="Update document metadata",
        request=DocumentMetadataUpdateSerializer,
        responses=DocumentSerializer,
        tags=["Documents"],
    ),
    delete=extend_schema(
        summary="Delete a document", responses={204: None}, tags=["Documents"]
    ),
)
class DocumentDetailView(APIView):
    permission_classes = [IsOrganizationMember]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def _get_doc(self, request: Request, document_id):
        return get_document_by_id(
            organization=request.organization, document_id=document_id
        )

    def get(self, request: Request, document_id) -> Response:
        doc = self._get_doc(request, document_id)
        return Response({"data": DocumentSerializer(doc).data})

    def patch(self, request: Request, document_id) -> Response:
        FolderListCreateView._require_editor(request)
        doc = self._get_doc(request, document_id)
        serializer = DocumentMetadataUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if "status" in data:
            doc = document_service.change_document_status(
                organization=request.organization,
                user=request.user,
                document=doc,
                new_status=DocumentStatus(data.pop("status")),
            )

        if data:
            doc = document_service.update_document_metadata(
                organization=request.organization,
                user=request.user,
                document=doc,
                **data,
            )

        return Response({"data": DocumentSerializer(doc).data})

    def delete(self, request: Request, document_id) -> Response:
        FolderListCreateView._require_editor(request)
        doc = self._get_doc(request, document_id)
        document_service.soft_delete_document(
            organization=request.organization, user=request.user, document=doc
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Documents"])
class DocumentDownloadView(APIView):
    permission_classes = [IsOrganizationMember]

    @extend_schema(
        summary="Get presigned download URL",
        responses={
            200: {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "object",
                        "properties": {"url": {"type": "string"}},
                    }
                },
            }
        },
    )
    def get(self, request: Request, document_id) -> Response:
        from apps.documents.storage import StorageService

        doc = get_document_by_id(
            organization=request.organization, document_id=document_id
        )
        storage = StorageService()
        url = storage.get_presigned_url(doc.storage_path)
        return Response({"data": {"url": url}})


@extend_schema(tags=["Documents"])
class DocumentReprocessOcrView(APIView):
    permission_classes = [IsOrganizationMember]

    @extend_schema(
        summary="Re-run OCR for a document",
        request=None,
        responses={202: DocumentSerializer},
    )
    def post(self, request: Request, document_id) -> Response:
        FolderListCreateView._require_editor(request)
        doc = get_document_by_id(
            organization=request.organization, document_id=document_id
        )
        doc = document_service.reprocess_ocr(
            organization=request.organization, user=request.user, document=doc
        )
        return Response(
            {"data": DocumentSerializer(doc).data}, status=status.HTTP_202_ACCEPTED
        )


@extend_schema(tags=["Documents"])
class DocumentAnalyzeView(APIView):
    permission_classes = [IsOrganizationMember]

    @extend_schema(
        summary="Request AI analysis for a document (async)",
        description=(
            "Enqueues an AI analysis job. Returns 202 immediately. "
            "Result appears in document.metadata.ai_analysis once complete. "
            "Requires ANTHROPIC_API_KEY to be configured (returns 503 otherwise)."
        ),
        request=None,
        responses={202: DocumentSerializer},
    )
    def post(self, request: Request, document_id) -> Response:
        FolderListCreateView._require_editor(request)
        doc = get_document_by_id(
            organization=request.organization, document_id=document_id
        )
        doc = document_service.request_ai_analysis(
            organization=request.organization,
            user=request.user,
            document=doc,
        )
        return Response(
            {"data": DocumentSerializer(doc).data}, status=status.HTTP_202_ACCEPTED
        )


@extend_schema(tags=["Documents"])
class DocumentVersionListView(APIView):
    permission_classes = [IsOrganizationMember]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        summary="List document versions",
        responses=DocumentVersionSerializer(many=True),
    )
    def get(self, request: Request, document_id) -> Response:
        doc = get_document_by_id(
            organization=request.organization, document_id=document_id
        )
        versions = get_document_versions(
            organization=request.organization, document=doc
        )
        return Response(
            {"data": DocumentVersionSerializer(versions, many=True).data, "meta": {}}
        )

    @extend_schema(
        summary="Upload a new version",
        request={"multipart/form-data": DocumentVersionUploadSerializer},
        responses={201: DocumentSerializer},
    )
    def post(self, request: Request, document_id) -> Response:
        FolderListCreateView._require_editor(request)
        doc = get_document_by_id(
            organization=request.organization, document_id=document_id
        )
        serializer = DocumentVersionUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        updated_doc = document_service.upload_new_version(
            organization=request.organization,
            user=request.user,
            document=doc,
            file=data["file"],
            change_description=data["change_description"],
        )
        return Response(
            {"data": DocumentSerializer(updated_doc).data},
            status=status.HTTP_201_CREATED,
        )

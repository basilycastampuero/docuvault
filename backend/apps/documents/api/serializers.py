from rest_framework import serializers

from apps.documents.models import Document, DocumentStatus, DocumentVersion, Folder


class FolderSerializer(serializers.ModelSerializer):
    owner_email = serializers.CharField(source="owner.email", read_only=True)

    class Meta:
        model = Folder
        fields = ["id", "name", "parent", "owner_email", "created_at", "updated_at"]
        read_only_fields = ["id", "owner_email", "created_at", "updated_at"]


class FolderCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    parent_id = serializers.UUIDField(required=False, allow_null=True, default=None)


class FolderUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    parent_id = serializers.UUIDField(required=False, allow_null=True)


class DocumentVersionSerializer(serializers.ModelSerializer):
    created_by_email = serializers.CharField(source="created_by.email", read_only=True)

    class Meta:
        model = DocumentVersion
        fields = [
            "id",
            "version_number",
            "file_size",
            "checksum",
            "mime_type",
            "change_description",
            "created_by_email",
            "created_at",
        ]
        read_only_fields = fields


class DocumentSerializer(serializers.ModelSerializer):
    folder_name = serializers.CharField(
        source="folder.name", read_only=True, allow_null=True
    )
    created_by_email = serializers.CharField(source="created_by.email", read_only=True)

    class Meta:
        model = Document
        fields = [
            "id",
            "name",
            "description",
            "mime_type",
            "file_size",
            "checksum",
            "status",
            "ocr_status",
            "ocr_content",
            "version",
            "tags",
            "metadata",
            "folder",
            "folder_name",
            "created_by_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "mime_type",
            "file_size",
            "checksum",
            "ocr_status",
            "ocr_content",
            "version",
            "folder_name",
            "created_by_email",
            "created_at",
            "updated_at",
        ]


class DocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    name = serializers.CharField(max_length=255)
    folder_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        default=list,
    )


class DocumentMetadataUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(allow_blank=True, required=False)
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
    )
    status = serializers.ChoiceField(
        choices=[DocumentStatus.DRAFT, DocumentStatus.UNDER_REVIEW],
        required=False,
    )
    # No `default` so the field is absent from validated_data when not sent.
    folder_id = serializers.UUIDField(required=False, allow_null=True)


class DocumentVersionUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    change_description = serializers.CharField(
        max_length=500, required=False, allow_blank=True, default=""
    )


# ---------------------------------------------------------------------------
# AI analysis — used only for drf-spectacular schema documentation.
# The actual result lives inside Document.metadata["ai_analysis"] (JSONB).
# ---------------------------------------------------------------------------


class AiAnalysisEntitiesSerializer(serializers.Serializer):
    dates = serializers.ListField(child=serializers.CharField(), read_only=True)
    amounts = serializers.ListField(child=serializers.CharField(), read_only=True)
    names = serializers.ListField(child=serializers.CharField(), read_only=True)


class AiAnalysisSerializer(serializers.Serializer):
    summary = serializers.CharField(read_only=True)
    entities = AiAnalysisEntitiesSerializer(read_only=True)
    suggested_category = serializers.CharField(read_only=True)
    ai_analysis_at = serializers.DateTimeField(read_only=True)

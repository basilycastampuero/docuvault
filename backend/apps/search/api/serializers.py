from rest_framework import serializers

from apps.documents.models import Document, DocumentStatus


class SearchQuerySerializer(serializers.Serializer):
    q = serializers.CharField(min_length=2, max_length=200)
    folder = serializers.UUIDField(required=False, allow_null=True, default=None)
    status = serializers.ChoiceField(
        choices=DocumentStatus.choices,
        required=False,
        allow_null=True,
        default=None,
    )


class SearchResultSerializer(serializers.ModelSerializer):
    folder_name = serializers.CharField(
        source="folder.name", read_only=True, allow_null=True
    )
    created_by_email = serializers.CharField(source="created_by.email", read_only=True)
    rank = serializers.FloatField(read_only=True)

    class Meta:
        model = Document
        fields = [
            "id",
            "name",
            "description",
            "mime_type",
            "file_size",
            "status",
            "version",
            "tags",
            "folder",
            "folder_name",
            "created_by_email",
            "rank",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

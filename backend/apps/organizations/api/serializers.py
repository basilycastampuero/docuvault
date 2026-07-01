from rest_framework import serializers

from apps.organizations.models import Organization


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "slug",
            "is_active",
            "settings",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class OrganizationCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    slug = serializers.SlugField(max_length=100, required=False)


class OrganizationUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    settings = serializers.JSONField(required=False)

    def validate_name(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Name cannot be blank.")
        return value

from rest_framework import serializers

from apps.audit.models import AuditLog


class _AuditUserSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()


class AuditLogSerializer(serializers.ModelSerializer):
    user = _AuditUserSerializer(read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "action",
            "entity_type",
            "entity_id",
            "old_values",
            "new_values",
            "ip_address",
            "user_agent",
            "metadata",
            "created_at",
            "user",
        ]
        read_only_fields = fields

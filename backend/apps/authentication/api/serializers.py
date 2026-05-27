from rest_framework import serializers

from apps.authentication.models import User, UserRole


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class RefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "role",
            "organization_id",
            "is_active",
            "created_at",
        ]
        read_only_fields = fields


class UserCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=UserRole.choices)
    first_name = serializers.CharField(max_length=150, required=False, default="")
    last_name = serializers.CharField(max_length=150, required=False, default="")
    password = serializers.CharField(write_only=True, required=False)

    def validate_role(self, value: str) -> str:
        if value == UserRole.SUPER_ADMIN:
            raise serializers.ValidationError(
                "Cannot assign SUPER_ADMIN role through this endpoint."
            )
        return value


class UserUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    role = serializers.ChoiceField(choices=UserRole.choices, required=False)

    def validate_role(self, value: str) -> str:
        if value == UserRole.SUPER_ADMIN:
            raise serializers.ValidationError(
                "Cannot assign SUPER_ADMIN role through this endpoint."
            )
        return value

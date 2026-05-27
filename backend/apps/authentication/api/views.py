from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.api.serializers import (
    LoginSerializer,
    LogoutSerializer,
    RefreshSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from apps.authentication.selectors import user_selector
from apps.authentication.services import auth_service, user_service
from apps.permissions.permissions import IsOrgAdmin, IsOrganizationMember


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = auth_service.login(**serializer.validated_data)
        user = result.pop("user")

        return Response(
            {
                "data": {
                    **result,
                    "user": UserSerializer(user).data,
                }
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        auth_service.logout(serializer.validated_data["refresh"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class TokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tokens = auth_service.refresh_token_pair(serializer.validated_data["refresh"])
        return Response({"data": tokens}, status=status.HTTP_200_OK)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(
            {"data": UserSerializer(request.user).data},
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# User management (scoped to request.organization)
# ---------------------------------------------------------------------------


class UserListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsOrganizationMember(), IsOrgAdmin()]
        return [IsAuthenticated(), IsOrganizationMember()]

    def get(self, request: Request) -> Response:
        users = user_selector.get_users_by_organization(request.organization)
        return Response(
            {
                "data": UserSerializer(users, many=True).data,
                "meta": {"count": users.count()},
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request: Request) -> Response:
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_user = user_service.create_user(
            organization=request.organization,
            **serializer.validated_data,
        )
        return Response(
            {"data": UserSerializer(new_user).data},
            status=status.HTTP_201_CREATED,
        )


class UserDetailView(APIView):
    def get_permissions(self):
        if self.request.method in ("PATCH", "DELETE"):
            return [IsAuthenticated(), IsOrganizationMember(), IsOrgAdmin()]
        return [IsAuthenticated(), IsOrganizationMember()]

    def _get_user(self, request: Request, user_id: str):
        return user_selector.get_user_by_id(request.organization, user_id)

    def get(self, request: Request, user_id: str) -> Response:
        user = self._get_user(request, user_id)
        return Response({"data": UserSerializer(user).data}, status=status.HTTP_200_OK)

    def patch(self, request: Request, user_id: str) -> Response:
        user = self._get_user(request, user_id)
        serializer = UserUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated = user_service.update_user(
            organization=request.organization,
            user=user,
            requesting_user=request.user,
            **serializer.validated_data,
        )
        return Response(
            {"data": UserSerializer(updated).data}, status=status.HTTP_200_OK
        )

    def delete(self, request: Request, user_id: str) -> Response:
        user = self._get_user(request, user_id)
        user_service.deactivate_user(
            organization=request.organization,
            user=user,
            requesting_user=request.user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

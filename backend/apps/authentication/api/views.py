from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.api.serializers import (
    LoginSerializer,
    LogoutSerializer,
    RefreshSerializer,
    UserSerializer,
)
from apps.authentication.services import auth_service


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

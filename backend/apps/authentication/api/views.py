import logging

from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.api.cookies import (
    clear_refresh_cookie,
    get_refresh_from_cookie,
    issue_csrf_cookie,
    set_refresh_cookie,
    validate_csrf,
)
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
from apps.core.exceptions import ValidationError
from apps.core.pagination import StandardPagination
from apps.permissions.permissions import IsOrgAdmin, IsOrganizationMember

logger = logging.getLogger(__name__)


def _error_response(code: str, message: str, http_status: int) -> Response:
    """Build the standard `{"error": {...}}` envelope (CLAUDE.md §7)."""
    return Response(
        {"error": {"code": code, "message": message, "details": {}}},
        status=http_status,
    )


class LoginView(APIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    @extend_schema(
        request=LoginSerializer,
        responses={200: UserSerializer},
        summary="Authenticate and obtain JWT pair",
        description=(
            "When AUTH_REFRESH_COOKIE_ENABLED is on, the refresh token is set as an "
            "HttpOnly cookie (plus a CSRF double-submit cookie) instead of being "
            "returned in the body."
        ),
    )
    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = auth_service.login(**serializer.validated_data)
        user = result.pop("user")

        cookie_enabled = settings.AUTH_REFRESH_COOKIE_ENABLED
        if cookie_enabled:
            refresh_token = result.pop("refresh")

        response = Response(
            {
                "data": {
                    **result,
                    "user": UserSerializer(user).data,
                }
            },
            status=status.HTTP_200_OK,
        )

        if cookie_enabled:
            set_refresh_cookie(response, refresh_token)
            issue_csrf_cookie(response)

        return response


class LogoutView(APIView):
    # AllowAny: the refresh token (validated + blacklisted) is the real proof of
    # identity here, not the access token. Requiring IsAuthenticated would block a
    # user with an already-expired access token from logging out (phase-plan §6.1,
    # decision #5).
    permission_classes = [AllowAny]
    serializer_class = LogoutSerializer

    @extend_schema(
        request=LogoutSerializer,
        responses={
            204: OpenApiResponse(description="Logged out — refresh blacklisted"),
            403: OpenApiResponse(description="Invalid or missing CSRF token"),
        },
        summary="Blacklist the refresh token",
    )
    def post(self, request: Request) -> Response:
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cookie_enabled = settings.AUTH_REFRESH_COOKIE_ENABLED
        refresh_token = get_refresh_from_cookie(request) if cookie_enabled else None

        if refresh_token and not validate_csrf(request):
            return _error_response(
                "CSRF_INVALID",
                "Missing or invalid CSRF token.",
                status.HTTP_403_FORBIDDEN,
            )

        if not refresh_token:
            refresh_token = serializer.validated_data["refresh"]

        if refresh_token:
            try:
                auth_service.logout(refresh_token)
            except ValidationError as exc:
                # The token was already invalid/expired/blacklisted — the user
                # still wants to be logged out locally, so we don't fail the
                # request, we just clear the cookie below.
                logger.warning("Logout with invalid refresh token: %s", exc.message)

        response = Response(status=status.HTTP_204_NO_CONTENT)
        if cookie_enabled:
            clear_refresh_cookie(response)
        return response


class TokenRefreshView(APIView):
    permission_classes = [AllowAny]
    serializer_class = RefreshSerializer

    @extend_schema(
        request=RefreshSerializer,
        responses={
            200: OpenApiResponse(description="New access + refresh pair"),
            401: OpenApiResponse(description="No refresh token provided"),
            403: OpenApiResponse(description="Invalid or missing CSRF token"),
        },
        summary="Rotate refresh token",
        description=(
            "Reads the refresh token from its HttpOnly cookie when "
            "AUTH_REFRESH_COOKIE_ENABLED is on (validating the CSRF double-submit "
            "header); falls back to the request body during the rollout window or "
            "when the flag is off."
        ),
    )
    def post(self, request: Request) -> Response:
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cookie_enabled = settings.AUTH_REFRESH_COOKIE_ENABLED
        refresh_token = get_refresh_from_cookie(request) if cookie_enabled else None

        if refresh_token:
            if not validate_csrf(request):
                return _error_response(
                    "CSRF_INVALID",
                    "Missing or invalid CSRF token.",
                    status.HTTP_403_FORBIDDEN,
                )
        else:
            # No cookie: fall back to a refresh token in the body (transition
            # window while clients migrate, decision #4) or reject outright.
            refresh_token = serializer.validated_data["refresh"]
            if cookie_enabled and not refresh_token:
                return _error_response(
                    "INVALID_TOKEN",
                    "No refresh token provided.",
                    status.HTTP_401_UNAUTHORIZED,
                )

        tokens = auth_service.refresh_token_pair(refresh_token)

        if cookie_enabled:
            new_refresh_token = tokens.pop("refresh")
            response = Response({"data": tokens}, status=status.HTTP_200_OK)
            set_refresh_cookie(response, new_refresh_token)
            issue_csrf_cookie(response)
            return response

        return Response({"data": tokens}, status=status.HTTP_200_OK)


class MeView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    @extend_schema(
        responses={200: UserSerializer},
        summary="Current authenticated user",
    )
    def get(self, request: Request) -> Response:
        return Response(
            {"data": UserSerializer(request.user).data},
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# User management (scoped to request.organization)
# ---------------------------------------------------------------------------


class UserListCreateView(APIView):
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsOrganizationMember(), IsOrgAdmin()]
        return [IsAuthenticated(), IsOrganizationMember()]

    @extend_schema(
        responses={200: UserSerializer(many=True)},
        summary="List users in the current organization",
    )
    def get(self, request: Request) -> Response:
        users = user_selector.get_users_by_organization(request.organization)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(users, request, view=self)
        return paginator.get_paginated_response(UserSerializer(page, many=True).data)

    @extend_schema(
        request=UserCreateSerializer,
        responses={201: UserSerializer},
        summary="Create a user in the current organization (OrgAdmin+)",
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
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.request.method in ("PATCH", "DELETE"):
            return [IsAuthenticated(), IsOrganizationMember(), IsOrgAdmin()]
        return [IsAuthenticated(), IsOrganizationMember()]

    def _get_user(self, request: Request, user_id: str):
        return user_selector.get_user_by_id(request.organization, user_id)

    @extend_schema(responses={200: UserSerializer}, summary="Retrieve a user")
    def get(self, request: Request, user_id: str) -> Response:
        user = self._get_user(request, user_id)
        return Response({"data": UserSerializer(user).data}, status=status.HTTP_200_OK)

    @extend_schema(
        request=UserUpdateSerializer,
        responses={200: UserSerializer},
        summary="Update a user (OrgAdmin+)",
    )
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

    @extend_schema(
        responses={204: OpenApiResponse(description="User deactivated")},
        summary="Deactivate a user (OrgAdmin+)",
    )
    def delete(self, request: Request, user_id: str) -> Response:
        user = self._get_user(request, user_id)
        user_service.deactivate_user(
            organization=request.organization,
            user=user,
            requesting_user=request.user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

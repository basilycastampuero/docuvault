from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.services import health_service

# Reusable component-status field — CharField avoids drf-spectacular generating
# an anonymous enum (which would trigger an ENUM_NAME_OVERRIDES warning).
_COMPONENT_STATUS = serializers.CharField(
    help_text="'ok' if the component is reachable, 'error' otherwise."
)


class HealthCheckView(APIView):
    """Public endpoint for infrastructure health monitoring.

    Intentionally bypasses JWT authentication so that load balancers and
    external uptime monitors (Nginx upstream_check, UptimeRobot, etc.) can
    call it without credentials.

    Response envelope is deliberately different from the standard {data, meta}
    format — health checkers expect a flat JSON payload.
    """

    permission_classes = [AllowAny]
    # Skip JWT parsing entirely — health check is truly public.
    authentication_classes = []

    @extend_schema(
        summary="System health check",
        description=(
            "Returns the operational status of database, Redis cache, and object storage. "
            "Does not require authentication. "
            "Response envelope intentionally omits the standard {data, meta} wrapper "
            "for compatibility with external health monitoring tools. "
            "Possible values for 'status': 'ok' (all components healthy) or "
            "'degraded' (at least one component unreachable). "
            "Each component reports 'ok' or 'error'."
        ),
        responses={
            200: inline_serializer(
                name="HealthCheckResponse",
                fields={
                    "status": serializers.CharField(
                        help_text="'ok' if all components are healthy, 'degraded' otherwise."
                    ),
                    "components": inline_serializer(
                        name="HealthCheckComponents",
                        fields={
                            "database": _COMPONENT_STATUS,
                            "redis": _COMPONENT_STATUS,
                            "storage": _COMPONENT_STATUS,
                        },
                    ),
                },
            ),
            503: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description=(
                    "One or more infrastructure components are unreachable. "
                    "Response body has the same shape as the 200 response."
                ),
            ),
        },
        tags=["Health"],
        auth=[],
    )
    def get(self, request: Request) -> Response:
        """Return health status of all infrastructure components."""
        components = health_service.check_health()
        overall = "ok" if all(v == "ok" for v in components.values()) else "degraded"
        http_status = (
            status.HTTP_200_OK
            if overall == "ok"
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        return Response(
            {"status": overall, "components": components}, status=http_status
        )

from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from apps.core.pagination import StandardPagination
from apps.organizations.selectors import organization_selector
from apps.organizations.services import organization_service

from .serializers import (
    OrganizationCreateSerializer,
    OrganizationSerializer,
    OrganizationUpdateSerializer,
)

_id_param = OpenApiParameter(
    name="id",
    type=OpenApiTypes.UUID,
    location=OpenApiParameter.PATH,
    description="Organization UUID",
)


@extend_schema_view(
    list=extend_schema(
        responses={200: OrganizationSerializer(many=True)},
        summary="List active organizations",
    ),
    create=extend_schema(
        request=OrganizationCreateSerializer,
        responses={201: OrganizationSerializer},
        summary="Create an organization (SuperAdmin)",
    ),
    retrieve=extend_schema(
        parameters=[_id_param],
        responses={200: OrganizationSerializer},
        summary="Retrieve an organization",
    ),
    partial_update=extend_schema(
        parameters=[_id_param],
        request=OrganizationUpdateSerializer,
        responses={200: OrganizationSerializer},
        summary="Update an organization",
    ),
    destroy=extend_schema(
        parameters=[_id_param],
        responses={204: OpenApiResponse(description="Organization deactivated")},
        summary="Deactivate an organization",
    ),
)
class OrganizationViewSet(ViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = OrganizationSerializer

    def list(self, request: Request) -> Response:
        orgs = organization_selector.get_all_active()
        paginator = StandardPagination()
        page = paginator.paginate_queryset(orgs, request, view=self)
        return paginator.get_paginated_response(
            OrganizationSerializer(page, many=True).data
        )

    def create(self, request: Request) -> Response:
        serializer = OrganizationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = organization_service.create_organization(**serializer.validated_data)
        return Response(
            {"data": OrganizationSerializer(org).data},
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request: Request, pk: str = None) -> Response:
        org = organization_selector.get_by_id(pk)
        return Response(
            {"data": OrganizationSerializer(org).data},
            status=status.HTTP_200_OK,
        )

    def partial_update(self, request: Request, pk: str = None) -> Response:
        org = organization_selector.get_by_id(pk)
        serializer = OrganizationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = organization_service.update_organization(org, **serializer.validated_data)
        return Response(
            {"data": OrganizationSerializer(org).data},
            status=status.HTTP_200_OK,
        )

    def destroy(self, request: Request, pk: str = None) -> Response:
        org = organization_selector.get_by_id(pk)
        organization_service.deactivate_organization(org)
        return Response(status=status.HTTP_204_NO_CONTENT)

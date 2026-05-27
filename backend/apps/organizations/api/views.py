from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from apps.organizations.selectors import organization_selector
from apps.organizations.services import organization_service

from .serializers import (
    OrganizationCreateSerializer,
    OrganizationSerializer,
    OrganizationUpdateSerializer,
)


class OrganizationViewSet(ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request: Request) -> Response:
        orgs = organization_selector.get_all_active()
        serializer = OrganizationSerializer(orgs, many=True)
        return Response(
            {"data": serializer.data, "meta": {"count": orgs.count()}},
            status=status.HTTP_200_OK,
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

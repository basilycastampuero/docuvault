import logging

from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

logger = logging.getLogger(__name__)


class OrganizationTenantMiddleware:
    """
    Reads the JWT access token from each request and injects request.organization.
    If the token is absent, invalid, or carries no organization_id, sets it to None.
    The actual authentication/authorization enforcement is left to DRF permission classes.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.organization = None

        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Bearer "):
            token_str = auth_header.split(" ", 1)[1]
            try:
                token = AccessToken(token_str)
                org_id = token.get("organization_id")
                if org_id:
                    from apps.organizations.models import Organization

                    try:
                        request.organization = Organization.objects.get(id=org_id)
                    except Organization.DoesNotExist:
                        logger.warning(
                            "JWT references unknown organization_id=%s", org_id
                        )
            except (InvalidToken, TokenError):
                pass

        return self.get_response(request)

from django.urls import include, path

from apps.core.api.health_view import HealthCheckView

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health-check"),
    path("auth/", include("apps.authentication.api.urls")),
    path("organizations/", include("apps.organizations.api.urls")),
    path("users/", include("apps.authentication.api.user_urls")),
    path("", include("apps.documents.api.urls")),
    path("", include("apps.audit.api.urls")),
    path("workflows/", include("apps.workflows.api.urls")),
    path("", include("apps.search.api.urls")),
]

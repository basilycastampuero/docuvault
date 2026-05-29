from django.urls import include, path

urlpatterns = [
    path("auth/", include("apps.authentication.api.urls")),
    path("organizations/", include("apps.organizations.api.urls")),
    path("users/", include("apps.authentication.api.user_urls")),
    path("", include("apps.documents.api.urls")),
    path("", include("apps.audit.api.urls")),
]

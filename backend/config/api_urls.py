from django.urls import include, path

urlpatterns = [
    path("auth/", include("apps.authentication.api.urls")),
    path("organizations/", include("apps.organizations.api.urls")),
]

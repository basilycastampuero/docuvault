from django.urls import include, path

urlpatterns = [
    path("organizations/", include("apps.organizations.api.urls")),
]

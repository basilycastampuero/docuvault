from django.urls import path

from apps.search.api.views import DocumentSearchView

urlpatterns = [
    path("search/", DocumentSearchView.as_view(), name="document-search"),
]

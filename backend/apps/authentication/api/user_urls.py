from django.urls import path

from .views import UserDetailView, UserListCreateView

urlpatterns = [
    path("", UserListCreateView.as_view(), name="user-list-create"),
    path("<uuid:user_id>/", UserDetailView.as_view(), name="user-detail"),
]

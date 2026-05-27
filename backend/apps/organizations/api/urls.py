from rest_framework.routers import SimpleRouter

from .views import OrganizationViewSet

router = SimpleRouter()
router.register("", OrganizationViewSet, basename="organization")

urlpatterns = router.urls

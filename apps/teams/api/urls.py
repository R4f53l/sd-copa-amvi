from rest_framework.routers import DefaultRouter

from .views import TeamViewSet

app_name = "teams_api"

router = DefaultRouter()
router.register("", TeamViewSet, basename="team")

urlpatterns = router.urls

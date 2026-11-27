from rest_framework.routers import DefaultRouter

from .views import ChampionshipViewSet, StandingViewSet

app_name = "championships_api"

router = DefaultRouter()
router.register("standings", StandingViewSet, basename="standing")
router.register("", ChampionshipViewSet, basename="championship")

urlpatterns = router.urls

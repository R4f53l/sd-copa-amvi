from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.teams.models import Team

from .serializers import TeamSerializer


class TeamViewSet(ReadOnlyModelViewSet):
    queryset = Team.objects.select_related("city", "home_stadium__city")
    serializer_class = TeamSerializer
    search_fields = ("name", "short_name", "city__name")
    ordering_fields = ("name", "city__name")

from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.championships.models import Championship, ChampionshipTeam

from .serializers import ChampionshipSerializer, StandingSerializer


class ChampionshipViewSet(ReadOnlyModelViewSet):
    queryset = Championship.objects.exclude(
        status__in=(Championship.Status.DRAFT, Championship.Status.CANCELED)
    )
    serializer_class = ChampionshipSerializer
    search_fields = ("name",)
    filterset_fields = ("season", "status")
    ordering_fields = ("season", "start_date", "name")


class StandingViewSet(ReadOnlyModelViewSet):
    serializer_class = StandingSerializer
    filterset_fields = ("championship", "group", "team")
    ordering_fields = ("rank", "points", "goals_for", "yellow_cards")

    def get_queryset(self):
        return ChampionshipTeam.objects.select_related("team").exclude(
            championship__status__in=(
                Championship.Status.DRAFT,
                Championship.Status.CANCELED,
            )
        ).order_by("championship_id", "group", "rank", "team__name")

from rest_framework import serializers

from apps.championships.models import Championship, ChampionshipTeam


class ChampionshipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Championship
        fields = (
            "id", "name", "season", "slug", "description", "status",
            "start_date", "end_date",
        )


class StandingSerializer(serializers.ModelSerializer):
    team = serializers.CharField(source="team.name", read_only=True)
    short_name = serializers.CharField(
        source="team.short_name", read_only=True
    )
    goal_difference = serializers.IntegerField(read_only=True)

    class Meta:
        model = ChampionshipTeam
        fields = (
            "id", "championship", "team", "short_name", "group", "rank",
            "played", "wins", "draws", "losses", "goals_for",
            "goals_against", "goal_difference", "points", "yellow_cards",
            "red_cards", "is_withdrawn",
        )

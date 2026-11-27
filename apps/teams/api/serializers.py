from rest_framework import serializers

from apps.teams.models import City, Stadium, Team


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ("id", "name", "state", "slug")


class StadiumSerializer(serializers.ModelSerializer):
    city = CitySerializer(read_only=True)

    class Meta:
        model = Stadium
        fields = ("id", "name", "city", "address", "capacity")


class TeamSerializer(serializers.ModelSerializer):
    city = CitySerializer(read_only=True)
    home_stadium = StadiumSerializer(read_only=True)

    class Meta:
        model = Team
        fields = (
            "id", "name", "short_name", "slug", "city", "crest",
            "primary_color", "secondary_color", "founded_year",
            "home_stadium",
        )

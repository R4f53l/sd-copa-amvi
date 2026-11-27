from django.test import TestCase

from apps.championships.models import Championship, ChampionshipTeam
from apps.teams.models import City, Team


class ReadOnlyDomainApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        city = City.objects.create(name="Picos", state="PI", slug="picos")
        team = Team.objects.create(
            name="Picos FC",
            short_name="PIC",
            slug="picos-fc",
            city=city,
        )
        cls.championship = Championship.objects.create(
            name="Copa Teste",
            season=2026,
            slug="copa-api",
            status=Championship.Status.ONGOING,
        )
        ChampionshipTeam.objects.create(
            championship=cls.championship,
            team=team,
            group="A",
            points=3,
            rank=1,
        )

    def test_teams_championships_and_standings_are_read_only(self):
        for path in (
            "/api/v1/teams/",
            "/api/v1/championships/",
            "/api/v1/championships/standings/",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    self.client.post(path, {}).status_code, 405
                )

    def test_standings_can_be_filtered_by_championship(self):
        response = self.client.get(
            "/api/v1/championships/standings/",
            {"championship": self.championship.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 1)

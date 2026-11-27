from django.urls import reverse

from apps.championships.models import Championship
from apps.matches.models import Match
from apps.matches.tests.test_pages import MatchPagesTestCase, aware
from apps.teams.models import City, Stadium


class HomePageTests(MatchPagesTestCase):
    def setUp(self):
        Championship.objects.filter(pk=self.championship.pk).update(
            status=Championship.Status.ONGOING
        )

    def test_is_public(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["championship"], self.championship)
        self.assertContains(response, "Copa AMVI")

    def test_sections_split_matches_by_status(self):
        Match.objects.filter(pk=self.match.pk).update(
            status=Match.Status.SECOND_HALF
        )
        finished = Match.objects.create(
            championship=self.championship,
            home_team=self.away,
            away_team=self.home,
            round_number=2,
            scheduled_at=aware(2026, 10, 10, 16, 0),
            status=Match.Status.FINISHED,
            home_score=2,
            away_score=1,
        )
        upcoming = Match.objects.create(
            championship=self.championship,
            home_team=self.home,
            away_team=self.away,
            round_number=3,
            scheduled_at=aware(2026, 11, 5, 16, 0),
        )
        Match.objects.create(
            championship=self.championship,
            home_team=self.away,
            away_team=self.home,
            round_number=4,
            scheduled_at=aware(2026, 11, 12, 16, 0),
            status=Match.Status.CANCELED,
        )

        context = self.client.get(reverse("home")).context
        self.assertEqual(list(context["live_matches"]), [self.match])
        self.assertEqual(list(context["upcoming_matches"]), [upcoming])
        self.assertEqual(list(context["recent_results"]), [finished])
        self.assertEqual(
            context["summary"], {"teams": 2, "played": 1, "goals": 3}
        )

    def test_without_championship(self):
        Match.objects.all().delete()
        Championship.objects.all().delete()
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["championship"])

    def test_logout_returns_home(self):
        self.login(self.official)
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("home"))


class CityFilterTests(MatchPagesTestCase):
    def test_filters_by_the_city_where_the_match_is_played(self):
        picos = City.objects.get(slug="picos")
        oeiras = City.objects.create(name="Oeiras", slug="oeiras")
        stadium = Stadium.objects.create(name="Estadio Oeiras", city=oeiras)
        in_oeiras = Match.objects.create(
            championship=self.championship,
            home_team=self.home,
            away_team=self.away,
            round_number=2,
            scheduled_at=aware(2026, 10, 27, 16, 0),
            stadium=stadium,
        )
        url = reverse("matches:list")

        # No stadium yet: falls back to the home team's city (Picos).
        response = self.client.get(url, {"city": picos.pk})
        self.assertEqual(list(response.context["matches"]), [self.match])

        response = self.client.get(url, {"city": oeiras.pk})
        self.assertEqual(list(response.context["matches"]), [in_oeiras])

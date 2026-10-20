from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.championships.models import Championship, ChampionshipTeam
from apps.matches.models import Match
from apps.teams.models import City, Team


class PublicMatchListTests(TestCase):
    def setUp(self):
        self.city = City.objects.create(name="A cidade", slug="a-cidade")
        away_city = City.objects.create(name="B cidade", slug="b-cidade")
        championship = Championship.objects.create(
            name="Copa de Teste",
            season=2026,
            slug="copa-de-teste-2026",
        )
        home = Team.objects.create(
            name="Time da Casa",
            short_name="CASA",
            slug="time-da-casa",
            city=self.city,
        )
        away = Team.objects.create(
            name="Time Visitante",
            short_name="FORA",
            slug="time-visitante",
            city=away_city,
        )
        self.home_entry = ChampionshipTeam.objects.create(
            championship=championship,
            team=home,
        )
        self.away_entry = ChampionshipTeam.objects.create(
            championship=championship,
            team=away,
        )
        self.create_match(round_number=2, status=Match.Status.FINISHED)
        self.create_match(round_number=1)
        self.create_match(round_number=2, status=Match.Status.CANCELED)

    def create_match(self, round_number, status=Match.Status.SCHEDULED):
        return Match.objects.create(
            championship=self.home_entry.championship,
            home_team=self.home_entry,
            away_team=self.away_entry,
            scheduled_at=timezone.now() + timedelta(days=round_number),
            round_number=round_number,
            status=status,
            home_score=2 if status == Match.Status.FINISHED else 0,
            away_score=1 if status == Match.Status.FINISHED else 0,
        )

    def test_lists_results_and_hides_canceled_matches(self):
        response = self.client.get(reverse("matches:list"))
        match = self.home_entry.home_matches.first()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_manage"])
        self.assertTemplateUsed(response, "matches/match_list.html")
        self.assertContains(response, "Time da Casa")
        self.assertContains(response, "2–1")
        self.assertContains(
            response, reverse("matches:sheet", args=[match.pk])
        )
        self.assertNotContains(
            response, reverse("matches:update", args=[match.pk])
        )
        self.assertEqual(response.context["page_obj"].paginator.count, 2)

    def test_public_page_has_the_same_filters_as_the_match_panel(self):
        response = self.client.get(
            reverse("matches:list"),
            {
                "championship": str(self.home_entry.championship.pk),
                "round": "2",
                "status": Match.Status.FINISHED,
                "q": "Casa",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        self.assertEqual(
            set(response.context["form"].fields),
            {"championship", "round", "status", "q"},
        )
        self.assertContains(response, "2–1")

    def test_paginates_and_keeps_filters_in_page_links(self):
        for _ in range(10):
            self.create_match(round_number=1)

        response = self.client.get(
            reverse("matches:list"),
            {"round": "1", "q": "Casa"},
        )

        self.assertEqual(response.context["page_obj"].paginator.count, 11)
        self.assertContains(
            response,
            "?round=1&amp;q=Casa&amp;page=2",
        )

        second_page = self.client.get(
            reverse("matches:list"),
            {
                "round": "1",
                "q": "Casa",
                "page": "2",
            },
        )
        self.assertEqual(second_page.context["page_obj"].number, 2)
        self.assertEqual(len(second_page.context["page_obj"].object_list), 1)

    def test_match_sheet_is_public_but_read_only(self):
        match = self.home_entry.home_matches.first()
        sheet_url = reverse("matches:sheet", args=[match.pk])
        response = self.client.get(sheet_url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_officiate"])
        self.assertNotContains(response, "Record event")
        self.assertNotContains(response, "Define")

        post_response = self.client.post(sheet_url, {"event_type": "goal"})
        self.assertRedirects(
            post_response,
            f"{reverse('accounts:login')}?next={sheet_url}",
        )

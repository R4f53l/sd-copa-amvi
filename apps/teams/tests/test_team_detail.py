from django.urls import reverse

from apps.championships.models import PlayerRegistration
from apps.matches import services
from apps.matches.models import EventRole, EventType, Match
from apps.matches.tests.test_pages import MatchPagesTestCase, aware
from apps.teams.models import Team


class TeamDetailTests(MatchPagesTestCase):
    def url(self, team):
        return reverse("teams:team_detail", args=[team.pk])

    def test_is_public_and_shows_campaign(self):
        Match.objects.create(
            championship=self.championship,
            home_team=self.home,
            away_team=self.away,
            round_number=2,
            scheduled_at=aware(2026, 10, 27, 16, 0),
            status=Match.Status.FINISHED,
            home_score=3,
            away_score=1,
        )
        Match.objects.create(
            championship=self.championship,
            home_team=self.away,
            away_team=self.home,
            round_number=3,
            scheduled_at=aware(2026, 11, 3, 16, 0),
            status=Match.Status.FINISHED,
            home_score=2,
            away_score=2,
        )
        response = self.client.get(self.url(self.home.team))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["entry"], self.home)
        self.assertEqual(
            response.context["campaign"],
            {
                "played": 2,
                "wins": 1,
                "draws": 1,
                "losses": 0,
                "goals_for": 5,
                "goals_against": 3,
            },
        )
        self.assertEqual(list(response.context["upcoming"]), [self.match])

    def test_squad_hides_released_players(self):
        released = self.home.player_registrations.first()
        PlayerRegistration.objects.filter(pk=released.pk).update(
            status=PlayerRegistration.Status.RELEASED
        )
        squad = self.client.get(self.url(self.home.team)).context["squad"]
        self.assertNotIn(released, squad)
        self.assertEqual(
            len(squad), self.home.player_registrations.count() - 1
        )

    def test_lists_only_this_team_scorers(self):
        self.set_lineups()
        scorer = EventRole.objects.get(code="scorer")
        goal = EventType.objects.get(code="goal")
        for team in (self.home, self.away):
            services.record_event(
                self.match,
                event_type=goal,
                team=team,
                period=1,
                minute=10,
                recorded_by=self.official,
                participants={scorer: self.lineup_of(team, 9)},
            )
        scorers = self.client.get(self.url(self.away.team)).context["scorers"]
        self.assertEqual(
            [r.player.full_name for r in scorers], ["JAI Jogador 9"]
        )

    def test_team_without_championship(self):
        team = Team.objects.create(
            name="Sem Copa",
            short_name="SC",
            slug="sem-copa",
            city=self.home.team.city,
        )
        response = self.client.get(self.url(team))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["entry"])

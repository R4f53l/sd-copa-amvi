from django.urls import reverse

from apps.championships.models import Championship
from apps.matches import services, stats
from apps.matches.models import EventRole, EventType
from apps.matches.tests.test_pages import MatchPagesTestCase


class StatisticsTests(MatchPagesTestCase):
    def setUp(self):
        Championship.objects.filter(pk=self.championship.pk).update(
            status=Championship.Status.ONGOING
        )
        self.set_lineups()
        self.types = {t.code: t for t in EventType.objects.all()}
        self.roles = {r.code: r for r in EventRole.objects.all()}

    def record(self, code, team, minute=10, **participants):
        return services.record_event(
            self.match,
            event_type=self.types[code],
            team=team,
            period=1,
            minute=minute,
            recorded_by=self.official,
            participants={
                self.roles[role.replace("_", "-")]: lineup
                for role, lineup in participants.items()
            },
        )

    def test_top_scorers_ignore_own_goals_shootouts_and_canceled(self):
        nine = self.lineup_of(self.home, 9)
        ten = self.lineup_of(self.home, 10)
        self.record("goal", self.home, scorer=nine, assist=ten)
        self.record("penalty-goal", self.home, minute=20, scorer=nine)
        self.record("goal", self.home, minute=30, scorer=ten)
        canceled = self.record(
            "goal", self.away, minute=40, scorer=self.lineup_of(self.away, 9)
        )
        services.cancel_event(canceled, reason="Impedimento")
        self.record(
            "own-goal",
            self.away,
            minute=50,
            own_goal_author=self.lineup_of(self.away, 4),
        )
        self.record(
            "shootout-goal",
            self.away,
            minute=90,
            penalty_taker=self.lineup_of(self.away, 7),
        )

        ranking = [
            (r.player.full_name, r.total)
            for r in stats.top_scorers(self.championship)
        ]
        self.assertEqual(
            ranking, [("PIC Jogador 9", 2), ("PIC Jogador 10", 1)]
        )

        assists = [
            (r.player.full_name, r.total)
            for r in stats.top_assists(self.championship)
        ]
        self.assertEqual(assists, [("PIC Jogador 10", 1)])

    def test_scorers_can_be_limited_to_a_team(self):
        self.record("goal", self.home, scorer=self.lineup_of(self.home, 9))
        self.record("goal", self.away, scorer=self.lineup_of(self.away, 9))
        names = [
            r.player.full_name
            for r in stats.top_scorers(self.championship, team=self.away.team)
        ]
        self.assertEqual(names, ["JAI Jogador 9"])

    def test_disciplinary_ranking_orders_red_before_yellow(self):
        five = self.lineup_of(self.home, 5)
        six = self.lineup_of(self.home, 6)
        self.record("yellow-card", self.home, booked_player=five)
        self.record("yellow-card", self.home, minute=20, booked_player=six)
        self.record(
            "second-yellow-card", self.home, minute=60, booked_player=six
        )

        ranking = [
            (r.player.full_name, r.yellow, r.red)
            for r in stats.disciplinary_ranking(self.championship)
        ]
        # Second yellow counts as a yellow and as a red card.
        self.assertEqual(
            ranking,
            [("PIC Jogador 6", 2, 1), ("PIC Jogador 5", 1, 0)],
        )

    def test_statistics_page_is_public(self):
        self.record("goal", self.home, scorer=self.lineup_of(self.home, 9))
        self.client.logout()
        response = self.client.get(
            reverse("matches:stats"),
            {"championship": str(self.championship.pk)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["championship"], self.championship)
        self.assertContains(response, "PIC Jogador 9")

    def test_invalid_championship_falls_back_to_featured(self):
        response = self.client.get(
            reverse("matches:stats"), {"championship": "not-a-uuid"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["championship"], self.championship)

    def test_drafts_are_never_shown(self):
        Championship.objects.filter(pk=self.championship.pk).update(
            status=Championship.Status.DRAFT
        )
        response = self.client.get(
            reverse("matches:stats"),
            {"championship": str(self.championship.pk)},
        )
        self.assertIsNone(response.context["championship"])

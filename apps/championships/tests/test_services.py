from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.championships.models import (
    Championship,
    ChampionshipTeam,
    PlayerRegistration,
)
from apps.championships.services import recompute_standings
from apps.matches.models import (
    EventRole,
    EventType,
    Match,
    MatchEvent,
    MatchEventParticipant,
)
from apps.teams.models import City, Player, Team


class RecomputeStandingsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        city = City.objects.create(name="Picos", state="PI", slug="picos")
        cls.teams = [
            Team.objects.create(
                name=name,
                short_name=short,
                slug=slug,
                city=city,
            )
            for name, short, slug in (
                ("Time A", "A", "time-a"),
                ("Time B", "B", "time-b"),
                ("Time C", "C", "time-c"),
            )
        ]
        cls.championship = Championship.objects.create(
            name="Copa Teste",
            season=2026,
            slug="copa-teste",
            status=Championship.Status.ONGOING,
        )
        cls.entries = [
            ChampionshipTeam.objects.create(
                championship=cls.championship, team=team, group="A"
            )
            for team in cls.teams
        ]

    def create_finished_match(self, home, away, score):
        return Match.objects.create(
            championship=self.championship,
            home_team=self.entries[home],
            away_team=self.entries[away],
            scheduled_at=timezone.now() + timedelta(days=home + away),
            status=Match.Status.FINISHED,
            home_score=score[0],
            away_score=score[1],
        )

    def test_points_and_head_to_head_set_rank(self):
        # A and B both finish on three points. B has a better goal
        # difference, but A won their head-to-head match.
        self.create_finished_match(0, 1, (1, 0))
        self.create_finished_match(0, 2, (0, 10))
        self.create_finished_match(1, 2, (10, 0))

        entries = recompute_standings(self.championship)
        by_team = {entry.team_id: entry for entry in entries}
        a, b, c = (by_team[team.pk] for team in self.teams)

        self.assertEqual((a.points, b.points, c.points), (3, 3, 6))
        self.assertLess(a.rank, b.rank)
        self.assertEqual((a.played, a.wins, a.losses), (2, 1, 1))
        self.assertEqual((a.goals_for, a.goals_against), (1, 10))

    def test_withdrawn_team_has_no_rank_and_deductions_apply(self):
        entry = self.entries[0]
        entry.is_withdrawn = True
        entry.points_deducted = 2
        entry.save(update_fields=["is_withdrawn", "points_deducted"])
        self.create_finished_match(0, 1, (2, 0))

        entries = recompute_standings(self.championship)
        refreshed = {entry.pk: entry for entry in entries}
        self.assertIsNone(refreshed[entry.pk].rank)
        self.assertEqual(refreshed[entry.pk].points, 1)

    def test_recompute_suspends_player_at_yellow_card_threshold(self):
        self.championship.yellow_cards_for_suspension = 2
        self.championship.save(update_fields=["yellow_cards_for_suspension"])
        player = Player.objects.create(full_name="Atleta Teste")
        registration = PlayerRegistration.objects.create(
            championship_team=self.entries[0],
            player=player,
            registered_on=timezone.localdate(),
        )
        card = EventType.objects.get(code="yellow-card")
        booked = EventRole.objects.get(code="booked-player")
        match = self.create_finished_match(0, 1, (0, 0))
        for minute in (20, 60):
            event = MatchEvent.objects.create(
                match=match,
                event_type=card,
                team=self.entries[0],
                period=1,
                minute=minute,
            )
            MatchEventParticipant.objects.create(
                event=event,
                player_registration=registration,
                role=booked,
            )

        recompute_standings(self.championship)
        registration.refresh_from_db()
        self.assertEqual(
            registration.status, PlayerRegistration.Status.SUSPENDED
        )

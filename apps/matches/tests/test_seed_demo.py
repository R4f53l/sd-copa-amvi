from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.championships.models import (
    Championship,
    ChampionshipTeam,
    PlayerRegistration,
)
from apps.matches.models import (
    EventRole,
    EventType,
    Lineup,
    Match,
    MatchEvent,
    MatchEventParticipant,
)
from apps.teams.models import City, Player, Stadium, Team


class SeedDemoTest(TestCase):
    def test_seed_demo_execution_and_idempotency(self):
        # primeira execucao
        out = StringIO()
        call_command("seed_demo", stdout=out)
        self.assertIn(
            "Dados de demonstracao carregados com sucesso!", out.getvalue()
        )

        # contagens esperadas
        cities_count = City.objects.count()
        stadiums_count = Stadium.objects.count()
        teams_count = Team.objects.count()
        champs_count = Championship.objects.count()
        champ_teams_count = ChampionshipTeam.objects.count()
        players_count = Player.objects.count()
        regs_count = PlayerRegistration.objects.count()
        matches_count = Match.objects.count()
        lineups_count = Lineup.objects.count()
        events_count = MatchEvent.objects.count()
        participants_count = MatchEventParticipant.objects.count()
        types_count = EventType.objects.count()
        roles_count = EventRole.objects.count()

        self.assertGreaterEqual(cities_count, 6)
        self.assertGreaterEqual(stadiums_count, 4)
        self.assertEqual(teams_count, 4)
        self.assertEqual(champs_count, 1)
        self.assertEqual(champ_teams_count, 4)
        self.assertEqual(players_count, 56)
        self.assertEqual(regs_count, 56)
        self.assertEqual(matches_count, 3)
        self.assertGreaterEqual(lineups_count, 50)
        self.assertEqual(events_count, 5)
        self.assertGreaterEqual(participants_count, 7)
        self.assertGreaterEqual(types_count, 10)
        self.assertGreaterEqual(roles_count, 8)

        # segunda execucao para validar idempotencia
        out2 = StringIO()
        call_command("seed_demo", stdout=out2)
        self.assertEqual(City.objects.count(), cities_count)
        self.assertEqual(Team.objects.count(), teams_count)
        self.assertEqual(Match.objects.count(), matches_count)
        self.assertEqual(MatchEvent.objects.count(), events_count)

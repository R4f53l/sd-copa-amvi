from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.championships.models import (
    Championship,
    ChampionshipTeam,
    PlayerRegistration,
)
from apps.matches.models import Match
from apps.teams.models import City, Player, Team

User = get_user_model()


class ChampionshipsPagesTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            "adm", password="x", role=User.Role.ADMIN
        )
        cls.official = User.objects.create_user(
            "mesario", password="x", role=User.Role.TABLE_OFFICIAL
        )
        cls.city = City.objects.create(name="Picos", state="PI", slug="picos")
        cls.team_a = Team.objects.create(
            name="Picos EC", short_name="PIC", slug="picos-ec", city=cls.city
        )
        cls.team_b = Team.objects.create(
            name="Jaicós FC", short_name="JAI", slug="jaicos-fc", city=cls.city
        )
        cls.team_c = Team.objects.create(
            name="Oeiras AC", short_name="OEI", slug="oeiras-ac", city=cls.city
        )
        cls.championship = Championship.objects.create(
            name="Copa AMVI",
            season=2026,
            slug="copa-amvi-2026",
            status=Championship.Status.REGISTRATION,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 12, 15),
            max_players_per_team=3,
        )
        cls.entry_a = ChampionshipTeam.objects.create(
            championship=cls.championship, team=cls.team_a, group="A"
        )
        cls.entry_b = ChampionshipTeam.objects.create(
            championship=cls.championship, team=cls.team_b, group="A"
        )
        cls.player_1 = Player.objects.create(full_name="Atleta Um")
        cls.player_2 = Player.objects.create(full_name="Atleta Dois")
        cls.player_3 = Player.objects.create(full_name="Atleta Três")
        cls.player_4 = Player.objects.create(full_name="Atleta Quatro")

    def login(self, user):
        self.client.force_login(user)

    def test_public_read_pages_and_admin_permissions(self):
        list_url = reverse("championships:list")
        resp = self.client.get(list_url)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context["can_manage"])
        self.assertNotContains(
            resp, reverse("championships:create")
        )
        detail_url = reverse(
            "championships:detail", args=[self.championship.pk]
        )
        detail = self.client.get(detail_url)
        self.assertEqual(detail.status_code, 200)
        self.assertFalse(detail.context["can_manage"])
        roster_url = reverse(
            "championships:roster",
            args=[self.championship.pk, self.entry_a.pk],
        )
        roster = self.client.get(roster_url)
        self.assertEqual(roster.status_code, 200)
        self.assertFalse(roster.context["can_manage"])
        register_response = self.client.post(roster_url, {})
        self.assertRedirects(
            register_response,
            f"{reverse('accounts:login')}?next={roster_url}",
        )

        # mesario pode ver mas nao pode alterar
        self.login(self.official)
        self.assertEqual(self.client.get(list_url).status_code, 200)
        self.assertEqual(
            self.client.get(
                reverse("championships:detail", args=[self.championship.pk])
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("championships:create")).status_code, 403
        )
        self.assertEqual(
            self.client.get(
                reverse("championships:teams", args=[self.championship.pk])
            ).status_code,
            403,
        )

    def test_create_and_update_championship(self):
        self.login(self.admin)
        response = self.client.post(
            reverse("championships:create"),
            {
                "name": "Supercopa Vale",
                "season": "2027",
                "slug": "",
                "status": Championship.Status.DRAFT,
                "start_date": "2027-03-01",
                "end_date": "2027-06-30",
                "points_per_win": "3",
                "points_per_draw": "1",
                "points_per_loss": "0",
                "yellow_cards_for_suspension": "3",
                "max_players_per_team": "25",
            },
        )
        created = Championship.objects.get(name="Supercopa Vale")
        self.assertEqual(created.slug, "supercopa-vale-2027")
        self.assertRedirects(
            response, reverse("championships:detail", args=[created.pk])
        )

        # data de termino anterior ao inicio deve falhar
        bad_resp = self.client.post(
            reverse("championships:update", args=[created.pk]),
            {
                "name": "Supercopa Vale",
                "season": "2027",
                "slug": created.slug,
                "status": Championship.Status.DRAFT,
                "start_date": "2027-06-30",
                "end_date": "2027-03-01",
                "points_per_win": "3",
                "points_per_draw": "1",
                "points_per_loss": "0",
                "yellow_cards_for_suspension": "3",
                "max_players_per_team": "25",
            },
        )
        self.assertIn("end_date", bad_resp.context["form"].errors)

    def test_team_enrollment_formset(self):
        self.login(self.admin)
        url = reverse("championships:teams", args=[self.championship.pk])
        teams = list(Team.objects.order_by("name"))
        payload = {
            "form-TOTAL_FORMS": str(len(teams)),
            "form-INITIAL_FORMS": str(len(teams)),
        }
        # inscreve todos os 3 times atribuindo grupo especifico ao time C
        for i, team in enumerate(teams):
            payload[f"form-{i}-team_id"] = str(team.pk)
            payload[f"form-{i}-enrolled"] = "on"
            payload[f"form-{i}-group"] = (
                "b" if team.pk == self.team_c.pk else "a"
            )
            payload[f"form-{i}-points_deducted"] = "0"

        resp = self.client.post(url, payload)
        self.assertRedirects(
            resp, reverse("championships:detail", args=[self.championship.pk])
        )
        self.assertEqual(self.championship.team_entries.count(), 3)
        entry_c = self.championship.team_entries.get(team=self.team_c)
        self.assertEqual(entry_c.group, "B")

    def test_cannot_remove_team_with_scheduled_match(self):
        self.login(self.admin)
        Match.objects.create(
            championship=self.championship,
            home_team=self.entry_a,
            away_team=self.entry_b,
            round_number=1,
            scheduled_at=timezone.make_aware(datetime(2026, 10, 20, 16, 0)),
        )
        url = reverse("championships:teams", args=[self.championship.pk])
        teams = list(Team.objects.order_by("name"))
        payload = {
            "form-TOTAL_FORMS": str(len(teams)),
            "form-INITIAL_FORMS": str(len(teams)),
        }
        # tenta desmarcar todos os times mesmo com jogo agendado
        for i, team in enumerate(teams):
            payload[f"form-{i}-team_id"] = str(team.pk)
            payload[f"form-{i}-group"] = ""
            payload[f"form-{i}-points_deducted"] = "0"

        resp = self.client.post(url, payload)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["formset"].non_form_errors())
        self.assertEqual(self.championship.team_entries.count(), 2)

    def test_player_registration_validations(self):
        self.login(self.admin)
        roster_a = reverse(
            "championships:roster",
            args=[self.championship.pk, self.entry_a.pk],
        )
        roster_b = reverse(
            "championships:roster",
            args=[self.championship.pk, self.entry_b.pk],
        )

        # inscreve jogador 1 com camisa 10 no time A
        resp = self.client.post(
            roster_a,
            {
                "player": str(self.player_1.pk),
                "shirt_number": "10",
                "status": PlayerRegistration.Status.ACTIVE,
                "registered_on": "2026-09-15",
            },
        )
        self.assertRedirects(resp, roster_a)
        self.assertEqual(self.entry_a.player_registrations.count(), 1)

        # tenta inscrever o mesmo jogador 1 no time B do mesmo campeonato
        clash_team = self.client.post(
            roster_b,
            {
                "player": str(self.player_1.pk),
                "shirt_number": "9",
                "status": PlayerRegistration.Status.ACTIVE,
                "registered_on": "2026-09-16",
            },
        )
        self.assertEqual(clash_team.status_code, 200)
        self.assertIn("player", clash_team.context["form"].errors)

        # tenta inscrever jogador 2 no time A com a mesma camisa 10
        clash_shirt = self.client.post(
            roster_a,
            {
                "player": str(self.player_2.pk),
                "shirt_number": "10",
                "status": PlayerRegistration.Status.ACTIVE,
                "registered_on": "2026-09-16",
            },
        )
        self.assertEqual(clash_shirt.status_code, 200)
        self.assertIn("shirt_number", clash_shirt.context["form"].errors)

        # inscreve jogadores 2 e 3 para atingir o limite de 3 do campeonato
        for num, player in ((11, self.player_2), (12, self.player_3)):
            self.client.post(
                roster_a,
                {
                    "player": str(player.pk),
                    "shirt_number": str(num),
                    "status": PlayerRegistration.Status.ACTIVE,
                    "registered_on": "2026-09-16",
                },
            )
        self.assertEqual(self.entry_a.player_registrations.count(), 3)

        # quarto jogador excede o limite maximo de jogadores por time
        over_limit = self.client.post(
            roster_a,
            {
                "player": str(self.player_4.pk),
                "shirt_number": "13",
                "status": PlayerRegistration.Status.ACTIVE,
                "registered_on": "2026-09-17",
            },
        )
        self.assertEqual(over_limit.status_code, 200)
        self.assertTrue(over_limit.context["form"].non_field_errors())

        # desligar jogador 1 libera vaga, camisa 10 e permite atuar no time B
        reg_1 = PlayerRegistration.objects.get(
            championship_team=self.entry_a, player=self.player_1
        )
        update_url = reverse(
            "championships:registration_update",
            args=[self.championship.pk, self.entry_a.pk, reg_1.pk],
        )
        self.client.post(
            update_url,
            {
                "shirt_number": "10",
                "status": PlayerRegistration.Status.RELEASED,
                "registered_on": "2026-09-15",
                "released_on": "2026-10-05",
            },
        )
        reg_1.refresh_from_db()
        self.assertEqual(reg_1.status, PlayerRegistration.Status.RELEASED)

        # agora jogador 4 pode usar a camisa 10 no time A
        ok_resp = self.client.post(
            roster_a,
            {
                "player": str(self.player_4.pk),
                "shirt_number": "10",
                "status": PlayerRegistration.Status.ACTIVE,
                "registered_on": "2026-10-06",
            },
        )
        self.assertRedirects(ok_resp, roster_a)

        # e o jogador 1 desligado pode ser inscrito no time B
        ok_transfer = self.client.post(
            roster_b,
            {
                "player": str(self.player_1.pk),
                "shirt_number": "10",
                "status": PlayerRegistration.Status.ACTIVE,
                "registered_on": "2026-10-06",
            },
        )
        self.assertRedirects(ok_transfer, roster_b)

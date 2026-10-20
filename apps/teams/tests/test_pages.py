from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.teams.models import City, Player, Stadium, Team

User = get_user_model()


class TeamsPagesTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # usuarios de teste para validar permissoes de admin e mesario
        cls.admin = User.objects.create_user(
            "adm", password="x", role=User.Role.ADMIN
        )
        cls.official = User.objects.create_user(
            "mesario", password="x", role=User.Role.TABLE_OFFICIAL
        )
        cls.city = City.objects.create(name="Picos", state="PI", slug="picos")
        cls.other_city = City.objects.create(
            name="Jaicós", state="PI", slug="jaicos"
        )
        cls.stadium = Stadium.objects.create(
            name="Helvídio Nunes", city=cls.city, capacity=5000
        )
        cls.team = Team.objects.create(
            name="Picos EC",
            short_name="PIC",
            slug="picos-ec",
            city=cls.city,
            home_stadium=cls.stadium,
        )
        cls.player = Player.objects.create(
            full_name="Francisco Silva",
            nickname="Chico",
            document_number="12345678901",
            position=Player.Position.FORWARD,
        )

    def login(self, user):
        self.client.force_login(user)

    def test_anonymous_is_redirected_to_login(self):
        for name in (
            "teams:team_list",
            "teams:player_list",
            "teams:stadium_list",
            "teams:city_list",
        ):
            url = reverse(name)
            response = self.client.get(url)
            self.assertRedirects(
                response, f"{reverse('accounts:login')}?next={url}"
            )

    def test_table_official_can_view_lists_but_cannot_mutate(self):
        self.login(self.official)
        for name in (
            "teams:team_list",
            "teams:player_list",
            "teams:stadium_list",
            "teams:city_list",
        ):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)

        for name, args in (
            ("teams:team_create", []),
            ("teams:team_update", [self.team.pk]),
            ("teams:player_create", []),
            ("teams:player_update", [self.player.pk]),
            ("teams:stadium_create", []),
            ("teams:stadium_update", [self.stadium.pk]),
            ("teams:city_create", []),
            ("teams:city_update", [self.city.pk]),
        ):
            self.assertEqual(
                self.client.get(reverse(name, args=args)).status_code, 403
            )

    def test_city_create_and_update_with_auto_slug(self):
        self.login(self.admin)
        response = self.client.post(
            reverse("teams:city_create"),
            {"name": "Paulistana", "state": "pi", "slug": ""},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        city = City.objects.get(name="Paulistana")
        self.assertEqual(city.slug, "paulistana")
        self.assertEqual(city.state, "PI")
        self.assertTrue(list(response.context["messages"]))

        response = self.client.post(
            reverse("teams:city_update", args=[city.pk]),
            {"name": "Paulistana do Piauí", "state": "PI", "slug": city.slug},
            follow=True,
        )
        city.refresh_from_db()
        self.assertEqual(city.name, "Paulistana do Piauí")

    def test_stadium_create_update_and_duplicate_error(self):
        self.login(self.admin)
        response = self.client.post(
            reverse("teams:stadium_create"),
            {
                "name": "Arena Verde",
                "city": str(self.city.pk),
                "address": "Centro",
                "capacity": "3000",
                "is_active": "on",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        stadium = Stadium.objects.get(name="Arena Verde")
        self.assertEqual(stadium.capacity, 3000)

        # estadio duplicado na mesma cidade gera mensagem de erro
        dup_resp = self.client.post(
            reverse("teams:stadium_create"),
            {
                "name": "Arena Verde",
                "city": str(self.city.pk),
                "is_active": "on",
            },
        )
        self.assertEqual(dup_resp.status_code, 200)
        self.assertTrue(dup_resp.context["form"].errors)
        self.assertTrue(list(dup_resp.context["messages"]))

    def test_team_create_and_update(self):
        self.login(self.admin)
        response = self.client.post(
            reverse("teams:team_create"),
            {
                "name": "Jaicós FC",
                "short_name": "jai",
                "slug": "",
                "city": str(self.other_city.pk),
                "home_stadium": str(self.stadium.pk),
                "primary_color": "#0e7a3e",
                "secondary_color": "#ffffff",
                "founded_year": "1998",
                "is_active": "on",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        team = Team.objects.get(name="Jaicós FC")
        self.assertEqual(team.short_name, "JAI")
        self.assertEqual(team.slug, "jaicos-fc")

        response = self.client.post(
            reverse("teams:team_update", args=[team.pk]),
            {
                "name": "Jaicós Esporte Clube",
                "short_name": "JEC",
                "slug": team.slug,
                "city": str(self.other_city.pk),
                "is_active": "on",
            },
            follow=True,
        )
        team.refresh_from_db()
        self.assertEqual(team.name, "Jaicós Esporte Clube")
        self.assertEqual(team.short_name, "JEC")

    def test_player_create_update_and_unique_document(self):
        self.login(self.admin)
        response = self.client.post(
            reverse("teams:player_create"),
            {
                "full_name": "João Sousa",
                "nickname": "Joãozinho",
                "document_number": "",
                "birth_date": "2001-05-14",
                "position": Player.Position.MIDFIELDER,
                "preferred_foot": Player.PreferredFoot.RIGHT,
                "is_active": "on",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        player = Player.objects.get(full_name="João Sousa")
        # documento em branco vira none para permitir varios jogadores sem cpf
        self.assertIsNone(player.document_number)

        # documento repetido deve ser rejeitado
        dup_resp = self.client.post(
            reverse("teams:player_create"),
            {
                "full_name": "Outro Atleta",
                "document_number": "12345678901",
                "is_active": "on",
            },
        )
        self.assertIn("document_number", dup_resp.context["form"].errors)

    def test_search_and_pagination(self):
        self.login(self.admin)
        for i in range(22):
            City.objects.create(
                name=f"Cidade {i:02d}", state="PI", slug=f"cidade-{i:02d}"
            )
        response = self.client.get(reverse("teams:city_list"))
        self.assertTrue(response.context["is_paginated"])
        self.assertEqual(len(response.context["cities"]), 20)

        page_2 = self.client.get(reverse("teams:city_list"), {"page": 2})
        self.assertEqual(len(page_2.context["cities"]), 4)

        filtered = self.client.get(reverse("teams:team_list"), {"q": "Picos"})
        self.assertEqual(list(filtered.context["teams"]), [self.team])

        empty = self.client.get(
            reverse("teams:player_list"), {"q": "Inexistente"}
        )
        self.assertEqual(list(empty.context["players"]), [])

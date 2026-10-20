from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.championships.models import Championship, ChampionshipTeam
from apps.matches.models import Match
from apps.teams.models import City, Team

User = get_user_model()


class AccountAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="admin",
            password="StrongPass123!",
            role=User.Role.ADMIN,
        )
        cls.official = User.objects.create_user(
            username="official",
            password="StrongPass123!",
            role=User.Role.TABLE_OFFICIAL,
        )
        cls.other_official = User.objects.create_user(
            username="other",
            password="StrongPass123!",
            role=User.Role.TABLE_OFFICIAL,
        )

        city = City.objects.create(name="Picos", state="PI", slug="picos")
        home = cls._team("Picos FC", "PIC", "picos-fc", city)
        away = cls._team("Jaicós FC", "JAI", "jaicos-fc", city)
        other_home = cls._team("Oeiras FC", "OEI", "oeiras-fc", city)
        other_away = cls._team("Inhuma FC", "INH", "inhuma-fc", city)

        cls.championship = Championship.objects.create(
            name="Copa AMVI",
            season=2026,
            slug="copa-amvi-2026",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 12, 15),
        )
        cls.home_entry = ChampionshipTeam.objects.create(
            championship=cls.championship, team=home
        )
        cls.away_entry = ChampionshipTeam.objects.create(
            championship=cls.championship, team=away
        )
        other_home_entry = ChampionshipTeam.objects.create(
            championship=cls.championship, team=other_home
        )
        other_away_entry = ChampionshipTeam.objects.create(
            championship=cls.championship, team=other_away
        )

        cls.assigned_match = cls._match(
            cls.championship, cls.home_entry, cls.away_entry, 16
        )
        cls.assigned_match.table_officials.add(cls.official)
        cls.unassigned_match = cls._match(
            cls.championship, other_home_entry, other_away_entry, 18
        )
        cls.unassigned_match.table_officials.add(cls.other_official)

    @staticmethod
    def _team(name, short_name, slug, city):
        return Team.objects.create(
            name=name,
            short_name=short_name,
            slug=slug,
            city=city,
        )

    @staticmethod
    def _match(championship, home, away, hour):
        return Match.objects.create(
            championship=championship,
            home_team=home,
            away_team=away,
            round_number=1,
            scheduled_at=timezone.make_aware(
                datetime(2026, 10, 20, hour, 0)
            ),
        )

    def test_anonymous_users_are_redirected_to_login(self):
        for url in (
            reverse("accounts:official_create"),
            reverse("accounts:official_dashboard"),
            reverse("accounts:password_change"),
            reverse("accounts:password_change_done"),
            reverse("championships:create"),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(
                    response,
                    f"{reverse('accounts:login')}?next={url}",
                )

    def test_table_official_cannot_access_admin_views(self):
        self.client.force_login(self.official)
        for url in (
            reverse("accounts:official_create"),
            reverse("championships:create"),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_admin_can_open_account_and_management_views(self):
        self.client.force_login(self.admin)
        for url in (
            reverse("accounts:official_create"),
            reverse("accounts:official_dashboard"),
            reverse("accounts:password_change"),
            reverse("championships:create"),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_official_dashboard_shows_only_assigned_matches(self):
        self.client.force_login(self.official)
        response = self.client.get(reverse("accounts:official_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertQuerySetEqual(
            response.context["matches"],
            [self.assigned_match],
        )
        self.assertContains(response, "Picos FC")
        self.assertNotContains(response, "Oeiras FC")

    def test_admin_created_account_is_always_a_table_official(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("accounts:official_create"),
            {
                "username": "novo-mesario",
                "email": "official@example.com",
                "first_name": "Novo",
                "last_name": "Mesário",
                "password1": "SecurePassword123!",
                "password2": "SecurePassword123!",
            },
        )

        self.assertRedirects(
            response, reverse("accounts:official_dashboard")
        )
        official = User.objects.get(username="novo-mesario")
        self.assertEqual(official.role, User.Role.TABLE_OFFICIAL)
        self.assertFalse(official.is_staff)

    def test_authenticated_user_can_change_password(self):
        self.client.force_login(self.official)
        response = self.client.post(
            reverse("accounts:password_change"),
            {
                "old_password": "StrongPass123!",
                "new_password1": "AnotherSecure456!",
                "new_password2": "AnotherSecure456!",
            },
        )

        self.assertRedirects(
            response, reverse("accounts:password_change_done")
        )
        self.official.refresh_from_db()
        self.assertTrue(self.official.check_password("AnotherSecure456!"))

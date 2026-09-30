from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.matches.models import EventRole, EventType, Lineup, Match, MatchEvent


class MatchesAdminTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # carrega dados de demonstracao para testes de admin
        call_command("seed_demo")
        user_model = get_user_model()
        cls.superuser = user_model.objects.create_superuser(
            username="admin_test",
            email="admin_test@test.com",
            password="testpassword",
        )

    def setUp(self):
        self.client.force_login(self.superuser)

    def test_models_registered_in_admin(self):
        # checa modelos registrados no admin
        registered = [Match, MatchEvent, EventType, EventRole, Lineup]
        for model in registered:
            self.assertIn(model, site._registry)

    def test_match_admin_changelist_and_changeform(self):
        # listagem de partidas
        url_list = reverse("admin:matches_match_changelist")
        resp_list = self.client.get(url_list)
        self.assertEqual(resp_list.status_code, 200)

        # formulario de edicao da partida com inlines
        match = Match.objects.first()
        url_change = reverse("admin:matches_match_change", args=[match.pk])
        resp_change = self.client.get(url_change)
        self.assertEqual(resp_change.status_code, 200)
        self.assertContains(resp_change, "lineups-group")
        self.assertContains(resp_change, "events-group")

    def test_match_event_admin_changelist_and_changeform(self):
        # listagem de eventos
        url_list = reverse("admin:matches_matchevent_changelist")
        resp_list = self.client.get(url_list)
        self.assertEqual(resp_list.status_code, 200)

        # formulario de edicao de evento com inline de participantes
        event = MatchEvent.objects.first()
        url_change = reverse(
            "admin:matches_matchevent_change", args=[event.pk]
        )
        resp_change = self.client.get(url_change)
        self.assertEqual(resp_change.status_code, 200)
        self.assertContains(resp_change, "participants-group")

    def test_event_type_and_role_admin_changelists(self):
        # listagem de tipos e papeis
        url_types = reverse("admin:matches_eventtype_changelist")
        resp_types = self.client.get(url_types)
        self.assertEqual(resp_types.status_code, 200)

        url_roles = reverse("admin:matches_eventrole_changelist")
        resp_roles = self.client.get(url_roles)
        self.assertEqual(resp_roles.status_code, 200)

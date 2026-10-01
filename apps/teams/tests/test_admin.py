from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.teams.admin import PREVIEW_LIST_SIZE, image_preview
from apps.teams.models import City, Player, Stadium, Team


class TeamsAdminTest(TestCase):
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
        for model in (City, Stadium, Team, Player):
            self.assertIn(model, site._registry)

    def test_changelists_and_changeforms(self):
        # listagem e formulario de edicao de cada modelo
        for model in (City, Stadium, Team, Player):
            opts = model._meta
            prefix = f"admin:{opts.app_label}_{opts.model_name}"
            obj = model.objects.first()
            self.assertIsNotNone(obj, f"seed_demo sem {opts.model_name}")

            resp_list = self.client.get(reverse(f"{prefix}_changelist"))
            self.assertEqual(resp_list.status_code, 200)

            resp_change = self.client.get(
                reverse(f"{prefix}_change", args=[obj.pk])
            )
            self.assertEqual(resp_change.status_code, 200)

    def test_changelist_search(self):
        # busca por nome retorna o time procurado
        team = Team.objects.first()
        url = reverse("admin:teams_team_changelist")
        resp = self.client.get(url, {"q": team.name})
        self.assertContains(resp, team.name)

    def _count_queries(self, url):
        with CaptureQueriesContext(connection) as ctx:
            self.client.get(url)
        return len(ctx)

    def test_changelists_do_not_query_per_row(self):
        # list_select_related: o numero de consultas nao cresce com as linhas
        city = City.objects.first()
        stadium = Stadium.objects.first()
        urls = [
            reverse("admin:teams_stadium_changelist"),
            reverse("admin:teams_team_changelist"),
        ]
        before = [self._count_queries(url) for url in urls]

        for i in range(5):
            s = Stadium.objects.create(name=f"Extra {i}", city=city)
            Team.objects.create(
                name=f"Extra {i}",
                short_name=f"EX{i}",
                slug=f"extra-{i}",
                city=city,
                home_stadium=s if i % 2 else stadium,
            )

        after = [self._count_queries(url) for url in urls]
        self.assertEqual(before, after)

    def test_fieldsets_rendered_in_portuguese(self):
        team = Team.objects.first()
        resp = self.client.get(
            reverse("admin:teams_team_change", args=[team.pk])
        )
        self.assertContains(resp, "Identidade")
        self.assertContains(resp, "Escudo")

    def test_image_preview(self):
        # sem imagem mostra traco; com imagem gera a tag <img>
        self.assertEqual(image_preview(Team().crest, PREVIEW_LIST_SIZE), "—")

        team = Team(crest="teams/crests/exemplo.png")
        html = image_preview(team.crest, PREVIEW_LIST_SIZE)
        self.assertIn('src="/media/teams/crests/exemplo.png"', html)
        self.assertIn(f"height:{PREVIEW_LIST_SIZE}px", html)

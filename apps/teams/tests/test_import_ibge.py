from io import StringIO
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.shared.http import ExternalServiceError
from apps.teams.models import City

IBGE = [{"nome": "Picos"}, {"nome": "Jaicós"}, {"nome": "Oeiras"}]


@mock.patch("apps.teams.management.commands.import_ibge_cities.get_json")
class ImportIbgeCitiesTests(TestCase):
    def setUp(self):
        # As in the demo data: no accent in the name, same slug as IBGE's.
        City.objects.create(name="Jaicos", state="PI", slug="jaicos")

    def run_command(self, *args):
        out = StringIO()
        call_command("import_ibge_cities", *args, stdout=out)
        return out.getvalue()

    def test_creates_missing_cities_without_duplicates(self, get_json):
        get_json.return_value = IBGE
        output = self.run_command()

        self.assertIn("2 created", output)
        self.assertEqual(City.objects.count(), 3)
        self.assertEqual(City.objects.get(slug="jaicos").name, "Jaicos")
        get_json.assert_called_once()
        self.assertIn("/estados/PI/", get_json.call_args.args[0])

    def test_update_names_uses_official_spelling(self, get_json):
        get_json.return_value = IBGE
        self.run_command("--update-names")
        self.assertEqual(City.objects.get(slug="jaicos").name, "Jaicós")

    def test_dry_run_saves_nothing(self, get_json):
        get_json.return_value = IBGE
        output = self.run_command("--dry-run", "--update-names")
        self.assertIn("[dry run]", output)
        self.assertEqual(City.objects.count(), 1)
        self.assertEqual(City.objects.get().name, "Jaicos")

    def test_other_states_get_suffixed_slugs(self, get_json):
        get_json.return_value = [{"nome": "Oeiras"}]
        self.run_command("--state", "ce")
        city = City.objects.get(state="CE")
        self.assertEqual(city.slug, "oeiras-ce")

    def test_api_failure_is_reported(self, get_json):
        get_json.side_effect = ExternalServiceError("offline")
        with self.assertRaises(CommandError):
            self.run_command()

    def test_rejects_invalid_state(self, get_json):
        with self.assertRaises(CommandError):
            self.run_command("--state", "Piaui")
        get_json.assert_not_called()

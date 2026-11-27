"""
Import the municipalities of a Brazilian state from the IBGE open-data API
(https://servicodados.ibge.gov.br/api/docs/localidades).

    python manage.py import_ibge_cities            # Piauí
    python manage.py import_ibge_cities --state CE --dry-run
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.shared.http import ExternalServiceError, get_json
from apps.teams.models import City

API_URL = (
    "https://servicodados.ibge.gov.br/api/v1/localidades/estados/"
    "{state}/municipios"
)
HOME_STATE = "PI"


def city_slug(name, state):
    # Piauí cities keep plain slugs (as in the demo data); other states get
    # a suffix because slugs are unique and names repeat across states.
    slug = slugify(name)
    return slug if state == HOME_STATE else f"{slug}-{state.lower()}"


class Command(BaseCommand):
    help = "Import municipalities of a state from the IBGE API."

    def add_arguments(self, parser):
        parser.add_argument(
            "--state",
            default=HOME_STATE,
            help="Two-letter state code (default: PI).",
        )
        parser.add_argument(
            "--update-names",
            action="store_true",
            help="Rename existing cities to the official IBGE spelling.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without saving.",
        )

    def handle(self, *args, state, update_names, dry_run, **options):
        state = state.upper()
        if len(state) != 2 or not state.isalpha():
            raise CommandError("--state must be a two-letter code, e.g. PI.")

        try:
            municipalities = get_json(API_URL.format(state=state), timeout=15)
        except ExternalServiceError as exc:
            raise CommandError(f"IBGE API unavailable: {exc}") from exc
        if not municipalities:
            raise CommandError(f"No municipalities found for {state}.")

        created = renamed = unchanged = 0
        with transaction.atomic():
            for item in municipalities:
                name = item["nome"]
                slug = city_slug(name, state)
                city = City.objects.filter(slug=slug).first()
                if city is None:
                    created += 1
                    if not dry_run:
                        City.objects.create(name=name, state=state, slug=slug)
                elif update_names and city.name != name:
                    renamed += 1
                    if not dry_run:
                        city.name = name
                        city.save(update_fields=["name"])
                else:
                    unchanged += 1
            if dry_run:
                transaction.set_rollback(True)

        prefix = "[dry run] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}{state}: {created} created, {renamed} renamed, "
                f"{unchanged} unchanged ({len(municipalities)} from IBGE)."
            )
        )

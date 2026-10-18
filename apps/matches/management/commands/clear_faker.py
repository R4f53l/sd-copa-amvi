from django.db import transaction

from apps.accounts.models import User
from apps.championships.models import Championship
from apps.matches.models import EventRole, EventType, Match

from apps.teams.models import City, Player, Stadium, Team

#pra exec: python manage.py shell < apps/matches/management/commands/clear_faker.py

with transaction.atomic():
    campeonato = Championship.objects.filter(
        slug="campeonato-faker-2026"
    ).first()

    times = Team.objects.filter(slug__startswith="time-faker-")
    ids_times = list(times.values_list("id", flat=True))
    ids_cidades = list(times.values_list("city_id", flat=True))
    ids_estadios = list(
        times.exclude(home_stadium_id=None)
        .values_list("home_stadium_id", flat=True)
    )

    ids_jogadores = []
    if campeonato:
        ids_jogadores = list(
            Player.objects.filter(
                registrations__championship_team__championship=campeonato
            ).values_list("id", flat=True).distinct()
        )
        Match.objects.filter(championship=campeonato).delete()
        campeonato.delete()

    # Remove os jogadores do seed que não tenham outras inscrições.
    Player.objects.filter(id__in=ids_jogadores).exclude(
        registrations__isnull=False
    ).delete()

    # Remove os times do seed sem participações em outros campeonatos.
    Team.objects.filter(id__in=ids_times).exclude(
        championship_entries__isnull=False
    ).delete()

    # Apaga estádios e cidades que ficaram sem uso.
    Stadium.objects.filter(id__in=ids_estadios).exclude(
        home_teams__isnull=False
    ).delete()
    City.objects.filter(id__in=ids_cidades).exclude(
        teams__isnull=False
    ).exclude(stadiums__isnull=False).delete()

    # Remove somente o mesário criado pelo seed, não o superuser.
    User.objects.filter(username="mesario-faker").delete()

    # O seed ajusta as relações desses papéis; restaura as relações
    # definidas originalmente pela migration matches.0002.
    scorer = EventRole.objects.get(code="scorer")
    scorer.event_types.set(
        EventType.objects.filter(code__in=["goal", "penalty-goal"])
    )

    booked_player = EventRole.objects.get(code="booked-player")
    booked_player.event_types.set(
        EventType.objects.filter(
            code__in=["yellow-card", "second-yellow-card", "red-card"]
        )
    )
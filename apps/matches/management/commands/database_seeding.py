from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from faker import Faker

from apps.accounts.models import User
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

#para exec python manage.py database_seeding

class Command(BaseCommand):
    help = "Cria dados fictícios, incluindo eventos de partidas."

    def criar_catalogo_eventos(self):
        """Obtém ou cria tipos de evento e papéis válidos."""
        tipos = {
            "goal": {
                "name": "Gol",
                "category": EventType.Category.SCORING,
                "score_effect": EventType.ScoreEffect.FOR_TEAM,
            },
            "yellow-card": {
                "name": "Cartão amarelo",
                "category": EventType.Category.DISCIPLINARY,
                "score_effect": EventType.ScoreEffect.NONE,
                "counts_as_yellow_card": True,
            },
            "substitution": {
                "name": "Substituição",
                "category": EventType.Category.SUBSTITUTION,
                "score_effect": EventType.ScoreEffect.NONE,
            },
        }

        eventos = {}
        for code, defaults in tipos.items():
            eventos[code] = EventType.objects.update_or_create(
                code=code,
                defaults=defaults,
            )[0]

        papeis = {
            "scorer": {
                "name": "Autor do gol",
                "event_types": ["goal"],
            },
            "booked-player": {
                "name": "Jogador punido",
                "event_types": ["yellow-card"],
            },
            "player-in": {
                "name": "Jogador que entra",
                "event_types": ["substitution"],
            },
            "player-out": {
                "name": "Jogador que sai",
                "event_types": ["substitution"],
            },
        }

        papeis_criados = {}
        for code, data in papeis.items():
            papel = EventRole.objects.update_or_create(
                code=code,
                defaults={"name": data["name"]},
            )[0]
            papel.event_types.set(
                [eventos[event_code] for event_code in data["event_types"]]
            )
            papeis_criados[code] = papel

        return eventos, papeis_criados

    @transaction.atomic
    def handle(self, *args, **options):
        fake = Faker("pt_BR")
        Faker.seed(2026)

        # 1. Cidades e estádios
        cidades = []
        estadios = []

        for indice in range(1, 10):
            cidade = City.objects.get_or_create(
                slug=f"cidade-faker-{indice}",
                defaults={
                    "name": fake.unique.city(),
                    "state": "PI",
                },
            )[0]
            cidades.append(cidade)

            estadio = Stadium.objects.get_or_create(
                name=f"Estádio Municipal Faker {indice}",
                city=cidade,
                defaults={
                    "address": fake.street_address(),
                    "capacity": fake.random_int(min=1500, max=12000),
                    "is_active": True,
                },
            )[0]
            estadios.append(estadio)

        # 2. Times
        times = []

        for indice, cidade in enumerate(cidades, start=1):
            time = Team.objects.get_or_create(
                slug=f"time-faker-{indice}",
                defaults={
                    "name": f"{fake.city()} Futebol Clube {indice}",
                    "short_name": f"T{indice:02d}",
                    "city": cidade,
                    "home_stadium": estadios[indice - 1],
                    "primary_color": fake.hex_color(),
                    "secondary_color": fake.hex_color(),
                    "founded_year": fake.random_int(min=1950, max=2020),
                    "is_active": True,
                },
            )[0]
            times.append(time)

        # 3. Campeonato e inscrições dos times
        hoje = timezone.localdate()
        campeonato = Championship.objects.get_or_create(
            slug="campeonato-faker-2026",
            defaults={
                "name": "Campeonato de Demonstração",
                "season": 2026,
                "description": "Dados fictícios para desenvolvimento.",
                "status": Championship.Status.ONGOING,
                "start_date": hoje,
                "end_date": hoje + timedelta(days=60),
            },
        )[0]

        dados_dos_times = {}

        for indice, time in enumerate(times, start=1):
            inscricao_time = ChampionshipTeam.objects.get_or_create(
                championship=campeonato,
                team=time,
                defaults={"group": "A" if indice <= 2 else "B"},
            )[0]

            # 4. Jogadores e suas inscrições no campeonato
            inscricoes_jogadores = []

            for numero_camisa in range(1, 15):
                documento = f"2026{indice:02d}{numero_camisa:03d}"

                jogador = Player.objects.get_or_create(
                    document_number=documento,
                    defaults={
                        "full_name": fake.name(),
                        "nickname": fake.first_name(),
                        "birth_date": fake.date_of_birth(
                            minimum_age=18,
                            maximum_age=38,
                        ),
                        "position": fake.random_element(
                            elements=[
                                Player.Position.GOALKEEPER,
                                Player.Position.DEFENDER,
                                Player.Position.MIDFIELDER,
                                Player.Position.FORWARD,
                            ]
                        ),
                        "preferred_foot": fake.random_element(
                            elements=[
                                Player.PreferredFoot.LEFT,
                                Player.PreferredFoot.RIGHT,
                                Player.PreferredFoot.BOTH,
                            ]
                        ),
                        "is_active": True,
                    },
                )[0]

                inscricao_jogador = PlayerRegistration.objects.get_or_create(
                    championship_team=inscricao_time,
                    player=jogador,
                    defaults={
                        "shirt_number": numero_camisa,
                        "status": PlayerRegistration.Status.ACTIVE,
                        "registered_on": hoje,
                    },
                )[0]
                inscricoes_jogadores.append(inscricao_jogador)

            dados_dos_times[time] = (
                inscricao_time,
                inscricoes_jogadores,
            )

        # 5. Tipos de evento e papéis
        eventos, papeis = self.criar_catalogo_eventos()

        # 6. Mesário
        mesario = User.objects.get_or_create(
            username="mesario-faker",
            defaults={
                "first_name": fake.first_name(),
                "last_name": fake.last_name(),
                "email": "mesario-faker@example.test",
                "role": User.Role.TABLE_OFFICIAL,
            },
        )[0]

        # 7. Partidas, escalações e eventos
        confrontos = [
            (times[0], times[1]),
            (times[2], times[3]),
        ]

        for rodada, (mandante, visitante) in enumerate(confrontos, start=1):
            inscricao_mandante, jogadores_mandante = dados_dos_times[mandante]
            inscricao_visitante, jogadores_visitante = dados_dos_times[visitante]

            horario = timezone.now() + timedelta(days=rodada)

            partida, _ = Match.objects.get_or_create(
                championship=campeonato,
                home_team=inscricao_mandante,
                away_team=inscricao_visitante,
                scheduled_at=horario,
                defaults={
                    "stadium": mandante.home_stadium,
                    "stage": Match.Stage.GROUP,
                    "round_number": rodada,
                    "status": Match.Status.FINISHED,
                    "referee_name": fake.name(),
                    "home_score": 2,
                    "away_score": 1,
                    "started_at": horario,
                    "finished_at": horario + timedelta(hours=2),
                },
            )
            partida.table_officials.add(mesario)

            # Escalação: 11 titulares e 3 reservas por time.
            for inscricao_time, jogadores in (
                (inscricao_mandante, jogadores_mandante),
                (inscricao_visitante, jogadores_visitante),
            ):
                for indice, inscricao_jogador in enumerate(jogadores):
                    Lineup.objects.get_or_create(
                        match=partida,
                        player_registration=inscricao_jogador,
                        defaults={
                            "team": inscricao_time,
                            "role": (
                                Lineup.Role.STARTER
                                if indice < 11
                                else Lineup.Role.SUBSTITUTE
                            ),
                            "shirt_number": inscricao_jogador.shirt_number,
                            "position": inscricao_jogador.player.position,
                            "is_captain": indice == 0,
                        },
                    )

            # Dois gols do mandante e um do visitante.
            gols = [
                (inscricao_mandante, jogadores_mandante[9], 18),
                (inscricao_visitante, jogadores_visitante[10], 47),
                (inscricao_mandante, jogadores_mandante[8], 73),
            ]

            for inscricao_time, jogador, minuto in gols:
                evento, _ = MatchEvent.objects.get_or_create(
                    match=partida,
                    event_type=eventos["goal"],
                    period=(
                        MatchEvent.Period.FIRST_HALF
                        if minuto <= 45
                        else MatchEvent.Period.SECOND_HALF
                    ),
                    minute=minuto,
                    defaults={
                        "team": inscricao_time,
                        "recorded_by": mesario,
                        "description": fake.sentence(nb_words=6),
                    },
                )
                MatchEventParticipant.objects.get_or_create(
                    event=evento,
                    player_registration=jogador,
                    role=papeis["scorer"],
                )

            # Um cartão amarelo para jogador escalado do visitante.
            evento_cartao, _ = MatchEvent.objects.get_or_create(
                match=partida,
                event_type=eventos["yellow-card"],
                period=MatchEvent.Period.FIRST_HALF,
                minute=32,
                defaults={
                    "team": inscricao_visitante,
                    "recorded_by": mesario,
                    "description": "Advertência por falta.",
                },
            )
            MatchEventParticipant.objects.get_or_create(
                event=evento_cartao,
                player_registration=jogadores_visitante[3],
                role=papeis["booked-player"],
            )

            # Substituição: o reserva entra e o titular sai.
            evento_substituicao, _ = MatchEvent.objects.get_or_create(
                match=partida,
                event_type=eventos["substitution"],
                period=MatchEvent.Period.SECOND_HALF,
                minute=80,
                defaults={
                    "team": inscricao_mandante,
                    "recorded_by": mesario,
                    "description": "Substituição por desgaste físico.",
                },
            )

            for jogador, codigo_papel in (
                (jogadores_mandante[11], "player-in"),
                (jogadores_mandante[9], "player-out"),
            ):
                MatchEventParticipant.objects.get_or_create(
                    event=evento_substituicao,
                    player_registration=jogador,
                    role=papeis[codigo_papel],
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Dados fictícios, partidas e eventos criados com sucesso."
            )
        )
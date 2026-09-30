from datetime import date, datetime

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

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


class Command(BaseCommand):
    help = "Popula o banco com dados de demonstracao da Copa AMVI"

    @transaction.atomic
    def handle(self, *args, **options):
        # cidades do piaui
        cities_raw = [
            ("Picos", "PI", "picos"),
            ("Oeiras", "PI", "oeiras"),
            ("Paulistana", "PI", "paulistana"),
            ("Simplicio Mendes", "PI", "simplicio-mendes"),
            ("Jaicos", "PI", "jaicos"),
            ("Fronteiras", "PI", "fronteiras"),
        ]
        cities = {}
        for name, state, slug in cities_raw:
            c, _ = City.objects.get_or_create(
                slug=slug, defaults={"name": name, "state": state}
            )
            cities[slug] = c

        # estadios
        stadiums_raw = [
            (
                "Estadio Helvidio Nunes",
                "picos",
                "Centro",
                5000,
                -7.0781,
                -41.4669,
            ),
            (
                "Estadio Gerson Campos",
                "oeiras",
                "Oeiras Nova",
                4000,
                -7.0252,
                -42.1311,
            ),
            (
                "Estadio Evaldao",
                "paulistana",
                "Correnteza",
                3000,
                -8.5333,
                -41.1472,
            ),
            (
                "Estadio Municipal Jose Retrao",
                "jaicos",
                "Centro",
                2500,
                -7.3592,
                -41.1378,
            ),
        ]
        stadiums = {}
        for name, c_slug, addr, cap, lat, lon in stadiums_raw:
            s, _ = Stadium.objects.get_or_create(
                name=name,
                city=cities[c_slug],
                defaults={
                    "address": addr,
                    "capacity": cap,
                    "latitude": lat,
                    "longitude": lon,
                },
            )
            stadiums[c_slug] = s

        # times
        teams_raw = [
            (
                "Sociedade Esportiva de Picos",
                "SEP",
                "sep",
                "picos",
                "#FEE12B",
                "#008000",
                1976,
            ),
            (
                "Oeiras Atletico Clube",
                "OAC",
                "oeiras",
                "oeiras",
                "#003399",
                "#FFFFFF",
                1995,
            ),
            (
                "Paulistana Futebol Clube",
                "PFC",
                "paulistana",
                "paulistana",
                "#CC0000",
                "#FFFFFF",
                2008,
            ),
            (
                "Jaicos Esporte Clube",
                "JEC",
                "jaicos",
                "jaicos",
                "#111111",
                "#FFFFFF",
                2012,
            ),
        ]
        teams = {}
        for name, short, slug, c_slug, col1, col2, year in teams_raw:
            t, _ = Team.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "short_name": short,
                    "city": cities[c_slug],
                    "home_stadium": stadiums.get(c_slug),
                    "primary_color": col1,
                    "secondary_color": col2,
                    "founded_year": year,
                },
            )
            teams[slug] = t

        # mesario
        official, _ = User.objects.get_or_create(
            username="mesario",
            defaults={
                "first_name": "Marcos",
                "last_name": "Mesario",
                "email": "mesario@copaamvi.local",
                "role": User.Role.TABLE_OFFICIAL,
            },
        )
        if _:
            official.set_password("mesario123")
            official.save()

        # campeonato
        champ, _ = Championship.objects.get_or_create(
            season=2026,
            name="Copa AMVI",
            defaults={
                "slug": "copa-amvi-2026",
                "description": "Edicao 2026 da Copa AMVI de Futebol Amador",
                "status": Championship.Status.ONGOING,
                "start_date": date(2026, 9, 1),
                "end_date": date(2026, 11, 30),
                "points_per_win": 3,
                "points_per_draw": 1,
                "points_per_loss": 0,
                "yellow_cards_for_suspension": 3,
            },
        )

        # inscricoes de times
        champ_teams_raw = [
            ("sep", "A"),
            ("oeiras", "A"),
            ("paulistana", "B"),
            ("jaicos", "B"),
        ]
        champ_teams = {}
        for t_slug, group in champ_teams_raw:
            ct, _ = ChampionshipTeam.objects.get_or_create(
                championship=champ,
                team=teams[t_slug],
                defaults={"group": group},
            )
            champ_teams[t_slug] = ct

        # jogadores e inscricoes
        base_positions = [
            ("GK", "Goleiro"),
            ("DF", "Zagueiro"),
            ("DF", "Lateral"),
            ("DF", "Lateral"),
            ("DF", "Zagueiro"),
            ("MF", "Volante"),
            ("MF", "Meia"),
            ("MF", "Meia"),
            ("MF", "Volante"),
            ("FW", "Atacante"),
            ("FW", "Centroavante"),
            ("FW", "Ponta"),
            ("MF", "Meia"),
            ("DF", "Zagueiro"),
        ]

        player_regs = {}
        p_counter = 1
        for t_slug, ct in champ_teams.items():
            player_regs[t_slug] = []
            for num in range(1, 15):
                pos_code, pos_desc = base_positions[num - 1]
                doc = f"{p_counter:011d}"
                full_name = f"Atleta {t_slug.upper()} {num}"
                nick = f"{t_slug.upper()} {num}"
                p, _ = Player.objects.get_or_create(
                    document_number=doc,
                    defaults={
                        "full_name": full_name,
                        "nickname": nick,
                        "position": pos_code,
                        "preferred_foot": Player.PreferredFoot.RIGHT,
                        "birth_date": date(
                            1998, (p_counter % 12) + 1, (p_counter % 28) + 1
                        ),
                    },
                )
                reg, _ = PlayerRegistration.objects.get_or_create(
                    championship_team=ct,
                    player=p,
                    defaults={
                        "shirt_number": num,
                        "status": PlayerRegistration.Status.ACTIVE,
                        "registered_on": date(2026, 8, 15),
                    },
                )
                player_regs[t_slug].append(reg)
                p_counter += 1

        # partida sep x oeiras
        tz = timezone.get_current_timezone()
        match1, _ = Match.objects.get_or_create(
            championship=champ,
            home_team=champ_teams["sep"],
            away_team=champ_teams["oeiras"],
            scheduled_at=timezone.make_aware(datetime(2026, 9, 20, 16, 0), tz),
            defaults={
                "stadium": stadiums["picos"],
                "stage": Match.Stage.GROUP,
                "round_number": 1,
                "status": Match.Status.FINISHED,
                "referee_name": "Raimundo Nonato Silva",
                "home_score": 2,
                "away_score": 1,
                "started_at": timezone.make_aware(
                    datetime(2026, 9, 20, 16, 2), tz
                ),
                "finished_at": timezone.make_aware(
                    datetime(2026, 9, 20, 17, 55), tz
                ),
            },
        )
        match1.table_officials.add(official)

        # escalacoes partida 1
        for idx, reg in enumerate(player_regs["sep"]):
            is_starter = idx < 11
            Lineup.objects.get_or_create(
                match=match1,
                player_registration=reg,
                defaults={
                    "team": champ_teams["sep"],
                    "role": Lineup.Role.STARTER
                    if is_starter
                    else Lineup.Role.SUBSTITUTE,
                    "shirt_number": reg.shirt_number,
                    "position": reg.player.position,
                    "is_captain": (reg.shirt_number == 10),
                },
            )

        for idx, reg in enumerate(player_regs["oeiras"]):
            is_starter = idx < 11
            Lineup.objects.get_or_create(
                match=match1,
                player_registration=reg,
                defaults={
                    "team": champ_teams["oeiras"],
                    "role": Lineup.Role.STARTER
                    if is_starter
                    else Lineup.Role.SUBSTITUTE,
                    "shirt_number": reg.shirt_number,
                    "position": reg.player.position,
                    "is_captain": (reg.shirt_number == 1),
                },
            )

        # eventos da partida 1
        goal_type = EventType.objects.get(code="goal")
        yellow_type = EventType.objects.get(code="yellow-card")
        sub_type = EventType.objects.get(code="substitution")

        role_scorer = EventRole.objects.get(code="scorer")
        role_assist = EventRole.objects.get(code="assist")
        role_booked = EventRole.objects.get(code="booked-player")
        role_in = EventRole.objects.get(code="player-in")
        role_out = EventRole.objects.get(code="player-out")

        # gol sep minuto 18
        ev1, _ = MatchEvent.objects.get_or_create(
            match=match1,
            period=MatchEvent.Period.FIRST_HALF,
            minute=18,
            event_type=goal_type,
            defaults={
                "team": champ_teams["sep"],
                "recorded_by": official,
                "description": "Gol de finalizacao no angulo",
            },
        )
        MatchEventParticipant.objects.get_or_create(
            event=ev1,
            player_registration=player_regs["sep"][9],
            role=role_scorer,
        )
        MatchEventParticipant.objects.get_or_create(
            event=ev1,
            player_registration=player_regs["sep"][8],
            role=role_assist,
        )

        # cartao amarelo oeiras minuto 34
        ev2, _ = MatchEvent.objects.get_or_create(
            match=match1,
            period=MatchEvent.Period.FIRST_HALF,
            minute=34,
            event_type=yellow_type,
            defaults={
                "team": champ_teams["oeiras"],
                "recorded_by": official,
                "description": "Falta tatica no meio campo",
            },
        )
        MatchEventParticipant.objects.get_or_create(
            event=ev2,
            player_registration=player_regs["oeiras"][3],
            role=role_booked,
        )

        # gol oeiras minuto 56
        ev3, _ = MatchEvent.objects.get_or_create(
            match=match1,
            period=MatchEvent.Period.SECOND_HALF,
            minute=56,
            event_type=goal_type,
            defaults={
                "team": champ_teams["oeiras"],
                "recorded_by": official,
                "description": "Gol de empate em contra-ataque",
            },
        )
        MatchEventParticipant.objects.get_or_create(
            event=ev3,
            player_registration=player_regs["oeiras"][10],
            role=role_scorer,
        )

        # gol sep minuto 78
        ev4, _ = MatchEvent.objects.get_or_create(
            match=match1,
            period=MatchEvent.Period.SECOND_HALF,
            minute=78,
            event_type=goal_type,
            defaults={
                "team": champ_teams["sep"],
                "recorded_by": official,
                "description": "Gol da vitoria em cobranca ensaiada",
            },
        )
        MatchEventParticipant.objects.get_or_create(
            event=ev4,
            player_registration=player_regs["sep"][8],
            role=role_scorer,
        )

        # substituicao sep minuto 82
        ev5, _ = MatchEvent.objects.get_or_create(
            match=match1,
            period=MatchEvent.Period.SECOND_HALF,
            minute=82,
            event_type=sub_type,
            defaults={
                "team": champ_teams["sep"],
                "recorded_by": official,
                "description": "Substituicao por cansaco",
            },
        )
        MatchEventParticipant.objects.get_or_create(
            event=ev5,
            player_registration=player_regs["sep"][11],
            role=role_in,
        )
        MatchEventParticipant.objects.get_or_create(
            event=ev5,
            player_registration=player_regs["sep"][9],
            role=role_out,
        )

        # partida paulistana x jaicos
        match2, _ = Match.objects.get_or_create(
            championship=champ,
            home_team=champ_teams["paulistana"],
            away_team=champ_teams["jaicos"],
            scheduled_at=timezone.make_aware(datetime(2026, 9, 21, 16, 0), tz),
            defaults={
                "stadium": stadiums["paulistana"],
                "stage": Match.Stage.GROUP,
                "round_number": 1,
                "status": Match.Status.FINISHED,
                "referee_name": "Antonio Carlos",
                "home_score": 0,
                "away_score": 0,
            },
        )
        match2.table_officials.add(official)

        for idx, reg in enumerate(player_regs["paulistana"]):
            is_starter = idx < 11
            Lineup.objects.get_or_create(
                match=match2,
                player_registration=reg,
                defaults={
                    "team": champ_teams["paulistana"],
                    "role": Lineup.Role.STARTER
                    if is_starter
                    else Lineup.Role.SUBSTITUTE,
                    "shirt_number": reg.shirt_number,
                    "position": reg.player.position,
                    "is_captain": (reg.shirt_number == 10),
                },
            )

        for idx, reg in enumerate(player_regs["jaicos"]):
            is_starter = idx < 11
            Lineup.objects.get_or_create(
                match=match2,
                player_registration=reg,
                defaults={
                    "team": champ_teams["jaicos"],
                    "role": Lineup.Role.STARTER
                    if is_starter
                    else Lineup.Role.SUBSTITUTE,
                    "shirt_number": reg.shirt_number,
                    "position": reg.player.position,
                    "is_captain": (reg.shirt_number == 5),
                },
            )

        # partida agendada rodada 2
        match3, _ = Match.objects.get_or_create(
            championship=champ,
            home_team=champ_teams["oeiras"],
            away_team=champ_teams["sep"],
            scheduled_at=timezone.make_aware(datetime(2026, 10, 5, 16, 0), tz),
            defaults={
                "stadium": stadiums["oeiras"],
                "stage": Match.Stage.GROUP,
                "round_number": 2,
                "status": Match.Status.SCHEDULED,
                "referee_name": "Francisco Pereira",
            },
        )
        match3.table_officials.add(official)

        self.stdout.write(
            self.style.SUCCESS("Dados de demonstracao carregados com sucesso!")
        )

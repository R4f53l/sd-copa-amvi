"""
Seed the event catalogue required by the digital match sheet.

``code`` values are stable identifiers used by the service layer and the
statistics queries; ``name`` values are what fans see.
"""

from django.db import migrations

# code, name, category, score_effect, yellow, red, requires_team, order
EVENT_TYPES = [
    ("goal", "Gol", "SCORING", "FOR_TEAM", False, False, True, 10),
    ("penalty-goal", "Gol de pênalti", "SCORING", "FOR_TEAM",
     False, False, True, 20),
    ("own-goal", "Gol contra", "SCORING", "FOR_OPPONENT",
     False, False, True, 30),
    ("penalty-missed", "Pênalti perdido", "OTHER", "NONE",
     False, False, True, 40),
    ("yellow-card", "Cartão amarelo", "DISCIPLINARY", "NONE",
     True, False, True, 50),
    ("second-yellow-card", "Segundo cartão amarelo", "DISCIPLINARY", "NONE",
     True, True, True, 60),
    ("red-card", "Cartão vermelho", "DISCIPLINARY", "NONE",
     False, True, True, 70),
    ("substitution", "Substituição", "SUBSTITUTION", "NONE",
     False, False, True, 80),
    ("shootout-goal", "Pênalti convertido (disputa)", "SHOOTOUT", "NONE",
     False, False, True, 90),
    ("shootout-missed", "Pênalti perdido (disputa)", "SHOOTOUT", "NONE",
     False, False, True, 100),
    ("period-start", "Início do período", "MATCH_FLOW", "NONE",
     False, False, False, 110),
    ("period-end", "Fim do período", "MATCH_FLOW", "NONE",
     False, False, False, 120),
]

# code, name, event type codes where the role is allowed
EVENT_ROLES = [
    ("scorer", "Autor do gol", ["goal", "penalty-goal"]),
    ("assist", "Assistência", ["goal"]),
    # Kept apart from "scorer" so own goals never count for top scorers.
    ("own-goal-author", "Autor do gol contra", ["own-goal"]),
    ("penalty-taker", "Cobrador do pênalti",
     ["penalty-missed", "shootout-goal", "shootout-missed"]),
    ("goalkeeper", "Goleiro",
     ["penalty-missed", "shootout-goal", "shootout-missed"]),
    ("booked-player", "Jogador punido",
     ["yellow-card", "second-yellow-card", "red-card"]),
    ("player-in", "Jogador que entra", ["substitution"]),
    ("player-out", "Jogador que sai", ["substitution"]),
]


def seed(apps, schema_editor):
    EventType = apps.get_model("matches", "EventType")
    EventRole = apps.get_model("matches", "EventRole")

    types_by_code = {}
    for (code, name, category, score_effect, yellow, red, requires_team,
         order) in EVENT_TYPES:
        types_by_code[code], _ = EventType.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "category": category,
                "score_effect": score_effect,
                "counts_as_yellow_card": yellow,
                "counts_as_red_card": red,
                "requires_team": requires_team,
                "display_order": order,
            },
        )

    for code, name, type_codes in EVENT_ROLES:
        role, _ = EventRole.objects.update_or_create(
            code=code, defaults={"name": name}
        )
        role.event_types.set(types_by_code[c] for c in type_codes)


def unseed(apps, schema_editor):
    apps.get_model("matches", "EventRole").objects.filter(
        code__in=[r[0] for r in EVENT_ROLES]
    ).delete()
    apps.get_model("matches", "EventType").objects.filter(
        code__in=[t[0] for t in EVENT_TYPES]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("matches", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]

from django.db import migrations


def seed_catalog(apps, schema_editor):
    event_type = apps.get_model("matches", "EventType")
    event_role = apps.get_model("matches", "EventRole")

    # tipos de evento
    types_data = [
        {
            "code": "goal",
            "name": "Gol",
            "category": "SCORING",
            "score_effect": "FOR_TEAM",
            "display_order": 10,
        },
        {
            "code": "penalty-goal",
            "name": "Gol de pênalti",
            "category": "SCORING",
            "score_effect": "FOR_TEAM",
            "display_order": 20,
        },
        {
            "code": "own-goal",
            "name": "Gol contra",
            "category": "SCORING",
            "score_effect": "FOR_OPPONENT",
            "display_order": 30,
        },
        {
            "code": "penalty-missed",
            "name": "Pênalti perdido",
            "category": "SCORING",
            "score_effect": "NONE",
            "display_order": 40,
        },
        {
            "code": "yellow-card",
            "name": "Cartão amarelo",
            "category": "DISCIPLINARY",
            "score_effect": "NONE",
            "counts_as_yellow_card": True,
            "display_order": 50,
        },
        {
            "code": "second-yellow-card",
            "name": "Segundo cartão amarelo",
            "category": "DISCIPLINARY",
            "score_effect": "NONE",
            "counts_as_yellow_card": True,
            "counts_as_red_card": True,
            "display_order": 60,
        },
        {
            "code": "red-card",
            "name": "Cartão vermelho",
            "category": "DISCIPLINARY",
            "score_effect": "NONE",
            "counts_as_red_card": True,
            "display_order": 70,
        },
        {
            "code": "substitution",
            "name": "Substituição",
            "category": "SUBSTITUTION",
            "score_effect": "NONE",
            "display_order": 80,
        },
        {
            "code": "shootout-goal",
            "name": "Pênalti convertido",
            "category": "SHOOTOUT",
            "score_effect": "NONE",
            "display_order": 90,
        },
        {
            "code": "shootout-missed",
            "name": "Pênalti perdido na disputa",
            "category": "SHOOTOUT",
            "score_effect": "NONE",
            "display_order": 100,
        },
        {
            "code": "period-start",
            "name": "Início de período",
            "category": "MATCH_FLOW",
            "score_effect": "NONE",
            "requires_team": False,
            "display_order": 110,
        },
        {
            "code": "period-end",
            "name": "Fim de período",
            "category": "MATCH_FLOW",
            "score_effect": "NONE",
            "requires_team": False,
            "display_order": 120,
        },
    ]

    type_objects = {}
    for item in types_data:
        obj, _ = event_type.objects.update_or_create(
            code=item["code"],
            defaults=item,
        )
        type_objects[item["code"]] = obj

    # papeis no evento
    roles_data = [
        ("scorer", "Autor do gol", ["goal", "penalty-goal"]),
        ("assist", "Assistência", ["goal"]),
        ("own-goal-author", "Autor do gol contra", ["own-goal"]),
        ("penalty-taker", "Cobrador", ["penalty-missed", "shootout-goal", "shootout-missed"]),
        ("goalkeeper", "Goleiro", ["penalty-missed", "shootout-goal", "shootout-missed"]),
        ("booked-player", "Jogador punido", ["yellow-card", "second-yellow-card", "red-card"]),
        ("player-in", "Jogador que entra", ["substitution"]),
        ("player-out", "Jogador que sai", ["substitution"]),
    ]

    for code, name, related_types in roles_data:
        role_obj, _ = event_role.objects.update_or_create(
            code=code,
            defaults={"name": name},
        )
        matching_types = [type_objects[t] for t in related_types if t in type_objects]
        role_obj.event_types.set(matching_types)


def remove_catalog(apps, schema_editor):
    event_type = apps.get_model("matches", "EventType")
    event_role = apps.get_model("matches", "EventRole")
    event_role.objects.all().delete()
    event_type.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("matches", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_catalog, remove_catalog),
    ]

"""Domain operations for championship standings and player discipline."""

from collections import defaultdict
from functools import cmp_to_key

from django.db import transaction
from django.db.models import Count

from apps.matches.models import Match, MatchEventParticipant

from .models import Championship, ChampionshipTeam, PlayerRegistration


def _head_to_head_stats(entries):
    """Return mini-table points, goal difference and goals for."""
    ids = {entry.pk for entry in entries}
    values = defaultdict(lambda: {"points": 0, "gd": 0, "gf": 0})
    matches = Match.objects.filter(
        championship_id=entries[0].championship_id,
        status=Match.Status.FINISHED,
        home_team_id__in=ids,
        away_team_id__in=ids,
    ).only("home_team_id", "away_team_id", "home_score", "away_score")
    for match in matches:
        if match.home_score > match.away_score:
            values[match.home_team_id]["points"] += (
                entries[0].championship.points_per_win
            )
        elif match.home_score < match.away_score:
            values[match.away_team_id]["points"] += (
                entries[0].championship.points_per_win
            )
        else:
            draw = entries[0].championship.points_per_draw
            values[match.home_team_id]["points"] += draw
            values[match.away_team_id]["points"] += draw
        values[match.home_team_id]["gf"] += match.home_score
        values[match.home_team_id]["gd"] += match.home_score - match.away_score
        values[match.away_team_id]["gf"] += match.away_score
        values[match.away_team_id]["gd"] += match.away_score - match.home_score
    return values


@transaction.atomic
def recompute_standings(championship):
    """Rebuild played, results, cards, points and rank for each group.

    Equal-points teams are ordered by head-to-head points, goal difference,
    goals scored, fair-play cards and team name. Rank is reset to null for
    withdrawn teams and then stored within each group.
    """
    if not isinstance(championship, Championship):
        championship = Championship.objects.get(pk=championship)
    entries = list(
        ChampionshipTeam.objects.select_for_update()
        .filter(championship=championship)
        .select_related("team")
    )
    totals = {entry.pk: defaultdict(int) for entry in entries}
    games = Match.objects.filter(
        championship=championship, status=Match.Status.FINISHED
    ).only("home_team_id", "away_team_id", "home_score", "away_score")
    for match in games:
        home = totals.get(match.home_team_id)
        away = totals.get(match.away_team_id)
        if home is None or away is None:
            continue
        home["played"] += 1
        away["played"] += 1
        home["goals_for"] += match.home_score
        home["goals_against"] += match.away_score
        away["goals_for"] += match.away_score
        away["goals_against"] += match.home_score
        if match.home_score > match.away_score:
            home["wins"] += 1
            away["losses"] += 1
            home["points"] += championship.points_per_win
            away["points"] += championship.points_per_loss
        elif match.home_score < match.away_score:
            away["wins"] += 1
            home["losses"] += 1
            away["points"] += championship.points_per_win
            home["points"] += championship.points_per_loss
        else:
            home["draws"] += 1
            away["draws"] += 1
            home["points"] += championship.points_per_draw
            away["points"] += championship.points_per_draw

    cards = defaultdict(lambda: [0, 0])
    participants = MatchEventParticipant.objects.filter(
        event__match__championship=championship,
        event__match__status=Match.Status.FINISHED,
        event__is_canceled=False,
        event__event_type__category="DISCIPLINARY",
    ).values_list(
        "player_registration__championship_team_id",
        "event__event_type__counts_as_yellow_card",
        "event__event_type__counts_as_red_card",
    )
    for entry_id, yellow, red in participants:
        cards[entry_id][0] += int(yellow)
        cards[entry_id][1] += int(red)

    for entry in entries:
        values = totals[entry.pk]
        entry.played = values["played"]
        entry.wins = values["wins"]
        entry.draws = values["draws"]
        entry.losses = values["losses"]
        entry.goals_for = values["goals_for"]
        entry.goals_against = values["goals_against"]
        entry.points = values["points"] - entry.points_deducted
        entry.yellow_cards, entry.red_cards = cards[entry.pk]
        entry.rank = None
        entry.save(
            update_fields=[
                "played",
                "wins",
                "draws",
                "losses",
                "goals_for",
                "goals_against",
                "points",
                "yellow_cards",
                "red_cards",
                "rank",
                "updated_at",
            ]
        )

    active = [entry for entry in entries if not entry.is_withdrawn]
    groups = defaultdict(list)
    for entry in active:
        groups[entry.group].append(entry)
    for group_entries in groups.values():
        by_points = defaultdict(list)
        for entry in group_entries:
            by_points[entry.points].append(entry)
        mini = {
            points: _head_to_head_stats(tied) if len(tied) > 1 else {}
            for points, tied in by_points.items()
        }

        def compare(left, right):
            left_key = (
                left.wins,
                mini[left.points].get(left.pk, {}).get("points", 0),
                mini[left.points].get(left.pk, {}).get("gd", 0),
                mini[left.points].get(left.pk, {}).get("gf", 0),
                left.goal_difference,
                left.goals_for,
                -left.yellow_cards,
                -left.red_cards,
            )
            right_key = (
                right.wins,
                mini[right.points].get(right.pk, {}).get("points", 0),
                mini[right.points].get(right.pk, {}).get("gd", 0),
                mini[right.points].get(right.pk, {}).get("gf", 0),
                right.goal_difference,
                right.goals_for,
                -right.yellow_cards,
                -right.red_cards,
            )
            if left.points != right.points:
                return -1 if left.points > right.points else 1
            if left_key != right_key:
                return -1 if left_key > right_key else 1
            return (left.team.name.lower() > right.team.name.lower()) - (
                left.team.name.lower() < right.team.name.lower()
            )

        ordered = sorted(group_entries, key=cmp_to_key(compare))
        for rank, entry in enumerate(ordered, 1):
            entry.rank = rank
            entry.save(update_fields=["rank", "updated_at"])
    update_suspensions(championship)
    return entries


def update_suspensions(championship):
    """Mark active registrations suspended once card threshold is reached.

    This is a conservative cumulative threshold rule; administrators can
    release a suspension by changing registration status after serving it.
    """
    if not isinstance(championship, Championship):
        championship = Championship.objects.get(pk=championship)
    threshold = championship.yellow_cards_for_suspension
    if threshold <= 0:
        return
    registrations = PlayerRegistration.objects.filter(
        championship_team__championship=championship,
        status__in=[
            PlayerRegistration.Status.ACTIVE,
            PlayerRegistration.Status.SUSPENDED,
        ],
    )
    counts = dict(
        MatchEventParticipant.objects.filter(
            player_registration__in=registrations,
            event__match__status=Match.Status.FINISHED,
            event__is_canceled=False,
            event__event_type__counts_as_yellow_card=True,
        )
        .values("player_registration_id")
        .annotate(total=Count("pk"))
        .values_list("player_registration_id", "total")
    )
    for registration in registrations:
        if counts.get(registration.pk, 0) >= threshold:
            registration.status = PlayerRegistration.Status.SUSPENDED
            registration.save(update_fields=["status", "updated_at"])

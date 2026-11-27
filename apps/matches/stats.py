"""
Individual rankings of a championship, computed from the match events.

Every query aggregates in the database (one query per ranking) and only
counts events that were not canceled. Own goals and penalty shoot-out
kicks never count for the top scorers.
"""

from django.db.models import Count, Q

from apps.championships.models import PlayerRegistration

from .models import EventType

DEFAULT_LIMIT = 10

SCORER = "scorer"
ASSIST = "assist"
BOOKED = "booked-player"


def _valid(role_code, **event_filters):
    """Filter for a player's participations with ``role_code``."""
    conditions = {
        "event_participations__role__code": role_code,
        "event_participations__event__is_canceled": False,
    }
    conditions.update(
        {
            f"event_participations__event__{key}": value
            for key, value in event_filters.items()
        }
    )
    return Q(**conditions)


def _registrations(championship, team=None):
    queryset = PlayerRegistration.objects.filter(
        championship_team__championship=championship
    ).select_related("player", "championship_team__team")
    if team is not None:
        queryset = queryset.filter(championship_team__team=team)
    return queryset


def top_scorers(championship, *, team=None, limit=DEFAULT_LIMIT):
    goals = Count(
        "event_participations",
        filter=_valid(
            SCORER,
            event_type__score_effect=EventType.ScoreEffect.FOR_TEAM,
        ),
    )
    return (
        _registrations(championship, team)
        .annotate(total=goals)
        .filter(total__gt=0)
        .order_by("-total", "player__full_name")[:limit]
    )


def top_assists(championship, *, team=None, limit=DEFAULT_LIMIT):
    assists = Count("event_participations", filter=_valid(ASSIST))
    return (
        _registrations(championship, team)
        .annotate(total=assists)
        .filter(total__gt=0)
        .order_by("-total", "player__full_name")[:limit]
    )


def disciplinary_ranking(championship, *, team=None, limit=DEFAULT_LIMIT):
    """Players ordered by red cards, then yellow cards."""
    yellow = Count(
        "event_participations",
        filter=_valid(BOOKED, event_type__counts_as_yellow_card=True),
    )
    red = Count(
        "event_participations",
        filter=_valid(BOOKED, event_type__counts_as_red_card=True),
    )
    return (
        _registrations(championship, team)
        .annotate(yellow=yellow, red=red)
        .filter(Q(yellow__gt=0) | Q(red__gt=0))
        .order_by("-red", "-yellow", "player__full_name")[:limit]
    )

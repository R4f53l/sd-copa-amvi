"""
Business rules for match sheets: lineups, events and the consolidated
score.

Views (and later the REST API) call these functions instead of touching
the models directly, so every entry point enforces the same rules.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.championships.models import PlayerRegistration

from .models import EventType, Lineup, Match, MatchEvent, MatchEventParticipant

# Laws of the Game: a match cannot start with fewer than 7 players.
MIN_STARTERS = 7
MAX_STARTERS = 11

# Roles that do not have to be filled when recording an event.
OPTIONAL_ROLES = frozenset({"assist", "goalkeeper"})
# Roles played by someone from the *other* team (e.g. the goalkeeper who
# faces a penalty).
OPPONENT_ROLES = frozenset({"goalkeeper"})

SHOOTOUT_GOAL = "shootout-goal"

LOCKED_STATUSES = frozenset({Match.Status.FINISHED, Match.Status.CANCELED})


def is_locked(match):
    """Finished or canceled matches have a closed match sheet."""
    return match.status in LOCKED_STATUSES


def ensure_editable(match):
    if is_locked(match):
        raise ValidationError(
            _("The match sheet is closed for finished or canceled matches.")
        )


# ---------------------------------------------------------------------------
# Lineups
# ---------------------------------------------------------------------------


def lineup_candidates(match, team):
    """
    Registrations that may appear on the team's match sheet: every active
    player, plus anyone already listed (so they can be removed even if
    their registration changed afterwards).
    """
    listed_ids = match.lineups.filter(team=team).values(
        "player_registration_id"
    )
    return (
        PlayerRegistration.objects.filter(championship_team=team)
        .filter(
            Q(status=PlayerRegistration.Status.ACTIVE) | Q(pk__in=listed_ids)
        )
        .select_related("player")
        .order_by("shirt_number", "player__full_name")
    )


def registrations_with_events(match, team):
    """Players of the team involved in non-canceled events of the match."""
    return set(
        MatchEventParticipant.objects.filter(
            event__match=match,
            event__is_canceled=False,
            player_registration__championship_team=team,
        ).values_list("player_registration_id", flat=True)
    )


@transaction.atomic
def save_lineup(match, team, entries):
    """
    Replace the team's match sheet.

    ``entries`` is a list of dicts with ``registration``, ``role``,
    ``shirt_number``, ``position`` and ``is_captain``. Validation is done
    by ``LineupFormSet``; this function only persists the result.
    """
    ensure_editable(match)
    match.lineups.filter(team=team).delete()
    Lineup.objects.bulk_create(
        Lineup(
            match=match,
            team=team,
            player_registration=entry["registration"],
            role=entry["role"],
            shirt_number=entry["shirt_number"],
            position=entry["position"],
            is_captain=entry["is_captain"],
        )
        for entry in entries
    )


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


def validate_participants(match, event_type, team, participants):
    """
    ``participants`` maps each ``EventRole`` to a ``Lineup`` entry (or
    ``None``). Raises ``ValidationError`` keyed by role code.
    """
    errors = {}
    seen = {}
    for role, lineup in participants.items():
        if lineup is None:
            if role.code not in OPTIONAL_ROLES:
                errors[role.code] = _("This field is required.")
            continue
        if lineup.match_id != match.pk:
            errors[role.code] = _(
                "Player is not on the match sheet for this match."
            )
            continue
        if team is not None:
            same_team = lineup.team_id == team.pk
            if role.code in OPPONENT_ROLES and same_team:
                errors[role.code] = _("Choose a player from the other team.")
            elif role.code not in OPPONENT_ROLES and not same_team:
                errors[role.code] = _("Choose a player from the event's team.")
        registration_id = lineup.player_registration_id
        if registration_id in seen:
            errors[role.code] = _(
                "The same player cannot have two roles in one event."
            )
        seen[registration_id] = role
    if errors:
        raise ValidationError(errors)


@transaction.atomic
def record_event(
    match,
    *,
    event_type,
    team,
    period,
    minute,
    stoppage_minute=0,
    description="",
    participants=None,
    recorded_by=None,
):
    """Record an event with its participants and refresh the score."""
    ensure_editable(match)
    participants = participants or {}
    validate_participants(match, event_type, team, participants)

    event = MatchEvent(
        match=match,
        event_type=event_type,
        team=team,
        period=period,
        minute=minute,
        stoppage_minute=stoppage_minute,
        description=description,
        recorded_by=recorded_by,
    )
    event.full_clean()
    event.save()
    MatchEventParticipant.objects.bulk_create(
        MatchEventParticipant(
            event=event,
            role=role,
            player_registration_id=lineup.player_registration_id,
        )
        for role, lineup in participants.items()
        if lineup is not None
    )
    recompute_score(match)
    return event


@transaction.atomic
def cancel_event(event, *, reason, canceled_by=None):
    """Soft-cancel an event (kept for auditing) and refresh the score."""
    ensure_editable(event.match)
    if event.is_canceled:
        raise ValidationError(_("This event has already been canceled."))
    event.is_canceled = True
    event.canceled_by = canceled_by
    event.canceled_at = timezone.now()
    event.cancel_reason = reason
    event.save(
        update_fields=[
            "is_canceled",
            "canceled_by",
            "canceled_at",
            "cancel_reason",
            "updated_at",
        ]
    )
    recompute_score(event.match)
    return event


def recompute_score(match):
    """
    Rebuild the consolidated score from the non-canceled events.

    Recomputing (instead of incrementing) keeps the score correct after
    cancellations and is cheap: a match has a few dozen events at most.
    """
    home = away = 0
    home_shootout = away_shootout = 0
    has_shootout = False

    events = match.events.filter(is_canceled=False).select_related(
        "event_type"
    )
    for event in events:
        is_home = event.team_id == match.home_team_id
        effect = event.event_type.score_effect
        if effect == EventType.ScoreEffect.FOR_TEAM:
            home, away = (home + 1, away) if is_home else (home, away + 1)
        elif effect == EventType.ScoreEffect.FOR_OPPONENT:
            home, away = (home, away + 1) if is_home else (home + 1, away)
        if event.event_type.category == EventType.Category.SHOOTOUT:
            has_shootout = True
            if event.event_type.code == SHOOTOUT_GOAL:
                if is_home:
                    home_shootout += 1
                else:
                    away_shootout += 1

    match.home_score = home
    match.away_score = away
    match.home_penalty_score = home_shootout if has_shootout else None
    match.away_penalty_score = away_shootout if has_shootout else None
    match.save(
        update_fields=[
            "home_score",
            "away_score",
            "home_penalty_score",
            "away_penalty_score",
            "updated_at",
        ]
    )

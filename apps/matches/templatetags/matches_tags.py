"""Template helpers for match pages (icons and status styling)."""

from django import template

from apps.matches.models import EventType, Match

register = template.Library()

# Used when an EventType has no ``icon`` configured.
EVENT_ICONS = {
    "goal": "⚽",
    "penalty-goal": "⚽",
    "own-goal": "⚽",
    "penalty-missed": "✖️",
    "yellow-card": "🟨",
    "second-yellow-card": "🟨",
    "red-card": "🟥",
    "substitution": "🔄",
    "shootout-goal": "✅",
    "shootout-missed": "❌",
    "period-start": "▶️",
    "period-end": "⏸️",
}
CATEGORY_ICONS = {
    EventType.Category.SCORING: "⚽",
    EventType.Category.DISCIPLINARY: "🟨",
    EventType.Category.SUBSTITUTION: "🔄",
    EventType.Category.SHOOTOUT: "🎯",
    EventType.Category.MATCH_FLOW: "⏱️",
}

STATUS_CLASSES = {
    Match.Status.SCHEDULED: "is-scheduled",
    Match.Status.FINISHED: "is-finished",
    Match.Status.POSTPONED: "is-off",
    Match.Status.CANCELED: "is-off",
}


@register.filter
def event_icon(event_type):
    if event_type.icon:
        return event_type.icon
    return EVENT_ICONS.get(
        event_type.code, CATEGORY_ICONS.get(event_type.category, "•")
    )


@register.filter
def status_class(match):
    if match.is_live:
        return "is-live"
    return STATUS_CLASSES.get(match.status, "")

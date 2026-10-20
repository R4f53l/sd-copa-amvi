"""Template helpers to display teams consistently across the site."""

import re

from django import template
from django.utils.html import format_html

register = template.Library()

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
FALLBACK_BG = "#5b6b63"


def _readable_text_on(background):
    """Black or white, whichever contrasts more with ``background``."""
    red, green, blue = (int(background[i : i + 2], 16) for i in (1, 3, 5))
    luminance = 0.299 * red + 0.587 * green + 0.114 * blue
    return "#14231b" if luminance > 160 else "#ffffff"


@register.simple_tag
def team_badge(team, size="2.25rem"):
    """
    The team's crest, or its initials on the team colours when there is
    no crest. Accepts a ``Team`` or a ``ChampionshipTeam``.
    """
    team = getattr(team, "team", team)
    if team is None:
        return ""
    if team.crest:
        return format_html(
            '<span class="team-badge" style="--size:{}">'
            '<img src="{}" alt="{}"></span>',
            size,
            team.crest.url,
            team.name,
        )
    background = (
        team.primary_color
        if HEX_COLOR.match(team.primary_color or "")
        else FALLBACK_BG
    )
    color = (
        team.secondary_color
        if HEX_COLOR.match(team.secondary_color or "")
        and team.secondary_color.lower() != background.lower()
        else _readable_text_on(background)
    )
    return format_html(
        '<span class="team-badge" style="--size:{};background:{};color:{}" '
        'title="{}" aria-hidden="true">{}</span>',
        size,
        background,
        color,
        team.name,
        (team.short_name or team.name[:3]).upper(),
    )


@register.filter
def team_color(team):
    """Primary colour of a ``Team``/``ChampionshipTeam`` (for accents)."""
    team = getattr(team, "team", team)
    color = getattr(team, "primary_color", "") or ""
    return color if HEX_COLOR.match(color) else ""

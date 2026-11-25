"""
Weather forecast for a match, from the free Open-Meteo API
(https://open-meteo.com — no API key required).

Results are cached so a busy match page does not hit the API on every
request, and any failure simply hides the forecast.
"""

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.shared.http import ExternalServiceError, get_json

from .models import Match

logger = logging.getLogger(__name__)

API_URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_DAYS = 16  # Open-Meteo's forecast horizon
CACHE_SECONDS = 30 * 60
FAILURE_CACHE_SECONDS = 5 * 60
_FAILED = "failed"

# WMO weather interpretation codes, grouped.
WEATHER_CODES = [
    ((0,), "☀️", _("Clear sky")),
    ((1, 2), "🌤️", _("Partly cloudy")),
    ((3,), "☁️", _("Overcast")),
    ((45, 48), "🌫️", _("Fog")),
    ((51, 53, 55, 56, 57), "🌦️", _("Drizzle")),
    ((61, 63, 65, 66, 67, 80, 81, 82), "🌧️", _("Rain")),
    ((71, 73, 75, 77, 85, 86), "❄️", _("Snow")),
    ((95, 96, 99), "⛈️", _("Thunderstorm")),
]

FORECAST_STATUSES = (Match.Status.SCHEDULED, *Match.LIVE_STATUSES)


@dataclass(frozen=True)
class Forecast:
    temperature: float
    rain_chance: int | None
    code: int

    @property
    def icon(self):
        return self._describe()[0]

    @property
    def description(self):
        return self._describe()[1]

    def _describe(self):
        for codes, icon, label in WEATHER_CODES:
            if self.code in codes:
                return icon, label
        return "🌡️", ""


def match_forecast(match):
    """Forecast for the match kick-off hour, or ``None`` if unavailable."""
    stadium = match.stadium
    if (
        stadium is None
        or stadium.latitude is None
        or stadium.longitude is None
        or match.status not in FORECAST_STATUSES
    ):
        return None

    kickoff = timezone.localtime(match.scheduled_at)
    today = timezone.localdate()
    last_day = today + timedelta(days=FORECAST_DAYS - 1)
    if not today <= kickoff.date() <= last_day:
        return None

    hour = kickoff.strftime("%Y-%m-%dT%H:00")
    key = f"weather:{stadium.latitude}:{stadium.longitude}:{hour}"
    cached = cache.get(key)
    if cached == _FAILED:
        return None
    if cached is not None:
        return cached

    try:
        forecast = _fetch(stadium.latitude, stadium.longitude, kickoff, hour)
    except (
        ExternalServiceError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
    ) as exc:
        logger.warning("Weather forecast unavailable: %s", exc)
        cache.set(key, _FAILED, FAILURE_CACHE_SECONDS)
        return None
    cache.set(key, forecast, CACHE_SECONDS)
    return forecast


def _fetch(latitude, longitude, kickoff, hour):
    day = kickoff.date().isoformat()
    data = get_json(
        API_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "temperature_2m,precipitation_probability,weather_code",
            "timezone": settings.TIME_ZONE,
            "start_date": day,
            "end_date": day,
        },
    )
    hourly = data["hourly"]
    index = hourly["time"].index(hour)
    rain = hourly.get("precipitation_probability", [None] * (index + 1))
    return Forecast(
        temperature=hourly["temperature_2m"][index],
        rain_chance=rain[index],
        code=hourly["weather_code"][index],
    )

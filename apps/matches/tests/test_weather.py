from datetime import datetime, timedelta
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from apps.matches import weather
from apps.matches.models import Match
from apps.shared.http import ExternalServiceError
from apps.teams.models import City, Stadium


def api_answer(hour, temperature=31.4, rain=20, code=2):
    return {
        "hourly": {
            "time": [hour],
            "temperature_2m": [temperature],
            "precipitation_probability": [rain],
            "weather_code": [code],
        }
    }


class MatchForecastTests(TestCase):
    """``match_forecast`` only needs a few attributes, so no DB rows."""

    def setUp(self):
        cache.clear()
        stadium = Stadium(
            name="Estadio",
            city=City(name="Picos"),
            latitude=-7.07,
            longitude=-41.46,
        )
        kickoff = timezone.make_aware(
            datetime.combine(
                timezone.localdate() + timedelta(days=2),
                datetime.min.time().replace(hour=16),
            )
        )
        self.match = Match(
            stadium=stadium,
            scheduled_at=kickoff,
            status=Match.Status.SCHEDULED,
        )
        self.hour = timezone.localtime(kickoff).strftime("%Y-%m-%dT%H:00")

    @mock.patch("apps.matches.weather.get_json")
    def test_forecast_for_kickoff_hour_is_cached(self, get_json):
        get_json.return_value = api_answer(self.hour)
        first = weather.match_forecast(self.match)
        second = weather.match_forecast(self.match)

        self.assertEqual(get_json.call_count, 1)
        self.assertEqual(first, second)
        self.assertEqual(first.temperature, 31.4)
        self.assertEqual(first.rain_chance, 20)
        self.assertEqual(first.icon, "🌤️")

    @mock.patch("apps.matches.weather.get_json")
    def test_failures_hide_the_forecast(self, get_json):
        get_json.side_effect = ExternalServiceError("offline")
        self.assertIsNone(weather.match_forecast(self.match))
        self.assertIsNone(weather.match_forecast(self.match))
        self.assertEqual(get_json.call_count, 1)  # failure is cached too

    @mock.patch("apps.matches.weather.get_json")
    def test_unexpected_answer_hides_the_forecast(self, get_json):
        get_json.return_value = api_answer("2000-01-01T00:00")
        self.assertIsNone(weather.match_forecast(self.match))

    @mock.patch("apps.matches.weather.get_json")
    def test_no_request_when_forecast_cannot_exist(self, get_json):
        far = self.match.scheduled_at + timedelta(days=30)
        cases = [
            Match(stadium=None, scheduled_at=self.match.scheduled_at),
            Match(
                stadium=self.match.stadium,
                scheduled_at=self.match.scheduled_at,
                status=Match.Status.FINISHED,
            ),
            Match(stadium=self.match.stadium, scheduled_at=far),
        ]
        for match in cases:
            self.assertIsNone(weather.match_forecast(match))
        get_json.assert_not_called()

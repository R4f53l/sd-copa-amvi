from django.urls import reverse

from apps.matches import services
from apps.matches.models import EventRole, EventType, Match
from apps.matches.tests.test_pages import MatchPagesTestCase
from apps.matches.views import LIVE_REFRESH_SECONDS, UPCOMING_REFRESH_SECONDS


class MatchLiveTests(MatchPagesTestCase):
    def setUp(self):
        self.set_lineups()
        self.url = reverse("matches:live", args=[self.match.pk])

    def snapshot(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        return response.json()

    def set_status(self, status):
        Match.objects.filter(pk=self.match.pk).update(status=status)
        self.match.refresh_from_db()

    def test_interval_follows_the_match_status(self):
        self.assertEqual(self.snapshot()["interval"], UPCOMING_REFRESH_SECONDS)
        self.set_status(Match.Status.FIRST_HALF)
        self.assertEqual(self.snapshot()["interval"], LIVE_REFRESH_SECONDS)
        self.set_status(Match.Status.FINISHED)
        self.assertEqual(self.snapshot()["interval"], 0)

    def test_new_event_changes_version_score_and_timeline(self):
        before = self.snapshot()
        services.record_event(
            self.match,
            event_type=EventType.objects.get(code="goal"),
            team=self.home,
            period=1,
            minute=12,
            recorded_by=self.official,
            participants={
                EventRole.objects.get(code="scorer"): self.lineup_of(
                    self.home, 9
                )
            },
        )
        after = self.snapshot()
        self.assertNotEqual(before["version"], after["version"])
        self.assertIn("1<span", after["regions"]["score"])
        self.assertIn("12&#x27;", after["regions"]["timeline"])

    def test_visitors_get_no_cancel_controls(self):
        services.record_event(
            self.match,
            event_type=EventType.objects.get(code="goal"),
            team=self.home,
            period=1,
            minute=12,
            recorded_by=self.official,
            participants={
                EventRole.objects.get(code="scorer"): self.lineup_of(
                    self.home, 9
                )
            },
        )
        visitor = self.snapshot()["regions"]["timeline"]
        self.assertNotIn("/cancel/", visitor)

        self.login(self.official)
        official = self.snapshot()["regions"]["timeline"]
        self.assertIn("/cancel/", official)

    def test_sheet_polls_only_while_the_match_is_open(self):
        sheet = reverse("matches:sheet", args=[self.match.pk])
        self.assertContains(self.client.get(sheet), "data-live-url")
        self.set_status(Match.Status.FINISHED)
        self.assertNotContains(self.client.get(sheet), "data-live-url")


class BroadcastTests(MatchPagesTestCase):
    def sheet(self):
        return self.client.get(reverse("matches:sheet", args=[self.match.pk]))

    def test_youtube_link_is_embedded(self):
        Match.objects.filter(pk=self.match.pk).update(
            streaming_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )
        self.assertContains(
            self.sheet(),
            'src="https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"',
        )

    def test_other_links_become_a_button(self):
        Match.objects.filter(pk=self.match.pk).update(
            streaming_url="https://www.twitch.tv/copaamvi"
        )
        response = self.sheet()
        self.assertNotContains(response, "<iframe")
        self.assertContains(response, 'href="https://www.twitch.tv/copaamvi"')


class HomeLiveTests(MatchPagesTestCase):
    def test_live_now_region_appears_when_a_match_starts(self):
        url = reverse("home_live")
        self.assertNotIn("live-title", url)
        empty = self.client.get(url).json()
        self.assertNotIn("live-title", empty["regions"]["live-now"])

        Match.objects.filter(pk=self.match.pk).update(
            status=Match.Status.SECOND_HALF
        )
        live = self.client.get(url).json()
        self.assertIn("live-title", live["regions"]["live-now"])
        self.assertNotEqual(empty["version"], live["version"])

"""Site-level pages that aggregate several bounded contexts."""

from django.db.models import F, Sum
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views import View
from django.views.generic import TemplateView

from apps.championships.selectors import featured_championship
from apps.matches.models import Match

UPCOMING_LIMIT = 6
RESULTS_LIMIT = 6
# Seconds between refreshes of the "live now" section of the home page.
HOME_LIVE_REFRESH_SECONDS = 30


def visible_matches(championship):
    matches = Match.objects.select_related(
        "championship",
        "home_team__team",
        "away_team__team",
        "stadium__city",
    ).exclude(status=Match.Status.CANCELED)
    if championship is not None:
        matches = matches.filter(championship=championship)
    return matches


def live_matches(championship):
    return (
        visible_matches(championship)
        .filter(status__in=Match.LIVE_STATUSES)
        .order_by("scheduled_at")
    )


class HomeView(TemplateView):
    """Public landing page: live matches, next fixtures, latest results."""

    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        championship = featured_championship()
        matches = visible_matches(championship)

        if championship is not None:
            finished = matches.filter(status=Match.Status.FINISHED)
            context["summary"] = {
                "teams": championship.team_entries.filter(
                    is_withdrawn=False
                ).count(),
                "played": finished.count(),
                "goals": finished.aggregate(
                    total=Sum(F("home_score") + F("away_score"))
                )["total"]
                or 0,
            }

        context.update(
            championship=championship,
            live_matches=live_matches(championship),
            live_interval=HOME_LIVE_REFRESH_SECONDS,
            upcoming_matches=matches.filter(
                status=Match.Status.SCHEDULED
            ).order_by("scheduled_at")[:UPCOMING_LIMIT],
            recent_results=matches.filter(
                status=Match.Status.FINISHED
            ).order_by("-scheduled_at")[:RESULTS_LIMIT],
        )
        return context


class HomeLiveView(View):
    """JSON for the "live now" region of the home page (see live.js)."""

    def get(self, request):
        matches = list(live_matches(featured_championship()))
        version = "|".join(
            f"{m.pk}:{m.updated_at.isoformat()}" for m in matches
        )
        response = JsonResponse(
            {
                "version": version,
                "interval": HOME_LIVE_REFRESH_SECONDS,
                "regions": {
                    "live-now": render_to_string(
                        "_live_now.html", {"live_matches": matches}, request
                    )
                },
            }
        )
        response["Cache-Control"] = "no-store"
        return response

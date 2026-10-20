from django.shortcuts import render
from django.utils import timezone

from apps.matches.models import Match


def home(request):
    next_matches = (
        Match.objects.filter(scheduled_at__gte=timezone.now())
        .exclude(status=Match.Status.CANCELED)
        .select_related(
            "championship",
            "home_team__team__city",
            "away_team__team__city",
        )
        .order_by("scheduled_at")[:3]
    )
    return render(
        request,
        "home.html",
        {"next_matches": next_matches},
    )

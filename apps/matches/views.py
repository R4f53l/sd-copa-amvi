"""Server-rendered public views for matches."""

from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from apps.championships.models import ChampionshipTeam
from apps.matches.forms import PublicMatchFilterForm
from apps.matches.models import Match
from apps.teams.models import City

MATCHES_PER_PAGE = 10

def public_match_list(request):
    matches = (
        Match.objects.exclude(status=Match.Status.CANCELED)
        .select_related("stadium__city")
        .order_by("-scheduled_at", "-pk")
    )

    round_numbers = list(
        matches.exclude(round_number__isnull=True)
        .values_list("round_number", flat=True)
        .distinct()
        .order_by("round_number")
    )

    city_ids = ChampionshipTeam.objects.filter(
        Q(home_matches__in=matches) | Q(away_matches__in=matches)
    ).values_list("team__city_id", flat=True)
    cities = City.objects.filter(pk__in=city_ids).order_by("name", "state")

    form = PublicMatchFilterForm(
        request.GET,
        round_numbers=round_numbers,
        cities=cities,
    )

    if form.is_valid():
        round_number = form.cleaned_data["round_number"]
        city = form.cleaned_data["city"]
        if round_number is not None:
            matches = matches.filter(round_number=round_number)
        if city is not None:
            matches = matches.filter(stadium__city=city)

    page_obj = Paginator(matches, MATCHES_PER_PAGE).get_page(
        request.GET.get("page")
    )
    
    return render(
        request,
        "matches/public_match_list.html",
        {"form": form, "page_obj": page_obj},
    )

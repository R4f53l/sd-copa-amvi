"""Server-rendered views (Django templates) for the matches app."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from apps.championships.models import Championship
from apps.championships.selectors import (
    featured_championship,
    public_championships,
)
from apps.shared.validators import is_uuid

from . import services, stats, weather
from .forms import (
    CancelEventForm,
    LineupFormSet,
    MatchEventForm,
    MatchFilterForm,
    MatchForm,
)
from .models import EventType, Match, MatchEvent, MatchEventParticipant
from .permissions import (
    AdminRequiredMixin,
    MatchOfficialRequiredMixin,
    can_manage_matches,
    can_officiate,
)
from .routing import websocket_urlpatterns

# ---------------------------------------------------------------------------
# Fixtures (calendar)
# ---------------------------------------------------------------------------


class MatchListView(ListView):
    """
    Public match calendar and results. The panel subclass narrows this same
    page to the logged-in official's matches and exposes management actions.
    """

    template_name = "matches/match_list.html"
    context_object_name = "matches"

    @property
    def public_mode(self):
        return not self.request.user.is_authenticated

    def get_paginate_by(self, queryset):
        return 10 if self.public_mode else 20

    def get_base_queryset(self):
        queryset = Match.objects.select_related(
            "championship",
            "home_team__team__city",
            "away_team__team__city",
            "stadium__city",
        )
        if self.public_mode:
            queryset = queryset.exclude(status=Match.Status.CANCELED)
        elif not can_manage_matches(self.request.user):
            queryset = queryset.filter(table_officials=self.request.user)
        return queryset

    def get_queryset(self):
        queryset = self.get_base_queryset().order_by(
            "championship", "round_number", "scheduled_at"
        )

        form = MatchFilterForm(self.request.GET)
        self.match_filter_form = form
        if form.is_valid():
            if championship := form.cleaned_data["championship"]:
                queryset = queryset.filter(championship=championship)
            if city := form.cleaned_data["city"]:
                # Where the match is played: the stadium's city, or the
                # home team's city while no stadium has been set.
                queryset = queryset.filter(
                    Q(stadium__city=city)
                    | Q(stadium__isnull=True, home_team__team__city=city)
                )
            if round_number := form.cleaned_data["round"]:
                queryset = queryset.filter(round_number=round_number)
            if status := form.cleaned_data["status"]:
                queryset = queryset.filter(status=status)
            if search := form.cleaned_data["q"].strip():
                queryset = queryset.filter(
                    Q(home_team__team__name__icontains=search)
                    | Q(away_team__team__name__icontains=search)
                )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.copy()
        query.pop("page", None)
        context.update(
            championships=Championship.objects.all(),
            filters=self.request.GET,
            querystring=query.urlencode(),
            can_manage=can_manage_matches(self.request.user),
            public_mode=self.public_mode,
            form=self.match_filter_form,
        )
        return context


class MatchFormMixin(AdminRequiredMixin):
    model = Match
    form_class = MatchForm
    template_name = "matches/match_form.html"

    def get_championship(self):
        raise NotImplementedError

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["championship"] = self.get_championship()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["championship"] = self.get_championship()
        return context

    def get_success_url(self):
        return reverse("matches:sheet", args=[self.object.pk])


class MatchCreateView(MatchFormMixin, CreateView):
    def get_championship(self):
        return get_object_or_404(
            Championship, pk=self.kwargs["championship_pk"]
        )

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            _("Match %(match)s scheduled.") % {"match": self.object},
        )
        return response


class MatchUpdateView(MatchFormMixin, UpdateView):
    def get_championship(self):
        return self.object.championship

    def get_queryset(self):
        return Match.objects.select_related("championship")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            _("Match %(match)s updated.") % {"match": self.object},
        )
        return response


# ---------------------------------------------------------------------------
# Lineups
# ---------------------------------------------------------------------------


class LineupView(MatchOfficialRequiredMixin, TemplateView):
    template_name = "matches/lineup_form.html"

    def get_team(self):
        side = self.kwargs["side"]
        return self.match.home_team if side == "home" else self.match.away_team

    def get_formset(self):
        data = self.request.POST if self.request.method == "POST" else None
        return LineupFormSet(data, match=self.match, team=self.get_team())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            match=self.match,
            team=self.get_team(),
            formset=kwargs.get("formset") or self.get_formset(),
            locked=services.is_locked(self.match),
            min_starters=services.MIN_STARTERS,
            max_starters=services.MAX_STARTERS,
        )
        return context

    def post(self, request, *args, **kwargs):
        formset = self.get_formset()
        if not formset.is_valid():
            return self.render_to_response(
                self.get_context_data(formset=formset)
            )
        try:
            services.save_lineup(self.match, self.get_team(), formset.entries)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(
                request,
                _("Lineup of %(team)s saved.")
                % {"team": self.get_team().team.name},
            )
        return redirect("matches:sheet", pk=self.match.pk)


# ---------------------------------------------------------------------------
# Match sheet (events)
# ---------------------------------------------------------------------------

# Seconds between refreshes of the live regions (score and timeline).
LIVE_REFRESH_SECONDS = 10
UPCOMING_REFRESH_SECONDS = 60


def timeline_events(match):
    """Events of the match, most recent first (what matters live)."""
    return (
        match.events.select_related(
            "event_type", "team__team", "recorded_by", "canceled_by"
        )
        .prefetch_related(
            Prefetch(
                "participants",
                queryset=MatchEventParticipant.objects.select_related(
                    "role", "player_registration__player"
                ),
            )
        )
        .order_by("-period", "-minute", "-stoppage_minute", "-created_at")
    )


def live_context(request, match):
    """Context of the regions that refresh live (score and timeline)."""
    return {
        "match": match,
        "events": timeline_events(match),
        "locked": services.is_locked(match),
        "can_officiate": can_officiate(request.user, match),
        "cancel_form": CancelEventForm(),
    }


def websocket_enabled():
    """True once a WebSocket consumer is routed (see routing.py)."""
    return bool(websocket_urlpatterns)


def live_interval(match):
    """How often the page should refresh; 0 once the sheet is closed."""
    if services.is_locked(match):
        return 0
    if match.is_live:
        return LIVE_REFRESH_SECONDS
    return UPCOMING_REFRESH_SECONDS


def live_version(match, events):
    """Changes whenever the score, status or any event changes."""
    latest = max((e.updated_at for e in events), default=None)
    return "|".join(
        [
            match.updated_at.isoformat(),
            str(len(events)),
            latest.isoformat() if latest else "",
        ]
    )


class MatchLiveView(View):
    """
    JSON snapshot of the live regions of a match page, polled by
    ``static/js/live.js``. Public: it exposes the same data as the page.
    """

    def get(self, request, pk):
        match = get_object_or_404(
            Match.objects.select_related(
                "championship", "home_team__team", "away_team__team"
            ),
            pk=pk,
        )
        context = live_context(request, match)
        events = list(context["events"])
        context["events"] = events
        response = JsonResponse(
            {
                "version": live_version(match, events),
                "interval": live_interval(match),
                "regions": {
                    "score": render_to_string(
                        "matches/_live_score.html", context, request
                    ),
                    "timeline": render_to_string(
                        "matches/_timeline.html", context, request
                    ),
                },
            }
        )
        response["Cache-Control"] = "no-store"
        return response


class MatchSheetView(MatchOfficialRequiredMixin, TemplateView):
    """
    Digital match sheet: timeline, lineups and the form to record a new
    event. The event form depends on the chosen type (``?event_type=``),
    so recording is a two-step flow that works without JavaScript.
    """

    template_name = "matches/match_sheet.html"

    def dispatch(self, request, *args, **kwargs):
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return TemplateView.dispatch(self, request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)

    def get_event_type(self):
        code = self.request.GET.get("event_type") or self.request.POST.get(
            "event_type"
        )
        if not code:
            return None
        return EventType.objects.filter(code=code, is_active=True).first()

    def get_event_form(self, event_type):
        if event_type is None:
            return None
        data = self.request.POST if self.request.method == "POST" else None
        return MatchEventForm(data, match=self.match, event_type=event_type)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        match = self.match
        event_type = kwargs.get("event_type", self.get_event_type())
        lineups = match.lineups.select_related(
            "player_registration__player"
        ).order_by("role", "shirt_number")
        context.update(live_context(self.request, match))
        context.update(
            home_lineup=[
                e for e in lineups if e.team_id == match.home_team_id
            ],
            away_lineup=[
                e for e in lineups if e.team_id == match.away_team_id
            ],
            can_manage=can_manage_matches(self.request.user),
            forecast=weather.match_forecast(match),
            live_interval=live_interval(match),
            live_websocket=websocket_enabled(),
            event_types=EventType.objects.filter(is_active=True),
            event_type=event_type,
            event_form=kwargs.get("event_form")
            or self.get_event_form(event_type),
        )
        return context

    def post(self, request, *args, **kwargs):
        event_type = self.get_event_type()
        form = self.get_event_form(event_type)
        if form is None:
            messages.error(request, _("Choose an event type."))
            return redirect("matches:sheet", pk=self.match.pk)
        if not form.is_valid():
            return self.render_to_response(
                self.get_context_data(event_type=event_type, event_form=form)
            )
        data = form.cleaned_data
        try:
            event = services.record_event(
                self.match,
                event_type=event_type,
                team=data["team_obj"],
                period=data["period"],
                minute=data["minute"],
                stoppage_minute=data["stoppage_minute"] or 0,
                description=data["description"],
                participants=data["participants"],
                recorded_by=request.user,
            )
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return self.render_to_response(
                self.get_context_data(event_type=event_type, event_form=form)
            )
        messages.success(
            request,
            _("%(event)s recorded at %(minute)s.")
            % {"event": event.event_type.name, "minute": event.display_minute},
        )
        return redirect("matches:sheet", pk=self.match.pk)


class EventCancelView(MatchOfficialRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk, event_pk):
        event = get_object_or_404(MatchEvent, pk=event_pk, match=self.match)
        form = CancelEventForm(request.POST)
        if not form.is_valid():
            messages.error(request, _("Enter the cancellation reason."))
            return redirect("matches:sheet", pk=self.match.pk)
        try:
            services.cancel_event(
                event,
                reason=form.cleaned_data["reason"],
                canceled_by=request.user,
            )
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(
                request,
                _("Event %(event)s canceled.") % {"event": event.event_type},
            )
        return redirect("matches:sheet", pk=self.match.pk)


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


class StatisticsView(TemplateView):
    """Public rankings: top scorers, assists and disciplinary record."""

    template_name = "matches/statistics.html"

    def get_championship(self):
        championship_id = self.request.GET.get("championship")
        if championship_id:
            championship = (
                public_championships().filter(pk=championship_id).first()
                if is_uuid(championship_id)
                else None
            )
            if championship is not None:
                return championship
        return featured_championship()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        championship = self.get_championship()
        context.update(
            championship=championship,
            championships=public_championships(),
        )
        if championship is not None:
            context.update(
                scorers=stats.top_scorers(championship),
                assists=stats.top_assists(championship),
                discipline=stats.disciplinary_ranking(championship),
            )
        return context

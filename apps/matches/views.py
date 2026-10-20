"""Server-rendered views (Django templates) for the matches app."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from apps.championships.models import Championship

from . import services
from .forms import (
    CancelEventForm,
    EventTypeChoiceForm,
    LineupFormSet,
    MatchEventForm,
    MatchForm,
)
from .models import EventType, Match, MatchEvent, MatchEventParticipant
from .permissions import (
    AdminRequiredMixin,
    MatchOfficialRequiredMixin,
    can_manage_matches,
)

# ---------------------------------------------------------------------------
# Fixtures (calendar)
# ---------------------------------------------------------------------------


class MatchListView(LoginRequiredMixin, ListView):
    """
    Back-office fixture list, grouped by round. Administrators see every
    match; table officials only the matches assigned to them.
    """

    template_name = "matches/match_list.html"
    context_object_name = "matches"
    paginate_by = 20

    def get_queryset(self):
        queryset = Match.objects.select_related(
            "championship",
            "home_team__team",
            "away_team__team",
            "stadium__city",
        ).order_by("championship", "round_number", "scheduled_at")

        if not can_manage_matches(self.request.user):
            queryset = queryset.filter(table_officials=self.request.user)

        params = self.request.GET
        if championship := params.get("championship"):
            queryset = queryset.filter(championship_id=championship)
        if round_number := params.get("round"):
            if round_number.isdigit():
                queryset = queryset.filter(round_number=round_number)
        if status := params.get("status"):
            queryset = queryset.filter(status=status)
        if search := params.get("q", "").strip():
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
            statuses=Match.Status.choices,
            filters=self.request.GET,
            querystring=query.urlencode(),
            can_manage=can_manage_matches(self.request.user),
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


class MatchSheetView(MatchOfficialRequiredMixin, TemplateView):
    """
    Digital match sheet: timeline, lineups and the form to record a new
    event. The event form depends on the chosen type (``?event_type=``),
    so recording is a two-step flow that works without JavaScript.
    """

    template_name = "matches/match_sheet.html"

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
        events = match.events.select_related(
            "event_type", "team__team", "recorded_by"
        ).prefetch_related(
            Prefetch(
                "participants",
                queryset=MatchEventParticipant.objects.select_related(
                    "role", "player_registration__player"
                ),
            )
        )
        lineups = match.lineups.select_related(
            "player_registration__player"
        ).order_by("role", "shirt_number")
        context.update(
            match=match,
            events=events,
            home_lineup=[
                e for e in lineups if e.team_id == match.home_team_id
            ],
            away_lineup=[
                e for e in lineups if e.team_id == match.away_team_id
            ],
            locked=services.is_locked(match),
            can_manage=can_manage_matches(self.request.user),
            type_form=EventTypeChoiceForm(
                initial={"event_type": event_type.code if event_type else None}
            ),
            event_type=event_type,
            event_form=kwargs.get("event_form")
            or self.get_event_form(event_type),
            cancel_form=CancelEventForm(),
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

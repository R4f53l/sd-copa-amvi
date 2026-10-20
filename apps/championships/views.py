from functools import cached_property

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic import (
    CreateView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from apps.accounts.decorators import (
    AdminRequiredMixin,
    MesarioOuAdminRequiredMixin,
)

from .forms import (
    ChampionshipForm,
    ChampionshipTeamFormSet,
    PlayerRegistrationForm,
)
from .models import Championship, ChampionshipTeam, PlayerRegistration


def can_manage_championships(user):
    return user.is_authenticated and user.is_admin


# --- campeonatos ---


class ChampionshipListView(LoginRequiredMixin, ListView):
    model = Championship
    template_name = "championships/championship_list.html"
    context_object_name = "championships"
    paginate_by = 20

    def get_queryset(self):
        queryset = Championship.objects.annotate(
            team_count=Count("team_entries")
        ).order_by("-season", "name")

        params = self.request.GET
        if status := params.get("status"):
            queryset = queryset.filter(status=status)
        if search := params.get("q", "").strip():
            conditions = Q(name__icontains=search)
            if search.isdigit():
                conditions |= Q(season=int(search))
            queryset = queryset.filter(conditions)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.copy()
        query.pop("page", None)
        context.update(
            statuses=Championship.Status.choices,
            filters=self.request.GET,
            search_query=self.request.GET.get("q", "").strip(),
            querystring=query.urlencode(),
            can_manage=can_manage_championships(self.request.user),
        )
        return context


class ChampionshipDetailView(LoginRequiredMixin, DetailView):
    model = Championship
    template_name = "championships/championship_detail.html"
    context_object_name = "championship"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        team_entries = (
            self.object.team_entries.select_related("team__city")
            .annotate(
                active_players=Count(
                    "player_registrations",
                    filter=~Q(player_registrations__status="RELEASED"),
                )
            )
            .order_by("group", "rank", "-points", "-wins", "team__name")
        )
        context.update(
            team_entries=team_entries,
            can_manage=can_manage_championships(self.request.user),
        )
        return context


class ChampionshipFormMixin(AdminRequiredMixin):
    model = Championship
    form_class = ChampionshipForm
    template_name = "championships/championship_form.html"

    def form_invalid(self, form):
        messages.error(
            self.request, _("Please correct the highlighted errors below.")
        )
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse("championships:detail", args=[self.object.pk])


class ChampionshipCreateView(ChampionshipFormMixin, CreateView):
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            _("Championship %(championship)s created.")
            % {"championship": self.object},
        )
        return response


class ChampionshipUpdateView(ChampionshipFormMixin, UpdateView):
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            _("Championship %(championship)s updated.")
            % {"championship": self.object},
        )
        return response


# --- inscricao de times via formset ---


class ChampionshipTeamsView(AdminRequiredMixin, TemplateView):
    template_name = "championships/championship_teams_form.html"

    @cached_property
    def championship(self):
        return get_object_or_404(Championship, pk=self.kwargs["pk"])

    def get_formset(self):
        data = self.request.POST if self.request.method == "POST" else None
        return ChampionshipTeamFormSet(data, championship=self.championship)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            championship=self.championship,
            formset=kwargs.get("formset") or self.get_formset(),
        )
        return context

    def post(self, request, *args, **kwargs):
        formset = self.get_formset()
        if not formset.is_valid():
            messages.error(
                request, _("Please correct the highlighted errors below.")
            )
            return self.render_to_response(
                self.get_context_data(formset=formset)
            )

        with transaction.atomic():
            kept_team_ids = set()
            to_create = []
            to_update = []

            for team, existing, data in formset.entries:
                kept_team_ids.add(team.pk)
                group = data["group"]
                is_withdrawn = data["is_withdrawn"]
                points_deducted = data["points_deducted"]

                if existing is None:
                    to_create.append(
                        ChampionshipTeam(
                            championship=self.championship,
                            team=team,
                            group=group,
                            is_withdrawn=is_withdrawn,
                            points_deducted=points_deducted,
                        )
                    )
                elif (
                    existing.group != group
                    or existing.is_withdrawn != is_withdrawn
                    or existing.points_deducted != points_deducted
                ):
                    existing.group = group
                    existing.is_withdrawn = is_withdrawn
                    existing.points_deducted = points_deducted
                    to_update.append(existing)

            # remove inscricoes desmarcadas em lote
            self.championship.team_entries.exclude(
                team_id__in=kept_team_ids
            ).delete()
            if to_create:
                ChampionshipTeam.objects.bulk_create(to_create)
            if to_update:
                ChampionshipTeam.objects.bulk_update(
                    to_update,
                    ["group", "is_withdrawn", "points_deducted"],
                )

        messages.success(
            request,
            _("Enrolled teams for %(championship)s saved.")
            % {"championship": self.championship},
        )
        return redirect("championships:detail", pk=self.championship.pk)


# --- inscricao de jogadores por time no campeonato ---


class TeamRosterView(MesarioOuAdminRequiredMixin, TemplateView):
    template_name = "championships/team_roster.html"

    @cached_property
    def entry(self):
        return get_object_or_404(
            ChampionshipTeam.objects.select_related(
                "championship", "team__city"
            ),
            pk=self.kwargs["entry_pk"],
            championship_id=self.kwargs["pk"],
        )

    def get_form(self):
        if not can_manage_championships(self.request.user):
            return None
        data = self.request.POST if self.request.method == "POST" else None
        return PlayerRegistrationForm(data, championship_team=self.entry)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        registrations = self.entry.player_registrations.select_related(
            "player"
        ).order_by("status", "shirt_number", "player__full_name")
        active_count = sum(
            1
            for reg in registrations
            if reg.status != PlayerRegistration.Status.RELEASED
        )
        context.update(
            championship=self.entry.championship,
            entry=self.entry,
            registrations=registrations,
            active_count=active_count,
            max_players=self.entry.championship.max_players_per_team,
            form=kwargs.get("form") or self.get_form(),
            can_manage=can_manage_championships(self.request.user),
        )
        return context

    def post(self, request, *args, **kwargs):
        if not can_manage_championships(request.user):
            raise PermissionDenied
        form = self.get_form()
        if not form.is_valid():
            messages.error(
                request, _("Please correct the highlighted errors below.")
            )
            return self.render_to_response(self.get_context_data(form=form))

        registration = form.save()
        messages.success(
            request,
            _("Player %(player)s registered for %(team)s.")
            % {
                "player": registration.player.display_name,
                "team": self.entry.team.name,
            },
        )
        return redirect(
            "championships:roster",
            pk=self.entry.championship_id,
            entry_pk=self.entry.pk,
        )


class PlayerRegistrationUpdateView(AdminRequiredMixin, UpdateView):
    model = PlayerRegistration
    form_class = PlayerRegistrationForm
    template_name = "championships/player_registration_form.html"
    pk_url_kwarg = "reg_pk"

    @cached_property
    def entry(self):
        return get_object_or_404(
            ChampionshipTeam.objects.select_related(
                "championship", "team__city"
            ),
            pk=self.kwargs["entry_pk"],
            championship_id=self.kwargs["pk"],
        )

    def get_queryset(self):
        return PlayerRegistration.objects.filter(
            championship_team=self.entry
        ).select_related("player", "championship_team__championship")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["championship_team"] = self.entry
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            championship=self.entry.championship,
            entry=self.entry,
        )
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            _("Registration of %(player)s updated.")
            % {"player": self.object.player.display_name},
        )
        return response

    def form_invalid(self, form):
        messages.error(
            self.request, _("Please correct the highlighted errors below.")
        )
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse(
            "championships:roster",
            args=[self.entry.championship_id, self.entry.pk],
        )

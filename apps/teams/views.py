from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.views.generic import CreateView, ListView, UpdateView

from apps.accounts.decorators import AdminRequiredMixin

from .forms import CityForm, PlayerForm, StadiumForm, TeamForm
from .models import City, Player, Stadium, Team


# verifica permissao de administrador para escrita nos cadastros
def can_manage_registry(user):
    return user.is_authenticated and user.is_admin


# base paginada com filtro de busca e preservacao de querystring
class SearchableListView(ListView):
    paginate_by = 20
    search_param = "q"

    def get_search_query(self):
        return self.request.GET.get(self.search_param, "").strip()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.copy()
        query.pop("page", None)
        context.update(
            filters=self.request.GET,
            search_query=self.get_search_query(),
            querystring=query.urlencode(),
            can_manage=can_manage_registry(self.request.user),
        )
        return context


class FeedbackFormMixin(AdminRequiredMixin):
    success_message = ""
    error_message = _("Please correct the highlighted errors below.")

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.success_message:
            messages.success(
                self.request,
                self.success_message % {"object": self.object},
            )
        return response

    def form_invalid(self, form):
        messages.error(self.request, self.error_message)
        return super().form_invalid(form)


# --- times ---


class TeamListView(SearchableListView):
    model = Team
    template_name = "teams/team_list.html"
    context_object_name = "teams"

    def get_queryset(self):
        # evita consulta por linha para cidade e estadio
        queryset = Team.objects.select_related(
            "city", "home_stadium__city"
        ).order_by("name")
        if city_id := self.request.GET.get("city"):
            if city_id.isdigit():
                queryset = queryset.filter(city_id=city_id)
        if search := self.get_search_query():
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(short_name__icontains=search)
                | Q(city__name__icontains=search)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cities"] = City.objects.order_by("name")
        return context


class TeamCreateView(FeedbackFormMixin, CreateView):
    model = Team
    form_class = TeamForm
    template_name = "teams/team_form.html"
    success_url = reverse_lazy("teams:team_list")
    success_message = _("Team %(object)s saved.")


class TeamUpdateView(FeedbackFormMixin, UpdateView):
    model = Team
    form_class = TeamForm
    template_name = "teams/team_form.html"
    success_url = reverse_lazy("teams:team_list")
    success_message = _("Team %(object)s updated.")


# --- jogadores ---


class PlayerListView(SearchableListView):
    model = Player
    template_name = "teams/player_list.html"
    context_object_name = "players"

    def get_queryset(self):
        queryset = Player.objects.order_by("full_name")
        if position := self.request.GET.get("position"):
            queryset = queryset.filter(position=position)
        if search := self.get_search_query():
            queryset = queryset.filter(
                Q(full_name__icontains=search)
                | Q(nickname__icontains=search)
                | Q(document_number__icontains=search)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["positions"] = Player.Position.choices
        return context


class PlayerCreateView(FeedbackFormMixin, CreateView):
    model = Player
    form_class = PlayerForm
    template_name = "teams/player_form.html"
    success_url = reverse_lazy("teams:player_list")
    success_message = _("Player %(object)s saved.")


class PlayerUpdateView(FeedbackFormMixin, UpdateView):
    model = Player
    form_class = PlayerForm
    template_name = "teams/player_form.html"
    success_url = reverse_lazy("teams:player_list")
    success_message = _("Player %(object)s updated.")


# --- estadios ---


class StadiumListView(SearchableListView):
    model = Stadium
    template_name = "teams/stadium_list.html"
    context_object_name = "stadiums"

    def get_queryset(self):
        queryset = Stadium.objects.select_related("city").order_by("name")
        if city_id := self.request.GET.get("city"):
            if city_id.isdigit():
                queryset = queryset.filter(city_id=city_id)
        if search := self.get_search_query():
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(address__icontains=search)
                | Q(city__name__icontains=search)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cities"] = City.objects.order_by("name")
        return context


class StadiumCreateView(FeedbackFormMixin, CreateView):
    model = Stadium
    form_class = StadiumForm
    template_name = "teams/stadium_form.html"
    success_url = reverse_lazy("teams:stadium_list")
    success_message = _("Stadium %(object)s saved.")


class StadiumUpdateView(FeedbackFormMixin, UpdateView):
    model = Stadium
    form_class = StadiumForm
    template_name = "teams/stadium_form.html"
    success_url = reverse_lazy("teams:stadium_list")
    success_message = _("Stadium %(object)s updated.")


# --- cidades ---


class CityListView(SearchableListView):
    model = City
    template_name = "teams/city_list.html"
    context_object_name = "cities"

    def get_queryset(self):
        queryset = City.objects.order_by("name")
        if search := self.get_search_query():
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(state__icontains=search)
            )
        return queryset


class CityCreateView(FeedbackFormMixin, CreateView):
    model = City
    form_class = CityForm
    template_name = "teams/city_form.html"
    success_url = reverse_lazy("teams:city_list")
    success_message = _("City %(object)s saved.")


class CityUpdateView(FeedbackFormMixin, UpdateView):
    model = City
    form_class = CityForm
    template_name = "teams/city_form.html"
    success_url = reverse_lazy("teams:city_list")
    success_message = _("City %(object)s updated.")

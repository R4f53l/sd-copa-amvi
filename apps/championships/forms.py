from datetime import date

from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.shared.forms import BootstrapFormMixin
from apps.teams.models import Player, Team

from .models import Championship, PlayerRegistration

DATE_FORMAT = "%Y-%m-%d"


class ChampionshipForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Championship
        fields = (
            "name",
            "season",
            "slug",
            "status",
            "start_date",
            "end_date",
            "description",
            "regulation",
            "regulation_file",
            "points_per_win",
            "points_per_draw",
            "points_per_loss",
            "yellow_cards_for_suspension",
            "max_players_per_team",
        )
        widgets = {
            "start_date": forms.DateInput(
                attrs={"type": "date"}, format=DATE_FORMAT
            ),
            "end_date": forms.DateInput(
                attrs={"type": "date"}, format=DATE_FORMAT
            ),
            "description": forms.Textarea(attrs={"rows": 3}),
            "regulation": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        for name in ("start_date", "end_date"):
            self.fields[name].input_formats = [DATE_FORMAT]

    def clean_slug(self):
        slug = self.cleaned_data.get("slug")
        if not slug:
            name = self.cleaned_data.get("name", "")
            season = self.cleaned_data.get("season", "")
            slug = slugify(f"{name}-{season}" if season else name)
        return slug

    def clean(self):
        data = super().clean()
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        # garante que a data final nao seja anterior a data inicial
        if start_date and end_date and end_date < start_date:
            self.add_error(
                "end_date",
                _("The end date must be on or after the start date."),
            )
        return data


# --- inscricao de times com formset ---


class ChampionshipTeamEntryForm(BootstrapFormMixin, forms.Form):
    team_id = forms.UUIDField(widget=forms.HiddenInput)
    enrolled = forms.BooleanField(label=_("enrolled"), required=False)
    group = forms.CharField(
        label=_("group"),
        max_length=10,
        required=False,
    )
    is_withdrawn = forms.BooleanField(label=_("withdrawn"), required=False)
    points_deducted = forms.IntegerField(
        label=_("points deducted"),
        min_value=0,
        required=False,
        initial=0,
    )

    def __init__(self, *args, team=None, existing_entry=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.team = team
        self.existing_entry = existing_entry

    def clean_group(self):
        return (self.cleaned_data.get("group") or "").strip().upper()

    def clean_points_deducted(self):
        return self.cleaned_data.get("points_deducted") or 0


class BaseChampionshipTeamFormSet(forms.BaseFormSet):
    def __init__(self, *args, championship, **kwargs):
        self.championship = championship
        # busca times ativos ou ja inscritos em consulta unica
        existing_qs = championship.team_entries.select_related(
            "team__city"
        ).order_by("team__name")
        self.existing_by_team = {entry.team_id: entry for entry in existing_qs}

        teams_qs = (
            Team.objects.filter(is_active=True)
            .select_related("city")
            .order_by("name")
        )
        teams_map = {t.pk: t for t in teams_qs}
        for entry in existing_qs:
            teams_map.setdefault(entry.team_id, entry.team)

        self.teams = sorted(teams_map.values(), key=lambda t: t.name)

        initial = []
        for team in self.teams:
            entry = self.existing_by_team.get(team.pk)
            initial.append(
                {
                    "team_id": team.pk,
                    "enrolled": entry is not None,
                    "group": entry.group if entry else "",
                    "is_withdrawn": entry.is_withdrawn if entry else False,
                    "points_deducted": entry.points_deducted if entry else 0,
                }
            )
        kwargs.setdefault("initial", initial)
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        if index is not None and index < len(self.teams):
            team = self.teams[index]
            kwargs["team"] = team
            kwargs["existing_entry"] = self.existing_by_team.get(team.pk)
        return kwargs

    def clean(self):
        if any(self.errors):
            return
        teams_by_id = {t.pk: t for t in self.teams}
        seen_teams = set()
        selected = []

        # bloqueia remocao de times que ja possuem partidas agendadas
        locked_entry_ids = set(
            self.championship.matches.values_list("home_team_id", flat=True)
        ) | set(
            self.championship.matches.values_list("away_team_id", flat=True)
        )

        for form in self.forms:
            data = form.cleaned_data
            team_id = data.get("team_id")
            team = teams_by_id.get(team_id)
            if team is None or team_id in seen_teams:
                raise ValidationError(
                    _("Invalid team selection. Reload the page and try again.")
                )
            seen_teams.add(team_id)
            existing = self.existing_by_team.get(team_id)

            if data.get("enrolled"):
                selected.append((team, existing, data))
            elif existing and existing.pk in locked_entry_ids:
                raise ValidationError(
                    _(
                        "Team %(team)s already has scheduled matches and "
                        "cannot be removed."
                    ),
                    params={"team": team.name},
                )

        self.entries = selected

    def rows(self):
        return zip(self.forms, self.teams, strict=True)


ChampionshipTeamFormSet = forms.formset_factory(
    ChampionshipTeamEntryForm,
    formset=BaseChampionshipTeamFormSet,
    extra=0,
)


# --- inscricao de jogadores no time do campeonato ---


class PlayerRegistrationForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PlayerRegistration
        fields = (
            "player",
            "shirt_number",
            "status",
            "registered_on",
            "released_on",
        )
        widgets = {
            "registered_on": forms.DateInput(
                attrs={"type": "date"}, format=DATE_FORMAT
            ),
            "released_on": forms.DateInput(
                attrs={"type": "date"}, format=DATE_FORMAT
            ),
        }

    def __init__(self, *args, championship_team, **kwargs):
        super().__init__(*args, **kwargs)
        self.championship_team = championship_team
        self.instance.championship_team = championship_team

        for name in ("registered_on", "released_on"):
            self.fields[name].input_formats = [DATE_FORMAT]

        if self.instance._state.adding:
            self.fields["registered_on"].initial = date.today()
            self.fields["player"].queryset = Player.objects.filter(
                is_active=True
            ).order_by("full_name")
        else:
            # na edicao mantem o jogador fixo para preservar historico
            self.fields["player"].disabled = True
            self.fields["player"].queryset = Player.objects.filter(
                pk=self.instance.player_id
            )

    def clean_shirt_number(self):
        number = self.cleaned_data.get("shirt_number")
        if number is not None and not 1 <= number <= 99:
            raise ValidationError(_("Shirt number must be between 1 and 99."))
        return number

    def clean(self):
        data = super().clean()
        player = data.get("player") or getattr(self.instance, "player", None)
        status = data.get("status")
        shirt_number = data.get("shirt_number")
        registered_on = data.get("registered_on")
        released_on = data.get("released_on")

        if registered_on and released_on and released_on < registered_on:
            self.add_error(
                "released_on",
                _(
                    "The release date must be on or after the "
                    "registration date."
                ),
            )

        if not player or not self.championship_team:
            return data

        # evita duplicidade do mesmo jogador no mesmo time do campeonato
        same_team_clash = (
            PlayerRegistration.objects.filter(
                championship_team=self.championship_team,
                player=player,
            )
            .exclude(pk=self.instance.pk)
            .exists()
        )
        if same_team_clash:
            self.add_error(
                "player",
                _("This player is already registered in this team."),
            )

        if status != PlayerRegistration.Status.RELEASED:
            # valida que o jogador so atue por um time no campeonato
            other_team_clash = (
                PlayerRegistration.objects.filter(
                    player=player,
                    championship_team__championship_id=(
                        self.championship_team.championship_id
                    ),
                )
                .exclude(status=PlayerRegistration.Status.RELEASED)
                .exclude(pk=self.instance.pk)
                .exists()
            )
            if other_team_clash:
                self.add_error(
                    "player",
                    _(
                        "This player is already registered for another team "
                        "in this championship."
                    ),
                )

            # valida unicidade do numero da camisa entre atletas nao desligados
            if shirt_number is not None:
                shirt_clash = (
                    PlayerRegistration.objects.filter(
                        championship_team=self.championship_team,
                        shirt_number=shirt_number,
                    )
                    .exclude(status=PlayerRegistration.Status.RELEASED)
                    .exclude(pk=self.instance.pk)
                    .exists()
                )
                if shirt_clash:
                    self.add_error(
                        "shirt_number",
                        _(
                            "This shirt number is already in use by another "
                            "active player on this team."
                        ),
                    )

            # respeita limite maximo de jogadores ativos do regulamento
            max_players = (
                self.championship_team.championship.max_players_per_team
            )
            active_count = (
                PlayerRegistration.objects.filter(
                    championship_team=self.championship_team
                )
                .exclude(status=PlayerRegistration.Status.RELEASED)
                .exclude(pk=self.instance.pk)
                .count()
            )
            if active_count >= max_players:
                raise ValidationError(
                    _(
                        "This team has reached the limit of %(max)d active "
                        "players in the championship."
                    ),
                    params={"max": max_players},
                )

        return data

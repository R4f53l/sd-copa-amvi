from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.shared.forms import BootstrapFormMixin
from apps.teams.models import City, Player

from . import services
from .models import EventType, Lineup, Match, MatchEvent


class PublicMatchFilterForm(forms.Form):
    round_number = forms.TypedChoiceField(
        label=_("Round"),
        choices=(),
        coerce=int,
        empty_value=None,
        required=False,
    )
    city = forms.ModelChoiceField(
        label=_("City"),
        queryset=City.objects.none(),
        required=False,
        empty_label=_("All cities"),
    )

    def __init__(self, *args, round_numbers=(), cities=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["round_number"].choices = [
            ("", _("All rounds")),
            *((number, number) for number in round_numbers),
        ]
        if cities is not None:
            self.fields["city"].queryset = cities

DATETIME_LOCAL_FORMAT = "%Y-%m-%dT%H:%M"


def team_label(championship_team):
    return championship_team.team.name


def lineup_label(lineup):
    number = f"#{lineup.shirt_number} " if lineup.shirt_number else ""
    player = lineup.player_registration.player.display_name
    return f"{number}{player} ({lineup.team.team.short_name})"


class LineupSelect(forms.Select):
    """Select whose options carry the player's team, so the page can
    narrow the list to the chosen team (progressive enhancement)."""

    def create_option(self, name, value, *args, **kwargs):
        option = super().create_option(name, value, *args, **kwargs)
        instance = getattr(value, "instance", None)
        if instance is not None:
            option["attrs"]["data-team"] = str(instance.team_id)
        return option


# Period suggested for a new event, based on the match status.
PERIOD_BY_STATUS = {
    Match.Status.SECOND_HALF: MatchEvent.Period.SECOND_HALF,
    Match.Status.EXTRA_TIME: MatchEvent.Period.EXTRA_TIME_FIRST,
    Match.Status.PENALTIES: MatchEvent.Period.PENALTIES,
}


def suggested_period(match, event_type):
    if event_type.category == EventType.Category.SHOOTOUT:
        return MatchEvent.Period.PENALTIES
    return PERIOD_BY_STATUS.get(match.status, MatchEvent.Period.FIRST_HALF)


# ---------------------------------------------------------------------------
# Match scheduling
# ---------------------------------------------------------------------------


class MatchForm(BootstrapFormMixin, forms.ModelForm):
    """Create or edit a fixture within a single championship."""

    class Meta:
        model = Match
        fields = (
            "home_team",
            "away_team",
            "stadium",
            "stage",
            "round_number",
            "scheduled_at",
            "status",
            "referee_name",
            "streaming_url",
            "table_officials",
        )
        widgets = {
            "scheduled_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format=DATETIME_LOCAL_FORMAT,
            ),
            "table_officials": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, championship, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.championship = championship

        teams = championship.team_entries.filter(
            is_withdrawn=False
        ).select_related("team")
        for name in ("home_team", "away_team"):
            self.fields[name].queryset = teams
            self.fields[name].label_from_instance = team_label

        self.fields["stadium"].queryset = (
            self.fields["stadium"]
            .queryset.filter(is_active=True)
            .select_related("city")
        )
        self.fields["table_officials"].queryset = (
            get_user_model()
            .objects.filter(
                role=get_user_model().Role.TABLE_OFFICIAL,
                # Superusers already run every match.
                is_superuser=False,
                is_active=True,
            )
            .order_by("first_name", "username")
        )
        self.fields["scheduled_at"].input_formats = [DATETIME_LOCAL_FORMAT]

        # New fixtures always start as scheduled. (UUID primary keys are
        # set on instantiation, so ``pk`` cannot tell new objects apart.)
        if self.instance._state.adding:
            del self.fields["status"]


# ---------------------------------------------------------------------------
# Lineup (one form per eligible player)
# ---------------------------------------------------------------------------


class LineupEntryForm(BootstrapFormMixin, forms.Form):
    registration_id = forms.UUIDField(widget=forms.HiddenInput)
    role = forms.ChoiceField(
        label=_("role"),
        required=False,
        choices=[*Lineup.Role.choices, ("", _("Not listed"))],
        widget=forms.RadioSelect,
    )
    shirt_number = forms.IntegerField(
        label=_("shirt number"), required=False, min_value=1, max_value=99
    )
    position = forms.ChoiceField(
        label=_("position"),
        required=False,
        choices=[("", "—"), *Player.Position.choices],
    )
    is_captain = forms.BooleanField(label=_("captain"), required=False)

    def __init__(self, *args, registration=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.registration = registration

    def clean(self):
        data = super().clean()
        if data.get("is_captain") and not data.get("role"):
            self.add_error(
                "is_captain", _("The captain must be on the match sheet.")
            )
        if (
            data.get("role")
            and self.registration
            and (self.registration.status != self.registration.Status.ACTIVE)
        ):
            self.add_error(
                "role",
                _("Only players with an active registration can be listed."),
            )
        return data


class BaseLineupFormSet(forms.BaseFormSet):
    """Validates the match sheet of one team as a whole."""

    def __init__(self, *args, match, team, **kwargs):
        self.match = match
        self.team = team
        self.registrations = list(services.lineup_candidates(match, team))
        existing = {
            entry.player_registration_id: entry
            for entry in match.lineups.filter(team=team)
        }
        initial = []
        for registration in self.registrations:
            entry = existing.get(registration.pk)
            initial.append(
                {
                    "registration_id": registration.pk,
                    "role": entry.role if entry else "",
                    "shirt_number": (
                        entry.shirt_number
                        if entry
                        else registration.shirt_number
                    ),
                    "position": (
                        entry.position
                        if entry
                        else registration.player.position
                    ),
                    "is_captain": entry.is_captain if entry else False,
                }
            )
        kwargs.setdefault("initial", initial)
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        if index is not None and index < len(self.registrations):
            kwargs["registration"] = self.registrations[index]
        return kwargs

    def clean(self):
        if any(self.errors):
            return
        by_id = {r.pk: r for r in self.registrations}
        listed = []
        for form in self.forms:
            data = form.cleaned_data
            registration = by_id.get(data.get("registration_id"))
            if registration is None:
                raise ValidationError(
                    _(
                        "The match sheet was changed by someone else. "
                        "Reload the page and try again."
                    )
                )
            if data.get("role"):
                listed.append((registration, data))

        starters = sum(
            1 for _reg, data in listed if data["role"] == Lineup.Role.STARTER
        )
        if not services.MIN_STARTERS <= starters <= services.MAX_STARTERS:
            raise ValidationError(
                _(
                    "Choose between %(min)d and %(max)d starters "
                    "(currently %(count)d)."
                ),
                params={
                    "min": services.MIN_STARTERS,
                    "max": services.MAX_STARTERS,
                    "count": starters,
                },
            )

        if sum(1 for _reg, data in listed if data["is_captain"]) > 1:
            raise ValidationError(_("Choose only one captain."))

        numbers = [
            data["shirt_number"]
            for _reg, data in listed
            if data["shirt_number"]
        ]
        if len(numbers) != len(set(numbers)):
            raise ValidationError(
                _("Two listed players have the same shirt number.")
            )

        listed_ids = {reg.pk for reg, _data in listed}
        removed = (
            services.registrations_with_events(self.match, self.team)
            - listed_ids
        )
        if removed:
            names = ", ".join(
                sorted(by_id[pk].player.display_name for pk in removed)
            )
            raise ValidationError(
                _(
                    "These players took part in events of this match and "
                    "cannot be removed: %(names)s."
                ),
                params={"names": names},
            )

        self.entries = [
            {
                "registration": registration,
                "role": data["role"],
                "shirt_number": data["shirt_number"],
                "position": data["position"],
                "is_captain": data["is_captain"],
            }
            for registration, data in listed
        ]

    def rows(self):
        """Pairs each form with its registration, for the template."""
        return zip(self.forms, self.registrations, strict=True)


LineupFormSet = forms.formset_factory(
    LineupEntryForm, formset=BaseLineupFormSet, extra=0
)


# ---------------------------------------------------------------------------
# Match sheet: events
# ---------------------------------------------------------------------------


class MatchEventForm(BootstrapFormMixin, forms.Form):
    """
    Details of an event whose type was picked beforehand. One player
    field is added for each role allowed for that event type.
    """

    ROLE_PREFIX = "role_"

    team = forms.ChoiceField(label=_("team"), widget=forms.RadioSelect)
    period = forms.TypedChoiceField(
        label=_("period"), choices=MatchEvent.Period.choices, coerce=int
    )
    minute = forms.IntegerField(label=_("minute"), min_value=0, max_value=130)
    stoppage_minute = forms.IntegerField(
        label=_("stoppage time"), min_value=0, max_value=30, initial=0
    )
    description = forms.CharField(
        label=_("description"), max_length=255, required=False
    )

    def __init__(self, *args, match, event_type, **kwargs):
        super().__init__(*args, **kwargs)
        self.match = match
        self.event_type = event_type
        self.teams = {
            str(match.home_team_id): match.home_team,
            str(match.away_team_id): match.away_team,
        }

        self.fields["period"].initial = suggested_period(match, event_type)
        if event_type.requires_team:
            self.fields["team"].choices = [
                (pk, team_label(t)) for pk, t in self.teams.items()
            ]
        else:
            del self.fields["team"]

        lineups = match.lineups.select_related(
            "player_registration__player", "team__team"
        ).order_by("team", "role", "shirt_number")
        # Required roles first (e.g. scorer before assist).
        self.roles = sorted(
            event_type.allowed_roles.all(),
            key=lambda r: (r.code in services.OPTIONAL_ROLES, r.name),
        )
        for role in self.roles:
            field = forms.ModelChoiceField(
                label=role.name,
                queryset=lineups,
                required=role.code not in services.OPTIONAL_ROLES,
                widget=LineupSelect(
                    attrs={
                        "data-opponent": (
                            "1" if role.code in services.OPPONENT_ROLES else ""
                        )
                    }
                ),
            )
            field.label_from_instance = lineup_label
            field.empty_label = "—"
            self.fields[self.ROLE_PREFIX + role.code] = field
        self.order_fields(
            ["team", *(self.ROLE_PREFIX + r.code for r in self.roles)]
        )
        # The player fields were added after the mixin ran.
        self.apply_bootstrap_classes()

    @property
    def role_fields(self):
        return [self[self.ROLE_PREFIX + role.code] for role in self.roles]

    @property
    def team_options(self):
        """(value, ChampionshipTeam, checked) for the team buttons."""
        if "team" not in self.fields:
            return []
        selected = str(self["team"].value() or "")
        return [(pk, team, pk == selected) for pk, team in self.teams.items()]

    def clean(self):
        data = super().clean()
        team = (
            self.teams.get(data.get("team")) if "team" in self.fields else None
        )
        participants = {
            role: data.get(self.ROLE_PREFIX + role.code) for role in self.roles
        }
        try:
            services.validate_participants(
                self.match, self.event_type, team, participants
            )
        except ValidationError as exc:
            for code, messages in exc.message_dict.items():
                field = self.ROLE_PREFIX + code
                if field in self.fields and field not in self.errors:
                    self.add_error(field, messages)
        data["team_obj"] = team
        data["participants"] = participants
        return data


class CancelEventForm(BootstrapFormMixin, forms.Form):
    reason = forms.CharField(label=_("cancellation reason"), max_length=255)

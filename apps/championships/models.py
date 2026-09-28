from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils.translation import gettext_lazy as _

from apps.shared.models import TimeStampedModel


class Championship(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", _("Draft")
        REGISTRATION = "REGISTRATION", _("Registration open")
        ONGOING = "ONGOING", _("Ongoing")
        FINISHED = "FINISHED", _("Finished")
        CANCELED = "CANCELED", _("Canceled")

    name = models.CharField(_("name"), max_length=150)
    season = models.PositiveSmallIntegerField(
        _("season"), help_text=_("e.g. 2026")
    )
    slug = models.SlugField(_("slug"), max_length=170, unique=True)
    description = models.TextField(_("description"), blank=True)
    regulation = models.TextField(
        _("regulation"),
        blank=True,
        help_text=_("Full text of the competition rules."),
    )
    regulation_file = models.FileField(
        _("regulation file"),
        upload_to="championships/regulations/",
        blank=True,
        help_text=_("Official rules document (PDF)."),
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    start_date = models.DateField(_("start date"), null=True, blank=True)
    end_date = models.DateField(_("end date"), null=True, blank=True)

    # Scoring rules, configurable per edition.
    points_per_win = models.PositiveSmallIntegerField(
        _("points per win"), default=3
    )
    points_per_draw = models.PositiveSmallIntegerField(
        _("points per draw"), default=1
    )
    points_per_loss = models.PositiveSmallIntegerField(
        _("points per loss"), default=0
    )

    # Disciplinary rules used to compute suspensions.
    yellow_cards_for_suspension = models.PositiveSmallIntegerField(
        _("yellow cards for suspension"), default=3
    )
    max_players_per_team = models.PositiveSmallIntegerField(
        _("max players per team"), default=25
    )

    teams = models.ManyToManyField(
        "teams.Team",
        through="ChampionshipTeam",
        related_name="championships",
        verbose_name=_("teams"),
    )

    class Meta:
        verbose_name = _("championship")
        verbose_name_plural = _("championships")
        ordering = ("-season", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("name", "season"),
                name="unique_championship_per_season",
            ),
            models.CheckConstraint(
                condition=Q(end_date__isnull=True)
                | Q(start_date__isnull=True)
                | Q(end_date__gte=F("start_date")),
                name="championship_end_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.name} {self.season}"


class ChampionshipTeam(TimeStampedModel):
    """
    A team's participation in a championship (TimeCampeonato).

    The standings columns are a denormalised read model: they are
    recomputed by the matches service layer whenever a match result
    changes, so the public standings endpoint is a single cheap query.

    ``rank`` is also written by that service. Tie-break rules such as
    head-to-head results cannot be expressed as a SQL ORDER BY, so the
    service applies the full regulation and stores the final position.
    """

    championship = models.ForeignKey(
        Championship,
        on_delete=models.CASCADE,
        related_name="team_entries",
        verbose_name=_("championship"),
    )
    team = models.ForeignKey(
        "teams.Team",
        on_delete=models.PROTECT,
        related_name="championship_entries",
        verbose_name=_("team"),
    )
    group = models.CharField(
        _("group"),
        max_length=10,
        blank=True,
        help_text=_("Group label, e.g. 'A'."),
    )
    is_withdrawn = models.BooleanField(_("withdrawn"), default=False)

    # Consolidated standings (read model).
    played = models.PositiveSmallIntegerField(_("played"), default=0)
    wins = models.PositiveSmallIntegerField(_("wins"), default=0)
    draws = models.PositiveSmallIntegerField(_("draws"), default=0)
    losses = models.PositiveSmallIntegerField(_("losses"), default=0)
    goals_for = models.PositiveSmallIntegerField(_("goals for"), default=0)
    goals_against = models.PositiveSmallIntegerField(
        _("goals against"), default=0
    )
    points = models.SmallIntegerField(
        _("points"),
        default=0,
        help_text=_("May go negative after point deductions."),
    )
    points_deducted = models.PositiveSmallIntegerField(
        _("points deducted"), default=0
    )
    # Fair-play tie-breakers.
    yellow_cards = models.PositiveSmallIntegerField(
        _("yellow cards"), default=0
    )
    red_cards = models.PositiveSmallIntegerField(_("red cards"), default=0)
    rank = models.PositiveSmallIntegerField(
        _("rank"),
        null=True,
        blank=True,
        help_text=_("Final position within the group after tie-breakers."),
    )

    class Meta:
        verbose_name = _("championship team")
        verbose_name_plural = _("championship teams")
        ordering = ("championship", "group", "rank", "team__name")
        constraints = [
            models.UniqueConstraint(
                fields=("championship", "team"),
                name="unique_team_per_championship",
            ),
        ]

    def __str__(self):
        return f"{self.team} @ {self.championship}"

    @property
    def goal_difference(self):
        return self.goals_for - self.goals_against


class PlayerRegistration(TimeStampedModel):
    """
    Links a player to a team within a championship (JogadorTime).

    Rows are never deleted when a player leaves: ``released_on`` is set
    instead, which preserves the historical record of every event the
    player took part in.
    """

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", _("Active")
        SUSPENDED = "SUSPENDED", _("Suspended")
        RELEASED = "RELEASED", _("Released")

    championship_team = models.ForeignKey(
        ChampionshipTeam,
        on_delete=models.CASCADE,
        related_name="player_registrations",
        verbose_name=_("championship team"),
    )
    player = models.ForeignKey(
        "teams.Player",
        on_delete=models.PROTECT,
        related_name="registrations",
        verbose_name=_("player"),
    )
    shirt_number = models.PositiveSmallIntegerField(
        _("shirt number"), null=True, blank=True
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    registered_on = models.DateField(_("registered on"))
    released_on = models.DateField(_("released on"), null=True, blank=True)

    class Meta:
        verbose_name = _("player registration")
        verbose_name_plural = _("player registrations")
        ordering = ("championship_team", "shirt_number")
        constraints = [
            models.UniqueConstraint(
                fields=("championship_team", "player"),
                name="unique_player_per_championship_team",
            ),
            models.UniqueConstraint(
                fields=("championship_team", "shirt_number"),
                condition=~Q(status="RELEASED"),
                name="unique_active_shirt_number_per_team",
            ),
            models.CheckConstraint(
                condition=Q(released_on__isnull=True)
                | Q(released_on__gte=F("registered_on")),
                name="registration_release_after_start",
            ),
        ]

    def __str__(self):
        number = f"#{self.shirt_number} " if self.shirt_number else ""
        return f"{number}{self.player} ({self.championship_team.team})"

    def clean(self):
        # A player may only be active for one team per championship.
        # This spans a join, so it cannot be a database constraint.
        if (
            self.status == self.Status.RELEASED
            or not self.championship_team_id
        ):
            return
        clash = (
            PlayerRegistration.objects.filter(
                player_id=self.player_id,
                championship_team__championship_id=(
                    self.championship_team.championship_id
                ),
            )
            .exclude(status=self.Status.RELEASED)
            .exclude(pk=self.pk)
        )
        if clash.exists():
            raise ValidationError(
                _(
                    "This player is already registered for another team "
                    "in this championship."
                )
            )

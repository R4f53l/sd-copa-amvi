from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils.translation import gettext_lazy as _

from apps.shared.models import TimeStampedModel
from apps.teams.models import Player


class Match(TimeStampedModel):
    class Stage(models.TextChoices):
        GROUP = "GROUP", _("Group stage")
        ROUND_OF_16 = "ROUND_OF_16", _("Round of 16")
        QUARTER_FINAL = "QUARTER_FINAL", _("Quarter-final")
        SEMI_FINAL = "SEMI_FINAL", _("Semi-final")
        THIRD_PLACE = "THIRD_PLACE", _("Third-place play-off")
        FINAL = "FINAL", _("Final")

    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", _("Scheduled")
        FIRST_HALF = "FIRST_HALF", _("First half")
        HALF_TIME = "HALF_TIME", _("Half-time")
        SECOND_HALF = "SECOND_HALF", _("Second half")
        EXTRA_TIME = "EXTRA_TIME", _("Extra time")
        PENALTIES = "PENALTIES", _("Penalty shoot-out")
        FINISHED = "FINISHED", _("Finished")
        POSTPONED = "POSTPONED", _("Postponed")
        CANCELED = "CANCELED", _("Canceled")

    LIVE_STATUSES = (
        Status.FIRST_HALF,
        Status.HALF_TIME,
        Status.SECOND_HALF,
        Status.EXTRA_TIME,
        Status.PENALTIES,
    )

    championship = models.ForeignKey(
        "championships.Championship",
        on_delete=models.CASCADE,
        related_name="matches",
        verbose_name=_("championship"),
    )
    # Pointing at ChampionshipTeam (not teams.Team) guarantees both sides
    # are enrolled in the same championship as the match.
    home_team = models.ForeignKey(
        "championships.ChampionshipTeam",
        on_delete=models.PROTECT,
        related_name="home_matches",
        verbose_name=_("home team"),
    )
    away_team = models.ForeignKey(
        "championships.ChampionshipTeam",
        on_delete=models.PROTECT,
        related_name="away_matches",
        verbose_name=_("away team"),
    )
    stadium = models.ForeignKey(
        "teams.Stadium",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matches",
        verbose_name=_("stadium"),
    )
    table_officials = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="officiated_matches",
        verbose_name=_("table officials"),
        help_text=_("Users allowed to record events for this match."),
    )

    stage = models.CharField(
        _("stage"), max_length=20, choices=Stage.choices, default=Stage.GROUP
    )
    round_number = models.PositiveSmallIntegerField(
        _("round"), null=True, blank=True
    )
    scheduled_at = models.DateTimeField(_("scheduled at"), db_index=True)
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
        db_index=True,
    )
    referee_name = models.CharField(_("referee"), max_length=150, blank=True)
    streaming_url = models.URLField(
        _("streaming link"),
        blank=True,
        help_text=_("Live broadcast link (e.g. YouTube), when available."),
    )

    # Consolidated score, kept in sync with scoring events by the service
    # layer so scoreboards never need to aggregate events.
    home_score = models.PositiveSmallIntegerField(_("home score"), default=0)
    away_score = models.PositiveSmallIntegerField(_("away score"), default=0)
    home_penalty_score = models.PositiveSmallIntegerField(
        _("home penalty score"), null=True, blank=True
    )
    away_penalty_score = models.PositiveSmallIntegerField(
        _("away penalty score"), null=True, blank=True
    )
    is_walkover = models.BooleanField(_("walkover"), default=False)

    started_at = models.DateTimeField(_("started at"), null=True, blank=True)
    finished_at = models.DateTimeField(_("finished at"), null=True, blank=True)
    notes = models.TextField(_("notes"), blank=True)

    class Meta:
        verbose_name = _("match")
        verbose_name_plural = _("matches")
        ordering = ("scheduled_at",)
        indexes = [
            models.Index(fields=("championship", "status")),
            models.Index(fields=("championship", "round_number")),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~Q(home_team=F("away_team")),
                name="match_teams_must_differ",
            ),
        ]

    def __str__(self):
        return f"{self.home_team.team} x {self.away_team.team}"

    @property
    def is_live(self):
        return self.status in self.LIVE_STATUSES

    @property
    def winner(self):
        """Winning ChampionshipTeam, ``None`` for draws or unfinished."""
        if self.status != self.Status.FINISHED:
            return None
        if self.home_score != self.away_score:
            return (
                self.home_team
                if self.home_score > self.away_score
                else self.away_team
            )
        if self.home_penalty_score is not None and (
            self.away_penalty_score is not None
        ):
            if self.home_penalty_score > self.away_penalty_score:
                return self.home_team
            if self.away_penalty_score > self.home_penalty_score:
                return self.away_team
        return None

    def clean(self):
        for side in (self.home_team, self.away_team):
            if side and side.championship_id != self.championship_id:
                raise ValidationError(
                    _(
                        "Both teams must be enrolled in the match's "
                        "championship."
                    )
                )

    def involves(self, championship_team_id):
        return championship_team_id in (self.home_team_id, self.away_team_id)


class Lineup(TimeStampedModel):
    """One row per player listed on the match sheet (Escalacao)."""

    class Role(models.TextChoices):
        STARTER = "STARTER", _("Starter")
        SUBSTITUTE = "SUBSTITUTE", _("Substitute")

    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name="lineups",
        verbose_name=_("match"),
    )
    team = models.ForeignKey(
        "championships.ChampionshipTeam",
        on_delete=models.PROTECT,
        related_name="lineups",
        verbose_name=_("team"),
    )
    player_registration = models.ForeignKey(
        "championships.PlayerRegistration",
        on_delete=models.PROTECT,
        related_name="lineups",
        verbose_name=_("player"),
    )
    role = models.CharField(
        _("role"), max_length=20, choices=Role.choices, default=Role.STARTER
    )
    # Snapshot: the registration number may change later in the season.
    shirt_number = models.PositiveSmallIntegerField(
        _("shirt number"), null=True, blank=True
    )
    position = models.CharField(
        _("position"),
        max_length=2,
        choices=Player.Position.choices,
        blank=True,
    )
    is_captain = models.BooleanField(_("captain"), default=False)

    class Meta:
        verbose_name = _("lineup entry")
        verbose_name_plural = _("lineup entries")
        ordering = ("match", "team", "role", "shirt_number")
        constraints = [
            models.UniqueConstraint(
                fields=("match", "player_registration"),
                name="unique_player_per_match_lineup",
            ),
            models.UniqueConstraint(
                fields=("match", "team"),
                condition=Q(is_captain=True),
                name="one_captain_per_team_per_match",
            ),
        ]

    def __str__(self):
        return f"{self.player_registration.player} - {self.match}"

    def clean(self):
        if (
            self.match_id
            and self.team_id
            and not self.match.involves(self.team_id)
        ):
            raise ValidationError(_("Team is not playing this match."))
        if (
            self.player_registration_id
            and self.player_registration.championship_team_id != self.team_id
        ):
            raise ValidationError(_("Player is not registered for this team."))


class EventType(models.Model):
    """
    Catalogue of match events (TipoEvento), e.g. goal, own goal, yellow
    card, substitution. Stored as data rather than choices so the
    organisers can add types without a deploy.
    """

    class ScoreEffect(models.TextChoices):
        NONE = "NONE", _("Does not change the score")
        FOR_TEAM = "FOR_TEAM", _("Goal for the event's team")
        FOR_OPPONENT = "FOR_OPPONENT", _("Goal for the opponent (own goal)")

    class Category(models.TextChoices):
        SCORING = "SCORING", _("Scoring")
        DISCIPLINARY = "DISCIPLINARY", _("Disciplinary")
        SUBSTITUTION = "SUBSTITUTION", _("Substitution")
        SHOOTOUT = "SHOOTOUT", _("Penalty shoot-out")
        MATCH_FLOW = "MATCH_FLOW", _("Match flow")
        OTHER = "OTHER", _("Other")

    code = models.SlugField(
        _("code"),
        max_length=40,
        unique=True,
        help_text=_("e.g. 'goal', 'yellow-card'."),
    )
    name = models.CharField(_("name"), max_length=80)
    category = models.CharField(
        _("category"), max_length=20, choices=Category.choices
    )
    score_effect = models.CharField(
        _("score effect"),
        max_length=20,
        choices=ScoreEffect.choices,
        default=ScoreEffect.NONE,
    )
    counts_as_yellow_card = models.BooleanField(
        _("counts as yellow card"), default=False
    )
    counts_as_red_card = models.BooleanField(
        _("counts as red card"), default=False
    )
    requires_team = models.BooleanField(
        _("requires team"),
        default=True,
        help_text=_("False for events such as kick-off or full-time."),
    )
    icon = models.CharField(_("icon"), max_length=50, blank=True)
    display_order = models.PositiveSmallIntegerField(
        _("display order"), default=0
    )
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("event type")
        verbose_name_plural = _("event types")
        ordering = ("display_order", "name")

    def __str__(self):
        return self.name


class EventRole(models.Model):
    """
    Role a player plays in an event (PapelEvento), e.g. scorer, assist,
    player in, player out, booked player.
    """

    code = models.SlugField(_("code"), max_length=40, unique=True)
    name = models.CharField(_("name"), max_length=80)
    event_types = models.ManyToManyField(
        EventType,
        blank=True,
        related_name="allowed_roles",
        verbose_name=_("event types"),
        help_text=_("Event types in which this role may appear."),
    )

    class Meta:
        verbose_name = _("event role")
        verbose_name_plural = _("event roles")
        ordering = ("name",)

    def __str__(self):
        return self.name


class MatchEvent(TimeStampedModel):
    """
    A single occurrence recorded by a table official (EventoJogo).

    Events are never hard-deleted: corrections set ``is_canceled`` so the
    live feed can broadcast the reversal and the audit trail is preserved.
    """

    # Integer values so that ordering by period follows the match timeline.
    class Period(models.IntegerChoices):
        FIRST_HALF = 1, _("First half")
        SECOND_HALF = 2, _("Second half")
        EXTRA_TIME_FIRST = 3, _("Extra time - first half")
        EXTRA_TIME_SECOND = 4, _("Extra time - second half")
        PENALTIES = 5, _("Penalty shoot-out")

    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name=_("match"),
    )
    event_type = models.ForeignKey(
        EventType,
        on_delete=models.PROTECT,
        related_name="events",
        verbose_name=_("event type"),
    )
    team = models.ForeignKey(
        "championships.ChampionshipTeam",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="match_events",
        verbose_name=_("team"),
    )
    period = models.PositiveSmallIntegerField(
        _("period"), choices=Period.choices
    )
    minute = models.PositiveSmallIntegerField(
        _("minute"), help_text=_("Regular-time minute, e.g. 45.")
    )
    stoppage_minute = models.PositiveSmallIntegerField(
        _("stoppage time"),
        default=0,
        help_text=_("Added time, e.g. 2 for 45+2."),
    )
    description = models.CharField(
        _("description"), max_length=255, blank=True
    )

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="recorded_events",
        verbose_name=_("recorded by"),
    )
    is_canceled = models.BooleanField(_("canceled"), default=False)
    canceled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="canceled_events",
        verbose_name=_("canceled by"),
    )
    canceled_at = models.DateTimeField(_("canceled at"), null=True, blank=True)
    cancel_reason = models.CharField(
        _("cancellation reason"), max_length=255, blank=True
    )

    players = models.ManyToManyField(
        "championships.PlayerRegistration",
        through="MatchEventParticipant",
        related_name="match_events",
        verbose_name=_("players"),
    )

    class Meta:
        verbose_name = _("match event")
        verbose_name_plural = _("match events")
        ordering = (
            "match",
            "period",
            "minute",
            "stoppage_minute",
            "created_at",
        )
        indexes = [
            models.Index(fields=("match", "is_canceled")),
        ]

    def __str__(self):
        return f"{self.display_minute} {self.event_type} - {self.match}"

    @property
    def display_minute(self):
        if self.stoppage_minute:
            return f"{self.minute}+{self.stoppage_minute}'"
        return f"{self.minute}'"

    def clean(self):
        if not self.event_type_id:
            return
        if self.event_type.requires_team and not self.team_id:
            raise ValidationError(_("This event type requires a team."))
        if (
            self.team_id
            and self.match_id
            and not self.match.involves(self.team_id)
        ):
            raise ValidationError(_("Team is not playing this match."))


class MatchEventParticipant(models.Model):
    """Player involved in an event and in which role (EventoParticipante)."""

    event = models.ForeignKey(
        MatchEvent,
        on_delete=models.CASCADE,
        related_name="participants",
        verbose_name=_("event"),
    )
    player_registration = models.ForeignKey(
        "championships.PlayerRegistration",
        on_delete=models.PROTECT,
        related_name="event_participations",
        verbose_name=_("player"),
    )
    role = models.ForeignKey(
        EventRole,
        on_delete=models.PROTECT,
        related_name="participations",
        verbose_name=_("role"),
    )

    class Meta:
        verbose_name = _("event participant")
        verbose_name_plural = _("event participants")
        constraints = [
            models.UniqueConstraint(
                fields=("event", "player_registration", "role"),
                name="unique_participant_role_per_event",
            ),
        ]

    def __str__(self):
        return f"{self.player_registration.player} ({self.role})"

    def clean(self):
        # Only runs once the event is saved. When an event and its
        # participants are created together, the match sheet service
        # must perform these checks.
        if not (self.event_id and self.role_id):
            return
        if not self.role.event_types.filter(
            pk=self.event.event_type_id
        ).exists():
            raise ValidationError(
                _("Role '%(role)s' is not valid for event type '%(type)s'."),
                params={"role": self.role, "type": self.event.event_type},
            )
        if not self.event.match.lineups.filter(
            player_registration_id=self.player_registration_id
        ).exists():
            raise ValidationError(
                _("Player is not on the match sheet for this match.")
            )

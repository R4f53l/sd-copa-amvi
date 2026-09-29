from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.shared.models import TimeStampedModel


class City(models.Model):
    """
    Participating municipality. A table (instead of free text) keeps
    spelling consistent so the public "filter by city" works.
    """

    name = models.CharField(_("name"), max_length=100)
    state = models.CharField(_("state"), max_length=2, default="PI")
    slug = models.SlugField(_("slug"), max_length=120, unique=True)

    class Meta:
        verbose_name = _("city")
        verbose_name_plural = _("cities")
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("name", "state"), name="unique_city_per_state"
            ),
        ]

    def __str__(self):
        return f"{self.name}/{self.state}"


class Stadium(TimeStampedModel):
    name = models.CharField(_("name"), max_length=150)
    city = models.ForeignKey(
        City,
        on_delete=models.PROTECT,
        related_name="stadiums",
        verbose_name=_("city"),
    )
    address = models.CharField(_("address"), max_length=255, blank=True)
    capacity = models.PositiveIntegerField(
        _("capacity"), null=True, blank=True
    )
    latitude = models.DecimalField(
        _("latitude"), max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        _("longitude"), max_digits=9, decimal_places=6, null=True, blank=True
    )
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("stadium")
        verbose_name_plural = _("stadiums")
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("name", "city"), name="unique_stadium_per_city"
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.city})"


class Team(TimeStampedModel):
    name = models.CharField(_("name"), max_length=120, unique=True)
    short_name = models.CharField(
        _("short name"),
        max_length=5,
        help_text=_("Abbreviation shown on the scoreboard."),
    )
    slug = models.SlugField(_("slug"), max_length=140, unique=True)
    city = models.ForeignKey(
        City,
        on_delete=models.PROTECT,
        related_name="teams",
        verbose_name=_("city"),
    )
    crest = models.ImageField(
        _("crest"), upload_to="teams/crests/", blank=True
    )
    primary_color = models.CharField(
        _("primary colour"),
        max_length=7,
        blank=True,
        help_text=_("Hex colour, e.g. #1A2B3C."),
    )
    secondary_color = models.CharField(
        _("secondary colour"), max_length=7, blank=True
    )
    founded_year = models.PositiveSmallIntegerField(
        _("founded in"),
        null=True,
        blank=True,
        validators=[MinValueValidator(1850), MaxValueValidator(2100)],
    )
    home_stadium = models.ForeignKey(
        Stadium,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="home_teams",
        verbose_name=_("home stadium"),
    )
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("team")
        verbose_name_plural = _("teams")
        ordering = ("name",)

    def __str__(self):
        return self.name


class Player(TimeStampedModel):
    """
    A person who plays football. The link to a team is *not* stored here:
    it is time- and championship-dependent and lives in
    ``championships.PlayerRegistration``.
    """

    class Position(models.TextChoices):
        GOALKEEPER = "GK", _("Goalkeeper")
        DEFENDER = "DF", _("Defender")
        MIDFIELDER = "MF", _("Midfielder")
        FORWARD = "FW", _("Forward")

    class PreferredFoot(models.TextChoices):
        LEFT = "L", _("Left")
        RIGHT = "R", _("Right")
        BOTH = "B", _("Both")

    full_name = models.CharField(_("full name"), max_length=150)
    nickname = models.CharField(
        _("nickname"),
        max_length=60,
        blank=True,
        help_text=_("Name shown in live feeds."),
    )
    document_number = models.CharField(
        _("document number"),
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        help_text=_(
            "Official ID (e.g. CPF) used to prevent duplicate registrations."
        ),
    )
    birth_date = models.DateField(_("birth date"), null=True, blank=True)
    position = models.CharField(
        _("position"), max_length=2, choices=Position.choices, blank=True
    )
    preferred_foot = models.CharField(
        _("preferred foot"),
        max_length=1,
        choices=PreferredFoot.choices,
        blank=True,
    )
    photo = models.ImageField(
        _("photo"), upload_to="players/photos/", blank=True
    )
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("player")
        verbose_name_plural = _("players")
        ordering = ("full_name",)
        indexes = [models.Index(fields=("full_name",))]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        return self.nickname or self.full_name

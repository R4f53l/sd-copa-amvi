from django.contrib import admin

from .models import (
    EventRole,
    EventType,
    Lineup,
    Match,
    MatchEvent,
    MatchEventParticipant,
)


class LineupInline(admin.TabularInline):
    model = Lineup
    extra = 0
    raw_id_fields = ("player_registration",)
    fields = (
        "team",
        "player_registration",
        "role",
        "shirt_number",
        "position",
        "is_captain",
    )


class MatchEventInline(admin.TabularInline):
    model = MatchEvent
    extra = 0
    fields = (
        "period",
        "minute",
        "stoppage_minute",
        "event_type",
        "team",
        "description",
        "is_canceled",
    )


class MatchEventParticipantInline(admin.TabularInline):
    model = MatchEventParticipant
    extra = 0
    raw_id_fields = ("player_registration",)
    fields = ("player_registration", "role")


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "championship",
        "stage",
        "round_number",
        "scheduled_at",
        "status",
        "home_score",
        "away_score",
    )
    list_filter = ("championship", "status", "stage")
    search_fields = (
        "home_team__team__name",
        "away_team__team__name",
        "referee_name",
    )
    list_select_related = (
        "championship",
        "home_team__team",
        "away_team__team",
        "stadium",
    )
    filter_horizontal = ("table_officials",)
    inlines = [LineupInline, MatchEventInline]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "championship",
                    ("home_team", "away_team"),
                    "stadium",
                    ("stage", "round_number"),
                    "scheduled_at",
                    "status",
                    "referee_name",
                    "streaming_url",
                    "table_officials",
                )
            },
        ),
        (
            "Placar e resultado",
            {
                "fields": (
                    ("home_score", "away_score"),
                    ("home_penalty_score", "away_penalty_score"),
                    "is_walkover",
                    ("started_at", "finished_at"),
                    "notes",
                )
            },
        ),
    )


@admin.register(MatchEvent)
class MatchEventAdmin(admin.ModelAdmin):
    list_display = (
        "match",
        "event_type",
        "team",
        "period",
        "minute",
        "stoppage_minute",
        "is_canceled",
    )
    list_filter = ("event_type", "period", "is_canceled")
    search_fields = (
        "match__home_team__team__name",
        "match__away_team__team__name",
        "description",
    )
    list_select_related = (
        "match__home_team__team",
        "match__away_team__team",
        "event_type",
        "team__team",
    )
    inlines = [MatchEventParticipantInline]


@admin.register(EventType)
class EventTypeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "category",
        "score_effect",
        "counts_as_yellow_card",
        "counts_as_red_card",
        "requires_team",
        "display_order",
        "is_active",
    )
    list_filter = ("category", "score_effect", "is_active")
    search_fields = ("code", "name")


@admin.register(EventRole)
class EventRoleAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")
    filter_horizontal = ("event_types",)


@admin.register(Lineup)
class LineupAdmin(admin.ModelAdmin):
    list_display = (
        "match",
        "team",
        "player_registration",
        "role",
        "shirt_number",
        "position",
        "is_captain",
    )
    list_filter = ("role", "position", "is_captain")
    search_fields = (
        "player_registration__player__full_name",
        "player_registration__player__nickname",
    )
    list_select_related = (
        "match__home_team__team",
        "match__away_team__team",
        "team__team",
        "player_registration__player",
    )

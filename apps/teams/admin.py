"""Django admin configuration for the teams app."""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import City, Player, Stadium, Team

PREVIEW_LIST_SIZE = 32
PREVIEW_FORM_SIZE = 120


def image_preview(image, size):
    """Render an uploaded image as a thumbnail, or a dash when empty."""
    if not image:
        return "—"
    return format_html(
        '<img src="{}" alt="" style="height:{}px;width:auto;'
        'border-radius:4px;object-fit:contain">',
        image.url,
        size,
    )


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "state", "slug")
    list_filter = ("state",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Stadium)
class StadiumAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "capacity", "is_active")
    list_filter = ("is_active", "city")
    search_fields = ("name", "address", "city__name")
    list_select_related = ("city",)
    autocomplete_fields = ("city",)
    fieldsets = (
        (
            None,
            {"fields": ("name", "city", "address", "capacity", "is_active")},
        ),
        (
            _("Location"),
            {
                "fields": (("latitude", "longitude"),),
                "description": _(
                    "Used to show the weather forecast for matches."
                ),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = (
        "crest_thumbnail",
        "name",
        "short_name",
        "city",
        "home_stadium",
        "is_active",
    )
    list_display_links = ("crest_thumbnail", "name")
    list_filter = ("is_active", "city")
    search_fields = ("name", "short_name", "city__name")
    # Stadium.__str__ also reads its city.
    list_select_related = ("city", "home_stadium__city")
    autocomplete_fields = ("city", "home_stadium")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("crest_preview",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    ("short_name", "slug"),
                    "city",
                    "home_stadium",
                    "is_active",
                )
            },
        ),
        (
            _("Identity"),
            {
                "fields": (
                    "crest",
                    "crest_preview",
                    ("primary_color", "secondary_color"),
                    "founded_year",
                )
            },
        ),
    )

    @admin.display(description=_("crest"))
    def crest_thumbnail(self, obj):
        return image_preview(obj.crest, PREVIEW_LIST_SIZE)

    @admin.display(description=_("preview"))
    def crest_preview(self, obj):
        return image_preview(obj.crest, PREVIEW_FORM_SIZE)


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = (
        "photo_thumbnail",
        "full_name",
        "nickname",
        "position",
        "birth_date",
        "is_active",
    )
    list_display_links = ("photo_thumbnail", "full_name")
    list_filter = ("position", "preferred_foot", "is_active")
    search_fields = ("full_name", "nickname", "document_number")
    date_hierarchy = "birth_date"
    readonly_fields = ("photo_preview",)
    fieldsets = (
        (None, {"fields": ("full_name", "nickname", "is_active")}),
        (
            _("Personal data"),
            {
                "fields": (
                    "document_number",
                    "birth_date",
                    "photo",
                    "photo_preview",
                )
            },
        ),
        (_("On the pitch"), {"fields": ("position", "preferred_foot")}),
    )

    @admin.display(description=_("photo"))
    def photo_thumbnail(self, obj):
        return image_preview(obj.photo, PREVIEW_LIST_SIZE)

    @admin.display(description=_("preview"))
    def photo_preview(self, obj):
        return image_preview(obj.photo, PREVIEW_FORM_SIZE)

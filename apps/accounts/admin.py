"""Django admin configuration for the accounts app."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.db.models import Count
from django.utils.translation import gettext_lazy as _

from .models import User


class UserAdminCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "role")


class UserAdminChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm

    list_display = (
        "username",
        "get_full_name",
        "email",
        "role",
        "assigned_matches",
        "is_active",
        "is_staff",
    )
    list_display_links = ("username", "get_full_name")
    list_filter = ("role", "is_active", "is_staff", "is_superuser", "groups")
    search_fields = ("username", "first_name", "last_name", "email", "phone")
    ordering = ("first_name", "last_name", "username")

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            _("Personal info"),
            {"fields": (("first_name", "last_name"), "email", "phone")},
        ),
        (
            _("Role in the championship"),
            {
                "fields": ("role",),
                "description": _(
                    "Administrators manage the whole championship. Table "
                    "officials only run the matches assigned to them."
                ),
            },
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Important dates"),
            {
                "fields": ("last_login", "date_joined"),
                "classes": ("collapse",),
            },
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "role", "password1", "password2"),
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(_assigned_matches=Count("officiated_matches"))
        )

    @admin.display(description=_("full name"), ordering="first_name")
    def get_full_name(self, obj):
        return obj.get_full_name() or "—"

    @admin.display(
        description=_("assigned matches"), ordering="_assigned_matches"
    )
    def assigned_matches(self, obj):
        return obj._assigned_matches

"""Server-rendered account management and table official dashboard."""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.translation import gettext as _

from apps.accounts.decorators import admin_required, mesario_ou_admin_required
from apps.matches.models import Match

from .forms import TableOfficialCreationForm

User = get_user_model()


@admin_required
def official_create(request):
    """Allow administrators to create accounts that are always officials."""
    if request.method == "POST":
        form = TableOfficialCreationForm(request.POST)
        if form.is_valid():
            official = form.save()
            messages.success(
                request,
                _("Table official %(username)s created.")
                % {"username": official.username},
            )
            return redirect("accounts:official_dashboard")
    else:
        form = TableOfficialCreationForm()

    return render(
        request,
        "accounts/table_official_form.html",
        {"form": form},
    )


@mesario_ou_admin_required
def official_dashboard(request):
    """List only the matches assigned to the signed-in user."""
    matches = (
        Match.objects.filter(table_officials=request.user)
        .select_related(
            "championship",
            "home_team__team",
            "away_team__team",
            "stadium__city",
        )
        .order_by("scheduled_at")
    )
    return render(
        request,
        "accounts/official_dashboard.html",
        {"matches": matches},
    )


class PasswordChangeView(auth_views.PasswordChangeView):
    """Django's session-authenticated password change with project template."""

    template_name = "accounts/password_change_form.html"
    success_url = reverse_lazy("accounts:password_change_done")


class PasswordChangeDoneView(
    LoginRequiredMixin, auth_views.PasswordChangeDoneView
):
    """Keep the completion page behind authentication as well."""

    template_name = "accounts/password_change_done.html"

"""Access rules for the match pages of the back-office panel."""

from functools import cached_property

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404

from .models import Match


def can_manage_matches(user):
    """Scheduling fixtures is reserved to administrators."""
    return user.is_authenticated and user.is_admin


def can_officiate(user, match):
    """Administrators, or table officials assigned to this match."""
    if not user.is_authenticated:
        return False
    if user.is_admin:
        return True
    return match.table_officials.filter(pk=user.pk).exists()


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return can_manage_matches(self.request.user)


class MatchOfficialRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Loads ``self.match`` from the URL and checks the user may run it."""

    match_url_kwarg = "pk"

    @cached_property
    def match(self):
        return get_object_or_404(
            Match.objects.select_related(
                "championship",
                "home_team__team",
                "away_team__team",
                "stadium__city",
            ),
            pk=self.kwargs[self.match_url_kwarg],
        )

    def test_func(self):
        return can_officiate(self.request.user, self.match)

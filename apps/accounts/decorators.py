"""Shared access rules for server-rendered views."""

from functools import wraps

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import resolve_url


def is_admin(user):
    """Return whether the user has administrator privileges."""
    return user.is_authenticated and (
        user.is_superuser
        or user.is_staff
        or getattr(user, "role", None) == "ADMIN"
    )


def is_mesario_ou_admin(user):
    """Return whether the user may use the match operations panel."""
    return user.is_authenticated and (
        is_admin(user) or getattr(user, "role", None) == "TABLE_OFFICIAL"
    )


def admin_required(view_func):
    """Require login and administrator privileges for a function view."""
    return _role_required(is_admin)(view_func)


def mesario_ou_admin_required(view_func):
    """Require login and an administrator or table official role."""
    return _role_required(is_mesario_ou_admin)(view_func)


def _role_required(test_func):
    """Redirect anonymous users and return 403 for authenticated denials."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                login_url = resolve_url("accounts:login")
                return redirect_to_login(request.get_full_path(), login_url)
            if not test_func(request.user):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """CBV equivalent of :func:`admin_required`."""

    def test_func(self):
        return is_admin(self.request.user)


class MesarioOuAdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """CBV equivalent of :func:`mesario_ou_admin_required`."""

    def test_func(self):
        return is_mesario_ou_admin(self.request.user)

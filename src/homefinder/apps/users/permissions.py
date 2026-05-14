from __future__ import annotations

from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse

from homefinder.apps.users.models import UserRole

P = ParamSpec("P")
R = TypeVar("R", bound=HttpResponse)


def admin_required(view_func: Callable[P, R]) -> Callable[P, HttpResponse]:
    @wraps(view_func)
    def _wrapped_view(request: HttpRequest, *args: P.args, **kwargs: P.kwargs) -> HttpResponse:
        access_redirect = _require_admin_user(request=request, next_url=request.get_full_path())
        if access_redirect is not None:
            return access_redirect
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def _require_admin_user(*, request: HttpRequest, next_url: str) -> HttpResponse | None:
    guest_redirect = _require_authenticated_user(
        request=request,
        warning_message="Sign in with an admin account to access this page.",
        next_url=next_url,
    )
    if guest_redirect is not None:
        return guest_redirect

    if not _is_admin_user(request.user):
        raise PermissionDenied("Admin access is restricted to admin role users.")
    return None


def _require_authenticated_user(
    *,
    request: HttpRequest,
    warning_message: str,
    next_url: str,
) -> HttpResponse | None:
    if request.user.is_authenticated:
        return None

    messages.warning(request, warning_message)
    login_url = reverse("login-page")
    query_string = urlencode({"next": next_url}) if next_url else ""
    if query_string:
        login_url = f"{login_url}?{query_string}"
    return redirect(login_url)


def _is_admin_user(user: Any) -> bool:
    return getattr(user, "role", None) == UserRole.ADMIN

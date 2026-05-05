from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import authenticate
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from homefinder.apps.core.views import json_error_response, unauthorized_response
from homefinder.apps.interactions.services import log_auth_activity

from .forms import LoginForm, RegistrationForm, TwoFactorVerificationForm
from .models import User
from .services import (
    get_pending_login_state,
    logout_authenticated_user,
    register_user,
    start_pending_login,
    verify_pending_login,
)

HTML_ACCEPT_HEADER_FRAGMENT = "text/html"


@require_http_methods(["GET", "POST"])
def register(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        if _wants_html(request):
            messages.info(request, "You are already signed in.")
            return redirect("home")
        return json_error_response(400, "You are already authenticated.")

    if request.method == "GET":
        return _render_register_form(request, RegistrationForm())

    form = RegistrationForm(request.POST)
    if not form.is_valid():
        log_auth_activity(action="registration_failed_validation", details={"errors": form.errors.get_json_data()})
        if _wants_html(request):
            messages.error(request, "Check the highlighted fields and try again.")
            return _render_register_form(request, form, status=400)
        return _validation_error_response(form=form)

    user = register_user(
        email=form.cleaned_data["email"],
        password=form.cleaned_data["password"],
        full_name=form.cleaned_data.get("full_name", ""),
        phone=form.cleaned_data.get("phone", ""),
    )
    log_auth_activity(action="registration_succeeded", user=user, details={"user_id": user.pk})

    if _wants_html(request):
        messages.success(request, "Registration complete. Sign in to continue.")
        return redirect("auth-login")

    return JsonResponse(
        {
            "status": "ok",
            "data": {
                "message": "Registration successful.",
                "user": {
                    "id": user.pk,
                    "email": user.email,
                },
            },
        },
        status=201,
    )


@require_http_methods(["GET", "POST"])
def login(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        if _wants_html(request):
            messages.info(request, "You are already signed in.")
            return redirect("home")
        return json_error_response(400, "You are already authenticated.")

    if request.method == "GET":
        return _render_login_form(request, LoginForm())

    form = LoginForm(request.POST)
    if not form.is_valid():
        log_auth_activity(action="login_failed_validation", details={"errors": form.errors.get_json_data()})
        if _wants_html(request):
            messages.error(request, "Check the highlighted fields and try again.")
            return _render_login_form(request, form, status=400)
        return _validation_error_response(form=form)

    email = form.cleaned_data["email"]
    user = authenticate(request, email=email, password=form.cleaned_data["password"])
    if user is None or not user.is_active:
        log_auth_activity(action="login_failed_credentials", details={"email": email})
        if _wants_html(request):
            form.add_error(None, "Invalid email or password.")
            messages.error(request, "Invalid email or password.")
            return _render_login_form(request, form, status=401)
        return json_error_response(401, "Invalid email or password.")

    login_result = start_pending_login(request=request, user=user)

    if _wants_html(request):
        messages.success(request, "Credentials accepted. Enter your 2FA code to finish login.")
        return redirect("auth-2fa")

    return JsonResponse(
        {
            "status": "ok",
            "data": {
                "message": "Credentials accepted. Enter your 2FA code to finish login.",
                "pending_2fa": True,
                "token_expires_at": login_result.token_expires_at.isoformat(),
            },
        }
    )


@require_http_methods(["GET"])
def two_factor(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        messages.info(request, "You are already signed in.")
        return redirect("home")

    if get_pending_login_state(request.session) is None:
        messages.error(request, "Pending login not found. Start the login flow again.")
        return redirect("auth-login")

    return _render_two_factor_form(request, TwoFactorVerificationForm())


@require_http_methods(["POST"])
def verify_2fa(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        if _wants_html(request):
            messages.info(request, "You are already signed in.")
            return redirect("home")
        return json_error_response(400, "You are already authenticated.")

    form = TwoFactorVerificationForm(request.POST)
    if not form.is_valid():
        log_auth_activity(action="login_2fa_failed_validation", details={"errors": form.errors.get_json_data()})
        if _wants_html(request):
            messages.error(request, "Check the highlighted fields and try again.")
            return _render_two_factor_form(request, form, status=400)
        return _validation_error_response(form=form)

    verification_result = verify_pending_login(request=request, token=form.cleaned_data["token"])
    if verification_result.success and verification_result.user is not None:
        if _wants_html(request):
            messages.success(request, "You are signed in.")
            return redirect("home")
        return JsonResponse(
            {
                "status": "ok",
                "data": {
                    "message": "Login completed successfully.",
                    "user": {
                        "id": verification_result.user.pk,
                        "email": verification_result.user.email,
                    },
                },
            }
        )

    error_code = verification_result.error_code or "token_invalid"
    if _wants_html(request):
        message = _two_factor_error_message(
            error_code=error_code,
            attempts_remaining=verification_result.attempts_remaining,
        )
        if error_code == "token_invalid":
            form.add_error("token", message)
            messages.error(request, message)
            return _render_two_factor_form(request, form, status=400)

        messages.error(request, message)
        return redirect("auth-login")

    if error_code == "pending_login_required":
        return unauthorized_response("Pending login not found. Start the login flow again.")
    if error_code == "token_expired":
        return json_error_response(400, "This 2FA token has expired. Start the login flow again.")
    if error_code == "token_already_used":
        return json_error_response(400, "This 2FA token has already been used.")
    if error_code == "max_attempts_exceeded":
        return json_error_response(400, "Too many invalid 2FA attempts. Start the login flow again.")
    if error_code == "inactive_user":
        return unauthorized_response("This account is inactive.")

    message = "Invalid 2FA token."
    attempts_remaining = verification_result.attempts_remaining
    error_payload = {
        "status": "error",
        "error": {
            "code": 400,
            "message": message,
        },
    }
    if attempts_remaining is not None:
        error_payload["error"]["details"] = {
            "attempts_remaining": attempts_remaining,
        }
    return JsonResponse(error_payload, status=400)


@require_http_methods(["POST"])
def logout(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        if _wants_html(request):
            messages.error(request, "You are not signed in.")
            return redirect("auth-login")
        return unauthorized_response()

    logout_authenticated_user(request)
    if _wants_html(request):
        messages.success(request, "You have been signed out.")
        return redirect("home")

    return JsonResponse(
        {
            "status": "ok",
            "data": {
                "message": "Logged out successfully.",
            },
        }
    )


def _wants_html(request: HttpRequest) -> bool:
    if request.method == "GET":
        return True
    return HTML_ACCEPT_HEADER_FRAGMENT in request.headers.get("Accept", "")


def _render_register_form(request: HttpRequest, form: RegistrationForm, *, status: int = 200) -> HttpResponse:
    return render(request, "auth/register.html", {"form": form}, status=status)


def _render_login_form(request: HttpRequest, form: LoginForm, *, status: int = 200) -> HttpResponse:
    return render(request, "auth/login.html", {"form": form}, status=status)


def _render_two_factor_form(
    request: HttpRequest,
    form: TwoFactorVerificationForm,
    *,
    status: int = 200,
) -> HttpResponse:
    pending_user_email = ""
    pending_state = get_pending_login_state(request.session)
    if pending_state is not None:
        pending_user_email = (
            User.objects.filter(pk=pending_state.user_id).values_list("email", flat=True).first() or ""
        )

    return render(
        request,
        "auth/2fa.html",
        {
            "form": form,
            "pending_user_email": pending_user_email,
        },
        status=status,
    )


def _two_factor_error_message(*, error_code: str, attempts_remaining: int | None = None) -> str:
    if error_code == "pending_login_required":
        return "Pending login not found. Start the login flow again."
    if error_code == "token_expired":
        return "This 2FA token has expired. Start the login flow again."
    if error_code == "token_already_used":
        return "This 2FA token has already been used."
    if error_code == "max_attempts_exceeded":
        return "Too many invalid 2FA attempts. Start the login flow again."
    if error_code == "inactive_user":
        return "This account is inactive."
    if attempts_remaining is not None:
        attempt_label = "attempt" if attempts_remaining == 1 else "attempts"
        return f"Invalid 2FA token. {attempts_remaining} {attempt_label} remaining."
    return "Invalid 2FA token."


def _validation_error_response(form: RegistrationForm | LoginForm | TwoFactorVerificationForm) -> JsonResponse:
    return JsonResponse(
        {
            "status": "error",
            "error": {
                "code": 400,
                "message": "Validation failed.",
                "details": form.errors.get_json_data(),
            },
        },
        status=400,
    )

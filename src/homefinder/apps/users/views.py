from __future__ import annotations

from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import authenticate
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from homefinder.apps.core.views import json_error_response, unauthorized_response
from homefinder.apps.interactions.services import log_auth_activity

from .forms import LoginForm, RegistrationForm, TwoFactorVerificationForm
from .services import (
    get_pending_login_state,
    logout_authenticated_user,
    register_user,
    start_pending_login,
    verify_pending_login,
)


@require_http_methods(["GET", "POST"])
def register_page(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        messages.info(request, "You are already signed in.")
        return redirect("home")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if not form.is_valid():
            log_auth_activity(action="registration_failed_validation", details={"errors": form.errors.get_json_data()})
            messages.error(request, "Please correct the highlighted fields and try again.")
            return _render_register_page(request=request, form=form)

        user = register_user(
            email=form.cleaned_data["email"],
            password=form.cleaned_data["password"],
            full_name=form.cleaned_data.get("full_name", ""),
            phone=form.cleaned_data.get("phone", ""),
        )
        log_auth_activity(action="registration_succeeded", user=user, details={"user_id": user.pk})

        messages.success(request, "Registration successful. Sign in to continue.")
        login_url = f"{reverse('login-page')}?{urlencode({'email': user.email})}"
        return redirect(login_url)

    initial: dict[str, str] = {}
    prefilled_email = (request.GET.get("email") or "").strip()
    if prefilled_email:
        initial["email"] = prefilled_email

    form = RegistrationForm(initial=initial)
    return _render_register_page(request=request, form=form)


@require_http_methods(["GET", "POST"])
def login_page(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        messages.info(request, "You are already signed in.")
        return redirect("home")

    if request.method == "POST":
        form = LoginForm(request.POST)
        if not form.is_valid():
            log_auth_activity(action="login_failed_validation", details={"errors": form.errors.get_json_data()})
            messages.error(request, "Please correct the highlighted fields and try again.")
            return _render_login_page(request=request, form=form)

        email = form.cleaned_data["email"]
        user = authenticate(request, email=email, password=form.cleaned_data["password"])
        if user is None or not user.is_active:
            log_auth_activity(action="login_failed_credentials", details={"email": email})
            form.add_error(None, "Invalid email or password.")
            return _render_login_page(request=request, form=form)

        start_pending_login(request=request, user=user)
        messages.success(request, "Credentials accepted. Enter your 2FA code to finish login.")
        return redirect("verify-2fa-page")

    initial: dict[str, str] = {}
    prefilled_email = (request.GET.get("email") or "").strip()
    if prefilled_email:
        initial["email"] = prefilled_email

    form = LoginForm(initial=initial)
    return _render_login_page(request=request, form=form)


@require_http_methods(["GET", "POST"])
def verify_2fa_page(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        messages.info(request, "You are already signed in.")
        return redirect("home")

    pending_state = get_pending_login_state(request.session)
    if pending_state is None:
        messages.warning(request, "Start the login flow before entering a 2FA code.")
        return redirect("login-page")

    if request.method == "POST":
        form = TwoFactorVerificationForm(request.POST)
        if not form.is_valid():
            log_auth_activity(action="login_2fa_failed_validation", details={"errors": form.errors.get_json_data()})
            messages.error(request, "Enter a valid 6-digit code.")
            return _render_verify_2fa_page(request=request, form=form)

        verification_result = verify_pending_login(request=request, token=form.cleaned_data["token"])
        if verification_result.success and verification_result.user is not None:
            messages.success(request, "Login completed successfully.")
            return redirect("home")

        error_code = verification_result.error_code or "token_invalid"
        if error_code == "pending_login_required":
            messages.warning(request, "Pending login not found. Start the login flow again.")
            return redirect("login-page")
        if error_code == "token_expired":
            messages.error(request, "This 2FA token has expired. Start the login flow again.")
            return redirect("login-page")
        if error_code == "token_already_used":
            messages.error(request, "This 2FA token has already been used. Start the login flow again.")
            return redirect("login-page")
        if error_code == "max_attempts_exceeded":
            messages.error(request, "Too many invalid 2FA attempts. Start the login flow again.")
            return redirect("login-page")
        if error_code == "inactive_user":
            messages.error(request, "This account is inactive.")
            return redirect("login-page")

        attempts_remaining = verification_result.attempts_remaining
        error_message = "Invalid 2FA token."
        if attempts_remaining is not None:
            attempt_label = "attempt" if attempts_remaining == 1 else "attempts"
            error_message = f"Invalid 2FA token. {attempts_remaining} {attempt_label} remaining."
        form.add_error("token", error_message)
        messages.error(request, "Unable to verify that code.")
        return _render_verify_2fa_page(request=request, form=form)

    form = TwoFactorVerificationForm()
    return _render_verify_2fa_page(request=request, form=form)


@require_http_methods(["POST"])
def logout_page(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        messages.warning(request, "You are already signed out.")
        return redirect("login-page")

    logout_authenticated_user(request)
    messages.success(request, "Signed out successfully.")
    return redirect("login-page")


@require_http_methods(["POST"])
def register(request: HttpRequest) -> JsonResponse:
    if request.user.is_authenticated:
        return json_error_response(400, "You are already authenticated.")

    form = RegistrationForm(request.POST)
    if not form.is_valid():
        log_auth_activity(action="registration_failed_validation", details={"errors": form.errors.get_json_data()})
        return _validation_error_response(form=form)

    user = register_user(
        email=form.cleaned_data["email"],
        password=form.cleaned_data["password"],
        full_name=form.cleaned_data.get("full_name", ""),
        phone=form.cleaned_data.get("phone", ""),
    )
    log_auth_activity(action="registration_succeeded", user=user, details={"user_id": user.pk})

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


@require_http_methods(["POST"])
def login(request: HttpRequest) -> JsonResponse:
    if request.user.is_authenticated:
        return json_error_response(400, "You are already authenticated.")

    form = LoginForm(request.POST)
    if not form.is_valid():
        log_auth_activity(action="login_failed_validation", details={"errors": form.errors.get_json_data()})
        return _validation_error_response(form=form)

    email = form.cleaned_data["email"]
    user = authenticate(request, email=email, password=form.cleaned_data["password"])
    if user is None or not user.is_active:
        log_auth_activity(action="login_failed_credentials", details={"email": email})
        return json_error_response(401, "Invalid email or password.")

    login_result = start_pending_login(request=request, user=user)

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


@require_http_methods(["POST"])
def verify_2fa(request: HttpRequest) -> JsonResponse:
    if request.user.is_authenticated:
        return json_error_response(400, "You are already authenticated.")

    form = TwoFactorVerificationForm(request.POST)
    if not form.is_valid():
        log_auth_activity(action="login_2fa_failed_validation", details={"errors": form.errors.get_json_data()})
        return _validation_error_response(form=form)

    verification_result = verify_pending_login(request=request, token=form.cleaned_data["token"])
    if verification_result.success and verification_result.user is not None:
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
def logout(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return unauthorized_response()

    logout_authenticated_user(request)
    return JsonResponse(
        {
            "status": "ok",
            "data": {
                "message": "Logged out successfully.",
            },
        }
    )


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


def _render_register_page(*, request: HttpRequest, form: RegistrationForm) -> HttpResponse:
    return render(
        request,
        "users/register.html",
        {
            "form": form,
            "submit_label": "Create account",
            "submit_loading_label": "Creating account...",
        },
    )


def _render_login_page(*, request: HttpRequest, form: LoginForm) -> HttpResponse:
    return render(
        request,
        "users/login.html",
        {
            "form": form,
            "submit_label": "Continue to 2FA",
            "submit_loading_label": "Checking credentials...",
        },
    )


def _render_verify_2fa_page(*, request: HttpRequest, form: TwoFactorVerificationForm) -> HttpResponse:
    return render(
        request,
        "users/verify_2fa.html",
        {
            "form": form,
            "submit_label": "Verify code",
            "submit_loading_label": "Verifying code...",
        },
    )

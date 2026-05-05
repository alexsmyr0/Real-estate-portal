from __future__ import annotations

from django.contrib.auth import authenticate
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_http_methods

from homefinder.apps.core.views import json_error_response, unauthorized_response
from homefinder.apps.interactions.services import log_auth_activity

from .forms import LoginForm, RegistrationForm, TwoFactorVerificationForm
from .services import (
    logout_authenticated_user,
    register_user,
    start_pending_login,
    verify_pending_login,
)


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

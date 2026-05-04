from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.sessions.backends.base import SessionBase
from django.contrib.sessions.models import Session
from django.db import transaction
from django.http import HttpRequest
from django.utils.crypto import salted_hmac
from django.utils import timezone

from homefinder.apps.interactions.services import log_auth_activity, send_login_2fa_email

from .models import ActiveSession, LoginTwoFactorToken, User

PENDING_LOGIN_USER_ID_SESSION_KEY = "pending_login_user_id"
PENDING_LOGIN_TOKEN_ID_SESSION_KEY = "pending_login_token_id"

LOGIN_2FA_TOKEN_LENGTH = 6
LOGIN_2FA_TOKEN_TTL = timedelta(minutes=10)
LOGIN_2FA_MAX_ATTEMPTS = 5

LOGIN_2FA_TOKEN_HASH_SALT = "homefinder.apps.users.login_2fa_token"
SESSION_TOKEN_HASH_SALT = "homefinder.apps.users.session_token"


@dataclass(frozen=True, slots=True)
class PendingLoginState:
    user_id: int
    token_id: int


@dataclass(frozen=True, slots=True)
class LoginStartResult:
    token_id: int
    token_expires_at: datetime


@dataclass(frozen=True, slots=True)
class TwoFactorVerificationResult:
    success: bool
    user: User | None = None
    error_code: str | None = None
    attempts_remaining: int | None = None


def register_user(
    *,
    email: str,
    password: str,
    full_name: str = "",
    phone: str = "",
) -> User:
    return User.objects.create_user(
        email=email,
        password=password,
        full_name=full_name,
        phone=phone,
    )


def start_pending_login(*, request: HttpRequest, user: User) -> LoginStartResult:
    clear_pending_login_state(request.session)

    token_value = generate_login_2fa_token_value()
    token_expires_at = timezone.now() + LOGIN_2FA_TOKEN_TTL
    token_record = LoginTwoFactorToken.objects.create(
        user=user,
        token_hash=hash_login_2fa_token(token_value),
        expires_at=token_expires_at,
    )

    set_pending_login_state(
        request.session,
        user_id=user.pk,
        token_id=token_record.pk,
    )
    send_login_2fa_email(user=user, token=token_value)
    log_auth_activity(
        action="login_password_verified",
        user=user,
        details={
            "token_id": token_record.pk,
            "expires_at": token_expires_at.isoformat(),
        },
    )

    return LoginStartResult(
        token_id=token_record.pk,
        token_expires_at=token_expires_at,
    )


def verify_pending_login(*, request: HttpRequest, token: str) -> TwoFactorVerificationResult:
    pending_state = get_pending_login_state(request.session)
    if pending_state is None:
        return TwoFactorVerificationResult(success=False, error_code="pending_login_required")

    now = timezone.now()
    should_clear_pending = False
    verification_result: TwoFactorVerificationResult | None = None
    authenticated_user: User | None = None

    with transaction.atomic():
        token_record = (
            LoginTwoFactorToken.objects.select_for_update()
            .select_related("user")
            .filter(pk=pending_state.token_id, user_id=pending_state.user_id)
            .first()
        )
        if token_record is None:
            should_clear_pending = True
            verification_result = TwoFactorVerificationResult(success=False, error_code="pending_login_required")
        elif token_record.verified_at is not None:
            should_clear_pending = True
            verification_result = TwoFactorVerificationResult(success=False, error_code="token_already_used")
        elif token_record.expires_at <= now:
            should_clear_pending = True
            verification_result = TwoFactorVerificationResult(success=False, error_code="token_expired")
        elif token_record.attempts_used >= LOGIN_2FA_MAX_ATTEMPTS:
            should_clear_pending = True
            verification_result = TwoFactorVerificationResult(success=False, error_code="max_attempts_exceeded")
        elif not verify_login_2fa_token(token=token, token_hash=token_record.token_hash):
            token_record.attempts_used += 1
            token_record.save(update_fields=["attempts_used"])
            attempts_remaining = max(0, LOGIN_2FA_MAX_ATTEMPTS - token_record.attempts_used)
            should_clear_pending = attempts_remaining == 0
            error_code = "max_attempts_exceeded" if attempts_remaining == 0 else "token_invalid"
            verification_result = TwoFactorVerificationResult(
                success=False,
                error_code=error_code,
                attempts_remaining=attempts_remaining,
            )
        else:
            token_record.verified_at = now
            token_record.save(update_fields=["verified_at"])
            authenticated_user = token_record.user

    if verification_result is not None:
        if should_clear_pending:
            clear_pending_login_state(request.session)
        return verification_result

    if should_clear_pending:
        clear_pending_login_state(request.session)

    if authenticated_user is None:
        clear_pending_login_state(request.session)
        return TwoFactorVerificationResult(success=False, error_code="pending_login_required")

    if not authenticated_user.is_active:
        clear_pending_login_state(request.session)
        return TwoFactorVerificationResult(success=False, error_code="inactive_user")

    finalize_authenticated_session(request=request, user=authenticated_user)
    clear_pending_login_state(request.session)
    log_auth_activity(
        action="login_2fa_verified",
        user=authenticated_user,
        details={"token_id": pending_state.token_id},
    )
    return TwoFactorVerificationResult(success=True, user=authenticated_user)


def finalize_authenticated_session(*, request: HttpRequest, user: User) -> ActiveSession:
    auth_login(request, user)
    if request.session.session_key is None:
        request.session.save()

    new_session_key = request.session.session_key
    if not new_session_key:
        raise ValueError("Unable to establish an authenticated session key.")

    new_session_hash = hash_session_token(new_session_key)
    session_expires_at = timezone.now() + timedelta(seconds=settings.SESSION_COOKIE_AGE)
    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        previous_session_hash = (
            ActiveSession.objects.filter(user_id=locked_user.pk).values_list("session_token_hash", flat=True).first()
        )
        if previous_session_hash and not hmac.compare_digest(previous_session_hash, new_session_hash):
            invalidate_session_by_hash(previous_session_hash)

        active_session, _created = ActiveSession.objects.update_or_create(
            user=locked_user,
            defaults={
                "session_token_hash": new_session_hash,
                "expires_at": session_expires_at,
            },
        )
    return active_session


def logout_authenticated_user(request: HttpRequest) -> bool:
    if not request.user.is_authenticated:
        return False

    user = request.user
    session_key = request.session.session_key
    session_hash = hash_session_token(session_key) if session_key else None

    auth_logout(request)

    if session_hash:
        deleted_count, _deleted_details = ActiveSession.objects.filter(
            user=user,
            session_token_hash=session_hash,
        ).delete()
        if deleted_count == 0:
            ActiveSession.objects.filter(user=user).delete()
    else:
        ActiveSession.objects.filter(user=user).delete()

    clear_pending_login_state(request.session)
    log_auth_activity(action="logout", user=user)
    return True


def get_pending_login_state(session: SessionBase) -> PendingLoginState | None:
    raw_user_id = session.get(PENDING_LOGIN_USER_ID_SESSION_KEY)
    raw_token_id = session.get(PENDING_LOGIN_TOKEN_ID_SESSION_KEY)

    try:
        user_id = int(raw_user_id)
        token_id = int(raw_token_id)
    except (TypeError, ValueError):
        return None

    if user_id <= 0 or token_id <= 0:
        return None
    return PendingLoginState(user_id=user_id, token_id=token_id)


def set_pending_login_state(session: SessionBase, *, user_id: int, token_id: int) -> None:
    session[PENDING_LOGIN_USER_ID_SESSION_KEY] = user_id
    session[PENDING_LOGIN_TOKEN_ID_SESSION_KEY] = token_id
    session.modified = True


def clear_pending_login_state(session: SessionBase) -> None:
    had_pending_state = False
    if PENDING_LOGIN_USER_ID_SESSION_KEY in session:
        had_pending_state = True
        session.pop(PENDING_LOGIN_USER_ID_SESSION_KEY, None)
    if PENDING_LOGIN_TOKEN_ID_SESSION_KEY in session:
        had_pending_state = True
        session.pop(PENDING_LOGIN_TOKEN_ID_SESSION_KEY, None)
    if had_pending_state:
        session.modified = True


def generate_login_2fa_token_value() -> str:
    return f"{secrets.randbelow(10**LOGIN_2FA_TOKEN_LENGTH):0{LOGIN_2FA_TOKEN_LENGTH}d}"


def hash_login_2fa_token(token: str) -> str:
    return _keyed_secret_hash(token, salt=LOGIN_2FA_TOKEN_HASH_SALT)


def verify_login_2fa_token(*, token: str, token_hash: str) -> bool:
    candidate_hash = hash_login_2fa_token(token)
    return hmac.compare_digest(candidate_hash, token_hash)


def hash_session_token(session_key: str) -> str:
    return _keyed_secret_hash(session_key, salt=SESSION_TOKEN_HASH_SALT)


def _keyed_secret_hash(raw_value: str, *, salt: str) -> str:
    return salted_hmac(salt, raw_value, algorithm="sha256").hexdigest()


def invalidate_session_by_hash(session_token_hash: str) -> bool:
    now = timezone.now()
    for session in Session.objects.filter(expire_date__gte=now).only("session_key").iterator():
        candidate_hash = hash_session_token(session.session_key)
        if hmac.compare_digest(candidate_hash, session_token_hash):
            session.delete()
            return True
    return False

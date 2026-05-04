from __future__ import annotations

import os
from datetime import timedelta
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django

django.setup()

from django.contrib.sessions.models import Session
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from homefinder.apps.interactions.models import EmailNotification, EmailNotificationPurpose
from homefinder.apps.users.models import ActiveSession, LoginTwoFactorToken, User
from homefinder.apps.users.services import (
    PENDING_LOGIN_TOKEN_ID_SESSION_KEY,
    PENDING_LOGIN_USER_ID_SESSION_KEY,
    hash_login_2fa_token,
    hash_session_token,
)


@override_settings(ALLOWED_HOSTS=["testserver"])
class AuthFlowTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.password = "StrongPassword123!"

    def test_registration_creates_user_and_allows_login_start(self) -> None:
        register_response = self.client.post(
            "/auth/register/",
            {
                "email": "new-user@example.com",
                "password": self.password,
                "full_name": "New User",
            },
        )

        self.assertEqual(register_response.status_code, 201)
        user = User.objects.get(email="new-user@example.com")

        login_response = self._start_login(client=self.client, user=user, token="654321")
        self.assertEqual(login_response.status_code, 200)
        self.assertTrue(login_response.json()["data"]["pending_2fa"])

        token_record = LoginTwoFactorToken.objects.get(user=user)
        self.assertEqual(token_record.token_hash, hash_login_2fa_token("654321"))
        self.assertEqual(
            EmailNotification.objects.filter(user=user, purpose=EmailNotificationPurpose.LOGIN_2FA).count(),
            1,
        )

        session = self.client.session
        self.assertIsNone(session.get("_auth_user_id"))
        self.assertEqual(session.get(PENDING_LOGIN_USER_ID_SESSION_KEY), user.pk)
        self.assertEqual(session.get(PENDING_LOGIN_TOKEN_ID_SESSION_KEY), token_record.pk)

    def test_login_requires_2fa_before_final_session_creation(self) -> None:
        user = self._create_user()

        response = self._start_login(client=self.client, user=user, token="123456")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ActiveSession.objects.filter(user=user).exists())
        self.assertEqual(LoginTwoFactorToken.objects.filter(user=user).count(), 1)
        self.assertIsNone(self.client.session.get("_auth_user_id"))

    def test_invalid_2fa_submission_fails_and_increments_attempt_counter(self) -> None:
        user = self._create_user()
        self._start_login(client=self.client, user=user, token="123456")

        token_record = LoginTwoFactorToken.objects.get(user=user)
        response = self.client.post("/auth/2fa/verify/", {"token": "000000"})

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["error"]["message"], "Invalid 2FA token.")
        self.assertEqual(payload["error"]["details"]["attempts_remaining"], 4)

        token_record.refresh_from_db()
        self.assertEqual(token_record.attempts_used, 1)
        self.assertIsNone(token_record.verified_at)
        self.assertIsNone(self.client.session.get("_auth_user_id"))
        self.assertEqual(self.client.session.get(PENDING_LOGIN_USER_ID_SESSION_KEY), user.pk)
        self.assertEqual(self.client.session.get(PENDING_LOGIN_TOKEN_ID_SESSION_KEY), token_record.pk)

    def test_invalid_credentials_do_not_create_pending_login_state(self) -> None:
        user = self._create_user()

        response = self.client.post(
            "/auth/login/",
            {
                "email": user.email,
                "password": "WrongPassword123!",
            },
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["message"], "Invalid email or password.")
        self.assertFalse(LoginTwoFactorToken.objects.filter(user=user).exists())
        self.assertIsNone(self.client.session.get(PENDING_LOGIN_USER_ID_SESSION_KEY))
        self.assertIsNone(self.client.session.get(PENDING_LOGIN_TOKEN_ID_SESSION_KEY))

    def test_duplicate_registration_is_rejected(self) -> None:
        existing_user = self._create_user()

        response = self.client.post(
            "/auth/register/",
            {
                "email": existing_user.email,
                "password": self.password,
            },
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["error"]["message"], "Validation failed.")
        self.assertIn("email", payload["error"]["details"])
        self.assertEqual(User.objects.filter(email=existing_user.email).count(), 1)

    def test_registration_rejects_weak_password(self) -> None:
        response = self.client.post(
            "/auth/register/",
            {
                "email": "weak-password@example.com",
                "password": "short",
            },
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["error"]["message"], "Validation failed.")
        self.assertIn("password", payload["error"]["details"])
        self.assertFalse(User.objects.filter(email="weak-password@example.com").exists())

    def test_verify_2fa_requires_pending_login(self) -> None:
        response = self.client.post("/auth/2fa/verify/", {"token": "123456"})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["message"], "Pending login not found. Start the login flow again.")

    def test_expired_2fa_token_fails_and_clears_pending_state(self) -> None:
        user = self._create_user()
        self._start_login(client=self.client, user=user, token="123456")
        token_record = LoginTwoFactorToken.objects.get(user=user)
        token_record.expires_at = timezone.now() - timedelta(seconds=1)
        token_record.save(update_fields=["expires_at"])

        response = self.client.post("/auth/2fa/verify/", {"token": "123456"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["message"], "This 2FA token has expired. Start the login flow again.")
        self.assertIsNone(self.client.session.get(PENDING_LOGIN_USER_ID_SESSION_KEY))
        self.assertIsNone(self.client.session.get(PENDING_LOGIN_TOKEN_ID_SESSION_KEY))
        self.assertFalse(ActiveSession.objects.filter(user=user).exists())

    def test_already_used_2fa_token_is_rejected(self) -> None:
        user = self._create_user()
        self._complete_login(client=self.client, user=user, token="123456")
        used_token = LoginTwoFactorToken.objects.get(user=user, token_hash=hash_login_2fa_token("123456"))

        another_client = Client()
        self._set_pending_login_state(client=another_client, user_id=user.pk, token_id=used_token.pk)
        response = another_client.post("/auth/2fa/verify/", {"token": "123456"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["message"], "This 2FA token has already been used.")
        self.assertIsNone(another_client.session.get(PENDING_LOGIN_USER_ID_SESSION_KEY))
        self.assertIsNone(another_client.session.get(PENDING_LOGIN_TOKEN_ID_SESSION_KEY))

    def test_inactive_user_cannot_complete_2fa_login(self) -> None:
        user = self._create_user()
        self._start_login(client=self.client, user=user, token="123456")
        user.is_active = False
        user.save(update_fields=["is_active"])

        response = self.client.post("/auth/2fa/verify/", {"token": "123456"})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["message"], "This account is inactive.")
        self.assertFalse(ActiveSession.objects.filter(user=user).exists())
        self.assertIsNone(self.client.session.get(PENDING_LOGIN_USER_ID_SESSION_KEY))
        self.assertIsNone(self.client.session.get(PENDING_LOGIN_TOKEN_ID_SESSION_KEY))

    def test_fifth_invalid_2fa_attempt_returns_max_attempts_error(self) -> None:
        user = self._create_user()
        self._start_login(client=self.client, user=user, token="123456")
        token_record = LoginTwoFactorToken.objects.get(user=user)

        for _attempt in range(4):
            response = self.client.post("/auth/2fa/verify/", {"token": "000000"})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()["error"]["message"], "Invalid 2FA token.")

        fifth_response = self.client.post("/auth/2fa/verify/", {"token": "000000"})
        self.assertEqual(fifth_response.status_code, 400)
        self.assertEqual(
            fifth_response.json()["error"]["message"],
            "Too many invalid 2FA attempts. Start the login flow again.",
        )

        token_record.refresh_from_db()
        self.assertEqual(token_record.attempts_used, 5)
        self.assertIsNone(self.client.session.get(PENDING_LOGIN_USER_ID_SESSION_KEY))
        self.assertIsNone(self.client.session.get(PENDING_LOGIN_TOKEN_ID_SESSION_KEY))

        sixth_response = self.client.post("/auth/2fa/verify/", {"token": "123456"})
        self.assertEqual(sixth_response.status_code, 401)
        self.assertEqual(sixth_response.json()["error"]["message"], "Pending login not found. Start the login flow again.")

    def test_valid_2fa_submission_completes_login_and_creates_active_session(self) -> None:
        user = self._create_user()
        self._start_login(client=self.client, user=user, token="123456")
        token_record = LoginTwoFactorToken.objects.get(user=user)

        response = self.client.post("/auth/2fa/verify/", {"token": "123456"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["user"]["id"], user.pk)

        token_record.refresh_from_db()
        self.assertIsNotNone(token_record.verified_at)

        session = self.client.session
        self.assertEqual(int(session.get("_auth_user_id")), user.pk)
        self.assertIsNone(session.get(PENDING_LOGIN_USER_ID_SESSION_KEY))
        self.assertIsNone(session.get(PENDING_LOGIN_TOKEN_ID_SESSION_KEY))

        active_session = ActiveSession.objects.get(user=user)
        self.assertEqual(active_session.session_token_hash, hash_session_token(session.session_key))

    def test_logout_clears_authenticated_session_and_active_session_record(self) -> None:
        user = self._create_user()
        self._complete_login(client=self.client, user=user, token="123456")
        self.assertTrue(ActiveSession.objects.filter(user=user).exists())

        logout_response = self.client.post("/auth/logout/")

        self.assertEqual(logout_response.status_code, 200)
        self.assertFalse(ActiveSession.objects.filter(user=user).exists())
        self.assertIsNone(self.client.session.get("_auth_user_id"))

        second_logout_response = self.client.post("/auth/logout/")
        self.assertEqual(second_logout_response.status_code, 401)

    def test_repeated_login_replaces_previous_active_session(self) -> None:
        user = self._create_user()
        first_client = Client()
        second_client = Client()

        self._complete_login(client=first_client, user=user, token="111111")
        old_session_key = first_client.session.session_key
        old_session_hash = hash_session_token(old_session_key)
        self.assertEqual(ActiveSession.objects.get(user=user).session_token_hash, old_session_hash)
        self.assertTrue(Session.objects.filter(session_key=old_session_key).exists())

        self._complete_login(client=second_client, user=user, token="222222")
        new_active_session_hash = ActiveSession.objects.get(user=user).session_token_hash

        self.assertNotEqual(new_active_session_hash, old_session_hash)
        self.assertFalse(Session.objects.filter(session_key=old_session_key).exists())

        old_session_logout_response = first_client.post("/auth/logout/")
        self.assertEqual(old_session_logout_response.status_code, 401)

    def test_parallel_pending_logins_still_enforce_single_active_session(self) -> None:
        user = self._create_user()
        first_client = Client()
        second_client = Client()

        first_login_response = self._start_login(client=first_client, user=user, token="111111")
        second_login_response = self._start_login(client=second_client, user=user, token="222222")
        self.assertEqual(first_login_response.status_code, 200)
        self.assertEqual(second_login_response.status_code, 200)
        self.assertEqual(LoginTwoFactorToken.objects.filter(user=user).count(), 2)

        first_verify_response = first_client.post("/auth/2fa/verify/", {"token": "111111"})
        self.assertEqual(first_verify_response.status_code, 200)
        first_session_key = first_client.session.session_key
        self.assertTrue(Session.objects.filter(session_key=first_session_key).exists())

        second_verify_response = second_client.post("/auth/2fa/verify/", {"token": "222222"})
        self.assertEqual(second_verify_response.status_code, 200)

        latest_hash = ActiveSession.objects.get(user=user).session_token_hash
        self.assertEqual(latest_hash, hash_session_token(second_client.session.session_key))
        self.assertFalse(Session.objects.filter(session_key=first_session_key).exists())
        self.assertEqual(first_client.post("/auth/logout/").status_code, 401)

    def _create_user(self) -> User:
        return User.objects.create_user(email="existing-user@example.com", password=self.password)

    def _start_login(self, *, client: Client, user: User, token: str) -> object:
        with patch("homefinder.apps.users.services.generate_login_2fa_token_value", return_value=token):
            return client.post(
                "/auth/login/",
                {
                    "email": user.email,
                    "password": self.password,
                },
            )

    def _complete_login(self, *, client: Client, user: User, token: str) -> None:
        login_response = self._start_login(client=client, user=user, token=token)
        self.assertEqual(login_response.status_code, 200)
        verify_response = client.post("/auth/2fa/verify/", {"token": token})
        self.assertEqual(verify_response.status_code, 200)

    def _set_pending_login_state(self, *, client: Client, user_id: int, token_id: int) -> None:
        session = client.session
        session[PENDING_LOGIN_USER_ID_SESSION_KEY] = user_id
        session[PENDING_LOGIN_TOKEN_ID_SESSION_KEY] = token_id
        session.save()

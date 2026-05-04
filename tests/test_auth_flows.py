from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django

django.setup()

from django.contrib.sessions.models import Session
from django.test import Client, TestCase, override_settings

from homefinder.apps.interactions.models import EmailNotification, EmailNotificationPurpose
from homefinder.apps.users.models import ActiveSession, LoginTwoFactorToken, User
from homefinder.apps.users.services import (
    PENDING_LOGIN_TOKEN_ID_SESSION_KEY,
    PENDING_LOGIN_USER_ID_SESSION_KEY,
    hash_secret_value,
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
        self.assertEqual(token_record.token_hash, hash_secret_value("654321"))
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
        self.assertEqual(active_session.session_token_hash, hash_secret_value(session.session_key))

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
        old_session_hash = hash_secret_value(old_session_key)
        self.assertEqual(ActiveSession.objects.get(user=user).session_token_hash, old_session_hash)
        self.assertTrue(Session.objects.filter(session_key=old_session_key).exists())

        self._complete_login(client=second_client, user=user, token="222222")
        new_active_session_hash = ActiveSession.objects.get(user=user).session_token_hash

        self.assertNotEqual(new_active_session_hash, old_session_hash)
        self.assertFalse(Session.objects.filter(session_key=old_session_key).exists())

        old_session_logout_response = first_client.post("/auth/logout/")
        self.assertEqual(old_session_logout_response.status_code, 401)

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

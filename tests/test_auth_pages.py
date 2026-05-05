from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django

django.setup()

from django.test import Client, TestCase, override_settings

from homefinder.apps.users.models import ActiveSession, LoginTwoFactorToken, User
from homefinder.apps.users.services import (
    PENDING_LOGIN_TOKEN_ID_SESSION_KEY,
    PENDING_LOGIN_USER_ID_SESSION_KEY,
)

HTML_ACCEPT = "text/html,application/xhtml+xml"


@override_settings(ALLOWED_HOSTS=["testserver"])
class AuthPageTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.password = "StrongPassword123!"

    def test_registration_page_loads_in_shared_layout(self) -> None:
        response = self.client.get("/auth/register/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "auth/register.html")
        self.assertContains(response, "Create Account")
        self.assertContains(response, "Registration")
        self.assertContains(response, "data-disable-on-submit")

    def test_login_page_loads_in_shared_layout(self) -> None:
        response = self.client.get("/auth/login/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "auth/login.html")
        self.assertContains(response, "Sign In")
        self.assertContains(response, "Login")
        self.assertContains(response, "data-disable-on-submit")

    def test_2fa_page_loads_after_password_step(self) -> None:
        user = self._create_user()
        self._start_html_login(user=user, token="123456")

        response = self.client.get("/auth/2fa/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "auth/2fa.html")
        self.assertContains(response, "2FA Verification")
        self.assertContains(response, user.email)
        self.assertContains(response, "Verify and sign in")

    def test_invalid_registration_input_shows_field_errors_and_preserves_email(self) -> None:
        response = self.client.post(
            "/auth/register/",
            {"email": "bad-email", "password": "short", "full_name": "New Buyer"},
            HTTP_ACCEPT=HTML_ACCEPT,
        )

        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, "auth/register.html")
        self.assertContains(response, "Enter a valid email address.", status_code=400)
        self.assertContains(response, 'value="bad-email"', status_code=400)
        self.assertContains(response, "Check the highlighted fields and try again.", status_code=400)
        self.assertFalse(User.objects.filter(email="bad-email").exists())

    def test_invalid_login_credentials_show_form_error_without_pending_state(self) -> None:
        user = self._create_user()

        response = self.client.post(
            "/auth/login/",
            {"email": user.email, "password": "WrongPassword123!"},
            HTTP_ACCEPT=HTML_ACCEPT,
        )

        self.assertEqual(response.status_code, 401)
        self.assertTemplateUsed(response, "auth/login.html")
        self.assertContains(response, "Invalid email or password.", status_code=401)
        self.assertContains(response, f'value="{user.email}"', status_code=401)
        self.assertFalse(LoginTwoFactorToken.objects.filter(user=user).exists())
        self.assertIsNone(self.client.session.get(PENDING_LOGIN_USER_ID_SESSION_KEY))
        self.assertIsNone(self.client.session.get(PENDING_LOGIN_TOKEN_ID_SESSION_KEY))

    def test_invalid_2fa_token_shows_error_and_keeps_pending_state(self) -> None:
        user = self._create_user()
        self._start_html_login(user=user, token="123456")

        response = self.client.post(
            "/auth/2fa/verify/",
            {"token": "000000"},
            HTTP_ACCEPT=HTML_ACCEPT,
        )

        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, "auth/2fa.html")
        self.assertContains(response, "Invalid 2FA token.", status_code=400)
        self.assertContains(response, "4 attempts remaining", status_code=400)
        self.assertIsNone(self.client.session.get("_auth_user_id"))
        self.assertEqual(self.client.session.get(PENDING_LOGIN_USER_ID_SESSION_KEY), user.pk)

    def test_login_redirects_to_2fa_without_authenticating_user(self) -> None:
        user = self._create_user()

        response = self._start_html_login(user=user, token="123456")

        self.assertRedirects(response, "/auth/2fa/", fetch_redirect_response=False)
        self.assertTrue(LoginTwoFactorToken.objects.filter(user=user).exists())
        self.assertIsNone(self.client.session.get("_auth_user_id"))
        self.assertEqual(self.client.session.get(PENDING_LOGIN_USER_ID_SESSION_KEY), user.pk)

    def test_valid_2fa_completes_login_and_redirects_home(self) -> None:
        user = self._create_user()
        self._start_html_login(user=user, token="123456")
        token_record = LoginTwoFactorToken.objects.get(user=user)

        response = self.client.post(
            "/auth/2fa/verify/",
            {"token": "123456"},
            HTTP_ACCEPT=HTML_ACCEPT,
        )

        self.assertRedirects(response, "/", fetch_redirect_response=False)
        token_record.refresh_from_db()
        self.assertIsNotNone(token_record.verified_at)
        self.assertEqual(int(self.client.session.get("_auth_user_id")), user.pk)
        self.assertIsNone(self.client.session.get(PENDING_LOGIN_USER_ID_SESSION_KEY))
        self.assertTrue(ActiveSession.objects.filter(user=user).exists())

    def test_password_step_does_not_unlock_authenticated_navigation(self) -> None:
        user = self._create_user()
        self._start_html_login(user=user, token="123456")

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Guest")
        self.assertContains(response, "Sign in")
        self.assertNotContains(response, "Sign out")
        self.assertIsNone(self.client.session.get("_auth_user_id"))

    def test_logout_post_redirects_and_clears_session(self) -> None:
        user = self._create_user()
        self._complete_html_login(user=user, token="123456")
        self.assertTrue(ActiveSession.objects.filter(user=user).exists())

        response = self.client.post("/auth/logout/", HTTP_ACCEPT=HTML_ACCEPT)

        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertFalse(ActiveSession.objects.filter(user=user).exists())
        self.assertIsNone(self.client.session.get("_auth_user_id"))

    def _create_user(self) -> User:
        return User.objects.create_user(email="auth-page@example.com", password=self.password)

    def _start_html_login(self, *, user: User, token: str) -> object:
        with patch("homefinder.apps.users.services.generate_login_2fa_token_value", return_value=token):
            return self.client.post(
                "/auth/login/",
                {
                    "email": user.email,
                    "password": self.password,
                },
                HTTP_ACCEPT=HTML_ACCEPT,
            )

    def _complete_html_login(self, *, user: User, token: str) -> None:
        login_response = self._start_html_login(user=user, token=token)
        self.assertRedirects(login_response, "/auth/2fa/", fetch_redirect_response=False)
        verify_response = self.client.post(
            "/auth/2fa/verify/",
            {"token": token},
            HTTP_ACCEPT=HTML_ACCEPT,
        )
        self.assertRedirects(verify_response, "/", fetch_redirect_response=False)

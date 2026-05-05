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


@override_settings(ALLOWED_HOSTS=["testserver"])
class AuthPageTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.password = "StrongPassword123!"

    def test_registration_and_login_pages_render_through_shared_shell(self) -> None:
        register_response = self.client.get("/register/")
        self.assertEqual(register_response.status_code, 200)
        self.assertTemplateUsed(register_response, "base.html")
        self.assertTemplateUsed(register_response, "users/register.html")
        self.assertContains(register_response, "Create your HomeFinder account")
        self.assertContains(register_response, 'data-loading-label="Creating account..."')

        login_response = self.client.get("/login/")
        self.assertEqual(login_response.status_code, 200)
        self.assertTemplateUsed(login_response, "base.html")
        self.assertTemplateUsed(login_response, "users/login.html")
        self.assertContains(login_response, "Step 1 of 2")
        self.assertContains(login_response, 'data-loading-label="Checking credentials..."')

    def test_verify_2fa_page_renders_after_valid_login_step(self) -> None:
        user = self._create_user()
        self._start_login(token="123456", user=user)

        response = self.client.get("/login/2fa/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "users/verify_2fa.html")
        self.assertContains(response, "Step 2 of 2")
        self.assertContains(response, 'data-loading-label="Verifying code..."')

    def test_registration_page_shows_field_validation_feedback(self) -> None:
        existing_user = self._create_user()

        response = self.client.post(
            "/register/",
            {
                "email": existing_user.email,
                "password": self.password,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please correct the highlighted fields and try again.")
        self.assertContains(response, "A user with this email already exists.")
        self.assertEqual(User.objects.filter(email=existing_user.email).count(), 1)

    def test_login_page_shows_clear_feedback_for_invalid_credentials(self) -> None:
        user = self._create_user()

        response = self.client.post(
            "/login/",
            {
                "email": user.email,
                "password": "WrongPassword123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid email or password.")
        self.assertFalse(LoginTwoFactorToken.objects.filter(user=user).exists())
        self.assertIsNone(self.client.session.get(PENDING_LOGIN_USER_ID_SESSION_KEY))
        self.assertIsNone(self.client.session.get(PENDING_LOGIN_TOKEN_ID_SESSION_KEY))

    def test_2fa_page_shows_attempts_remaining_for_invalid_token(self) -> None:
        user = self._create_user()
        self._start_login(token="123456", user=user)
        token_record = LoginTwoFactorToken.objects.get(user=user)

        response = self.client.post("/login/2fa/", {"token": "000000"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid 2FA token. 4 attempts remaining.")
        token_record.refresh_from_db()
        self.assertEqual(token_record.attempts_used, 1)
        self.assertIsNone(self.client.session.get("_auth_user_id"))
        self.assertEqual(self.client.session.get(PENDING_LOGIN_USER_ID_SESSION_KEY), user.pk)
        self.assertEqual(self.client.session.get(PENDING_LOGIN_TOKEN_ID_SESSION_KEY), token_record.pk)

    def test_full_page_flow_respects_two_step_login_and_logout(self) -> None:
        registration_response = self.client.post(
            "/register/",
            {
                "email": "new-user@example.com",
                "password": self.password,
                "full_name": "New User",
            },
        )
        self.assertRedirects(registration_response, "/login/?email=new-user%40example.com")

        user = User.objects.get(email="new-user@example.com")

        with patch("homefinder.apps.users.services.generate_login_2fa_token_value", return_value="654321"):
            login_response = self.client.post(
                "/login/",
                {
                    "email": user.email,
                    "password": self.password,
                },
            )
        self.assertRedirects(login_response, "/login/2fa/")
        self.assertIsNone(self.client.session.get("_auth_user_id"))
        self.assertEqual(
            self.client.session.get(PENDING_LOGIN_USER_ID_SESSION_KEY),
            user.pk,
        )

        verify_response = self.client.post("/login/2fa/", {"token": "654321"})
        self.assertRedirects(verify_response, "/")
        self.assertEqual(int(self.client.session.get("_auth_user_id")), user.pk)
        self.assertTrue(ActiveSession.objects.filter(user=user).exists())

        nav_response = self.client.get("/")
        self.assertContains(nav_response, 'action="/logout/"')
        self.assertContains(nav_response, "Sign out")

        logout_response = self.client.post("/logout/")
        self.assertRedirects(logout_response, "/login/")
        self.assertIsNone(self.client.session.get("_auth_user_id"))
        self.assertFalse(ActiveSession.objects.filter(user=user).exists())

    def _create_user(self) -> User:
        return User.objects.create_user(email="existing-user@example.com", password=self.password)

    def _start_login(self, *, token: str, user: User) -> None:
        with patch("homefinder.apps.users.services.generate_login_2fa_token_value", return_value=token):
            response = self.client.post(
                "/login/",
                {
                    "email": user.email,
                    "password": self.password,
                },
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/login/2fa/")

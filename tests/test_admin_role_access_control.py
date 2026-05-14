from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django

django.setup()

from django.http import HttpRequest, HttpResponse
from django.test import Client, TestCase, override_settings
from django.urls import path

from homefinder.apps.users.models import User, UserRole
from homefinder.apps.users.permissions import admin_required


def login_placeholder(_request: HttpRequest) -> HttpResponse:
    return HttpResponse("Login")


@admin_required
def admin_only_placeholder(_request: HttpRequest) -> HttpResponse:
    return HttpResponse("Admin ok")


urlpatterns = [
    path("login/", login_placeholder, name="login-page"),
    path("staff/admin-only-placeholder/", admin_only_placeholder, name="admin-only-placeholder"),
]

handler403 = "homefinder.apps.core.views.permission_denied_view"


@override_settings(ROOT_URLCONF=__name__, ALLOWED_HOSTS=["testserver"])
class AdminRequiredAccessControlTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.regular_user = User.objects.create_user(
            email="regular-admin-gate@example.com",
            password="StrongPassword123!",
            role=UserRole.USER,
        )
        self.supervisor_user = User.objects.create_user(
            email="supervisor-admin-gate@example.com",
            password="StrongPassword123!",
            role=UserRole.SUPERVISOR,
            is_staff=True,
        )
        self.admin_user = User.objects.create_superuser(
            email="admin-admin-gate@example.com",
            password="StrongPassword123!",
        )

    def test_guest_is_redirected_to_login(self) -> None:
        response = self.client.get("/staff/admin-only-placeholder/")

        self.assertRedirects(
            response,
            "/login/?next=%2Fstaff%2Fadmin-only-placeholder%2F",
            fetch_redirect_response=False,
        )

    def test_regular_user_receives_forbidden_response(self) -> None:
        self.client.force_login(self.regular_user)

        response = self.client.get("/staff/admin-only-placeholder/")

        self.assertEqual(response.status_code, 403)
        self.assertJSONEqual(
            response.content,
            {
                "status": "error",
                "error": {
                    "code": 403,
                    "message": "Forbidden",
                },
            },
        )

    def test_supervisor_receives_forbidden_response(self) -> None:
        self.client.force_login(self.supervisor_user)

        response = self.client.get("/staff/admin-only-placeholder/")

        self.assertEqual(response.status_code, 403)
        self.assertJSONEqual(
            response.content,
            {
                "status": "error",
                "error": {
                    "code": 403,
                    "message": "Forbidden",
                },
            },
        )

    def test_admin_is_admitted(self) -> None:
        self.client.force_login(self.admin_user)

        response = self.client.get("/staff/admin-only-placeholder/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"Admin ok")

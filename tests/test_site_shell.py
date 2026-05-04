from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django

django.setup()

from django.conf import settings
from django.test import Client, TestCase, override_settings

from homefinder.apps.users.models import User


@override_settings(ALLOWED_HOSTS=["testserver"])
class SharedSiteShellTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    def test_root_home_uses_base_template_and_guest_navigation(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "partials/_navigation.html")
        self.assertTemplateUsed(response, "partials/_form_layout.html")
        self.assertTemplateUsed(response, "partials/_property_card.html")
        self.assertTemplateUsed(response, "partials/_empty_state.html")
        self.assertContains(response, "Guest")
        self.assertContains(response, "Sign in")
        self.assertNotContains(response, "Sign out")
        self.assertContains(response, "Home")
        self.assertContains(response, "Browse Listings")
        self.assertContains(response, "/static/core/css/shared-shell.css")

    def test_root_home_authenticated_navigation_state(self) -> None:
        user = User.objects.create_user(
            email="signed-in@example.com",
            password="StrongPassword123!",
            full_name="Signed In User",
        )
        self.client.force_login(user)

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Signed In User")
        self.assertContains(response, "Sign out")
        self.assertNotContains(response, "Sign in")

    def test_flash_message_partial_renders_on_home_page(self) -> None:
        response = self.client.get("/?flash=1")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "partials/_flash_messages.html")
        self.assertContains(response, "Shared shell is active.")

    def test_site_catalog_route_is_not_available_in_a03(self) -> None:
        response = self.client.get("/site/catalog/")

        self.assertEqual(response.status_code, 404)

    def test_css_contains_375px_responsive_shell_rules(self) -> None:
        css_file = Path(settings.BASE_DIR) / "src" / "homefinder" / "apps" / "core" / "static" / "core" / "css" / "shared-shell.css"
        css = css_file.read_text(encoding="utf-8")

        self.assertIn("@media (max-width: 375px)", css)
        self.assertIn(".site-nav,", css)
        self.assertIn(".nav-auth {", css)
        self.assertIn(".button {", css)

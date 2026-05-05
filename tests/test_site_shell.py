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

    def test_root_returns_json_index(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "homefinder")

    def test_site_home_uses_base_template_and_guest_navigation(self) -> None:
        response = self.client.get("/site/")

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

    def test_site_home_authenticated_navigation_state(self) -> None:
        user = User.objects.create_user(
            email="signed-in@example.com",
            password="StrongPassword123!",
            full_name="Signed In User",
        )
        self.client.force_login(user)

        response = self.client.get("/site/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Signed In User")
        self.assertContains(response, "Sign out")
        self.assertNotContains(response, "Sign in")

    def test_flash_message_partial_renders_on_site_home(self) -> None:
        response = self.client.get("/site/?flash=1")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "partials/_flash_messages.html")
        self.assertContains(response, "Shared shell is active.")

    def test_contact_form_shows_validation_errors_when_submitted_incomplete(self) -> None:
        response = self.client.get("/site/?intent=BUY")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")

    def test_contact_form_shows_success_message_when_valid(self) -> None:
        response = self.client.get(
            "/site/",
            {"intent": "BUY", "full_name": "Alex Jordan", "email": "alex@example.com"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Preferences noted")

    def test_site_catalog_route_is_not_available_in_a03(self) -> None:
        response = self.client.get("/site/catalog/")

        self.assertEqual(response.status_code, 404)

    def test_css_contains_375px_responsive_shell_rules(self) -> None:
        css_file = Path(settings.BASE_DIR) / "src" / "homefinder" / "apps" / "core" / "static" / "core" / "css" / "shared-shell.css"
        css = css_file.read_text(encoding="utf-8")

        marker = "@media (max-width: 375px)"
        self.assertIn(marker, css)

        block_start = css.index(marker)
        block = css[block_start:]
        next_media = block.find("@media", len(marker))
        if next_media != -1:
            block = block[:next_media]

        self.assertIn(".site-nav,", block)
        self.assertIn(".nav-auth {", block)
        self.assertIn(".button {", block)

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django

django.setup()

from django.conf import settings
from django.test import Client, TestCase, override_settings

from homefinder.apps.properties.models import Property, PropertyCategory, PropertyStatus
from homefinder.apps.users.models import User


@override_settings(ALLOWED_HOSTS=["testserver"])
class SharedSiteShellTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    def _create_visible_property(self, *, title: str = "Athens Skyline Loft") -> Property:
        return Property.objects.create(
            title=title,
            description=f"{title} description",
            category=PropertyCategory.RESIDENTIAL,
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            area="Center",
            address_line="Center street",
            price=Decimal("365000.00"),
            bedrooms=3,
            bathrooms=Decimal("2.0"),
        )

    def test_root_returns_json_index(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "homefinder")

    def test_site_home_uses_base_template_and_guest_navigation(self) -> None:
        self._create_visible_property()
        response = self.client.get("/site/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "partials/_navigation.html")
        self.assertTemplateUsed(response, "partials/_property_card.html")
        self.assertContains(response, "Guest")
        self.assertContains(response, "Sign in")
        self.assertNotContains(response, "Sign out")
        self.assertContains(response, "Home")
        self.assertContains(response, "Browse Listings")
        self.assertContains(response, "Browse Catalog")
        self.assertContains(response, "/site/catalog/")
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

    def test_site_home_renders_featured_property_snapshot(self) -> None:
        featured_property = self._create_visible_property(title="Featured Listing")
        response = self.client.get("/site/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Current Listings")
        self.assertContains(response, "Featured Listing")
        self.assertContains(response, str(featured_property.price))

    def test_site_catalog_route_is_available_after_a05(self) -> None:
        response = self.client.get("/site/catalog/")

        self.assertEqual(response.status_code, 200)

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

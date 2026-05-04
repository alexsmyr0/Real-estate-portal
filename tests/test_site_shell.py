from __future__ import annotations

import os
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django

django.setup()

from django.test import Client, TestCase, override_settings

from homefinder.apps.properties.models import Property, PropertyCategory, PropertyStatus
from homefinder.apps.users.models import User


@override_settings(ALLOWED_HOSTS=["testserver"])
class SharedSiteShellTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.property = Property.objects.create(
            title="Shell Test Listing",
            description="Used by shared shell tests.",
            category=PropertyCategory.RESIDENTIAL,
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            area="Center",
            address_line="12 Demo Street",
            price=Decimal("325000.00"),
            bedrooms=2,
            bathrooms=Decimal("1.5"),
        )

    def test_site_home_uses_base_template_and_guest_navigation(self) -> None:
        response = self.client.get("/site/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "partials/_navigation.html")
        self.assertContains(response, "Guest")
        self.assertContains(response, "Sign In (A-04)")
        self.assertNotContains(response, "Sign out")
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
        self.assertNotContains(response, "Sign In (A-04)")

    def test_flash_message_partial_renders_on_shell_page(self) -> None:
        response = self.client.get("/site/?flash=1")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "partials/_flash_messages.html")
        self.assertContains(response, "Shared shell is active.")

    def test_site_catalog_uses_form_and_property_card_partials(self) -> None:
        response = self.client.get("/site/catalog/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "partials/_form_layout.html")
        self.assertTemplateUsed(response, "partials/_property_card.html")
        self.assertContains(response, "Filter Form Layout")
        self.assertContains(response, "Shell Test Listing")

    def test_site_catalog_uses_empty_state_partial_when_no_visible_properties(self) -> None:
        Property.objects.all().delete()

        response = self.client.get("/site/catalog/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "partials/_empty_state.html")
        self.assertContains(response, "No visible listings yet")

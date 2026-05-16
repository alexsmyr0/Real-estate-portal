from __future__ import annotations

import os
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django

django.setup()

from django.test import Client, TestCase, override_settings

from homefinder.apps.interactions.models import UserFavorite
from homefinder.apps.properties.models import Property, PropertyCategory, PropertyStatus
from homefinder.apps.users.models import User


@override_settings(ALLOWED_HOSTS=["testserver"])
class FavoritesFlowTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.user = User.objects.create_user(
            email="favorites-user@example.com",
            password="StrongPassword123!",
            full_name="Favorites User",
        )
        self.other_user = User.objects.create_user(
            email="other-favorites-user@example.com",
            password="StrongPassword123!",
        )

        self.available_property = self._create_property(
            title="Favorite Ready Listing",
            status=PropertyStatus.AVAILABLE,
            city="Athens",
        )
        self.unavailable_property = self._create_property(
            title="Unavailable Favorite Listing",
            status=PropertyStatus.UNAVAILABLE,
            city="Patra",
        )
        self.removed_property = self._create_property(
            title="Removed Hidden Listing",
            status=PropertyStatus.REMOVED,
            city="Larisa",
        )

    def _create_property(self, *, title: str, status: str, city: str) -> Property:
        return Property.objects.create(
            title=title,
            description=f"{title} description",
            category=PropertyCategory.RESIDENTIAL,
            status=status,
            city=city,
            area="Center",
            address_line=f"{city} address",
            price=Decimal("255000.00"),
            bedrooms=2,
            bathrooms=Decimal("1.5"),
        )

    def test_guest_requests_are_blocked_for_favorite_actions_and_favorites_page(self) -> None:
        add_response = self.client.post(
            f"/catalog/{self.available_property.id}/favorite/",
            {"next": "/catalog/", "surface": "catalog"},
            follow=True,
        )

        self.assertRedirects(add_response, "/login/?next=%2Fcatalog%2F")
        self.assertContains(add_response, "Sign in to save listings.")
        self.assertEqual(UserFavorite.objects.count(), 0)

        remove_response = self.client.post(
            f"/catalog/{self.available_property.id}/unfavorite/",
            {"next": "/catalog/", "surface": "catalog"},
            follow=True,
        )

        self.assertRedirects(remove_response, "/login/?next=%2Fcatalog%2F")
        self.assertContains(remove_response, "Sign in to manage favorites.")

        favorites_page_response = self.client.get("/saved-listings/", follow=True)
        self.assertRedirects(favorites_page_response, "/login/?next=%2Fsaved-listings%2F")
        self.assertContains(favorites_page_response, "Sign in to view your saved listings.")

    def test_authenticated_user_can_add_and_remove_favorites_from_catalog_detail_and_favorites_views(self) -> None:
        self.client.force_login(self.user)

        add_response = self.client.post(
            f"/catalog/{self.available_property.id}/favorite/",
            {"next": "/catalog/?location=Athens", "surface": "catalog"},
        )
        self.assertRedirects(add_response, "/catalog/?location=Athens")
        self.assertTrue(
            UserFavorite.objects.filter(user=self.user, property=self.available_property).exists(),
        )

        detail_add_response = self.client.post(
            f"/catalog/{self.unavailable_property.id}/favorite/",
            {"next": f"/catalog/{self.unavailable_property.id}/", "surface": "detail"},
        )
        self.assertRedirects(detail_add_response, f"/catalog/{self.unavailable_property.id}/")
        self.assertTrue(
            UserFavorite.objects.filter(user=self.user, property=self.unavailable_property).exists(),
        )

        catalog_response = self.client.get("/catalog/")
        property_payload = next(
            property_row
            for property_row in catalog_response.context["properties"]
            if property_row["id"] == self.available_property.id
        )
        self.assertTrue(property_payload["is_favorited"])

        detail_response = self.client.get(f"/catalog/{self.available_property.id}/")
        self.assertTrue(detail_response.context["property"]["is_favorited"])

        favorites_response = self.client.get("/saved-listings/")
        self.assertEqual(favorites_response.status_code, 200)
        self.assertTemplateUsed(favorites_response, "properties/favorites.html")
        self.assertContains(favorites_response, "Favorite Ready Listing")
        self.assertContains(favorites_response, "Unavailable Favorite Listing")

        remove_response = self.client.post(
            f"/catalog/{self.available_property.id}/unfavorite/",
            {"next": "/saved-listings/", "surface": "favorites"},
        )
        self.assertRedirects(remove_response, "/saved-listings/")
        self.assertFalse(
            UserFavorite.objects.filter(user=self.user, property=self.available_property).exists(),
        )

    def test_duplicate_favorite_submissions_do_not_create_duplicate_rows(self) -> None:
        self.client.force_login(self.user)

        self.client.post(
            f"/catalog/{self.available_property.id}/favorite/",
            {"next": "/catalog/", "surface": "catalog"},
        )
        second_response = self.client.post(
            f"/catalog/{self.available_property.id}/favorite/",
            {"next": "/catalog/", "surface": "catalog"},
            follow=True,
        )

        self.assertRedirects(second_response, "/catalog/")
        self.assertEqual(
            UserFavorite.objects.filter(user=self.user, property=self.available_property).count(),
            1,
        )
        self.assertContains(second_response, "already in your favorites")

    def test_favorites_page_renders_only_current_users_visible_favorites(self) -> None:
        self.client.force_login(self.user)
        UserFavorite.objects.create(user=self.user, property=self.available_property)
        UserFavorite.objects.create(user=self.user, property=self.removed_property)
        UserFavorite.objects.create(user=self.other_user, property=self.unavailable_property)

        response = self.client.get("/saved-listings/")

        self.assertEqual(response.status_code, 200)
        context_ids = [property_row["id"] for property_row in response.context["properties"]]
        self.assertEqual(context_ids, [self.available_property.id])
        self.assertContains(response, "Favorite Ready Listing")
        self.assertNotContains(response, "Removed Hidden Listing")
        self.assertNotContains(response, "Unavailable Favorite Listing")

    def test_favorite_actions_do_not_fail_when_logging_pipeline_raises(self) -> None:
        self.client.force_login(self.user)

        with patch("homefinder.apps.properties.views.log_interaction_activity", side_effect=RuntimeError("logger down")):
            add_response = self.client.post(
                f"/catalog/{self.available_property.id}/favorite/",
                {"next": "/catalog/", "surface": "catalog"},
            )

        self.assertRedirects(add_response, "/catalog/")
        self.assertTrue(UserFavorite.objects.filter(user=self.user, property=self.available_property).exists())

        with patch("homefinder.apps.properties.views.log_interaction_activity", side_effect=RuntimeError("logger down")):
            remove_response = self.client.post(
                f"/catalog/{self.available_property.id}/unfavorite/",
                {"next": "/catalog/", "surface": "catalog"},
            )

        self.assertRedirects(remove_response, "/catalog/")
        self.assertFalse(UserFavorite.objects.filter(user=self.user, property=self.available_property).exists())

    def test_favorite_post_returns_not_found_for_removed_or_unknown_property(self) -> None:
        self.client.force_login(self.user)

        removed_response = self.client.post(
            f"/catalog/{self.removed_property.id}/favorite/",
            {"next": "/catalog/", "surface": "catalog"},
        )
        missing_response = self.client.post(
            "/catalog/999999/favorite/",
            {"next": "/catalog/", "surface": "catalog"},
        )

        self.assertEqual(removed_response.status_code, 404)
        self.assertEqual(missing_response.status_code, 404)
        self.assertEqual(UserFavorite.objects.count(), 0)

    def test_untrusted_next_redirect_target_falls_back_to_property_detail(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(
            f"/catalog/{self.available_property.id}/favorite/",
            {"next": "http://evil.example/attack", "surface": "catalog"},
        )

        self.assertRedirects(response, f"/catalog/{self.available_property.id}/")
        self.assertTrue(
            UserFavorite.objects.filter(user=self.user, property=self.available_property).exists(),
        )

    def test_guest_templates_show_sign_in_to_save_cta(self) -> None:
        catalog_response = self.client.get("/catalog/")
        detail_response = self.client.get(f"/catalog/{self.available_property.id}/")

        self.assertContains(catalog_response, "Sign in to save")
        self.assertContains(detail_response, "Sign in to save")

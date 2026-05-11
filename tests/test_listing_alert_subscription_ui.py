from __future__ import annotations

import os
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django

django.setup()

from django.test import Client, TestCase, override_settings

from homefinder.apps.interactions.models import (
    BookingRequest,
    EmailNotification,
    Payment,
    PropertyInquiry,
    SimilarListingAlertDispatch,
    ViewingRequest,
)
from homefinder.apps.properties.models import (
    Amenity,
    ListingAlertSubscription,
    Property,
    PropertyCategory,
    PropertyStatus,
)
from homefinder.apps.properties.services import create_listing_alert_subscription
from homefinder.apps.users.models import User


@override_settings(
    ALLOWED_HOSTS=["testserver"],
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class ListingAlertSubscriptionUITests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.user = User.objects.create_user(
            email="alert-user@example.com",
            password="StrongPassword123!",
            full_name="Alert User",
        )
        self.other_user = User.objects.create_user(
            email="other-alert-user@example.com",
            password="StrongPassword123!",
        )
        self.pool = Amenity.objects.create(name="Pool")
        self.gym = Amenity.objects.create(name="Gym")
        self.available_property = self._create_property(
            title="Available Alert Listing",
            status=PropertyStatus.AVAILABLE,
            city="Athens",
        )
        self.unavailable_property = self._create_property(
            title="Unavailable Alert Listing",
            status=PropertyStatus.UNAVAILABLE,
            city="Athens",
        )
        self.unavailable_property.amenities.add(self.pool, self.gym)
        self.removed_property = self._create_property(
            title="Removed Alert Listing",
            status=PropertyStatus.REMOVED,
            city="Athens",
        )

    def test_unavailable_detail_shows_subscribe_action_for_authenticated_user(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(f"/catalog/{self.unavailable_property.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Similar Listing Alerts")
        self.assertContains(response, "Subscribe to alerts")
        self.assertContains(response, f"/catalog/{self.unavailable_property.id}/similar-listing-alert/")
        self.assertFalse(response.context["property"]["alert_subscription"]["is_subscribed"])

    def test_available_and_removed_listings_do_not_expose_alert_subscription_ui(self) -> None:
        self.client.force_login(self.user)

        available_response = self.client.get(f"/catalog/{self.available_property.id}/")
        removed_response = self.client.get(f"/catalog/{self.removed_property.id}/")

        self.assertEqual(available_response.status_code, 200)
        self.assertNotContains(available_response, "Similar Listing Alerts")
        self.assertNotContains(available_response, "Subscribe to alerts")
        self.assertNotContains(available_response, "similar-listing-alert")
        self.assertEqual(removed_response.status_code, 404)

    def test_anonymous_unavailable_detail_shows_sign_in_prompt_without_active_post_action(self) -> None:
        response = self.client.get(f"/catalog/{self.unavailable_property.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Similar Listing Alerts")
        self.assertContains(response, "Sign in to get alerts")
        self.assertNotContains(response, "Subscribe to alerts")
        self.assertNotContains(response, f"<form method=\"post\" action=\"/catalog/{self.unavailable_property.id}/similar-listing-alert/\"")

    def test_anonymous_post_redirects_to_login_and_creates_no_subscription(self) -> None:
        response = self.client.post(
            f"/catalog/{self.unavailable_property.id}/similar-listing-alert/",
            follow=True,
        )

        self.assertRedirects(response, f"/login/?next=%2Fcatalog%2F{self.unavailable_property.id}%2F")
        self.assertContains(response, "Sign in to get similar-listing alerts.")
        self.assertEqual(ListingAlertSubscription.objects.count(), 0)

    def test_authenticated_post_creates_subscription_through_backend_flow(self) -> None:
        self.client.force_login(self.user)

        with patch("homefinder.apps.properties.views.create_listing_alert_subscription", wraps=create_listing_alert_subscription) as creator:
            response = self.client.post(
                f"/catalog/{self.unavailable_property.id}/similar-listing-alert/",
                follow=True,
            )

        self.assertRedirects(response, f"/catalog/{self.unavailable_property.id}/")
        creator.assert_called_once()
        self.assertContains(response, "Alert subscription active")
        self.assertContains(response, "You are subscribed")
        self.assertIsNotNone(response.context["alert_subscription_confirmation"])

        subscription = ListingAlertSubscription.objects.get()
        self.assertEqual(subscription.user, self.user)
        self.assertEqual(subscription.source_property, self.unavailable_property)
        self.assertEqual(subscription.category, PropertyCategory.RESIDENTIAL)
        self.assertEqual(subscription.location_city, "Athens")
        self.assertEqual(subscription.bedrooms_min, 2)
        self.assertTrue(subscription.is_active)
        self.assertEqual(set(subscription.amenities.values_list("id", flat=True)), {self.pool.id, self.gym.id})

    def test_manual_post_for_available_removed_or_unknown_property_is_rejected(self) -> None:
        self.client.force_login(self.user)

        cases = (
            self.available_property.id,
            self.removed_property.id,
            self.removed_property.id + 999,
        )
        for property_id in cases:
            with self.subTest(property_id=property_id):
                response = self.client.post(f"/catalog/{property_id}/similar-listing-alert/")

                self.assertEqual(response.status_code, 404)
                self.assertEqual(ListingAlertSubscription.objects.count(), 0)

    def test_sequential_duplicate_subscription_attempt_reuses_existing_active_subscription(self) -> None:
        self.client.force_login(self.user)

        first_response = self.client.post(
            f"/catalog/{self.unavailable_property.id}/similar-listing-alert/",
            follow=True,
        )
        second_response = self.client.post(
            f"/catalog/{self.unavailable_property.id}/similar-listing-alert/",
            follow=True,
        )

        self.assertContains(first_response, "Alert subscription active")
        self.assertContains(second_response, "already subscribed")
        self.assertEqual(ListingAlertSubscription.objects.count(), 1)
        self.assertEqual(ListingAlertSubscription.objects.get().user, self.user)

    def test_confirmation_is_not_query_parameter_driven_and_refresh_does_not_duplicate(self) -> None:
        self.client.force_login(self.user)

        forged_response = self.client.get(f"/catalog/{self.unavailable_property.id}/?alert=created")
        self.assertEqual(forged_response.status_code, 200)
        self.assertNotContains(forged_response, "Alert subscription active")
        self.assertNotContains(forged_response, "You are subscribed")

        success_response = self.client.post(
            f"/catalog/{self.unavailable_property.id}/similar-listing-alert/",
            follow=True,
        )
        self.assertContains(success_response, "Alert subscription active")

        refresh_response = self.client.get(f"/catalog/{self.unavailable_property.id}/")
        self.assertEqual(refresh_response.status_code, 200)
        self.assertNotContains(refresh_response, "Alert subscription active")
        self.assertContains(refresh_response, "You are subscribed")
        self.assertEqual(ListingAlertSubscription.objects.count(), 1)

    def test_ui_action_does_not_trigger_matching_dispatch_email_or_other_side_effects(self) -> None:
        self.client.force_login(self.user)

        with patch("homefinder.apps.properties.services.dispatch_similar_listing_alerts") as dispatcher:
            response = self.client.post(
                f"/catalog/{self.unavailable_property.id}/similar-listing-alert/",
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        dispatcher.assert_not_called()
        self.assertEqual(EmailNotification.objects.count(), 0)
        self.assertEqual(SimilarListingAlertDispatch.objects.count(), 0)
        self.assertEqual(ViewingRequest.objects.count(), 0)
        self.assertEqual(PropertyInquiry.objects.count(), 0)
        self.assertEqual(BookingRequest.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)
        self.assertContains(response, "Recommended Similar Listings")

    def test_post_uses_request_user_and_ignores_forged_user_identity(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(
            f"/catalog/{self.unavailable_property.id}/similar-listing-alert/",
            {"user": str(self.other_user.id), "user_id": str(self.other_user.id)},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        subscription = ListingAlertSubscription.objects.get()
        self.assertEqual(subscription.user, self.user)
        self.assertNotEqual(subscription.user, self.other_user)

    def test_subscribed_state_is_owned_by_current_user(self) -> None:
        create_listing_alert_subscription(user=self.other_user, source_property=self.unavailable_property)
        self.client.force_login(self.user)

        response = self.client.get(f"/catalog/{self.unavailable_property.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Subscribe to alerts")
        self.assertNotContains(response, "You are subscribed")
        self.assertFalse(response.context["property"]["alert_subscription"]["is_subscribed"])

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

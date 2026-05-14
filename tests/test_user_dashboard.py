from __future__ import annotations

import os
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django

django.setup()

from django.test import Client, TestCase, override_settings
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from homefinder.apps.interactions.models import (
    ActivityLog,
    PropertyInquiry,
    PropertyInquiryStatus,
    SearchHistory,
    UserFavorite,
    ViewingRequest,
    ViewingRequestStatus,
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


@override_settings(ALLOWED_HOSTS=["testserver"])
class UserDashboardTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.user = User.objects.create_user(
            email="dashboard-user@example.com",
            password="StrongPassword123!",
            full_name="Dashboard User",
        )
        self.other_user = User.objects.create_user(
            email="other-dashboard-user@example.com",
            password="StrongPassword123!",
        )
        self.property = self._create_property(title="User Dashboard Listing", city="Athens")
        self.other_property = self._create_property(title="Other User Listing", city="Patra")

    def test_anonymous_user_is_redirected_to_login_with_next_preserved(self) -> None:
        response = self.client.get("/dashboard/")

        self.assertRedirects(response, "/login/?next=%2Fdashboard%2F", fetch_redirect_response=False)

    def test_authenticated_empty_dashboard_renders_coherent_shell_and_empty_states(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get("/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "interactions/dashboard.html")
        self.assertContains(response, "Your HomeFinder activity")
        self.assertContains(response, "You have not searched yet.")
        self.assertContains(response, "You have not saved any properties yet.")
        self.assertContains(response, "You have not submitted inquiries yet.")
        self.assertContains(response, "You have not requested any viewings yet.")
        self.assertContains(response, "You have not subscribed to similar-listing alerts yet.")
        self.assertEqual(response.context["searches"]["total_count"], 0)
        self.assertEqual(response.context["favorites"]["total_count"], 0)
        self.assertEqual(response.context["inquiries"]["total_count"], 0)
        self.assertEqual(response.context["viewings"]["total_count"], 0)
        self.assertEqual(response.context["alerts"]["total_count"], 0)

    def test_populated_dashboard_shows_only_current_users_activity(self) -> None:
        self.client.force_login(self.user)
        SearchHistory.objects.create(
            user=self.user,
            location_city="Athens",
            category=PropertyCategory.RESIDENTIAL,
            min_price=Decimal("200000.00"),
            bedrooms_min=2,
        )
        SearchHistory.objects.create(user=self.other_user, location_city="Patra")
        UserFavorite.objects.create(user=self.user, property=self.property)
        UserFavorite.objects.create(user=self.other_user, property=self.other_property)
        PropertyInquiry.objects.create(
            user=self.user,
            property=self.property,
            message="Could you share building-fee details?",
            status=PropertyInquiryStatus.OPEN,
        )
        PropertyInquiry.objects.create(
            user=self.other_user,
            property=self.other_property,
            message="Other user private inquiry",
            status=PropertyInquiryStatus.OPEN,
        )
        ViewingRequest.objects.create(
            user=self.user,
            property=self.property,
            requested_datetime=timezone.now() + timedelta(days=2),
            status=ViewingRequestStatus.PENDING,
            note="Morning visit preferred",
        )
        ViewingRequest.objects.create(
            user=self.other_user,
            property=self.other_property,
            requested_datetime=timezone.now() + timedelta(days=3),
            status=ViewingRequestStatus.PENDING,
            note="Other user private viewing",
        )

        response = self.client.get("/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Location: Athens")
        self.assertContains(response, "Category: Residential")
        self.assertContains(response, "User Dashboard Listing")
        self.assertContains(response, "Could you share building-fee details?")
        self.assertContains(response, "Morning visit preferred")
        self.assertNotContains(response, "Location: Patra")
        self.assertNotContains(response, "Other user private inquiry")
        self.assertNotContains(response, "Other user private viewing")

        self.assertEqual(response.context["searches"]["items"][0]["criteria"][0], "Location: Athens")
        self.assertEqual(response.context["favorites"]["items"][0].user_id, self.user.id)
        self.assertNotIn(
            self.other_property.id,
            [favorite.property_id for favorite in response.context["favorites"]["items"]],
        )
        self.assertEqual(response.context["inquiries"]["total_count"], 1)
        self.assertEqual(response.context["viewings"]["total_count"], 1)
        self.assertEqual(response.context["inquiries"]["items"][0]["property_title"], "User Dashboard Listing")
        self.assertEqual(response.context["viewings"]["items"][0]["property_title"], "User Dashboard Listing")

    def test_dashboard_orders_limits_and_groups_activity_predictably(self) -> None:
        self.client.force_login(self.user)
        base_time = timezone.now() - timedelta(days=1)

        for index in range(12):
            search = SearchHistory.objects.create(user=self.user, location_city=f"Limit City {index:02d}")
            SearchHistory.objects.filter(pk=search.pk).update(created_at=base_time + timedelta(minutes=index))

        response = self.client.get("/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["searches"]["items"]), 3)
        self.assertEqual(response.context["searches"]["total_count"], 12)
        self.assertEqual(response.context["searches"]["items"][0]["criteria"], ["Location: Limit City 11"])
        self.assertEqual(response.context["searches"]["items"][-1]["criteria"], ["Location: Limit City 09"])
        self.assertContains(response, "View all")
        self.assertContains(response, "Limit City 11")
        self.assertNotContains(response, "Limit City 00")
        self.assertNotContains(response, "Limit City 08")

    def test_dashboard_orders_limits_and_groups_favorites_inquiries_and_viewings(self) -> None:
        self.client.force_login(self.user)
        base_time = timezone.now() - timedelta(days=1)

        for index in range(12):
            property_obj = self._create_property(title=f"Favorite Listing {index:02d}", city="Athens")
            favorite = UserFavorite.objects.create(user=self.user, property=property_obj)
            self._set_created_at(favorite, base_time + timedelta(minutes=index))

            inquiry_property = self._create_property(title=f"Inquiry Listing {index:02d}", city="Athens")
            inquiry = PropertyInquiry.objects.create(
                user=self.user,
                property=inquiry_property,
                message=f"Inquiry message {index:02d}",
            )
            self._set_created_at(inquiry, base_time + timedelta(minutes=index))

            viewing_property = self._create_property(title=f"Viewing Listing {index:02d}", city="Athens")
            viewing = ViewingRequest.objects.create(
                user=self.user,
                property=viewing_property,
                requested_datetime=timezone.now() + timedelta(days=index + 1),
                note=f"Viewing note {index:02d}",
            )
            self._set_created_at(viewing, base_time + timedelta(minutes=index))

        response = self.client.get("/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["favorites"]["items"]), 3)
        self.assertEqual(response.context["favorites"]["total_count"], 12)
        self.assertEqual(response.context["favorites"]["items"][0].property.title, "Favorite Listing 11")
        self.assertEqual(response.context["favorites"]["items"][-1].property.title, "Favorite Listing 09")
        self.assertNotContains(response, "Favorite Listing 00")
        self.assertNotContains(response, "Favorite Listing 08")

        self.assertEqual(len(response.context["inquiries"]["items"]), 3)
        self.assertEqual(response.context["inquiries"]["total_count"], 12)
        self.assertEqual(response.context["inquiries"]["items"][0]["property_title"], "Inquiry Listing 11")
        self.assertEqual(response.context["inquiries"]["items"][-1]["property_title"], "Inquiry Listing 09")
        self.assertNotContains(response, "Inquiry Listing 00")
        self.assertNotContains(response, "Inquiry Listing 08")

        self.assertEqual(len(response.context["viewings"]["items"]), 3)
        self.assertEqual(response.context["viewings"]["total_count"], 12)
        self.assertEqual(response.context["viewings"]["items"][0]["property_title"], "Viewing Listing 11")
        self.assertEqual(response.context["viewings"]["items"][-1]["property_title"], "Viewing Listing 09")
        self.assertNotContains(response, "Viewing Listing 00")
        self.assertNotContains(response, "Viewing Listing 08")

    def test_dashboard_filters_removed_favorites_without_leaking_other_favorites(self) -> None:
        self.client.force_login(self.user)
        removed_property = self._create_property(
            title="Removed Saved Listing",
            city="Larisa",
            status=PropertyStatus.REMOVED,
        )
        UserFavorite.objects.create(user=self.user, property=self.property)
        UserFavorite.objects.create(user=self.user, property=removed_property)
        UserFavorite.objects.create(user=self.other_user, property=self.other_property)

        response = self.client.get("/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "User Dashboard Listing")
        self.assertNotContains(response, "Removed Saved Listing")
        self.assertEqual(
            [favorite.property_id for favorite in response.context["favorites"]["items"]],
            [self.property.id],
        )

    def test_removed_inquiry_and_viewing_properties_render_without_dead_detail_links(self) -> None:
        self.client.force_login(self.user)
        removed_property = self._create_property(
            title="Removed Interaction Listing",
            city="Larisa",
            status=PropertyStatus.REMOVED,
        )
        PropertyInquiry.objects.create(
            user=self.user,
            property=self.property,
            message="Visible inquiry message",
        )
        PropertyInquiry.objects.create(
            user=self.user,
            property=removed_property,
            message="Historical removed-property inquiry",
        )
        ViewingRequest.objects.create(
            user=self.user,
            property=self.property,
            requested_datetime=timezone.now() + timedelta(days=2),
            note="Visible viewing note",
        )
        ViewingRequest.objects.create(
            user=self.user,
            property=removed_property,
            requested_datetime=timezone.now() + timedelta(days=3),
            note="Historical removed-property viewing",
        )

        response = self.client.get("/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="/catalog/{self.property.id}/"')
        self.assertContains(response, "User Dashboard Listing")
        self.assertContains(response, "Listing removed", count=2)
        self.assertContains(response, "This listing is no longer available.", count=2)
        self.assertContains(response, "Historical removed-property inquiry")
        self.assertContains(response, "Historical removed-property viewing")
        self.assertNotContains(response, "Removed Interaction Listing")
        self.assertNotContains(response, f'href="/catalog/{removed_property.id}/"')

    def test_dashboard_shows_only_current_users_active_alert_subscriptions(self) -> None:
        self.client.force_login(self.user)

        unavailable_property = self._create_property(
            title="Unavailable Source Listing",
            city="Athens",
            status=PropertyStatus.UNAVAILABLE,
        )
        other_unavailable_property = self._create_property(
            title="Other User Source Listing",
            city="Patra",
            status=PropertyStatus.UNAVAILABLE,
        )
        pool = Amenity.objects.create(name="Pool")
        unavailable_property.amenities.add(pool)

        own_subscription = create_listing_alert_subscription(
            user=self.user,
            source_property=unavailable_property,
        )
        other_subscription = create_listing_alert_subscription(
            user=self.other_user,
            source_property=other_unavailable_property,
        )
        inactive_subscription = create_listing_alert_subscription(
            user=self.user,
            source_property=unavailable_property,
        )
        inactive_subscription.is_active = False
        inactive_subscription.save(update_fields=["is_active"])

        response = self.client.get("/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["alerts"]["total_count"], 1)
        self.assertEqual(response.context["alerts"]["items"][0]["source_property_title"], "Unavailable Source Listing")
        self.assertIn("Location: Athens", response.context["alerts"]["items"][0]["criteria"])
        self.assertIn("Category: Residential", response.context["alerts"]["items"][0]["criteria"])
        self.assertIn("Amenities: Pool", response.context["alerts"]["items"][0]["criteria"])
        self.assertContains(response, "Unavailable Source Listing")
        self.assertContains(response, f'href="/catalog/{unavailable_property.id}/"')
        self.assertNotContains(response, "Other User Source Listing")
        self.assertNotIn(other_subscription.pk, [item.get("id") for item in response.context["alerts"]["items"]])
        self.assertEqual(
            ListingAlertSubscription.objects.filter(user=self.user).count(),
            2,
        )

    def test_dashboard_alert_subscriptions_orders_limits_and_groups_predictably(self) -> None:
        self.client.force_login(self.user)
        base_time = timezone.now() - timedelta(days=1)

        for index in range(12):
            source_property = self._create_property(
                title=f"Alert Source Listing {index:02d}",
                city="Athens",
                status=PropertyStatus.UNAVAILABLE,
            )
            subscription = create_listing_alert_subscription(
                user=self.user,
                source_property=source_property,
            )
            self._set_created_at(subscription, base_time + timedelta(minutes=index))

        response = self.client.get("/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["alerts"]["items"]), 3)
        self.assertEqual(response.context["alerts"]["total_count"], 12)
        self.assertEqual(response.context["alerts"]["items"][0]["source_property_title"], "Alert Source Listing 11")
        self.assertEqual(response.context["alerts"]["items"][-1]["source_property_title"], "Alert Source Listing 09")
        self.assertNotContains(response, "Alert Source Listing 00")
        self.assertNotContains(response, "Alert Source Listing 08")

    def test_dashboard_alert_subscription_with_removed_source_renders_without_dead_link(self) -> None:
        self.client.force_login(self.user)
        unavailable_property = self._create_property(
            title="Will Be Removed Source",
            city="Athens",
            status=PropertyStatus.UNAVAILABLE,
        )
        subscription = create_listing_alert_subscription(
            user=self.user,
            source_property=unavailable_property,
        )
        unavailable_property.status = PropertyStatus.REMOVED
        unavailable_property.save(update_fields=["status"])

        response = self.client.get("/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Source listing removed")
        self.assertContains(response, "The source listing is no longer available.")
        self.assertNotContains(response, "Will Be Removed Source")
        self.assertNotContains(response, f'href="/catalog/{unavailable_property.id}/"')
        self.assertEqual(response.context["alerts"]["total_count"], 1)
        self.assertEqual(response.context["alerts"]["items"][0]["source_property_detail_url"], "")
        self.assertEqual(
            ListingAlertSubscription.objects.filter(pk=subscription.pk).get().is_active,
            True,
        )

    def test_dashboard_recommendations_do_not_add_reporting_or_logging_side_effects(self) -> None:
        self.client.force_login(self.user)
        SearchHistory.objects.create(user=self.user, location_city="Athens")

        response = self.client.get("/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ActivityLog.objects.count(), 0)
        self.assertNotContains(response, "Supervisor")
        self.assertContains(response, "Recommended For You")
        with self.assertRaises(NoReverseMatch):
            reverse("site-supervisor-dashboard")

    def test_anonymous_dashboard_login_flow_preserves_next_through_2fa(self) -> None:
        dashboard_response = self.client.get("/dashboard/")
        self.assertRedirects(dashboard_response, "/login/?next=%2Fdashboard%2F", fetch_redirect_response=False)

        login_page_response = self.client.get("/login/", {"next": "/dashboard/"})
        self.assertContains(login_page_response, 'name="next" value="/dashboard/"')

        with patch("homefinder.apps.users.services.generate_login_2fa_token_value", return_value="654321"):
            login_response = self.client.post(
                "/login/",
                {
                    "email": self.user.email,
                    "password": "StrongPassword123!",
                    "next": "/dashboard/",
                },
            )

        self.assertRedirects(login_response, "/login/2fa/?next=%2Fdashboard%2F", fetch_redirect_response=False)

        verify_page_response = self.client.get("/login/2fa/")
        self.assertContains(verify_page_response, 'name="next" value="/dashboard/"')

        verify_response = self.client.post("/login/2fa/", {"token": "654321", "next": "/dashboard/"})
        self.assertRedirects(verify_response, "/dashboard/")

    def test_unsafe_login_next_is_ignored_and_normal_login_still_goes_home(self) -> None:
        with patch("homefinder.apps.users.services.generate_login_2fa_token_value", return_value="111111"):
            unsafe_login_response = self.client.post(
                "/login/",
                {
                    "email": self.user.email,
                    "password": "StrongPassword123!",
                    "next": "https://evil.example/dashboard",
                },
            )
        self.assertRedirects(unsafe_login_response, "/login/2fa/", fetch_redirect_response=False)
        unsafe_verify_response = self.client.post("/login/2fa/", {"token": "111111"})
        self.assertRedirects(unsafe_verify_response, "/")

        self.client.post("/logout/")

        with patch("homefinder.apps.users.services.generate_login_2fa_token_value", return_value="222222"):
            normal_login_response = self.client.post(
                "/login/",
                {
                    "email": self.user.email,
                    "password": "StrongPassword123!",
                },
            )
        self.assertRedirects(normal_login_response, "/login/2fa/", fetch_redirect_response=False)
        normal_verify_response = self.client.post("/login/2fa/", {"token": "222222"})
        self.assertRedirects(normal_verify_response, "/")

    def _create_property(
        self,
        *,
        title: str,
        city: str,
        status: str = PropertyStatus.AVAILABLE,
    ) -> Property:
        return Property.objects.create(
            title=title,
            description=f"{title} description",
            category=PropertyCategory.RESIDENTIAL,
            status=status,
            city=city,
            area="Center",
            address_line=f"{city} address",
            price=Decimal("250000.00"),
            bedrooms=2,
            bathrooms=Decimal("1.5"),
        )

    def _set_created_at(self, record: object, created_at) -> None:
        record.__class__.objects.filter(pk=record.pk).update(created_at=created_at)
        record.created_at = created_at

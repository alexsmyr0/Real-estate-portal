from __future__ import annotations

import os
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django

django.setup()

from django.test import Client, TestCase, override_settings

from homefinder.apps.interactions.models import SearchHistory, UserFavorite
from homefinder.apps.properties.models import Property, PropertyCategory, PropertyImage, PropertyStatus
from homefinder.apps.properties.services import build_property_availability_context
from homefinder.apps.users.models import User


@override_settings(ALLOWED_HOSTS=["testserver"])
class RecommendationSurfaceUITests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.user = User.objects.create_user(
            email="recommendation-ui@example.com",
            password="StrongPassword123!",
            full_name="Recommendation UI User",
        )
        self.other_user = User.objects.create_user(
            email="other-recommendation-ui@example.com",
            password="StrongPassword123!",
        )

    def test_landing_catalog_and_dashboard_render_recommendation_cards_with_catalog_card_markup(self) -> None:
        recommended = self._create_property(
            title="Athens Recommended Home",
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            price=Decimal("245000.00"),
        )
        PropertyImage.objects.create(property=recommended, image_url="https://img.example.com/recommended-home.jpg")
        self._create_property(
            title="Removed Recommendation Candidate",
            status=PropertyStatus.REMOVED,
            city="Athens",
            price=Decimal("240000.00"),
        )
        SearchHistory.objects.create(
            user=self.user,
            category=PropertyCategory.RESIDENTIAL,
            location_city="Athens",
            min_price=Decimal("200000.00"),
            max_price=Decimal("260000.00"),
        )
        SearchHistory.objects.create(
            user=self.other_user,
            category=PropertyCategory.RENTAL,
            location_city="Patra",
        )
        self.client.force_login(self.user)

        for path, heading in [
            ("/", "Recommended Listings"),
            ("/catalog/", "Recommended Listings"),
            ("/dashboard/", "Recommended For You"),
        ]:
            with self.subTest(path=path):
                response = self.client.get(path)

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "partials/_recommendation_section.html")
                self.assertTemplateUsed(response, "partials/_property_card.html")
                self.assertContains(response, heading)
                self.assertContains(response, "Athens Recommended Home")
                self.assertContains(response, 'class="property-card"')
                self.assertContains(response, 'class="property-title-link"')
                self.assertContains(response, 'class="status-tag status-available"')
                self.assertContains(response, "https://img.example.com/recommended-home.jpg")
                self.assertContains(response, f'href="/catalog/{recommended.id}/"')
                self.assertNotContains(response, "Removed Recommendation Candidate")
                self.assertIn(recommended.id, [item["id"] for item in response.context["recommended_properties"]])

    def test_anonymous_detail_surface_renders_source_based_similar_picks_without_private_signals(self) -> None:
        source_property = self._create_property(
            title="Source Detail Listing",
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            price=Decimal("300000.00"),
        )
        recommended = self._create_property(
            title="Similar Visible Recommendation",
            status=PropertyStatus.UNAVAILABLE,
            city="Athens",
            price=Decimal("310000.00"),
        )
        removed = self._create_property(
            title="Similar Removed Recommendation",
            status=PropertyStatus.REMOVED,
            city="Athens",
            price=Decimal("305000.00"),
        )
        private_signal = self._create_property(
            title="Private Other User Signal Candidate",
            status=PropertyStatus.AVAILABLE,
            city="Patra",
            price=Decimal("900.00"),
            category=PropertyCategory.RENTAL,
        )
        SearchHistory.objects.create(
            user=self.other_user,
            category=PropertyCategory.RENTAL,
            location_city="Patra",
        )

        response = self.client.get(f"/catalog/{source_property.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "partials/_recommendation_section.html")
        self.assertTemplateUsed(response, "partials/_property_card.html")
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertContains(response, "Similar Picks")
        self.assertContains(response, "Recommended Similar Listings")
        self.assertNotContains(response, "Personalized")
        self.assertContains(response, "Similar Visible Recommendation")
        self.assertContains(response, "Unavailable")
        self.assertContains(response, f'href="/catalog/{recommended.id}/"')
        self.assertNotIn(source_property.id, [item["id"] for item in response.context["recommended_properties"]])
        self.assertNotIn(private_signal.id, [item["id"] for item in response.context["recommended_properties"]])
        self.assertNotContains(response, "Similar Removed Recommendation")
        self.assertNotContains(response, f'href="/catalog/{removed.id}/"')

    def test_authenticated_detail_surface_still_uses_current_user_recommendation_state(self) -> None:
        source_property = self._create_property(
            title="Authenticated Detail Source",
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            price=Decimal("300000.00"),
        )
        favorited = self._create_property(
            title="Already Saved Similar Listing",
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            price=Decimal("305000.00"),
        )
        fresh = self._create_property(
            title="Fresh Similar Listing",
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            price=Decimal("310000.00"),
        )
        UserFavorite.objects.create(user=self.user, property=favorited)
        self.client.force_login(self.user)

        response = self.client.get(f"/catalog/{source_property.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recommended Similar Listings")
        self.assertContains(response, "Fresh Similar Listing")
        self.assertNotIn(source_property.id, [item["id"] for item in response.context["recommended_properties"]])
        self.assertNotIn(favorited.id, [item["id"] for item in response.context["recommended_properties"]])
        self.assertIn(fresh.id, [item["id"] for item in response.context["recommended_properties"]])

    def test_anonymous_landing_and_catalog_recommendation_states_are_empty_and_neutral(self) -> None:
        for path in ["/", "/catalog/"]:
            with self.subTest(path=path):
                response = self.client.get(path)

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "No recommendations available yet")
                self.assertContains(response, "Save or view more properties to improve recommendations.")
                self.assertNotContains(response, "Personalized")
                self.assertEqual(response.context["recommended_properties"], [])

    def test_empty_recommendation_states_render_for_authenticated_users(self) -> None:
        self.client.force_login(self.user)
        dashboard_response = self.client.get("/dashboard/")

        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, "No recommendations available yet")
        self.assertContains(dashboard_response, "Save or view more properties to improve recommendations.")
        self.assertEqual(dashboard_response.context["recommended_properties"], [])

    def test_anonymous_dashboard_remains_login_gated_without_recommendation_data(self) -> None:
        response = self.client.get("/dashboard/")

        self.assertRedirects(response, "/login/?next=%2Fdashboard%2F", fetch_redirect_response=False)
        self.assertIsNone(response.context)

    def test_views_call_k11_recommendation_service_for_each_surface(self) -> None:
        source_property = self._create_property(
            title="Detail Source For Service Calls",
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            price=Decimal("280000.00"),
        )
        card = self._card_payload(title="Patched Recommendation")
        self.client.force_login(self.user)

        with patch("homefinder.apps.core.views.get_personalized_recommendations", return_value=[card]) as landing_service:
            self.client.get("/")
        landing_kwargs = landing_service.call_args.kwargs
        self.assertEqual(landing_kwargs["user"], self.user)
        self.assertEqual(landing_kwargs["request_surface"], "landing")

        with patch("homefinder.apps.properties.views.get_personalized_recommendations", return_value=[card]) as catalog_service:
            self.client.get("/catalog/")
        catalog_kwargs = catalog_service.call_args.kwargs
        self.assertEqual(catalog_kwargs["user"], self.user)
        self.assertEqual(catalog_kwargs["request_surface"], "catalog")

        with patch("homefinder.apps.properties.views.get_personalized_recommendations", return_value=[card]) as detail_service:
            self.client.get(f"/catalog/{source_property.id}/")
        detail_kwargs = detail_service.call_args.kwargs
        self.assertEqual(detail_kwargs["user"], self.user)
        self.assertEqual(detail_kwargs["request_surface"], "detail")
        self.assertEqual(detail_kwargs["source_property"].id, source_property.id)

        with patch("homefinder.apps.interactions.views.get_personalized_recommendations", return_value=[card]) as dashboard_service:
            self.client.get("/dashboard/")
        dashboard_kwargs = dashboard_service.call_args.kwargs
        self.assertEqual(dashboard_kwargs["user"], self.user)
        self.assertEqual(dashboard_kwargs["request_surface"], "dashboard")

    def test_catalog_recommendation_service_failure_falls_back_to_empty_state(self) -> None:
        with patch(
            "homefinder.apps.properties.views.get_personalized_recommendations",
            side_effect=RuntimeError("ranking backend exploded"),
        ), patch("homefinder.apps.properties.views.logger.exception") as logger_exception:
            response = self.client.get("/catalog/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recommended Listings")
        self.assertContains(response, "No recommendations available yet")
        self.assertNotContains(response, "ranking backend exploded")
        logger_exception.assert_called_once()

    def test_already_favorited_and_other_user_recommendation_data_do_not_leak(self) -> None:
        favorited = self._create_property(
            title="Already Saved Recommendation",
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            price=Decimal("245000.00"),
        )
        fresh = self._create_property(
            title="Fresh Private Recommendation",
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            price=Decimal("250000.00"),
        )
        other_only = self._create_property(
            title="Other User Recommendation Signal",
            status=PropertyStatus.AVAILABLE,
            city="Patra",
            price=Decimal("900.00"),
            category=PropertyCategory.RENTAL,
        )
        UserFavorite.objects.create(user=self.user, property=favorited)
        SearchHistory.objects.create(
            user=self.user,
            category=PropertyCategory.RESIDENTIAL,
            location_city="Athens",
        )
        SearchHistory.objects.create(
            user=self.other_user,
            category=PropertyCategory.RENTAL,
            location_city="Patra",
        )
        self.client.force_login(self.user)

        response = self.client.get("/catalog/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fresh Private Recommendation")
        self.assertIn(fresh.id, [item["id"] for item in response.context["recommended_properties"]])
        self.assertNotIn(favorited.id, [item["id"] for item in response.context["recommended_properties"]])
        self.assertNotIn(other_only.id, [item["id"] for item in response.context["recommended_properties"]])

    def _create_property(
        self,
        *,
        title: str,
        status: str,
        city: str,
        price: Decimal,
        category: str = PropertyCategory.RESIDENTIAL,
    ) -> Property:
        return Property.objects.create(
            title=title,
            description=f"{title} description",
            category=category,
            status=status,
            city=city,
            area="Center",
            address_line=f"{city} address",
            price=price,
            bedrooms=2,
            bathrooms=Decimal("1.5"),
        )

    def _card_payload(self, *, title: str) -> dict[str, object]:
        return {
            "id": 999,
            "title": title,
            "category": PropertyCategory.RESIDENTIAL,
            "status": PropertyStatus.AVAILABLE,
            "availability": build_property_availability_context(PropertyStatus.AVAILABLE).as_payload(),
            "city": "Athens",
            "area": "Center",
            "price": "250000.00",
            "bedrooms": 2,
            "bathrooms": "1.5",
            "primary_image_url": "https://img.example.com/patched-recommendation.jpg",
        }

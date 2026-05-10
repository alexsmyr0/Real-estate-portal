from __future__ import annotations

import os
from datetime import timedelta
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django

django.setup()

from django.test import TestCase
from django.utils import timezone

from homefinder.apps.interactions.models import SearchHistory, UserFavorite
from homefinder.apps.properties.models import Amenity, Property, PropertyCategory, PropertyStatus
from homefinder.apps.properties.services import get_personalized_recommendations
from homefinder.apps.users.models import User


class PersonalizedRecommendationsServiceTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="recommendations-user@example.com",
            password="secret-pass",
            full_name="Recommendations User",
        )
        self.pool = Amenity.objects.create(name="Pool")
        self.gym = Amenity.objects.create(name="Gym")
        self.parking = Amenity.objects.create(name="Parking")

    def test_recommendations_require_category_match_and_rank_by_city_price_band_and_amenities(self) -> None:
        seed_favorite = self._property(
            title="Seed Favorite",
            category=PropertyCategory.RESIDENTIAL,
            status=PropertyStatus.REMOVED,
            city="Athens",
            price="220000.00",
        )
        seed_favorite.amenities.add(self.pool, self.gym)
        UserFavorite.objects.create(user=self.user, property=seed_favorite)
        SearchHistory.objects.create(
            user=self.user,
            category=PropertyCategory.RESIDENTIAL,
            location_city="Athens",
            min_price=Decimal("200000.00"),
            max_price=Decimal("250000.00"),
        )

        best_match = self._property(
            title="Best Match",
            category=PropertyCategory.RESIDENTIAL,
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            price="230000.00",
        )
        best_match.amenities.add(self.pool, self.gym)

        city_match_only = self._property(
            title="City Match Only",
            category=PropertyCategory.RESIDENTIAL,
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            price="650000.00",
        )
        city_match_only.amenities.add(self.pool, self.gym)

        price_band_match = self._property(
            title="Price Band Match",
            category=PropertyCategory.RESIDENTIAL,
            status=PropertyStatus.AVAILABLE,
            city="Patra",
            price="230000.00",
        )
        price_band_match.amenities.add(self.pool, self.gym)

        lower_amenity_overlap = self._property(
            title="Lower Amenity Overlap",
            category=PropertyCategory.RESIDENTIAL,
            status=PropertyStatus.AVAILABLE,
            city="Patra",
            price="230000.00",
        )
        lower_amenity_overlap.amenities.add(self.pool)

        excluded_category = self._property(
            title="Commercial Candidate",
            category=PropertyCategory.COMMERCIAL,
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            price="230000.00",
        )
        excluded_category.amenities.add(self.pool, self.gym)

        recommendations = get_personalized_recommendations(
            user=self.user,
            request_surface="catalog",
        )

        recommendation_ids = [candidate["id"] for candidate in recommendations]
        self.assertEqual(
            recommendation_ids[:4],
            [
                best_match.id,
                city_match_only.id,
                price_band_match.id,
                lower_amenity_overlap.id,
            ],
        )
        self.assertNotIn(excluded_category.id, recommendation_ids)

    def test_recent_behavior_signals_break_ties_after_city_price_band_and_amenity_overlap(self) -> None:
        now = timezone.now()
        recent_pool_signal = self._property(
            title="Recent Pool Favorite",
            category=PropertyCategory.RESIDENTIAL,
            status=PropertyStatus.REMOVED,
            city="Athens",
            price="230000.00",
        )
        recent_pool_signal.amenities.add(self.pool)
        recent_favorite = UserFavorite.objects.create(user=self.user, property=recent_pool_signal)
        self._set_created_at(recent_favorite, now - timedelta(minutes=5))

        older_gym_signal = self._property(
            title="Older Gym Favorite",
            category=PropertyCategory.RESIDENTIAL,
            status=PropertyStatus.REMOVED,
            city="Athens",
            price="230000.00",
        )
        older_gym_signal.amenities.add(self.gym)
        older_favorite = UserFavorite.objects.create(user=self.user, property=older_gym_signal)
        self._set_created_at(older_favorite, now - timedelta(days=2))

        pool_candidate = self._property(
            title="Pool Candidate",
            category=PropertyCategory.RESIDENTIAL,
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            price="230000.00",
        )
        pool_candidate.amenities.add(self.pool)

        gym_candidate = self._property(
            title="Gym Candidate",
            category=PropertyCategory.RESIDENTIAL,
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            price="230000.00",
        )
        gym_candidate.amenities.add(self.gym)

        recommendations = get_personalized_recommendations(
            user=self.user,
            request_surface="landing",
        )
        recommendation_ids = [candidate["id"] for candidate in recommendations]

        self.assertEqual(recommendation_ids[:2], [pool_candidate.id, gym_candidate.id])

    def test_recommendations_return_only_visible_candidates_and_cap_at_six(self) -> None:
        source_property = self._property(
            title="Source Residential Listing",
            category=PropertyCategory.RESIDENTIAL,
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            price="260000.00",
        )
        source_property.amenities.add(self.pool, self.gym)

        visible_candidate_ids: list[int] = []
        for index in range(8):
            status = PropertyStatus.UNAVAILABLE if index == 0 else PropertyStatus.AVAILABLE
            candidate = self._property(
                title=f"Visible Candidate {index}",
                category=PropertyCategory.RESIDENTIAL,
                status=status,
                city="Athens",
                price=f"{240000 + (index * 1000)}.00",
            )
            candidate.amenities.add(self.pool)
            visible_candidate_ids.append(candidate.id)

        removed_candidate = self._property(
            title="Removed Candidate",
            category=PropertyCategory.RESIDENTIAL,
            status=PropertyStatus.REMOVED,
            city="Athens",
            price="240000.00",
        )

        recommendations = get_personalized_recommendations(
            user=None,
            request_surface="detail",
            source_property=source_property,
        )
        recommendation_ids = [candidate["id"] for candidate in recommendations]

        self.assertEqual(len(recommendations), 6)
        self.assertNotIn(source_property.id, recommendation_ids)
        self.assertNotIn(removed_candidate.id, recommendation_ids)
        self.assertTrue(set(recommendation_ids).issubset(set(visible_candidate_ids)))

    def test_detail_surface_source_category_is_strictly_enforced(self) -> None:
        commercial_signal = self._property(
            title="Commercial Favorite Signal",
            category=PropertyCategory.COMMERCIAL,
            status=PropertyStatus.REMOVED,
            city="Athens",
            price="510000.00",
        )
        UserFavorite.objects.create(user=self.user, property=commercial_signal)

        source_property = self._property(
            title="Residential Source",
            category=PropertyCategory.RESIDENTIAL,
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            price="300000.00",
        )
        residential_candidate = self._property(
            title="Residential Candidate",
            category=PropertyCategory.RESIDENTIAL,
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            price="320000.00",
        )
        commercial_candidate = self._property(
            title="Commercial Candidate",
            category=PropertyCategory.COMMERCIAL,
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            price="320000.00",
        )

        recommendations = get_personalized_recommendations(
            user=self.user,
            request_surface="detail",
            source_property=source_property,
        )

        recommendation_ids = [candidate["id"] for candidate in recommendations]
        self.assertIn(residential_candidate.id, recommendation_ids)
        self.assertNotIn(commercial_candidate.id, recommendation_ids)
        self.assertTrue(all(candidate["category"] == PropertyCategory.RESIDENTIAL for candidate in recommendations))

    def _property(
        self,
        *,
        title: str,
        category: str,
        status: str,
        city: str,
        price: str,
    ) -> Property:
        return Property.objects.create(
            title=title,
            description=f"{title} description",
            category=category,
            status=status,
            city=city,
            area="Center",
            address_line=f"{city} address line",
            price=Decimal(price),
            bedrooms=2,
            bathrooms=Decimal("1.5"),
            listed_by=self.user,
        )

    def _set_created_at(self, model_obj: object, created_at) -> None:
        model_cls = type(model_obj)
        model_cls.objects.filter(pk=model_obj.pk).update(created_at=created_at)

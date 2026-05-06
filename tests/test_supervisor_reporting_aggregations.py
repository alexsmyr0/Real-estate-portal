from __future__ import annotations

from datetime import date, datetime, timezone as datetime_timezone
from decimal import Decimal

from django.test import TestCase

from homefinder.apps.interactions.models import PropertyInquiry, UserFavorite
from homefinder.apps.properties.models import Property, PropertyCategory, PropertyStatus
from homefinder.apps.properties.services import get_monthly_inquiry_and_saved_property_metrics
from homefinder.apps.users.models import User


class SupervisorReportingAggregationServiceTests(TestCase):
    def setUp(self) -> None:
        self.users = [
            User.objects.create_user(email="reporter-one@example.com"),
            User.objects.create_user(email="reporter-two@example.com"),
            User.objects.create_user(email="reporter-three@example.com"),
        ]
        self.properties = [
            self._create_property(
                title="Seed Listing One",
                city="Athens",
            ),
            self._create_property(
                title="Seed Listing Two",
                city="Thessaloniki",
            ),
            self._create_property(
                title="Seed Listing Three",
                city="Patra",
            ),
        ]
        self._seed_reporting_interactions()

    def _create_property(self, *, title: str, city: str) -> Property:
        return Property.objects.create(
            title=title,
            description=f"{title} description",
            category=PropertyCategory.RESIDENTIAL,
            status=PropertyStatus.AVAILABLE,
            city=city,
            area="Center",
            address_line=f"{city} Main Street 1",
            price=Decimal("250000.00"),
            bedrooms=2,
            bathrooms=Decimal("1.5"),
        )

    def _seed_reporting_interactions(self) -> None:
        inquiry_records = [
            (
                PropertyInquiry.objects.create(
                    user=self.users[0],
                    property=self.properties[0],
                    message="Interested in details.",
                ),
                datetime(2026, 1, 5, 9, 0, tzinfo=datetime_timezone.utc),
            ),
            (
                PropertyInquiry.objects.create(
                    user=self.users[1],
                    property=self.properties[1],
                    message="Can I schedule a call?",
                ),
                datetime(2026, 1, 16, 13, 30, tzinfo=datetime_timezone.utc),
            ),
            (
                PropertyInquiry.objects.create(
                    user=self.users[0],
                    property=self.properties[1],
                    message="Please share floor plans.",
                ),
                datetime(2026, 2, 11, 11, 15, tzinfo=datetime_timezone.utc),
            ),
            (
                PropertyInquiry.objects.create(
                    user=self.users[2],
                    property=self.properties[2],
                    message="Is this still available?",
                ),
                datetime(2026, 4, 4, 17, 45, tzinfo=datetime_timezone.utc),
            ),
        ]
        for inquiry, created_at in inquiry_records:
            PropertyInquiry.objects.filter(pk=inquiry.pk).update(
                created_at=created_at,
                updated_at=created_at,
            )

        favorite_records = [
            (
                UserFavorite.objects.create(user=self.users[0], property=self.properties[0]),
                datetime(2026, 1, 9, 8, 20, tzinfo=datetime_timezone.utc),
            ),
            (
                UserFavorite.objects.create(user=self.users[0], property=self.properties[1]),
                datetime(2026, 2, 3, 10, 0, tzinfo=datetime_timezone.utc),
            ),
            (
                UserFavorite.objects.create(user=self.users[1], property=self.properties[0]),
                datetime(2026, 2, 14, 19, 35, tzinfo=datetime_timezone.utc),
            ),
            (
                UserFavorite.objects.create(user=self.users[2], property=self.properties[0]),
                datetime(2026, 2, 25, 7, 5, tzinfo=datetime_timezone.utc),
            ),
        ]
        for favorite, created_at in favorite_records:
            UserFavorite.objects.filter(pk=favorite.pk).update(created_at=created_at)

    def test_monthly_reporting_aggregations_include_inquiries_and_saved_properties(self) -> None:
        metrics = get_monthly_inquiry_and_saved_property_metrics()

        self.assertEqual(
            metrics,
            [
                {"month": "2026-01", "inquiry_count": 2, "saved_property_count": 1},
                {"month": "2026-02", "inquiry_count": 1, "saved_property_count": 3},
                {"month": "2026-04", "inquiry_count": 1, "saved_property_count": 0},
            ],
        )

    def test_monthly_reporting_aggregation_accepts_period_filters_without_logic_changes(self) -> None:
        metrics = get_monthly_inquiry_and_saved_property_metrics(
            period_start=date(2026, 1, 1),
            period_end=date(2026, 4, 30),
        )

        self.assertEqual(
            metrics,
            [
                {"month": "2026-01", "inquiry_count": 2, "saved_property_count": 1},
                {"month": "2026-02", "inquiry_count": 1, "saved_property_count": 3},
                {"month": "2026-03", "inquiry_count": 0, "saved_property_count": 0},
                {"month": "2026-04", "inquiry_count": 1, "saved_property_count": 0},
            ],
        )

from __future__ import annotations

from datetime import date, datetime, timezone as datetime_timezone
from decimal import Decimal

from django.test import TestCase

from homefinder.apps.interactions.models import PropertyInquiry, SearchHistory, UserFavorite
from homefinder.apps.properties.models import Property, PropertyCategory, PropertyStatus
from homefinder.apps.properties.services import (
    get_monthly_inquiry_and_saved_property_metrics,
    get_monthly_search_trend_metrics,
)
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
        self._seed_reporting_search_history()

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

    def _seed_reporting_search_history(self) -> None:
        search_records = [
            (
                SearchHistory.objects.create(
                    user=self.users[0],
                    location_city="Athens",
                    category=PropertyCategory.RESIDENTIAL,
                    min_price=Decimal("95000.00"),
                    max_price=Decimal("120000.00"),
                    bedrooms_min=2,
                ),
                datetime(2026, 1, 6, 9, 10, tzinfo=datetime_timezone.utc),
            ),
            (
                SearchHistory.objects.create(
                    user=self.users[1],
                    location_city="ATHENS",
                    category=PropertyCategory.RESIDENTIAL,
                    min_price=Decimal("100000.00"),
                    max_price=Decimal("249999.00"),
                    bedrooms_min=1,
                ),
                datetime(2026, 1, 18, 14, 0, tzinfo=datetime_timezone.utc),
            ),
            (
                SearchHistory.objects.create(
                    user=self.users[1],
                    location_city="Thessaloniki",
                    category=PropertyCategory.COMMERCIAL,
                    min_price=Decimal("250000.00"),
                    max_price=Decimal("499999.00"),
                ),
                datetime(2026, 1, 22, 16, 45, tzinfo=datetime_timezone.utc),
            ),
            (
                SearchHistory.objects.create(
                    user=self.users[2],
                    location_city="Patra",
                    category=PropertyCategory.RESIDENTIAL,
                    max_price=Decimal("90000.00"),
                ),
                datetime(2026, 1, 29, 11, 55, tzinfo=datetime_timezone.utc),
            ),
            (
                SearchHistory.objects.create(
                    user=self.users[0],
                    location_city="Athens",
                    category=PropertyCategory.RENTAL,
                    min_price=Decimal("500000.00"),
                    max_price=Decimal("999999.00"),
                ),
                datetime(2026, 2, 2, 8, 0, tzinfo=datetime_timezone.utc),
            ),
            (
                SearchHistory.objects.create(
                    user=self.users[1],
                    location_city="Volos",
                    category=PropertyCategory.RENTAL,
                    min_price=Decimal("1000000.00"),
                ),
                datetime(2026, 2, 7, 10, 5, tzinfo=datetime_timezone.utc),
            ),
            (
                SearchHistory.objects.create(
                    user=self.users[2],
                    location_city="Heraklion",
                    category=PropertyCategory.COMMERCIAL,
                    min_price=Decimal("200000.00"),
                    max_price=Decimal("400000.00"),
                ),
                datetime(2026, 2, 16, 9, 40, tzinfo=datetime_timezone.utc),
            ),
            (
                SearchHistory.objects.create(
                    user=self.users[0],
                    location_city="",
                    category=PropertyCategory.RESIDENTIAL,
                    min_price=Decimal("-100.00"),
                    max_price=Decimal("150000.00"),
                ),
                datetime(2026, 2, 20, 13, 25, tzinfo=datetime_timezone.utc),
            ),
            (
                SearchHistory.objects.create(
                    user=self.users[2],
                    location_city="Larissa",
                    min_price=Decimal("300000.00"),
                    max_price=Decimal("250000.00"),
                ),
                datetime(2026, 2, 26, 19, 15, tzinfo=datetime_timezone.utc),
            ),
            (
                SearchHistory.objects.create(
                    user=self.users[0],
                    location_city="Athens",
                    category=PropertyCategory.RESIDENTIAL,
                    min_price=Decimal("1000000.00"),
                    max_price=Decimal("1200000.00"),
                ),
                datetime(2026, 4, 8, 7, 50, tzinfo=datetime_timezone.utc),
            ),
        ]
        for search_history, created_at in search_records:
            SearchHistory.objects.filter(pk=search_history.pk).update(created_at=created_at)

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

    def test_monthly_reporting_aggregation_swaps_reversed_period_bounds(self) -> None:
        metrics = get_monthly_inquiry_and_saved_property_metrics(
            period_start=date(2026, 4, 30),
            period_end=date(2026, 1, 1),
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

    def test_monthly_reporting_aggregation_with_only_period_start(self) -> None:
        metrics = get_monthly_inquiry_and_saved_property_metrics(
            period_start=date(2026, 2, 1),
        )

        self.assertEqual(
            metrics,
            [
                {"month": "2026-02", "inquiry_count": 1, "saved_property_count": 3},
                {"month": "2026-04", "inquiry_count": 1, "saved_property_count": 0},
            ],
        )

    def test_monthly_reporting_aggregation_with_only_period_end(self) -> None:
        metrics = get_monthly_inquiry_and_saved_property_metrics(
            period_end=date(2026, 1, 31),
        )

        self.assertEqual(
            metrics,
            [
                {"month": "2026-01", "inquiry_count": 2, "saved_property_count": 1},
            ],
        )

    def test_monthly_reporting_aggregation_accepts_datetime_period_inputs(self) -> None:
        metrics = get_monthly_inquiry_and_saved_property_metrics(
            period_start=datetime(2026, 2, 15, 12, 0, tzinfo=datetime_timezone.utc),
            period_end=datetime(2026, 4, 4, 17, 45, tzinfo=datetime_timezone.utc),
        )

        self.assertEqual(
            metrics,
            [
                {"month": "2026-02", "inquiry_count": 1, "saved_property_count": 3},
                {"month": "2026-03", "inquiry_count": 0, "saved_property_count": 0},
                {"month": "2026-04", "inquiry_count": 1, "saved_property_count": 0},
            ],
        )

    def test_monthly_reporting_aggregation_returns_empty_list_when_no_data(self) -> None:
        PropertyInquiry.objects.all().delete()
        UserFavorite.objects.all().delete()

        metrics = get_monthly_inquiry_and_saved_property_metrics()

        self.assertEqual(metrics, [])

    def test_monthly_search_trend_aggregation_returns_city_category_and_price_band_metrics(self) -> None:
        metrics = get_monthly_search_trend_metrics()

        self.assertEqual(
            metrics,
            [
                {
                    "month": "2026-01",
                    "top_cities": [
                        {"city": "Athens", "search_count": 2},
                        {"city": "Patra", "search_count": 1},
                        {"city": "Thessaloniki", "search_count": 1},
                    ],
                    "top_categories": [
                        {"category": PropertyCategory.RESIDENTIAL, "search_count": 3},
                        {"category": PropertyCategory.COMMERCIAL, "search_count": 1},
                    ],
                    "top_price_bands": [
                        {"price_band": "<100k", "search_count": 2},
                        {"price_band": "100k-249,999", "search_count": 2},
                        {"price_band": "250k-499,999", "search_count": 1},
                    ],
                },
                {
                    "month": "2026-02",
                    "top_cities": [
                        {"city": "Athens", "search_count": 1},
                        {"city": "Heraklion", "search_count": 1},
                        {"city": "Larissa", "search_count": 1},
                        {"city": "Volos", "search_count": 1},
                    ],
                    "top_categories": [
                        {"category": PropertyCategory.RENTAL, "search_count": 2},
                        {"category": PropertyCategory.COMMERCIAL, "search_count": 1},
                        {"category": PropertyCategory.RESIDENTIAL, "search_count": 1},
                    ],
                    "top_price_bands": [
                        {"price_band": "100k-249,999", "search_count": 2},
                        {"price_band": "250k-499,999", "search_count": 2},
                        {"price_band": "<100k", "search_count": 1},
                        {"price_band": "500k-999,999", "search_count": 1},
                        {"price_band": "1,000,000+", "search_count": 1},
                    ],
                },
                {
                    "month": "2026-04",
                    "top_cities": [
                        {"city": "Athens", "search_count": 1},
                    ],
                    "top_categories": [
                        {"category": PropertyCategory.RESIDENTIAL, "search_count": 1},
                    ],
                    "top_price_bands": [
                        {"price_band": "1,000,000+", "search_count": 1},
                    ],
                },
            ],
        )

    def test_monthly_search_trend_aggregation_accepts_period_filters_and_fills_missing_months(self) -> None:
        metrics = get_monthly_search_trend_metrics(
            period_start=date(2026, 1, 1),
            period_end=date(2026, 4, 30),
        )

        self.assertEqual(
            [record["month"] for record in metrics],
            ["2026-01", "2026-02", "2026-03", "2026-04"],
        )
        self.assertEqual(metrics[2]["top_cities"], [])
        self.assertEqual(metrics[2]["top_categories"], [])
        self.assertEqual(metrics[2]["top_price_bands"], [])

    def test_monthly_search_trend_aggregation_limits_city_trends_to_top_ten(self) -> None:
        for index in range(1, 13):
            search_history = SearchHistory.objects.create(
                location_city=f"City{index:02d}",
                category=PropertyCategory.RESIDENTIAL,
            )
            SearchHistory.objects.filter(pk=search_history.pk).update(
                created_at=datetime(2026, 6, 10, 9, index, tzinfo=datetime_timezone.utc),
            )

        metrics = get_monthly_search_trend_metrics(
            period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 30),
        )

        self.assertEqual(len(metrics), 1)
        june_metrics = metrics[0]
        self.assertEqual(june_metrics["month"], "2026-06")
        self.assertEqual(len(june_metrics["top_cities"]), 10)
        self.assertEqual(
            [entry["city"] for entry in june_metrics["top_cities"]],
            [
                "City01",
                "City02",
                "City03",
                "City04",
                "City05",
                "City06",
                "City07",
                "City08",
                "City09",
                "City10",
            ],
        )
        self.assertLessEqual(len(june_metrics["top_categories"]), 10)
        self.assertLessEqual(len(june_metrics["top_price_bands"]), 10)

    def test_monthly_search_trend_aggregation_returns_empty_list_when_no_search_data(self) -> None:
        SearchHistory.objects.all().delete()

        metrics = get_monthly_search_trend_metrics()

        self.assertEqual(metrics, [])

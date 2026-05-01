from __future__ import annotations

import os
from io import StringIO

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django

django.setup()

from django.core.management import call_command
from django.db.models import Max, Min
from django.test import TestCase

from homefinder.apps.properties.demo_catalog import (
    DEMO_CATALOG_BASELINE_COUNTS,
    DEMO_LISTING_TITLE_PREFIX,
)
from homefinder.apps.properties.models import Amenity, Property, PropertyCategory, PropertyImage, PropertyStatus


class DemoCatalogSeedCommandTests(TestCase):
    def test_seed_demo_catalog_loads_expected_baseline_counts(self) -> None:
        output = StringIO()
        call_command("seed_demo_catalog", stdout=output)

        self.assertIn("Seeded demo catalog dataset.", output.getvalue())
        self.assertEqual(Property.objects.count(), DEMO_CATALOG_BASELINE_COUNTS.properties)
        self.assertEqual(Amenity.objects.count(), DEMO_CATALOG_BASELINE_COUNTS.amenities)
        self.assertEqual(PropertyImage.objects.count(), DEMO_CATALOG_BASELINE_COUNTS.images)

        self.assertEqual(
            Property.objects.filter(category=PropertyCategory.RESIDENTIAL).count(),
            DEMO_CATALOG_BASELINE_COUNTS.category_counts[PropertyCategory.RESIDENTIAL],
        )
        self.assertEqual(
            Property.objects.filter(category=PropertyCategory.COMMERCIAL).count(),
            DEMO_CATALOG_BASELINE_COUNTS.category_counts[PropertyCategory.COMMERCIAL],
        )
        self.assertEqual(
            Property.objects.filter(category=PropertyCategory.RENTAL).count(),
            DEMO_CATALOG_BASELINE_COUNTS.category_counts[PropertyCategory.RENTAL],
        )
        self.assertEqual(
            Property.objects.filter(status=PropertyStatus.AVAILABLE).count(),
            DEMO_CATALOG_BASELINE_COUNTS.status_counts[PropertyStatus.AVAILABLE],
        )
        self.assertEqual(
            Property.objects.filter(status=PropertyStatus.UNAVAILABLE).count(),
            DEMO_CATALOG_BASELINE_COUNTS.status_counts[PropertyStatus.UNAVAILABLE],
        )
        self.assertEqual(
            Property.objects.filter(status=PropertyStatus.REMOVED).count(),
            DEMO_CATALOG_BASELINE_COUNTS.status_counts[PropertyStatus.REMOVED],
        )

        self.assertGreater(Property.objects.filter(images__isnull=False).distinct().count(), 0)
        self.assertGreater(Property.objects.filter(amenities__isnull=False).distinct().count(), 0)

        price_window = Property.objects.aggregate(min_price=Min("price"), max_price=Max("price"))
        self.assertIsNotNone(price_window["min_price"])
        self.assertIsNotNone(price_window["max_price"])
        self.assertLess(price_window["min_price"], 100000)
        self.assertGreaterEqual(price_window["max_price"], 1000000)

    def test_seed_demo_catalog_is_repeatable_without_count_drift(self) -> None:
        call_command("seed_demo_catalog", stdout=StringIO())
        call_command("seed_demo_catalog", stdout=StringIO())

        self.assertEqual(
            Property.objects.filter(title__startswith=DEMO_LISTING_TITLE_PREFIX).count(),
            DEMO_CATALOG_BASELINE_COUNTS.properties,
        )
        self.assertEqual(
            Property.objects.values("title").distinct().count(),
            DEMO_CATALOG_BASELINE_COUNTS.properties,
        )
        self.assertEqual(
            PropertyImage.objects.count(),
            DEMO_CATALOG_BASELINE_COUNTS.images,
        )

    def test_seed_demo_catalog_keeps_non_demo_records(self) -> None:
        Property.objects.create(
            title="User Listing Outside Demo Seed",
            description="This listing should remain untouched.",
            category=PropertyCategory.RESIDENTIAL,
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            area="Center",
            address_line="1 Independent Street",
            price="199999.00",
            bedrooms=2,
            bathrooms="1.0",
        )

        call_command("seed_demo_catalog", stdout=StringIO())

        self.assertTrue(Property.objects.filter(title="User Listing Outside Demo Seed").exists())
        self.assertEqual(
            Property.objects.filter(title__startswith=DEMO_LISTING_TITLE_PREFIX).count(),
            DEMO_CATALOG_BASELINE_COUNTS.properties,
        )

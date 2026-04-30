from __future__ import annotations

import os
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django

django.setup()

from django.test import Client, TestCase, override_settings

from homefinder.apps.properties.models import Amenity, Property, PropertyCategory, PropertyImage, PropertyStatus
from homefinder.apps.properties.services import (
    get_visible_property_detail,
    list_visible_properties,
    visible_properties_queryset,
)


class PublicCatalogServiceTests(TestCase):
    def setUp(self) -> None:
        self.pool = Amenity.objects.create(name="Pool")
        self.gym = Amenity.objects.create(name="Gym")

        self.available_property = self._create_property(
            title="City Loft",
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            area="Center",
            price=Decimal("220000.00"),
        )
        self.available_property.amenities.add(self.pool, self.gym)
        PropertyImage.objects.create(property=self.available_property, image_url="https://img.example.com/loft-1.jpg")
        PropertyImage.objects.create(property=self.available_property, image_url="https://img.example.com/loft-2.jpg")

        self.unavailable_property = self._create_property(
            title="Suburban Office",
            status=PropertyStatus.UNAVAILABLE,
            city="Patra",
            area="North",
            price=Decimal("410000.00"),
        )
        PropertyImage.objects.create(property=self.unavailable_property, image_url="https://img.example.com/office-1.jpg")

        self.removed_property = self._create_property(
            title="Hidden Listing",
            status=PropertyStatus.REMOVED,
            city="Thessaloniki",
            area="South",
            price=Decimal("180000.00"),
        )

    def _create_property(
        self,
        *,
        title: str,
        status: str,
        city: str,
        area: str,
        price: Decimal,
    ) -> Property:
        return Property.objects.create(
            title=title,
            description=f"{title} description",
            category=PropertyCategory.RESIDENTIAL,
            status=status,
            city=city,
            area=area,
            address_line=f"{city} address line",
            price=price,
            bedrooms=2,
            bathrooms=Decimal("1.5"),
        )

    def test_visible_queryset_excludes_removed_properties(self) -> None:
        visible_ids = set(visible_properties_queryset().values_list("id", flat=True))

        self.assertIn(self.available_property.id, visible_ids)
        self.assertIn(self.unavailable_property.id, visible_ids)
        self.assertNotIn(self.removed_property.id, visible_ids)

    def test_list_visible_properties_returns_payload_for_visible_records(self) -> None:
        records = list_visible_properties()
        records_by_id = {record["id"]: record for record in records}

        self.assertIn(self.available_property.id, records_by_id)
        self.assertIn(self.unavailable_property.id, records_by_id)
        self.assertNotIn(self.removed_property.id, records_by_id)
        self.assertEqual(
            records_by_id[self.available_property.id]["primary_image_url"],
            "https://img.example.com/loft-1.jpg",
        )
        self.assertEqual(records_by_id[self.unavailable_property.id]["status"], PropertyStatus.UNAVAILABLE)

    def test_get_visible_property_detail_returns_none_for_removed_listing(self) -> None:
        self.assertIsNone(get_visible_property_detail(self.removed_property.id))

    def test_get_visible_property_detail_returns_enriched_payload(self) -> None:
        payload = get_visible_property_detail(self.available_property.id)

        self.assertIsNotNone(payload)
        if payload is None:
            self.fail("Expected payload for visible property")
        self.assertEqual(payload["id"], self.available_property.id)
        self.assertEqual(
            payload["image_urls"],
            [
                "https://img.example.com/loft-1.jpg",
                "https://img.example.com/loft-2.jpg",
            ],
        )
        self.assertEqual(payload["amenities"], ["Gym", "Pool"])


@override_settings(ALLOWED_HOSTS=["testserver"])
class PublicCatalogViewTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()

        self.visible_property = Property.objects.create(
            title="Harbor Flat",
            description="Waterfront property",
            category=PropertyCategory.RESIDENTIAL,
            status=PropertyStatus.AVAILABLE,
            city="Piraeus",
            area="Marina",
            address_line="Dock street",
            price=Decimal("299000.00"),
            bedrooms=3,
            bathrooms=Decimal("2.0"),
        )
        PropertyImage.objects.create(
            property=self.visible_property,
            image_url="https://img.example.com/harbor-flat.jpg",
        )

        self.removed_property = Property.objects.create(
            title="Removed Listing",
            description="Should never be public",
            category=PropertyCategory.RESIDENTIAL,
            status=PropertyStatus.REMOVED,
            city="Piraeus",
            area="Marina",
            address_line="Removed street",
            price=Decimal("150000.00"),
            bedrooms=1,
            bathrooms=Decimal("1.0"),
        )

    def test_catalog_list_route_returns_public_visible_properties(self) -> None:
        response = self.client.get("/catalog/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["status"], "ok")
        ids = {item["id"] for item in payload["data"]["properties"]}
        self.assertIn(self.visible_property.id, ids)
        self.assertNotIn(self.removed_property.id, ids)

    def test_catalog_detail_route_returns_visible_property(self) -> None:
        response = self.client.get(f"/catalog/{self.visible_property.id}/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data"]["property"]["id"], self.visible_property.id)

    def test_catalog_detail_route_returns_not_found_for_removed_listing(self) -> None:
        response = self.client.get(f"/catalog/{self.removed_property.id}/")

        self.assertEqual(response.status_code, 404)
        self.assertJSONEqual(
            response.content,
            {
                "status": "error",
                "error": {"code": 404, "message": "Not Found"},
            },
        )

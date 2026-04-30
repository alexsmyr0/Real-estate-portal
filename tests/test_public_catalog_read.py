from __future__ import annotations

import os
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django

django.setup()

from django.http import QueryDict
from django.test import Client, TestCase, override_settings

from homefinder.apps.properties.models import Amenity, Property, PropertyCategory, PropertyImage, PropertyStatus
from homefinder.apps.properties.services import (
    CATALOG_PAGE_SIZE,
    CatalogSearchParams,
    get_visible_property_detail,
    list_visible_properties,
    parse_catalog_search_params,
    search_visible_properties,
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


class CatalogSearchServiceTests(TestCase):
    def setUp(self) -> None:
        self.pool = Amenity.objects.create(name="Pool")
        self.gym = Amenity.objects.create(name="Gym")

        self.matching_property = self._create_property(
            title="Matched Listing",
            category=PropertyCategory.RESIDENTIAL,
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            area="Marina Hills",
            price=Decimal("250000.00"),
            bedrooms=3,
        )
        self.matching_property.amenities.add(self.pool, self.gym)

        self.partial_amenity_property = self._create_property(
            title="Partial Amenity Listing",
            category=PropertyCategory.RESIDENTIAL,
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            area="Marina View",
            price=Decimal("245000.00"),
            bedrooms=3,
        )
        self.partial_amenity_property.amenities.add(self.pool)

        self.wrong_price_property = self._create_property(
            title="Wrong Price Listing",
            category=PropertyCategory.RESIDENTIAL,
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            area="Marina Point",
            price=Decimal("450000.00"),
            bedrooms=3,
        )
        self.wrong_price_property.amenities.add(self.pool, self.gym)

        self.removed_matching_property = self._create_property(
            title="Removed Match",
            category=PropertyCategory.RESIDENTIAL,
            status=PropertyStatus.REMOVED,
            city="Athens",
            area="Marina Hills",
            price=Decimal("255000.00"),
            bedrooms=3,
        )
        self.removed_matching_property.amenities.add(self.pool, self.gym)

        self.city_location_property = self._create_property(
            title="City Location Match",
            category=PropertyCategory.COMMERCIAL,
            status=PropertyStatus.AVAILABLE,
            city="Thessaloniki",
            area="Business District",
            price=Decimal("600000.00"),
            bedrooms=2,
        )

    def _create_property(
        self,
        *,
        title: str,
        category: str,
        status: str,
        city: str,
        area: str,
        price: Decimal,
        bedrooms: int,
    ) -> Property:
        return Property.objects.create(
            title=title,
            description=f"{title} description",
            category=category,
            status=status,
            city=city,
            area=area,
            address_line=f"{city} address line",
            price=price,
            bedrooms=bedrooms,
            bathrooms=Decimal("2.0"),
        )

    def test_search_visible_properties_applies_combined_filters(self) -> None:
        params = CatalogSearchParams(
            location="RINA",
            min_price=Decimal("200000"),
            max_price=Decimal("300000"),
            category=PropertyCategory.RESIDENTIAL,
            bedrooms_min=3,
            amenity_names=("Pool", "Gym"),
            page=1,
        )

        payload = search_visible_properties(search_params=params)

        self.assertEqual([record["id"] for record in payload["properties"]], [self.matching_property.id])
        self.assertEqual(payload["pagination"]["per_page"], CATALOG_PAGE_SIZE)
        self.assertEqual(payload["pagination"]["total_items"], 1)

    def test_search_location_filter_matches_city_and_area_with_case_insensitive_substrings(self) -> None:
        city_match_payload = search_visible_properties(
            search_params=CatalogSearchParams(location="sSaLON", page=1),
        )
        area_match_payload = search_visible_properties(
            search_params=CatalogSearchParams(location="RINA", page=1),
        )

        city_match_ids = {record["id"] for record in city_match_payload["properties"]}
        area_match_ids = {record["id"] for record in area_match_payload["properties"]}

        self.assertIn(self.city_location_property.id, city_match_ids)
        self.assertIn(self.matching_property.id, area_match_ids)
        self.assertNotIn(self.removed_matching_property.id, city_match_ids)
        self.assertNotIn(self.removed_matching_property.id, area_match_ids)

    def test_parse_catalog_search_params_tolerates_invalid_values(self) -> None:
        params = parse_catalog_search_params(
            QueryDict(
                "min_price=invalid&max_price=invalid&category=unknown&bedrooms=NaN&page=-1&amenities=&location=   "
            )
        )

        self.assertIsNone(params.min_price)
        self.assertIsNone(params.max_price)
        self.assertIsNone(params.category)
        self.assertIsNone(params.bedrooms_min)
        self.assertEqual(params.page, 1)
        self.assertEqual(params.amenity_ids, ())
        self.assertEqual(params.amenity_names, ())
        self.assertIsNone(params.location)


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
        self.assertEqual(payload["data"]["pagination"]["per_page"], CATALOG_PAGE_SIZE)

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

    def test_catalog_list_route_paginates_results_with_fixed_page_size(self) -> None:
        for index in range(CATALOG_PAGE_SIZE + 3):
            Property.objects.create(
                title=f"Extra Listing {index}",
                description="Extra listing for pagination tests",
                category=PropertyCategory.RESIDENTIAL,
                status=PropertyStatus.AVAILABLE,
                city="Athens",
                area="Center",
                address_line=f"Street {index}",
                price=Decimal("200000.00"),
                bedrooms=2,
                bathrooms=Decimal("1.0"),
            )

        page_one_response = self.client.get("/catalog/?page=1")
        page_two_response = self.client.get("/catalog/?page=2")

        self.assertEqual(page_one_response.status_code, 200)
        self.assertEqual(page_two_response.status_code, 200)

        page_one_payload = page_one_response.json()
        page_two_payload = page_two_response.json()

        expected_total = Property.objects.exclude(status=PropertyStatus.REMOVED).count()

        self.assertEqual(len(page_one_payload["data"]["properties"]), CATALOG_PAGE_SIZE)
        self.assertEqual(page_one_payload["data"]["pagination"]["page"], 1)
        self.assertEqual(page_one_payload["data"]["pagination"]["per_page"], CATALOG_PAGE_SIZE)
        self.assertEqual(page_one_payload["data"]["pagination"]["total_items"], expected_total)
        self.assertEqual(page_one_payload["data"]["pagination"]["total_pages"], 2)
        self.assertTrue(page_one_payload["data"]["pagination"]["has_next"])

        self.assertEqual(page_two_payload["data"]["pagination"]["page"], 2)
        self.assertEqual(len(page_two_payload["data"]["properties"]), expected_total - CATALOG_PAGE_SIZE)
        self.assertFalse(page_two_payload["data"]["pagination"]["has_next"])
        self.assertTrue(page_two_payload["data"]["pagination"]["has_previous"])

    def test_catalog_list_route_ignores_invalid_filter_parameters(self) -> None:
        Property.objects.create(
            title="Second Visible Listing",
            description="Visible listing for invalid filter checks",
            category=PropertyCategory.COMMERCIAL,
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            area="Center",
            address_line="Second street",
            price=Decimal("350000.00"),
            bedrooms=4,
            bathrooms=Decimal("2.5"),
        )

        baseline_response = self.client.get("/catalog/")
        invalid_response = self.client.get(
            "/catalog/?min_price=oops&max_price=bad&category=INVALID&bedrooms=nope&page=-2&location=   "
        )

        self.assertEqual(invalid_response.status_code, 200)

        baseline_ids = [item["id"] for item in baseline_response.json()["data"]["properties"]]
        invalid_ids = [item["id"] for item in invalid_response.json()["data"]["properties"]]

        self.assertEqual(invalid_ids, baseline_ids)
        self.assertEqual(invalid_response.json()["data"]["pagination"]["page"], 1)

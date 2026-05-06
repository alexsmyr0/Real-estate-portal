from __future__ import annotations

import os
from decimal import Decimal
from urllib.parse import parse_qs

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django

django.setup()

from django.test import Client, TestCase, override_settings

from homefinder.apps.properties.models import Amenity, Property, PropertyCategory, PropertyImage, PropertyStatus
from homefinder.apps.properties.services import parse_catalog_search_params, search_visible_properties


@override_settings(ALLOWED_HOSTS=["testserver"])
class PublicCatalogPageTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.pool = Amenity.objects.create(name="Pool")
        self.gym = Amenity.objects.create(name="Gym")

    def _create_property(
        self,
        *,
        title: str,
        status: str,
        city: str,
        area: str,
        price: Decimal,
        bedrooms: int,
        category: str = PropertyCategory.RESIDENTIAL,
    ) -> Property:
        return Property.objects.create(
            title=title,
            description=f"{title} description",
            category=category,
            status=status,
            city=city,
            area=area,
            address_line=f"{city} address",
            price=price,
            bedrooms=bedrooms,
            bathrooms=Decimal("2.0"),
        )

    def test_landing_page_renders_and_links_to_catalog(self) -> None:
        self._create_property(
            title="Landing Snapshot Listing",
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            area="Pangrati",
            price=Decimal("320000.00"),
            bedrooms=2,
        )

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/site_home.html")
        self.assertContains(response, "Browse Catalog")
        self.assertContains(response, "/catalog/")
        self.assertContains(response, "Landing Snapshot Listing")

    def test_catalog_page_results_match_backend_payload(self) -> None:
        visible_property = self._create_property(
            title="Visible Listing",
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            area="Center",
            price=Decimal("275000.00"),
            bedrooms=2,
        )
        unavailable_property = self._create_property(
            title="Unavailable Listing",
            status=PropertyStatus.UNAVAILABLE,
            city="Athens",
            area="Center",
            price=Decimal("285000.00"),
            bedrooms=2,
        )
        self._create_property(
            title="Removed Listing",
            status=PropertyStatus.REMOVED,
            city="Athens",
            area="Center",
            price=Decimal("295000.00"),
            bedrooms=2,
        )

        response = self.client.get("/catalog/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "properties/catalog.html")
        expected_payload = search_visible_properties(search_params=parse_catalog_search_params(response.wsgi_request.GET))
        expected_ids = [record["id"] for record in expected_payload["properties"]]
        context_ids = [record["id"] for record in response.context["properties"]]

        self.assertEqual(context_ids, expected_ids)
        self.assertIn(visible_property.id, context_ids)
        self.assertIn(unavailable_property.id, context_ids)
        self.assertContains(response, "Visible Listing")
        self.assertContains(response, "Unavailable Listing")
        self.assertNotContains(response, "Removed Listing")

    def test_catalog_filters_preserve_active_values_and_match_backend_results(self) -> None:
        matching_property = self._create_property(
            title="Matching Filter Listing",
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            area="Marina Hills",
            price=Decimal("250000.00"),
            bedrooms=3,
        )
        matching_property.amenities.add(self.pool, self.gym)

        non_matching_property = self._create_property(
            title="Non Matching Listing",
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            area="Center",
            price=Decimal("460000.00"),
            bedrooms=1,
            category=PropertyCategory.COMMERCIAL,
        )
        non_matching_property.amenities.add(self.pool)

        query = {
            "location": "RINA",
            "min_price": "200000",
            "max_price": "300000",
            "category": PropertyCategory.RESIDENTIAL,
            "bedrooms_min": "3",
            "amenities": [str(self.pool.id), str(self.gym.id)],
        }
        response = self.client.get("/catalog/", query)

        self.assertEqual(response.status_code, 200)
        expected_payload = search_visible_properties(search_params=parse_catalog_search_params(response.wsgi_request.GET))
        expected_ids = [record["id"] for record in expected_payload["properties"]]
        context_ids = [record["id"] for record in response.context["properties"]]

        self.assertEqual(context_ids, expected_ids)
        self.assertEqual(context_ids, [matching_property.id])
        self.assertNotIn(non_matching_property.id, context_ids)
        self.assertContains(response, "Matching Filter Listing")
        self.assertNotContains(response, "Non Matching Listing")

        active_filters = response.context["active_filters"]
        self.assertEqual(active_filters["location"], "RINA")
        self.assertEqual(active_filters["min_price"], "200000")
        self.assertEqual(active_filters["max_price"], "300000")
        self.assertEqual(active_filters["category"], PropertyCategory.RESIDENTIAL)
        self.assertEqual(active_filters["bedrooms_min"], "3")

        selected_amenity_ids = {
            option["id"]
            for option in response.context["amenity_filter_options"]
            if option["is_selected"]
        }
        self.assertEqual(selected_amenity_ids, {self.pool.id, self.gym.id})

    def test_catalog_pagination_uses_twelve_per_page_and_keeps_filters(self) -> None:
        for index in range(14):
            self._create_property(
                title=f"Athens Listing {index}",
                status=PropertyStatus.AVAILABLE,
                city="Athens",
                area="Center",
                price=Decimal("220000.00"),
                bedrooms=2,
            )

        for index in range(3):
            self._create_property(
                title=f"Patra Listing {index}",
                status=PropertyStatus.AVAILABLE,
                city="Patra",
                area="Center",
                price=Decimal("210000.00"),
                bedrooms=2,
            )

        page_one_response = self.client.get("/catalog/", {"location": "Athens", "page": "1"})
        self.assertEqual(page_one_response.status_code, 200)

        page_one_expected = search_visible_properties(
            search_params=parse_catalog_search_params(page_one_response.wsgi_request.GET),
        )
        page_one_ids = [record["id"] for record in page_one_response.context["properties"]]
        expected_page_one_ids = [record["id"] for record in page_one_expected["properties"]]
        self.assertEqual(page_one_ids, expected_page_one_ids)
        self.assertEqual(page_one_response.context["pagination"]["per_page"], 12)
        self.assertEqual(page_one_response.context["pagination"]["total_items"], 14)
        self.assertEqual(page_one_response.context["pagination"]["page"], 1)
        self.assertEqual(len(page_one_ids), 12)

        next_page_query = parse_qs(page_one_response.context["next_page_query"])
        self.assertEqual(next_page_query.get("location"), ["Athens"])
        self.assertEqual(next_page_query.get("page"), ["2"])

        for page_link in page_one_response.context["page_links"]:
            page_link_query = parse_qs(page_link["query_string"])
            self.assertEqual(page_link_query.get("location"), ["Athens"])

        page_two_response = self.client.get("/catalog/", {"location": "Athens", "page": "2"})
        self.assertEqual(page_two_response.status_code, 200)

        page_two_expected = search_visible_properties(
            search_params=parse_catalog_search_params(page_two_response.wsgi_request.GET),
        )
        page_two_ids = [record["id"] for record in page_two_response.context["properties"]]
        expected_page_two_ids = [record["id"] for record in page_two_expected["properties"]]
        self.assertEqual(page_two_ids, expected_page_two_ids)
        self.assertEqual(page_two_response.context["pagination"]["page"], 2)
        self.assertEqual(len(page_two_ids), 2)

    def test_catalog_empty_state_renders_when_no_results(self) -> None:
        self._create_property(
            title="Athens Listing",
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            area="Center",
            price=Decimal("300000.00"),
            bedrooms=2,
        )

        response = self.client.get("/catalog/", {"location": "Nowhere"})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "properties/catalog.html")
        self.assertFalse(response.context["properties"])
        self.assertContains(response, "No properties match those filters")

    def test_property_detail_page_renders_visible_listing_content(self) -> None:
        property_obj = self._create_property(
            title="Visible Detail Listing",
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            area="Kolonaki",
            price=Decimal("510000.00"),
            bedrooms=3,
            category=PropertyCategory.COMMERCIAL,
        )
        property_obj.amenities.add(self.pool, self.gym)
        PropertyImage.objects.create(property=property_obj, image_url="https://img.example.com/detail-visible-1.jpg")
        PropertyImage.objects.create(property=property_obj, image_url="https://img.example.com/detail-visible-2.jpg")

        response = self.client.get(f"/catalog/{property_obj.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "properties/detail.html")
        self.assertContains(response, "Visible Detail Listing")
        self.assertContains(response, "Gallery")
        self.assertContains(response, "Key Facts")
        self.assertContains(response, "Amenities")
        self.assertContains(response, "https://img.example.com/detail-visible-1.jpg")
        self.assertContains(response, "https://img.example.com/detail-visible-2.jpg")
        self.assertContains(response, "Pool")
        self.assertContains(response, "Gym")
        self.assertContains(response, "EUR 510000.00")
        self.assertContains(response, "/catalog/")
        self.assertEqual(response.context["property"]["id"], property_obj.id)
        self.assertEqual(response.context["category_label"], "Commercial")
        self.assertTrue(response.context["property"]["availability"]["is_available"])

    def test_property_detail_page_renders_unavailable_listing_with_clear_messaging(self) -> None:
        property_obj = self._create_property(
            title="Unavailable Detail Listing",
            status=PropertyStatus.UNAVAILABLE,
            city="Patra",
            area="North",
            price=Decimal("330000.00"),
            bedrooms=2,
        )
        PropertyImage.objects.create(property=property_obj, image_url="https://img.example.com/detail-unavailable-1.jpg")

        response = self.client.get(f"/catalog/{property_obj.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "properties/detail.html")
        self.assertContains(response, "Unavailable Detail Listing")
        self.assertContains(response, "Unavailable")
        self.assertContains(response, "currently unavailable")
        self.assertTrue(response.context["property"]["availability"]["is_unavailable"])

    def test_property_detail_page_returns_not_found_for_removed_listing(self) -> None:
        property_obj = self._create_property(
            title="Removed Detail Listing",
            status=PropertyStatus.REMOVED,
            city="Larisa",
            area="Center",
            price=Decimal("290000.00"),
            bedrooms=2,
        )

        response = self.client.get(f"/catalog/{property_obj.id}/")

        self.assertEqual(response.status_code, 404)
        self.assertJSONEqual(
            response.content,
            {
                "status": "error",
                "error": {
                    "code": 404,
                    "message": "Not Found",
                },
            },
        )

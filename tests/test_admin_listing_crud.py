from __future__ import annotations

import os
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django
from django.contrib import admin
from django.test import Client, TestCase
from django.urls import reverse

django.setup()

from homefinder.apps.properties.models import Amenity, Property, PropertyAmenity, PropertyCategory, PropertyImage, PropertyStatus  # noqa: E402
from homefinder.apps.properties.services import is_publicly_visible_property_status, visible_properties_queryset  # noqa: E402
from homefinder.apps.users.models import User  # noqa: E402


class AdminListingCrudTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            email="admin@example.com",
            password="password123",
        )
        self.client.force_login(self.admin_user)
        self.pool = Amenity.objects.create(name="Pool")

    def test_property_admin_configuration_is_practical_for_listing_management(self) -> None:
        property_admin = admin.site._registry[Property]
        amenity_admin = admin.site._registry[Amenity]
        image_admin = admin.site._registry[PropertyImage]

        self.assertEqual(property_admin.list_editable, ("status",))
        self.assertIn("catalog_visibility", property_admin.list_display)
        self.assertIn("status", property_admin.list_filter)
        self.assertIn("category", property_admin.list_filter)
        self.assertIn("city", property_admin.list_filter)
        self.assertIn("title", property_admin.search_fields)
        self.assertIn("listed_by__email", property_admin.search_fields)
        self.assertEqual([inline.model for inline in property_admin.inlines], [PropertyAmenity, PropertyImage])
        self.assertTrue(
            any(getattr(list_filter, "parameter_name", None) == "catalog_visibility" for list_filter in property_admin.list_filter)
        )

        self.assertIn("name", amenity_admin.list_display)
        self.assertIn("property_count", amenity_admin.list_display)
        self.assertIn("name", amenity_admin.search_fields)

        self.assertIn("property", image_admin.list_display)
        self.assertIn("property_status", image_admin.list_display)
        self.assertIn("property__status", image_admin.list_filter)
        self.assertIn("property__title", image_admin.search_fields)

    def test_admin_can_create_listing_from_property_add_view(self) -> None:
        add_url = reverse("admin:properties_property_add")
        response = self.client.post(
            add_url,
            data={
                "title": "Admin Added Listing",
                "description": "Created from admin",
                "category": PropertyCategory.RESIDENTIAL,
                "status": PropertyStatus.AVAILABLE,
                "city": "Athens",
                "area": "Center",
                "address_line": "12 Central Street",
                "price": "320000.00",
                "bedrooms": "3",
                "bathrooms": "2.0",
                "listed_by": str(self.admin_user.id),
                **self._empty_inline_formset_payload(),
                **self._amenity_inline_formset_payload(self.pool.id),
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 302)

        created_listing = Property.objects.get(title="Admin Added Listing")
        self.assertEqual(created_listing.status, PropertyStatus.AVAILABLE)
        self.assertEqual(created_listing.city, "Athens")
        self.assertEqual(
            set(created_listing.amenities.values_list("name", flat=True)),
            {"Pool"},
        )

    def test_admin_listing_status_changes_follow_visibility_rules(self) -> None:
        listing = self._create_property(
            title="Visibility Candidate",
            status=PropertyStatus.AVAILABLE,
            city="Patra",
            area="Center",
        )
        change_url = reverse("admin:properties_property_change", args=[listing.id])

        unavailable_response = self.client.post(
            change_url,
            data=self._property_change_payload(listing, status=PropertyStatus.UNAVAILABLE),
        )
        self.assertEqual(unavailable_response.status_code, 302)

        listing.refresh_from_db()
        visible_ids = set(visible_properties_queryset().values_list("id", flat=True))
        self.assertEqual(listing.status, PropertyStatus.UNAVAILABLE)
        self.assertTrue(is_publicly_visible_property_status(listing.status))
        self.assertIn(listing.id, visible_ids)

        removed_response = self.client.post(
            change_url,
            data=self._property_change_payload(listing, status=PropertyStatus.REMOVED),
        )
        self.assertEqual(removed_response.status_code, 302)

        listing.refresh_from_db()
        visible_ids = set(visible_properties_queryset().values_list("id", flat=True))
        self.assertEqual(listing.status, PropertyStatus.REMOVED)
        self.assertFalse(is_publicly_visible_property_status(listing.status))
        self.assertNotIn(listing.id, visible_ids)

    def test_admin_changelist_supports_filtering_and_search_for_listing_workflows(self) -> None:
        available_listing = self._create_property(
            title="Marina Loft",
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            area="Marina",
        )
        unavailable_listing = self._create_property(
            title="Business Tower",
            status=PropertyStatus.UNAVAILABLE,
            city="Athens",
            area="CBD",
        )
        removed_listing = self._create_property(
            title="Archived Cottage",
            status=PropertyStatus.REMOVED,
            city="Patra",
            area="Hills",
        )
        changelist_url = reverse("admin:properties_property_changelist")

        removed_filter_response = self.client.get(changelist_url, {"status__exact": PropertyStatus.REMOVED})
        self.assertEqual(removed_filter_response.status_code, 200)
        self.assertEqual(
            set(removed_filter_response.context["cl"].queryset.values_list("id", flat=True)),
            {removed_listing.id},
        )

        hidden_filter_response = self.client.get(changelist_url, {"catalog_visibility": "hidden"})
        self.assertEqual(hidden_filter_response.status_code, 200)
        self.assertEqual(
            set(hidden_filter_response.context["cl"].queryset.values_list("id", flat=True)),
            {removed_listing.id},
        )

        visible_filter_response = self.client.get(changelist_url, {"catalog_visibility": "visible"})
        self.assertEqual(visible_filter_response.status_code, 200)
        self.assertEqual(
            set(visible_filter_response.context["cl"].queryset.values_list("id", flat=True)),
            {available_listing.id, unavailable_listing.id},
        )

        search_response = self.client.get(changelist_url, {"q": "Marina"})
        self.assertEqual(search_response.status_code, 200)
        self.assertEqual(
            set(search_response.context["cl"].queryset.values_list("id", flat=True)),
            {available_listing.id},
        )

    def _create_property(
        self,
        *,
        title: str,
        status: str,
        city: str,
        area: str,
    ) -> Property:
        return Property.objects.create(
            title=title,
            description=f"{title} description",
            category=PropertyCategory.RESIDENTIAL,
            status=status,
            city=city,
            area=area,
            address_line=f"{city} address line",
            price=Decimal("250000.00"),
            bedrooms=2,
            bathrooms=Decimal("1.5"),
            listed_by=self.admin_user,
        )

    def _property_change_payload(self, property_obj: Property, **overrides: str) -> dict[str, object]:
        payload: dict[str, object] = {
            "title": property_obj.title,
            "description": property_obj.description,
            "category": property_obj.category,
            "status": property_obj.status,
            "city": property_obj.city,
            "area": property_obj.area,
            "address_line": property_obj.address_line,
            "price": str(property_obj.price),
            "bedrooms": str(property_obj.bedrooms or ""),
            "bathrooms": str(property_obj.bathrooms or ""),
            "listed_by": str(property_obj.listed_by_id or ""),
            **self._empty_inline_formset_payload(),
            "_save": "Save",
        }
        payload.update(overrides)
        return payload

    def _empty_inline_formset_payload(self) -> dict[str, str]:
        return {
            "propertyamenity_set-TOTAL_FORMS": "0",
            "propertyamenity_set-INITIAL_FORMS": "0",
            "propertyamenity_set-MIN_NUM_FORMS": "0",
            "propertyamenity_set-MAX_NUM_FORMS": "1000",
            "images-TOTAL_FORMS": "0",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "1000",
        }

    def _amenity_inline_formset_payload(self, amenity_id: int) -> dict[str, str]:
        return {
            "propertyamenity_set-TOTAL_FORMS": "1",
            "propertyamenity_set-INITIAL_FORMS": "0",
            "propertyamenity_set-MIN_NUM_FORMS": "0",
            "propertyamenity_set-MAX_NUM_FORMS": "1000",
            "propertyamenity_set-0-amenity": str(amenity_id),
            "propertyamenity_set-0-id": "",
        }

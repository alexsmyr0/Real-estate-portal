from __future__ import annotations

import os
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django

django.setup()

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from homefinder.apps.properties.models import Amenity, Property, PropertyAmenity, PropertyCategory, PropertyImage, PropertyStatus
from homefinder.apps.users.models import User, UserRole


@override_settings(ALLOWED_HOSTS=["testserver"])
class AdminStaffListingCrudPageTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.regular_user = User.objects.create_user(
            email="regular-listing-staff@example.com",
            password="StrongPassword123!",
            role=UserRole.USER,
        )
        self.supervisor_user = User.objects.create_user(
            email="supervisor-listing-staff@example.com",
            password="StrongPassword123!",
            role=UserRole.SUPERVISOR,
            is_staff=True,
        )
        self.admin_user = User.objects.create_superuser(
            email="admin-listing-staff@example.com",
            password="StrongPassword123!",
        )
        self.pool = Amenity.objects.create(name="Pool")
        self.parking = Amenity.objects.create(name="Parking")

    def test_non_admin_users_receive_forbidden_on_staff_listing_routes(self) -> None:
        listing = self._create_property(title="Staff Route Guard Listing", status=PropertyStatus.AVAILABLE)
        route_paths = (
            "/staff/listings/",
            "/staff/listings/new/",
            f"/staff/listings/{listing.id}/edit/",
            f"/staff/listings/{listing.id}/delete/",
        )
        expected_forbidden_json = {
            "status": "error",
            "error": {
                "code": 403,
                "message": "Forbidden",
            },
        }

        for user in (self.regular_user, self.supervisor_user):
            self.client.force_login(user)
            for route_path in route_paths:
                with self.subTest(user=user.role, route_path=route_path):
                    response = self.client.get(route_path)
                    self.assertEqual(response.status_code, 403)
                    self.assertJSONEqual(response.content, expected_forbidden_json)

    def test_admin_can_create_listing_with_image_and_amenity_in_single_submission(self) -> None:
        self.client.force_login(self.admin_user)

        response = self.client.post(
            "/staff/listings/new/",
            data=self._create_payload(
                title="Inline Formset Created Listing",
                image_url="https://images.example.com/create-listing.jpg",
                amenity_id=self.pool.id,
            ),
        )

        self.assertRedirects(response, "/staff/listings/")

        created_listing = Property.objects.get(title="Inline Formset Created Listing")
        self.assertEqual(created_listing.status, PropertyStatus.AVAILABLE)
        self.assertEqual(created_listing.listed_by_id, self.admin_user.id)
        self.assertTrue(PropertyImage.objects.filter(property=created_listing).exists())
        self.assertTrue(PropertyAmenity.objects.filter(property=created_listing, amenity=self.pool).exists())

    def test_admin_can_edit_listing_without_losing_existing_images_or_amenities(self) -> None:
        listing = self._create_property(title="Editable Listing", status=PropertyStatus.UNAVAILABLE)
        existing_image = PropertyImage.objects.create(
            property=listing,
            image_url="https://images.example.com/existing-image.jpg",
        )
        existing_property_amenity = PropertyAmenity.objects.create(property=listing, amenity=self.pool)

        self.client.force_login(self.admin_user)
        response = self.client.post(
            f"/staff/listings/{listing.id}/edit/",
            data=self._edit_payload(
                listing=listing,
                existing_image=existing_image,
                existing_property_amenity=existing_property_amenity,
                additional_image_url="https://images.example.com/new-image.jpg",
                additional_amenity_id=self.parking.id,
            ),
        )

        self.assertRedirects(response, "/staff/listings/")
        listing.refresh_from_db()

        self.assertEqual(listing.title, "Edited Listing Title")
        self.assertEqual(listing.city, "Patra")
        self.assertEqual(listing.price, Decimal("345000.00"))
        self.assertTrue(PropertyImage.objects.filter(pk=existing_image.pk, property=listing).exists())
        self.assertEqual(
            set(listing.images.values_list("image_url", flat=True)),
            {
                "https://images.example.com/existing-image.jpg",
                "https://images.example.com/new-image.jpg",
            },
        )
        self.assertEqual(
            set(listing.amenities.values_list("id", flat=True)),
            {self.pool.id, self.parking.id},
        )

    def test_admin_delete_flow_requires_confirmation_then_removes_listing(self) -> None:
        listing = self._create_property(title="Delete Me Listing", status=PropertyStatus.REMOVED)
        self.client.force_login(self.admin_user)

        delete_url = reverse("staff-listing-delete", args=[listing.id])
        confirm_response = self.client.get(delete_url)
        self.assertEqual(confirm_response.status_code, 200)
        self.assertTemplateUsed(confirm_response, "properties/listing_confirm_delete.html")
        self.assertContains(confirm_response, "Yes, delete listing")
        self.assertTrue(Property.objects.filter(pk=listing.id).exists())

        response = self.client.post(delete_url)
        self.assertRedirects(response, "/staff/listings/")
        self.assertFalse(Property.objects.filter(pk=listing.id).exists())

    def test_invalid_create_renders_validation_errors_and_persists_nothing(self) -> None:
        self.client.force_login(self.admin_user)

        payload = self._create_payload(
            title="Invalid Inline Listing",
            image_url="",
            amenity_id=self.pool.id,
        )
        payload.update(
            {
                "images-TOTAL_FORMS": "0",
                "images-INITIAL_FORMS": "0",
                "amenities": [],
            }
        )

        response = self.client.post("/staff/listings/new/", data=payload)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "properties/listing_form.html")
        self.assertContains(response, "Select at least one amenity for the listing.")
        self.assertFalse(Property.objects.filter(title="Invalid Inline Listing").exists())

    def test_listing_pages_reuse_shared_shell_and_admin_navigation_link(self) -> None:
        guest_response = self.client.get("/")
        self.assertNotContains(guest_response, 'href="/staff/listings/"')

        self.client.force_login(self.regular_user)
        regular_response = self.client.get("/")
        self.assertNotContains(regular_response, 'href="/staff/listings/"')

        self.client.force_login(self.supervisor_user)
        supervisor_response = self.client.get("/")
        self.assertNotContains(supervisor_response, 'href="/staff/listings/"')

        self.client.force_login(self.admin_user)
        admin_home_response = self.client.get("/")
        self.assertContains(admin_home_response, 'href="/staff/listings/"')

        self._create_property(title="Shell Styled Listing", status=PropertyStatus.AVAILABLE)
        listing_page_response = self.client.get("/staff/listings/")
        self.assertEqual(listing_page_response.status_code, 200)
        self.assertTemplateUsed(listing_page_response, "base.html")
        self.assertTemplateUsed(listing_page_response, "properties/listing_list.html")
        self.assertContains(listing_page_response, 'class="report-table"')
        self.assertContains(listing_page_response, 'class="form-control"')

        create_page_response = self.client.get("/staff/listings/new/")
        self.assertEqual(create_page_response.status_code, 200)
        self.assertTemplateUsed(create_page_response, "base.html")
        self.assertTemplateUsed(create_page_response, "properties/listing_form.html")
        self.assertContains(create_page_response, 'class="form-control"')

    def test_listing_visibility_filters_follow_locked_available_unavailable_removed_rules(self) -> None:
        available_listing = self._create_property(title="Visible Available", status=PropertyStatus.AVAILABLE)
        unavailable_listing = self._create_property(title="Visible Unavailable", status=PropertyStatus.UNAVAILABLE)
        removed_listing = self._create_property(title="Hidden Removed", status=PropertyStatus.REMOVED)
        self.client.force_login(self.admin_user)

        response = self.client.get("/staff/listings/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="status-pill status-pill-available">Available</span>')
        self.assertContains(response, 'class="status-pill status-pill-unavailable">Unavailable</span>')
        self.assertContains(response, 'class="status-pill status-pill-hidden">Removed</span>')

        removed_only_response = self.client.get("/staff/listings/", {"status": PropertyStatus.REMOVED})
        self.assertContains(removed_only_response, removed_listing.title)
        self.assertNotContains(removed_only_response, available_listing.title)
        self.assertNotContains(removed_only_response, unavailable_listing.title)

    def _create_property(self, *, title: str, status: str) -> Property:
        return Property.objects.create(
            title=title,
            description=f"{title} description",
            category=PropertyCategory.RESIDENTIAL,
            status=status,
            city="Athens",
            area="Center",
            address_line="1 Demo Street",
            price=Decimal("250000.00"),
            bedrooms=2,
            bathrooms=Decimal("1.5"),
            listed_by=self.admin_user,
        )

    def _create_payload(self, *, title: str, image_url: str, amenity_id: int) -> dict[str, object]:
        return {
            "title": title,
            "description": "Created from staff listing form.",
            "category": PropertyCategory.RESIDENTIAL,
            "status": PropertyStatus.AVAILABLE,
            "city": "Athens",
            "area": "Center",
            "address_line": "22 Staff Street",
            "price": "310000.00",
            "bedrooms": "3",
            "bathrooms": "2.0",
            "images-TOTAL_FORMS": "1",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "1",
            "images-MAX_NUM_FORMS": "1000",
            "images-0-id": "",
            "images-0-image_url": image_url,
            "amenities": [str(amenity_id)],
        }

    def _edit_payload(
        self,
        *,
        listing: Property,
        existing_image: PropertyImage,
        existing_property_amenity: PropertyAmenity,
        additional_image_url: str,
        additional_amenity_id: int,
    ) -> dict[str, object]:
        return {
            "title": "Edited Listing Title",
            "description": "Updated listing details.",
            "category": listing.category,
            "status": listing.status,
            "city": "Patra",
            "area": listing.area,
            "address_line": listing.address_line,
            "price": "345000.00",
            "bedrooms": "4",
            "bathrooms": "2.5",
            "images-TOTAL_FORMS": "2",
            "images-INITIAL_FORMS": "1",
            "images-MIN_NUM_FORMS": "1",
            "images-MAX_NUM_FORMS": "1000",
            "images-0-id": str(existing_image.id),
            "images-0-image_url": existing_image.image_url,
            "images-1-id": "",
            "images-1-image_url": additional_image_url,
            "amenities": [
                str(existing_property_amenity.amenity_id),
                str(additional_amenity_id),
            ],
        }

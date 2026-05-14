from __future__ import annotations

import os
from datetime import timedelta
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django

django.setup()

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from homefinder.apps.interactions.models import (
    BookingRequest,
    BookingRequestStatus,
    PropertyInquiry,
    PropertyInquiryStatus,
    ViewingRequest,
    ViewingRequestStatus,
)
from homefinder.apps.properties.models import Property, PropertyCategory, PropertyStatus
from homefinder.apps.users.models import User, UserRole


@override_settings(ALLOWED_HOSTS=["testserver"])
class AdminStaffInteractionPagesTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.regular_user = User.objects.create_user(
            email="regular-user@example.com",
            password="StrongPassword123!",
            role=UserRole.USER,
        )
        self.supervisor_user = User.objects.create_user(
            email="supervisor-user@example.com",
            password="StrongPassword123!",
            role=UserRole.SUPERVISOR,
            is_staff=True,
        )
        self.admin_user = User.objects.create_superuser(
            email="admin-user@example.com",
            password="StrongPassword123!",
        )
        self.interaction_user = User.objects.create_user(
            email="interaction-user@example.com",
            password="StrongPassword123!",
            role=UserRole.USER,
        )
        self.rental_property = self._create_rental_property()
        self.inquiry = PropertyInquiry.objects.create(
            user=self.interaction_user,
            property=self.rental_property,
            message="I want to confirm if pets are allowed.",
            status=PropertyInquiryStatus.OPEN,
        )
        self.viewing_request = ViewingRequest.objects.create(
            user=self.interaction_user,
            property=self.rental_property,
            requested_datetime=timezone.now() + timedelta(days=2),
            note="Late afternoon works best.",
            status=ViewingRequestStatus.PENDING,
        )
        self.booking_request = BookingRequest.objects.create(
            user=self.interaction_user,
            property=self.rental_property,
            start_date=timezone.localdate() + timedelta(days=10),
            end_date=timezone.localdate() + timedelta(days=15),
            note="Traveling with family.",
            status=BookingRequestStatus.PENDING,
        )

    def test_non_admin_requests_are_rejected_with_403(self) -> None:
        protected_paths = (
            "/staff/interactions/inquiries/",
            "/staff/interactions/viewings/",
            "/staff/interactions/bookings/",
        )
        expected_error_response = {
            "status": "error",
            "error": {
                "code": 403,
                "message": "Forbidden",
            },
        }

        for user in (self.regular_user, self.supervisor_user):
            self.client.force_login(user)
            for path in protected_paths:
                with self.subTest(user=user.email, path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 403)
                    self.assertJSONEqual(response.content, expected_error_response)

    def test_admin_can_render_interaction_lists_with_current_status(self) -> None:
        self.client.force_login(self.admin_user)

        inquiry_response = self.client.get("/staff/interactions/inquiries/")
        self.assertEqual(inquiry_response.status_code, 200)
        self.assertTemplateUsed(inquiry_response, "interactions/staff_inquiry_list.html")
        self.assertContains(inquiry_response, "I want to confirm if pets are allowed.")
        self.assertContains(inquiry_response, PropertyInquiryStatus(PropertyInquiryStatus.OPEN).label)
        self.assertContains(inquiry_response, "report-table")

        viewing_response = self.client.get("/staff/interactions/viewings/")
        self.assertEqual(viewing_response.status_code, 200)
        self.assertTemplateUsed(viewing_response, "interactions/staff_viewing_list.html")
        self.assertContains(viewing_response, "Late afternoon works best.")
        self.assertContains(viewing_response, ViewingRequestStatus(ViewingRequestStatus.PENDING).label)

        booking_response = self.client.get("/staff/interactions/bookings/")
        self.assertEqual(booking_response.status_code, 200)
        self.assertTemplateUsed(booking_response, "interactions/staff_booking_list.html")
        self.assertContains(booking_response, "Traveling with family.")
        self.assertContains(booking_response, BookingRequestStatus(BookingRequestStatus.PENDING).label)

    def test_admin_can_advance_booking_status_from_staff_page(self) -> None:
        self.client.force_login(self.admin_user)

        response = self.client.post(
            "/staff/interactions/bookings/",
            data={"booking_request_id": str(self.booking_request.id)},
            follow=False,
        )

        self.assertRedirects(response, "/staff/interactions/bookings/", fetch_redirect_response=False)
        self.booking_request.refresh_from_db()
        self.assertEqual(self.booking_request.status, BookingRequestStatus.APPROVED)

    def test_interaction_navigation_links_are_visible_only_to_admin(self) -> None:
        guest_response = self.client.get("/")
        self.assertNotContains(guest_response, 'href="/staff/interactions/inquiries/"')
        self.assertNotContains(guest_response, 'href="/staff/interactions/viewings/"')
        self.assertNotContains(guest_response, 'href="/staff/interactions/bookings/"')

        self.client.force_login(self.regular_user)
        regular_response = self.client.get("/")
        self.assertNotContains(regular_response, 'href="/staff/interactions/inquiries/"')
        self.assertNotContains(regular_response, 'href="/staff/interactions/viewings/"')
        self.assertNotContains(regular_response, 'href="/staff/interactions/bookings/"')

        self.client.force_login(self.admin_user)
        admin_response = self.client.get("/")
        self.assertContains(admin_response, 'href="/staff/interactions/inquiries/"')
        self.assertContains(admin_response, 'href="/staff/interactions/viewings/"')
        self.assertContains(admin_response, 'href="/staff/interactions/bookings/"')

    def _create_rental_property(self) -> Property:
        return Property.objects.create(
            title="Admin Interaction Rental",
            description="Rental listing for admin interaction workflows.",
            category=PropertyCategory.RENTAL,
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            area="Center",
            address_line="Center 10",
            price=Decimal("1400.00"),
            bedrooms=2,
            bathrooms=Decimal("1.0"),
        )

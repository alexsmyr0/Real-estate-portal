from __future__ import annotations

import os
from datetime import date, timedelta
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django

django.setup()

from django.test import Client, TestCase, override_settings
from django.urls import Resolver404, resolve
from django.utils import timezone

from homefinder.apps.interactions.models import (
    ActivityLog,
    BookingRequest,
    BookingRequestStatus,
    EmailNotification,
    EmailNotificationPurpose,
    EmailNotificationStatus,
    Payment,
)
from homefinder.apps.properties.models import Property, PropertyCategory, PropertyStatus
from homefinder.apps.properties.views import VERIFIED_BOOKING_REQUEST_SESSION_KEY
from homefinder.apps.users.models import User


@override_settings(
    ALLOWED_HOSTS=["testserver"],
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class RentalBookingRequestUiTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.user = User.objects.create_user(
            email="renter@example.com",
            password="StrongPassword123!",
            full_name="Renter Example",
        )
        self.other_user = User.objects.create_user(
            email="other-renter@example.com",
            password="StrongPassword123!",
        )
        self.rental_property = self._create_property(
            title="Rental Booking Listing",
            category=PropertyCategory.RENTAL,
            status=PropertyStatus.AVAILABLE,
        )
        self.unavailable_rental_property = self._create_property(
            title="Unavailable Rental Listing",
            category=PropertyCategory.RENTAL,
            status=PropertyStatus.UNAVAILABLE,
        )
        self.residential_property = self._create_property(
            title="Residential Sale Listing",
            category=PropertyCategory.RESIDENTIAL,
            status=PropertyStatus.AVAILABLE,
        )
        self.commercial_property = self._create_property(
            title="Commercial Listing",
            category=PropertyCategory.COMMERCIAL,
            status=PropertyStatus.AVAILABLE,
        )
        self.removed_rental_property = self._create_property(
            title="Removed Rental Listing",
            category=PropertyCategory.RENTAL,
            status=PropertyStatus.REMOVED,
        )
        self.start_date = timezone.localdate() + timedelta(days=5)
        self.end_date = timezone.localdate() + timedelta(days=9)

    def test_rental_property_detail_page_shows_booking_form(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(f"/catalog/{self.rental_property.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "properties/detail.html")
        self.assertContains(response, "Request a Rental Booking")
        self.assertContains(response, f"/catalog/{self.rental_property.id}/booking-request/")
        self.assertContains(response, "name=\"start_date\"")
        self.assertContains(response, "name=\"end_date\"")
        self.assertContains(response, "type=\"date\"")
        self.assertIsNotNone(response.context["booking_form"])
        self.assertTrue(response.context["is_rental_listing"])

    def test_non_rental_property_detail_pages_do_not_show_active_booking_form(self) -> None:
        self.client.force_login(self.user)

        for property_obj in (self.residential_property, self.commercial_property):
            with self.subTest(category=property_obj.category):
                response = self.client.get(f"/catalog/{property_obj.id}/")

                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "Request a Rental Booking")
                self.assertNotContains(response, "booking-request")
                self.assertNotContains(response, "name=\"start_date\"")
                self.assertIsNone(response.context["booking_form"])
                self.assertFalse(response.context["is_rental_listing"])

    def test_removed_property_does_not_expose_booking_form(self) -> None:
        self.client.force_login(self.user)

        detail_response = self.client.get(f"/catalog/{self.removed_rental_property.id}/")
        post_response = self.client.post(
            f"/catalog/{self.removed_rental_property.id}/booking-request/",
            {
                "start_date": self._form_date(self.start_date),
                "end_date": self._form_date(self.end_date),
            },
        )

        self.assertEqual(detail_response.status_code, 404)
        self.assertEqual(post_response.status_code, 404)
        self.assertEqual(BookingRequest.objects.count(), 0)
        self.assertEqual(EmailNotification.objects.count(), 0)

    def test_anonymous_user_sees_booking_auth_gate_and_post_redirects_to_login_with_next(self) -> None:
        detail_response = self.client.get(f"/catalog/{self.rental_property.id}/")

        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Sign in to request a rental booking.")
        self.assertNotContains(detail_response, "Booking request sent")

        post_response = self.client.post(
            f"/catalog/{self.rental_property.id}/booking-request/",
            {
                "start_date": self._form_date(self.start_date),
                "end_date": self._form_date(self.end_date),
            },
            follow=True,
        )

        self.assertRedirects(post_response, f"/login/?next=%2Fcatalog%2F{self.rental_property.id}%2F")
        self.assertContains(post_response, "Sign in to request a booking.")
        self.assertEqual(BookingRequest.objects.count(), 0)
        self.assertEqual(EmailNotification.objects.count(), 0)

    def test_authenticated_user_can_submit_valid_rental_booking_request(self) -> None:
        self.client.force_login(self.user)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/catalog/{self.rental_property.id}/booking-request/",
                {
                    "start_date": self._form_date(self.start_date),
                    "end_date": self._form_date(self.end_date),
                },
                follow=True,
            )

        self.assertRedirects(response, f"/catalog/{self.rental_property.id}/")
        self.assertContains(response, "Booking request sent")
        self.assertIsNotNone(response.context["booking_confirmation"])

        booking_request = BookingRequest.objects.get()
        self.assertEqual(booking_request.user, self.user)
        self.assertEqual(booking_request.property, self.rental_property)
        self.assertEqual(booking_request.start_date, self.start_date)
        self.assertEqual(booking_request.end_date, self.end_date)
        self.assertEqual(booking_request.status, BookingRequestStatus.PENDING)

        notification = EmailNotification.objects.get()
        self.assertEqual(notification.user, self.user)
        self.assertEqual(notification.purpose, EmailNotificationPurpose.BOOKING_UPDATE)
        self.assertEqual(notification.recipient_email, "renter@example.com")
        self.assertEqual(notification.status, EmailNotificationStatus.SENT)

        activity_log = ActivityLog.objects.get()
        self.assertEqual(activity_log.action, "booking_requested")
        self.assertEqual(activity_log.user, self.user)
        self.assertEqual(activity_log.entity_type, "bookingrequest")
        self.assertEqual(activity_log.entity_id, booking_request.id)
        self.assertEqual(activity_log.details["surface"], "detail")

        self.assertEqual(Payment.objects.count(), 0)

    def test_booking_validation_errors_return_clear_feedback_without_persistence(self) -> None:
        self.client.force_login(self.user)
        today = timezone.localdate()
        invalid_cases = (
            ({}, "Choose a booking start date."),
            ({"start_date": self._form_date(self.start_date)}, "Choose a booking end date."),
            (
                {"end_date": self._form_date(self.end_date)},
                "Choose a booking start date.",
            ),
            (
                {
                    "start_date": self._form_date(self.start_date),
                    "end_date": self._form_date(self.start_date),
                },
                "Booking end date must be after the start date.",
            ),
            (
                {
                    "start_date": self._form_date(self.end_date),
                    "end_date": self._form_date(self.start_date),
                },
                "Booking end date must be after the start date.",
            ),
            (
                {
                    "start_date": self._form_date(today - timedelta(days=1)),
                    "end_date": self._form_date(today + timedelta(days=1)),
                },
                "Booking start date must be today or in the future.",
            ),
        )

        for payload, expected_error in invalid_cases:
            with self.subTest(payload=payload):
                response = self.client.post(
                    f"/catalog/{self.rental_property.id}/booking-request/",
                    payload,
                )

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "properties/detail.html")
                self.assertContains(response, expected_error)
                self.assertEqual(BookingRequest.objects.count(), 0)
                self.assertEqual(EmailNotification.objects.count(), 0)
                self.assertEqual(Payment.objects.count(), 0)

    def test_non_rental_post_is_rejected_server_side(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(
            f"/catalog/{self.residential_property.id}/booking-request/",
            {
                "start_date": self._form_date(self.start_date),
                "end_date": self._form_date(self.end_date),
            },
            follow=True,
        )

        self.assertRedirects(response, f"/catalog/{self.residential_property.id}/")
        self.assertContains(response, "Booking requests are only available for rental listings.")
        self.assertNotContains(response, "Request a Rental Booking")
        self.assertEqual(BookingRequest.objects.count(), 0)
        self.assertEqual(EmailNotification.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)

    def test_unavailable_rental_property_can_receive_booking_request_but_removed_cannot(self) -> None:
        self.client.force_login(self.user)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/catalog/{self.unavailable_rental_property.id}/booking-request/",
                {
                    "start_date": self._form_date(self.start_date),
                    "end_date": self._form_date(self.end_date),
                },
                follow=True,
            )

        self.assertRedirects(response, f"/catalog/{self.unavailable_rental_property.id}/")
        self.assertContains(response, "Booking request sent")
        self.assertTrue(
            BookingRequest.objects.filter(
                user=self.user,
                property=self.unavailable_rental_property,
            ).exists()
        )

        removed_response = self.client.post(
            f"/catalog/{self.removed_rental_property.id}/booking-request/",
            {
                "start_date": self._form_date(self.start_date),
                "end_date": self._form_date(self.end_date),
            },
        )
        self.assertEqual(removed_response.status_code, 404)
        self.assertEqual(BookingRequest.objects.count(), 1)

    def test_success_confirmation_is_one_time_and_not_query_parameter_driven(self) -> None:
        self.client.force_login(self.user)

        forged_response = self.client.get(f"/catalog/{self.rental_property.id}/?booking=sent")
        self.assertEqual(forged_response.status_code, 200)
        self.assertNotContains(forged_response, "Booking request sent")

        with self.captureOnCommitCallbacks(execute=True):
            success_response = self.client.post(
                f"/catalog/{self.rental_property.id}/booking-request/",
                {
                    "start_date": self._form_date(self.start_date),
                    "end_date": self._form_date(self.end_date),
                },
                follow=True,
            )

        self.assertContains(success_response, "Booking request sent")
        self.assertEqual(BookingRequest.objects.count(), 1)
        self.assertEqual(EmailNotification.objects.count(), 1)

        refresh_response = self.client.get(f"/catalog/{self.rental_property.id}/")
        self.assertEqual(refresh_response.status_code, 200)
        self.assertNotContains(refresh_response, "Booking request sent")
        self.assertIsNone(refresh_response.context["booking_confirmation"])
        self.assertEqual(BookingRequest.objects.count(), 1)
        self.assertEqual(EmailNotification.objects.count(), 1)

    def test_user_cannot_submit_booking_as_another_user(self) -> None:
        self.client.force_login(self.user)

        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                f"/catalog/{self.rental_property.id}/booking-request/",
                {
                    "user": str(self.other_user.id),
                    "start_date": self._form_date(self.start_date),
                    "end_date": self._form_date(self.end_date),
                },
            )

        booking_request = BookingRequest.objects.get()
        self.assertEqual(booking_request.user, self.user)
        self.assertNotEqual(booking_request.user, self.other_user)

    def test_booking_confirmation_does_not_leak_another_users_booking_data(self) -> None:
        other_booking = BookingRequest.objects.create(
            user=self.other_user,
            property=self.rental_property,
            start_date=self.start_date,
            end_date=self.end_date,
            status=BookingRequestStatus.PENDING,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session[VERIFIED_BOOKING_REQUEST_SESSION_KEY] = other_booking.id
        session.save()

        response = self.client.get(f"/catalog/{self.rental_property.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Booking request sent")
        self.assertIsNone(response.context["booking_confirmation"])

    def test_booking_ui_does_not_add_payment_or_admin_workflows(self) -> None:
        self.client.force_login(self.user)
        response = self.client.get(f"/catalog/{self.rental_property.id}/")

        self.assertNotContains(response, "Simulated payment")
        self.assertNotContains(response, "Checkout")
        self.assertNotContains(response, "Payment method")
        self.assertEqual(Payment.objects.count(), 0)

        with self.assertRaises(Resolver404):
            resolve("/bookings/")

    def _create_property(self, *, title: str, category: str, status: str) -> Property:
        return Property.objects.create(
            title=title,
            description=f"{title} description",
            category=category,
            status=status,
            city="Athens",
            area="Center",
            address_line="1 Test Street",
            price=Decimal("1200.00"),
            bedrooms=2,
            bathrooms=Decimal("1.5"),
        )

    def _form_date(self, value: date) -> str:
        return value.isoformat()

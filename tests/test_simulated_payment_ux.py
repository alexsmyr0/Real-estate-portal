from __future__ import annotations

import os
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django

django.setup()

from django.test import Client, TestCase, override_settings
from django.urls import resolve
from django.utils import timezone

from homefinder.apps.interactions.models import (
    BookingRequest,
    BookingRequestStatus,
    Payment,
    PaymentMethod,
    PaymentPurpose,
    PaymentStatus,
)
from homefinder.apps.interactions.services import create_booking_fee_payment
from homefinder.apps.properties.models import Property, PropertyCategory, PropertyStatus
from homefinder.apps.users.models import User


@override_settings(
    ALLOWED_HOSTS=["testserver"],
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class SimulatedPaymentUxTests(TestCase):
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
            title="Payment UX Rental",
            status=PropertyStatus.AVAILABLE,
        )
        self.residential_property = self._create_property(
            title="Payment UX Residential",
            status=PropertyStatus.AVAILABLE,
            category=PropertyCategory.RESIDENTIAL,
        )
        self.start_date = timezone.localdate() + timedelta(days=5)
        self.end_date = timezone.localdate() + timedelta(days=9)

    def test_booking_confirmation_exposes_simulated_payment_handoff_without_creating_payment(self) -> None:
        self.client.force_login(self.user)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/catalog/{self.rental_property.id}/booking-request/",
                {
                    "start_date": self.start_date.isoformat(),
                    "end_date": self.end_date.isoformat(),
                },
                follow=True,
            )

        booking_request = BookingRequest.objects.get()
        self.assertContains(response, "Booking request sent")
        self.assertContains(response, "Continue to simulated payment")
        self.assertContains(response, f"/bookings/{booking_request.id}/simulated-payment/")
        self.assertEqual(Payment.objects.count(), 0)

    def test_owner_can_open_payment_page_and_refresh_without_duplicate_payment_rows(self) -> None:
        booking_request = self._create_booking_request()
        self.client.force_login(self.user)

        first_response = self.client.get(f"/bookings/{booking_request.id}/simulated-payment/")
        refresh_response = self.client.get(f"/bookings/{booking_request.id}/simulated-payment/?payment=success")

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(refresh_response.status_code, 200)
        self.assertTemplateUsed(first_response, "interactions/simulated_payment.html")
        self.assertContains(first_response, "Simulated payment pending")
        self.assertContains(first_response, "University project demo - no real payment will be processed.")
        self.assertContains(first_response, "Do not enter real card or bank details.")
        self.assertEqual(Payment.objects.count(), 1)

        payment = Payment.objects.get()
        self.assertEqual(payment.user, self.user)
        self.assertEqual(payment.booking_request, booking_request)
        self.assertEqual(payment.payment_purpose, PaymentPurpose.BOOKING_FEE)
        self.assertEqual(payment.status, PaymentStatus.PENDING)

    def test_anonymous_user_redirects_to_login_with_next_for_payment_page_and_action(self) -> None:
        booking_request = self._create_booking_request()

        page_response = self.client.get(f"/bookings/{booking_request.id}/simulated-payment/", follow=True)
        action_response = self.client.post(
            f"/bookings/{booking_request.id}/simulated-payment/complete/",
            follow=True,
        )

        expected_next = f"%2Fbookings%2F{booking_request.id}%2Fsimulated-payment%2F"
        self.assertRedirects(page_response, f"/login/?next={expected_next}")
        self.assertRedirects(action_response, f"/login/?next={expected_next}")
        self.assertContains(page_response, "Sign in to continue the simulated payment step.")
        self.assertEqual(Payment.objects.count(), 0)

    def test_another_user_cannot_view_or_mutate_payment(self) -> None:
        booking_request = self._create_booking_request()
        payment = create_booking_fee_payment(
            booking_request=booking_request,
            amount="49.99",
            method=PaymentMethod.CREDIT_CARD,
        )
        self.client.force_login(self.other_user)

        page_response = self.client.get(f"/bookings/{booking_request.id}/simulated-payment/")
        action_response = self.client.post(f"/bookings/{booking_request.id}/simulated-payment/complete/")

        self.assertEqual(page_response.status_code, 404)
        self.assertEqual(action_response.status_code, 404)
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.PENDING)

    def test_owner_can_complete_simulated_payment_and_duplicate_completion_is_idempotent(self) -> None:
        booking_request = self._create_booking_request()
        self.client.force_login(self.user)
        self.client.get(f"/bookings/{booking_request.id}/simulated-payment/")
        payment = Payment.objects.get()

        response = self.client.post(
            f"/bookings/{booking_request.id}/simulated-payment/complete/",
            follow=True,
        )
        completed_payment = Payment.objects.get(pk=payment.pk)
        first_updated_at = completed_payment.updated_at

        duplicate_response = self.client.post(
            f"/bookings/{booking_request.id}/simulated-payment/complete/",
            follow=True,
        )
        completed_payment.refresh_from_db()

        self.assertContains(response, "Simulated payment completed.")
        self.assertContains(response, "No real payment was processed.")
        self.assertContains(duplicate_response, "Simulated payment completed.")
        self.assertEqual(completed_payment.status, PaymentStatus.COMPLETED)
        self.assertEqual(completed_payment.updated_at, first_updated_at)
        self.assertEqual(Payment.objects.count(), 1)

    def test_approved_booking_can_create_and_complete_simulated_payment(self) -> None:
        booking_request = self._create_booking_request(status=BookingRequestStatus.APPROVED)
        self.client.force_login(self.user)

        page_response = self.client.get(f"/bookings/{booking_request.id}/simulated-payment/")
        action_response = self.client.post(
            f"/bookings/{booking_request.id}/simulated-payment/complete/",
            follow=True,
        )

        payment = Payment.objects.get()
        self.assertEqual(page_response.status_code, 200)
        self.assertContains(page_response, "Simulated payment pending")
        self.assertContains(page_response, "Complete simulated payment")
        self.assertContains(action_response, "Simulated payment completed.")
        self.assertEqual(payment.booking_request, booking_request)
        self.assertEqual(payment.status, PaymentStatus.COMPLETED)

    def test_failed_and_cancelled_statuses_render_and_failed_payment_can_start_new_attempt(self) -> None:
        booking_request = self._create_booking_request()
        self.client.force_login(self.user)
        self.client.get(f"/bookings/{booking_request.id}/simulated-payment/")

        failed_response = self.client.post(
            f"/bookings/{booking_request.id}/simulated-payment/fail/",
            follow=True,
        )
        retry_response = self.client.post(
            f"/bookings/{booking_request.id}/simulated-payment/retry/",
            follow=True,
        )
        cancel_response = self.client.post(
            f"/bookings/{booking_request.id}/simulated-payment/cancel/",
            follow=True,
        )

        self.assertContains(failed_response, "Simulated payment failed.")
        self.assertContains(failed_response, "Start new simulated attempt")
        self.assertContains(retry_response, "A new simulated payment attempt is ready.")
        self.assertContains(retry_response, "Simulated payment pending")
        self.assertContains(cancel_response, "Simulated payment was cancelled.")
        self.assertEqual(Payment.objects.filter(status=PaymentStatus.FAILED).count(), 1)
        self.assertEqual(Payment.objects.filter(status=PaymentStatus.CANCELLED).count(), 1)
        self.assertEqual(Payment.objects.count(), 2)

    def test_unsupported_action_slug_does_not_create_payment(self) -> None:
        booking_request = self._create_booking_request()
        self.client.force_login(self.user)

        response = self.client.post(f"/bookings/{booking_request.id}/simulated-payment/not-real/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(Payment.objects.count(), 0)

    def test_unsupported_action_slug_does_not_mutate_existing_payment(self) -> None:
        booking_request = self._create_booking_request()
        payment = create_booking_fee_payment(
            booking_request=booking_request,
            amount="49.99",
            method=PaymentMethod.CREDIT_CARD,
        )
        self.client.force_login(self.user)

        response = self.client.post(f"/bookings/{booking_request.id}/simulated-payment/not-real/")

        payment.refresh_from_db()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(payment.status, PaymentStatus.PENDING)

    def test_invalid_transition_shows_clear_error_and_preserves_persisted_status(self) -> None:
        booking_request = self._create_booking_request()
        payment = create_booking_fee_payment(
            booking_request=booking_request,
            amount="49.99",
            method=PaymentMethod.CREDIT_CARD,
        )
        self.client.force_login(self.user)
        self.client.post(f"/bookings/{booking_request.id}/simulated-payment/complete/")

        response = self.client.post(
            f"/bookings/{booking_request.id}/simulated-payment/fail/",
            follow=True,
        )

        payment.refresh_from_db()
        self.assertContains(response, "Payments cannot move from COMPLETED to FAILED.")
        self.assertContains(response, "Simulated payment completed")
        self.assertEqual(payment.status, PaymentStatus.COMPLETED)

    def test_payment_status_is_persisted_not_query_parameter_driven(self) -> None:
        booking_request = self._create_booking_request()
        self.client.force_login(self.user)

        response = self.client.get(f"/bookings/{booking_request.id}/simulated-payment/?payment=success")

        self.assertContains(response, "Simulated payment pending")
        self.assertNotContains(response, "Simulated payment completed.")
        self.assertEqual(Payment.objects.get().status, PaymentStatus.PENDING)

    def test_payment_ui_does_not_render_real_payment_data_fields_or_gateway_copy(self) -> None:
        booking_request = self._create_booking_request()
        self.client.force_login(self.user)

        response = self.client.get(f"/bookings/{booking_request.id}/simulated-payment/")

        self.assertNotContains(response, "name=\"card_number\"")
        self.assertNotContains(response, "name=\"cvv\"")
        self.assertNotContains(response, "name=\"bank_account\"")
        self.assertNotContains(response, "name=\"billing_address\"")
        self.assertNotContains(response, "Stripe")
        self.assertNotContains(response, "PayPal")
        self.assertNotContains(response, "invoice")
        self.assertNotContains(response, "receipt")
        self.assertContains(response, "Simulation controls")
        self.assertContains(response, "no real payment will be processed")

    def test_rejected_booking_cannot_create_new_simulated_payment(self) -> None:
        booking_request = self._create_booking_request(status=BookingRequestStatus.REJECTED)
        self.client.force_login(self.user)

        page_response = self.client.get(f"/bookings/{booking_request.id}/simulated-payment/")
        action_response = self.client.post(f"/bookings/{booking_request.id}/simulated-payment/complete/")

        self.assertEqual(page_response.status_code, 404)
        self.assertEqual(action_response.status_code, 404)
        self.assertEqual(Payment.objects.count(), 0)

    def test_cancelled_booking_cannot_create_new_simulated_payment(self) -> None:
        booking_request = self._create_booking_request(status=BookingRequestStatus.CANCELLED)
        self.client.force_login(self.user)

        page_response = self.client.get(f"/bookings/{booking_request.id}/simulated-payment/")
        action_response = self.client.post(f"/bookings/{booking_request.id}/simulated-payment/complete/")

        self.assertEqual(page_response.status_code, 404)
        self.assertEqual(action_response.status_code, 404)
        self.assertEqual(Payment.objects.count(), 0)

    def test_removed_listing_booking_cannot_create_new_simulated_payment(self) -> None:
        removed_property = self._create_property(
            title="Removed Payment UX Rental",
            status=PropertyStatus.REMOVED,
        )
        booking_request = BookingRequest.objects.create(
            user=self.user,
            property=removed_property,
            start_date=self.start_date,
            end_date=self.end_date,
            status=BookingRequestStatus.PENDING,
        )
        self.client.force_login(self.user)

        response = self.client.get(f"/bookings/{booking_request.id}/simulated-payment/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(Payment.objects.count(), 0)

    def test_abnormal_non_rental_booking_cannot_create_new_simulated_payment(self) -> None:
        booking_request = self._create_abnormal_non_rental_booking_request()
        self.client.force_login(self.user)

        page_response = self.client.get(f"/bookings/{booking_request.id}/simulated-payment/")
        action_response = self.client.post(f"/bookings/{booking_request.id}/simulated-payment/complete/")

        self.assertEqual(page_response.status_code, 404)
        self.assertEqual(action_response.status_code, 404)
        self.assertEqual(Payment.objects.count(), 0)

    def test_abnormal_non_rental_booking_existing_payment_actions_are_blocked(self) -> None:
        booking_request = self._create_abnormal_non_rental_booking_request()
        payment = Payment.objects.create(
            user=self.user,
            booking_request=booking_request,
            payment_purpose=PaymentPurpose.BOOKING_FEE,
            payment_method=PaymentMethod.CREDIT_CARD,
            amount=Decimal("49.99"),
            status=PaymentStatus.PENDING,
        )
        self.client.force_login(self.user)

        page_response = self.client.get(f"/bookings/{booking_request.id}/simulated-payment/")
        action_response = self.client.post(
            f"/bookings/{booking_request.id}/simulated-payment/complete/",
            follow=True,
        )

        payment.refresh_from_db()
        self.assertEqual(page_response.status_code, 200)
        self.assertContains(page_response, "no longer eligible for simulated payment actions")
        self.assertContains(action_response, "This booking is no longer eligible for simulated payment actions.")
        self.assertEqual(payment.status, PaymentStatus.PENDING)
        self.assertEqual(Payment.objects.count(), 1)

    def test_existing_payment_status_can_render_after_booking_later_becomes_non_payable(self) -> None:
        booking_request = self._create_booking_request()
        payment = create_booking_fee_payment(
            booking_request=booking_request,
            amount="49.99",
            method=PaymentMethod.CREDIT_CARD,
        )
        booking_request.status = BookingRequestStatus.CANCELLED
        booking_request.save()
        self.client.force_login(self.user)

        page_response = self.client.get(f"/bookings/{booking_request.id}/simulated-payment/")
        action_response = self.client.post(
            f"/bookings/{booking_request.id}/simulated-payment/complete/",
            follow=True,
        )

        payment.refresh_from_db()
        self.assertEqual(page_response.status_code, 200)
        self.assertContains(page_response, "Simulated payment pending")
        self.assertContains(page_response, "no longer eligible for simulated payment actions")
        self.assertContains(action_response, "This booking is no longer eligible for simulated payment actions.")
        self.assertEqual(payment.status, PaymentStatus.PENDING)

    def test_routes_are_user_facing_not_admin_payment_tooling(self) -> None:
        booking_request = self._create_booking_request()

        page_match = resolve(f"/bookings/{booking_request.id}/simulated-payment/")
        action_match = resolve(f"/bookings/{booking_request.id}/simulated-payment/complete/")

        self.assertEqual(page_match.url_name, "site-booking-simulated-payment")
        self.assertEqual(action_match.url_name, "site-booking-simulated-payment-action")

    def test_simulated_payment_actions_make_no_external_calls(self) -> None:
        booking_request = self._create_booking_request()
        self.client.force_login(self.user)

        with patch("homefinder.apps.interactions.services.send_mail") as send_mail:
            self.client.get(f"/bookings/{booking_request.id}/simulated-payment/")
            self.client.post(f"/bookings/{booking_request.id}/simulated-payment/complete/")

        send_mail.assert_not_called()

    def _create_booking_request(self, *, status: str = BookingRequestStatus.PENDING) -> BookingRequest:
        booking_request = BookingRequest.objects.create(
            user=self.user,
            property=self.rental_property,
            start_date=self.start_date,
            end_date=self.end_date,
            status=BookingRequestStatus.PENDING,
        )
        if status != BookingRequestStatus.PENDING:
            booking_request.status = status
            booking_request.save()
        return booking_request

    def _create_abnormal_non_rental_booking_request(self) -> BookingRequest:
        BookingRequest.objects.bulk_create(
            [
                BookingRequest(
                    user=self.user,
                    property=self.residential_property,
                    start_date=self.start_date,
                    end_date=self.end_date,
                    status=BookingRequestStatus.PENDING,
                )
            ]
        )
        return BookingRequest.objects.get(property=self.residential_property)

    def _create_property(
        self,
        *,
        title: str,
        status: str,
        category: str = PropertyCategory.RENTAL,
    ) -> Property:
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

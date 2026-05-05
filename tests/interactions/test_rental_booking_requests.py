from __future__ import annotations

import io
from contextlib import redirect_stdout
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import Resolver404, resolve, reverse
from django.utils import timezone

from homefinder.apps.interactions.models import (
    BookingRequest,
    BookingRequestStatus,
    EmailNotification,
    EmailNotificationPurpose,
    EmailNotificationStatus,
    Payment,
)
from homefinder.apps.interactions.services import (
    EmailNotificationMessage,
    EmailNotificationService,
    create_booking_request,
    update_booking_request_status,
)
from homefinder.apps.properties.models import Property, PropertyCategory
from homefinder.apps.users.models import User


class RecordingDeliveryAdapter:
    def __init__(self) -> None:
        self.messages: list[EmailNotificationMessage] = []

    def deliver(self, message: EmailNotificationMessage) -> int:
        self.messages.append(message)
        return 1


class RentalBookingRequestTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="renter@example.com",
            password="password123",
            full_name="Renter Example",
        )
        self.rental_property = self._create_property(
            title="Athens Rental",
            category=PropertyCategory.RENTAL,
        )
        self.residential_property = self._create_property(
            title="Athens Sale",
            category=PropertyCategory.RESIDENTIAL,
        )
        self.adapter = RecordingDeliveryAdapter()
        self.notification_service = EmailNotificationService(delivery_adapter=self.adapter)
        self.start_date = timezone.localdate() + timedelta(days=30)
        self.end_date = timezone.localdate() + timedelta(days=37)

    def test_rental_property_accepts_booking_request(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            booking_request = create_booking_request(
                user=self.user,
                property_obj=self.rental_property,
                start_date=self.start_date,
                end_date=self.end_date,
                notification_service_override=self.notification_service,
            )

        booking_request.refresh_from_db()
        self.assertEqual(BookingRequest.objects.count(), 1)
        self.assertEqual(booking_request.property, self.rental_property)
        self.assertEqual(booking_request.start_date, self.start_date)
        self.assertEqual(booking_request.end_date, self.end_date)
        self.assertEqual(booking_request.status, BookingRequestStatus.PENDING)

    def test_non_rental_property_rejects_booking_request(self) -> None:
        with self.assertRaises(ValidationError) as raised:
            create_booking_request(
                user=self.user,
                property_obj=self.residential_property,
                start_date=self.start_date,
                end_date=self.end_date,
                notification_service_override=self.notification_service,
            )

        self.assertIn("property", raised.exception.message_dict)
        self.assertEqual(BookingRequest.objects.count(), 0)

    def test_missing_start_date_is_rejected(self) -> None:
        with self.assertRaises(ValidationError) as raised:
            create_booking_request(
                user=self.user,
                property_obj=self.rental_property,
                start_date=None,
                end_date=self.end_date,
                notification_service_override=self.notification_service,
            )

        self.assertIn("start_date", raised.exception.message_dict)
        self.assertEqual(BookingRequest.objects.count(), 0)

    def test_missing_end_date_is_rejected(self) -> None:
        with self.assertRaises(ValidationError) as raised:
            create_booking_request(
                user=self.user,
                property_obj=self.rental_property,
                start_date=self.start_date,
                end_date=None,
                notification_service_override=self.notification_service,
            )

        self.assertIn("end_date", raised.exception.message_dict)
        self.assertEqual(BookingRequest.objects.count(), 0)

    def test_invalid_date_ordering_is_rejected(self) -> None:
        invalid_ranges = (
            (self.start_date, self.start_date),
            (self.end_date, self.start_date),
        )

        for start_date, end_date in invalid_ranges:
            with self.subTest(start_date=start_date, end_date=end_date):
                with self.assertRaises(ValidationError) as raised:
                    create_booking_request(
                        user=self.user,
                        property_obj=self.rental_property,
                        start_date=start_date,
                        end_date=end_date,
                        notification_service_override=self.notification_service,
                    )

                self.assertIn("end_date", raised.exception.message_dict)

        self.assertEqual(BookingRequest.objects.count(), 0)

    def test_past_start_date_is_rejected(self) -> None:
        today = timezone.localdate()

        with self.assertRaises(ValidationError) as raised:
            create_booking_request(
                user=self.user,
                property_obj=self.rental_property,
                start_date=today - timedelta(days=1),
                end_date=today + timedelta(days=1),
                notification_service_override=self.notification_service,
            )

        self.assertEqual(
            raised.exception.message_dict["start_date"],
            ["Booking start date must be today or in the future."],
        )
        self.assertEqual(BookingRequest.objects.count(), 0)

    def test_today_start_date_is_allowed_with_valid_end_date(self) -> None:
        today = timezone.localdate()

        with self.captureOnCommitCallbacks(execute=True):
            booking_request = create_booking_request(
                user=self.user,
                property_obj=self.rental_property,
                start_date=today,
                end_date=today + timedelta(days=1),
                notification_service_override=self.notification_service,
            )

        booking_request.refresh_from_db()
        self.assertEqual(booking_request.start_date, today)
        self.assertEqual(booking_request.status, BookingRequestStatus.PENDING)

    def test_future_start_date_is_allowed(self) -> None:
        today = timezone.localdate()

        with self.captureOnCommitCallbacks(execute=True):
            booking_request = create_booking_request(
                user=self.user,
                property_obj=self.rental_property,
                start_date=today + timedelta(days=1),
                end_date=today + timedelta(days=3),
                notification_service_override=self.notification_service,
            )

        booking_request.refresh_from_db()
        self.assertEqual(booking_request.start_date, today + timedelta(days=1))
        self.assertEqual(booking_request.status, BookingRequestStatus.PENDING)

    def test_booking_submission_creates_booking_update_notification_through_shared_service(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            booking_request = create_booking_request(
                user=self.user,
                property_obj=self.rental_property,
                start_date=self.start_date,
                end_date=self.end_date,
                notification_service_override=self.notification_service,
            )

        notification = EmailNotification.objects.get()
        self.assertEqual(notification.user, self.user)
        self.assertEqual(notification.purpose, EmailNotificationPurpose.BOOKING_UPDATE)
        self.assertEqual(notification.recipient_email, "renter@example.com")
        self.assertEqual(len(self.adapter.messages), 1)
        self.assertIn(str(booking_request.start_date), self.adapter.messages[0].body)
        self.assertIn("Pending", self.adapter.messages[0].body)

    def test_direct_missing_start_date_cannot_persist(self) -> None:
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                BookingRequest.objects.bulk_create(
                    [
                        self._unsaved_booking(
                            start_date=None,
                            end_date=self.end_date,
                        )
                    ]
                )

        self.assertEqual(BookingRequest.objects.count(), 0)

    def test_direct_missing_end_date_cannot_persist(self) -> None:
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                BookingRequest.objects.bulk_create(
                    [
                        self._unsaved_booking(
                            start_date=self.start_date,
                            end_date=None,
                        )
                    ]
                )

        self.assertEqual(BookingRequest.objects.count(), 0)

    def test_direct_invalid_date_ordering_cannot_persist(self) -> None:
        invalid_ranges = (
            (self.start_date, self.start_date),
            (self.end_date, self.start_date),
        )

        for start_date, end_date in invalid_ranges:
            with self.subTest(start_date=start_date, end_date=end_date):
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        BookingRequest.objects.bulk_create(
                            [
                                self._unsaved_booking(
                                    start_date=start_date,
                                    end_date=end_date,
                                )
                            ]
                        )

        self.assertEqual(BookingRequest.objects.count(), 0)

    def test_direct_invalid_status_cannot_persist(self) -> None:
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                BookingRequest.objects.bulk_create(
                    [
                        self._unsaved_booking(
                            start_date=self.start_date,
                            end_date=self.end_date,
                            status="NOT_A_STATUS",
                        )
                    ]
                )

        self.assertEqual(BookingRequest.objects.count(), 0)

    def test_direct_valid_booking_persists_with_database_constraints(self) -> None:
        BookingRequest.objects.bulk_create(
            [
                self._unsaved_booking(
                    start_date=self.start_date,
                    end_date=self.end_date,
                )
            ]
        )

        booking_request = BookingRequest.objects.get()
        self.assertEqual(booking_request.status, BookingRequestStatus.PENDING)
        self.assertEqual(booking_request.property, self.rental_property)

    def test_backend_status_update_persists_and_notifies(self) -> None:
        booking_request = self._create_booking_without_delivery()

        with self.captureOnCommitCallbacks(execute=True):
            updated_request = update_booking_request_status(
                booking_request,
                status=BookingRequestStatus.APPROVED,
                notification_service_override=self.notification_service,
            )

        updated_request.refresh_from_db()
        self.assertEqual(updated_request.status, BookingRequestStatus.APPROVED)
        self.assertEqual(EmailNotification.objects.count(), 2)
        self.assertEqual(len(self.adapter.messages), 2)
        self.assertIn("Approved", self.adapter.messages[-1].body)

    def test_lifecycle_update_succeeds_after_start_date_has_passed(self) -> None:
        booking_request = self._create_booking_without_delivery()
        simulated_today = self.start_date + timedelta(days=1)

        with patch("homefinder.apps.interactions.models.timezone.localdate", return_value=simulated_today):
            with self.captureOnCommitCallbacks(execute=True):
                updated_request = update_booking_request_status(
                    booking_request,
                    status=BookingRequestStatus.APPROVED,
                    notification_service_override=self.notification_service,
                )

        updated_request.refresh_from_db()
        self.assertEqual(updated_request.status, BookingRequestStatus.APPROVED)
        self.assertEqual(EmailNotification.objects.count(), 2)
        self.assertEqual(len(self.adapter.messages), 2)
        self.assertIn("Approved", self.adapter.messages[-1].body)

    def test_reapplying_same_status_is_idempotent(self) -> None:
        booking_request = self._create_booking_without_delivery()
        created_notification_count = EmailNotification.objects.count()
        created_message_count = len(self.adapter.messages)
        original_updated_at = booking_request.updated_at

        with self.captureOnCommitCallbacks(execute=True):
            unchanged_request = update_booking_request_status(
                booking_request,
                status=BookingRequestStatus.PENDING,
                notification_service_override=self.notification_service,
            )

        unchanged_request.refresh_from_db()
        self.assertEqual(unchanged_request.status, BookingRequestStatus.PENDING)
        self.assertEqual(unchanged_request.updated_at, original_updated_at)
        self.assertEqual(EmailNotification.objects.count(), created_notification_count)
        self.assertEqual(len(self.adapter.messages), created_message_count)

    def test_conflicting_stale_status_updates_cannot_both_succeed_or_double_notify(self) -> None:
        booking_request = self._create_booking_without_delivery()
        stale_admin_a = BookingRequest.objects.get(pk=booking_request.pk)
        stale_admin_b = BookingRequest.objects.get(pk=booking_request.pk)

        with self.captureOnCommitCallbacks(execute=True):
            update_booking_request_status(
                stale_admin_a,
                status=BookingRequestStatus.APPROVED,
                notification_service_override=self.notification_service,
            )

        with self.assertRaises(ValidationError) as raised:
            update_booking_request_status(
                stale_admin_b,
                status=BookingRequestStatus.REJECTED,
                notification_service_override=self.notification_service,
            )

        booking_request.refresh_from_db()
        self.assertEqual(booking_request.status, BookingRequestStatus.APPROVED)
        self.assertIn("status", raised.exception.message_dict)
        self.assertEqual(EmailNotification.objects.count(), 2)
        self.assertEqual(len(self.adapter.messages), 2)
        self.assertIn("Approved", self.adapter.messages[-1].body)

    def test_invalid_status_transition_is_rejected(self) -> None:
        booking_request = self._create_booking_without_delivery()

        with self.captureOnCommitCallbacks(execute=True):
            update_booking_request_status(
                booking_request,
                status=BookingRequestStatus.REJECTED,
                notification_service_override=self.notification_service,
            )

        with self.assertRaises(ValidationError) as raised:
            update_booking_request_status(
                booking_request,
                status=BookingRequestStatus.APPROVED,
                notification_service_override=self.notification_service,
            )

        booking_request.refresh_from_db()
        self.assertEqual(booking_request.status, BookingRequestStatus.REJECTED)
        self.assertIn("status", raised.exception.message_dict)
        self.assertEqual(EmailNotification.objects.count(), 2)

    def test_failed_status_update_does_not_create_notification_or_payment_side_effects(self) -> None:
        booking_request = self._create_booking_without_delivery()

        with self.captureOnCommitCallbacks(execute=True):
            update_booking_request_status(
                booking_request,
                status=BookingRequestStatus.CANCELLED,
                notification_service_override=self.notification_service,
            )

        notification_count = EmailNotification.objects.count()
        message_count = len(self.adapter.messages)

        with self.assertRaises(ValidationError):
            update_booking_request_status(
                booking_request,
                status=BookingRequestStatus.APPROVED,
                notification_service_override=self.notification_service,
            )

        booking_request.refresh_from_db()
        self.assertEqual(booking_request.status, BookingRequestStatus.CANCELLED)
        self.assertEqual(EmailNotification.objects.count(), notification_count)
        self.assertEqual(len(self.adapter.messages), message_count)
        self.assertEqual(Payment.objects.count(), 0)

    def test_booking_flow_does_not_create_payment_records(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            booking_request = create_booking_request(
                user=self.user,
                property_obj=self.rental_property,
                start_date=self.start_date,
                end_date=self.end_date,
                notification_service_override=self.notification_service,
            )
            update_booking_request_status(
                booking_request,
                status=BookingRequestStatus.APPROVED,
                notification_service_override=self.notification_service,
            )

        self.assertEqual(Payment.objects.count(), 0)

    def test_no_public_booking_routes_are_added(self) -> None:
        for path in ("/bookings/", f"/catalog/{self.rental_property.id}/bookings/"):
            with self.subTest(path=path):
                with self.assertRaises(Resolver404):
                    resolve(path)

    def _create_booking_without_delivery(self) -> BookingRequest:
        with self.captureOnCommitCallbacks(execute=True):
            return create_booking_request(
                user=self.user,
                property_obj=self.rental_property,
                start_date=self.start_date,
                end_date=self.end_date,
                notification_service_override=self.notification_service,
            )

    def _unsaved_booking(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
        status: str = BookingRequestStatus.PENDING,
    ) -> BookingRequest:
        return BookingRequest(
            user=self.user,
            property=self.rental_property,
            start_date=start_date,
            end_date=end_date,
            status=status,
        )

    def _create_property(self, *, title: str, category: str) -> Property:
        return Property.objects.create(
            title=title,
            description=f"{title} description",
            category=category,
            city="Athens",
            area="Center",
            price=Decimal("1200.00"),
        )


class RentalBookingAdminTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            email="admin@example.com",
            password="password123",
        )
        self.client.force_login(self.admin_user)
        self.user = User.objects.create_user(
            email="renter@example.com",
            password="password123",
            full_name="Renter Example",
        )
        self.rental_property = Property.objects.create(
            title="Admin Rental",
            description="Admin Rental description",
            category=PropertyCategory.RENTAL,
            city="Athens",
            area="Center",
            price=Decimal("1300.00"),
        )
        self.residential_property = Property.objects.create(
            title="Admin Sale",
            description="Admin Sale description",
            category=PropertyCategory.RESIDENTIAL,
            city="Athens",
            area="Center",
            price=Decimal("250000.00"),
        )
        self.adapter = RecordingDeliveryAdapter()
        self.notification_service = EmailNotificationService(delivery_adapter=self.adapter)
        self.start_date = timezone.localdate() + timedelta(days=30)
        self.end_date = timezone.localdate() + timedelta(days=37)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend")
    def test_admin_can_update_status_and_note_from_change_view(self) -> None:
        booking_request = BookingRequest.objects.create(
            user=self.user,
            property=self.rental_property,
            start_date=self.start_date,
            end_date=self.end_date,
        )
        change_url = reverse("admin:interactions_bookingrequest_change", args=[booking_request.id])
        updated_note = "Approved after owner confirmation."
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            with self.captureOnCommitCallbacks(execute=True):
                with patch(
                    "homefinder.apps.interactions.admin.services.update_booking_request_status",
                    wraps=update_booking_request_status,
                ) as status_update:
                    response = self.client.post(
                        change_url,
                        data={
                            "user": str(booking_request.user_id),
                            "property": str(booking_request.property_id),
                            "start_date": self.start_date.isoformat(),
                            "end_date": self.end_date.isoformat(),
                            "status": BookingRequestStatus.APPROVED,
                            "note": updated_note,
                            "_save": "Save",
                        },
                    )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(status_update.call_count, 1)
        booking_request.refresh_from_db()
        self.assertEqual(booking_request.status, BookingRequestStatus.APPROVED)
        self.assertEqual(booking_request.note, updated_note)
        self.assertEqual(EmailNotification.objects.count(), 1)
        notification = EmailNotification.objects.get()
        self.assertEqual(notification.purpose, EmailNotificationPurpose.BOOKING_UPDATE)
        self.assertEqual(notification.status, EmailNotificationStatus.SENT)
        self.assertIn("Your HomeFinder booking request", stdout.getvalue())

    def test_admin_invalid_booking_transition_is_rejected_without_notification(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            booking_request = create_booking_request(
                user=self.user,
                property_obj=self.rental_property,
                start_date=self.start_date,
                end_date=self.end_date,
                notification_service_override=self.notification_service,
            )
            update_booking_request_status(
                booking_request,
                status=BookingRequestStatus.REJECTED,
                notification_service_override=self.notification_service,
            )

        notification_count = EmailNotification.objects.count()
        change_url = reverse("admin:interactions_bookingrequest_change", args=[booking_request.id])

        response = self.client.post(
            change_url,
            data={
                "user": str(booking_request.user_id),
                "property": str(booking_request.property_id),
                "start_date": self.start_date.isoformat(),
                "end_date": self.end_date.isoformat(),
                "status": BookingRequestStatus.APPROVED,
                "note": booking_request.note,
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 200)
        booking_request.refresh_from_db()
        self.assertEqual(booking_request.status, BookingRequestStatus.REJECTED)
        self.assertEqual(EmailNotification.objects.count(), notification_count)
        self.assertEqual(Payment.objects.count(), 0)

    def test_admin_rejects_non_rental_booking_creation(self) -> None:
        add_url = reverse("admin:interactions_bookingrequest_add")

        response = self.client.post(
            add_url,
            data={
                "user": str(self.user.id),
                "property": str(self.residential_property.id),
                "start_date": self.start_date.isoformat(),
                "end_date": self.end_date.isoformat(),
                "status": BookingRequestStatus.PENDING,
                "note": "",
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Booking requests are only supported for rental properties.")
        self.assertEqual(BookingRequest.objects.count(), 0)
        self.assertEqual(EmailNotification.objects.count(), 0)

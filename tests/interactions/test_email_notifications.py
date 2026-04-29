from __future__ import annotations

import io
from contextlib import redirect_stdout
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from homefinder.apps.interactions.models import (
    EmailNotification,
    EmailNotificationPurpose,
    EmailNotificationStatus,
    PropertyInquiry,
    ViewingRequest,
)
from homefinder.apps.interactions.services import (
    EmailNotificationMessage,
    EmailNotificationService,
    send_inquiry_confirmation_email,
    send_login_2fa_email,
    send_viewing_confirmation_email,
)
from homefinder.apps.properties.models import Property, PropertyCategory
from homefinder.apps.users.models import User


class RecordingDeliveryAdapter:
    def __init__(self, *, delivered_count: int = 1, exception: Exception | None = None) -> None:
        self.delivered_count = delivered_count
        self.exception = exception
        self.messages: list[EmailNotificationMessage] = []

    def deliver(self, message: EmailNotificationMessage) -> int:
        self.messages.append(message)
        if self.exception:
            raise self.exception
        return self.delivered_count


class EmailNotificationServiceTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="buyer@example.com",
            password="secret-pass",
            full_name="Buyer Example",
        )
        self.property = Property.objects.create(
            title="Central Apartment",
            category=PropertyCategory.RESIDENTIAL,
            city="Athens",
            price=Decimal("250000.00"),
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend")
    def test_login_2fa_email_is_persisted_and_delivered_to_console(self) -> None:
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            with self.captureOnCommitCallbacks(execute=True):
                notification = send_login_2fa_email(user=self.user, token="123456")

        notification.refresh_from_db()
        self.assertEqual(EmailNotification.objects.count(), 1)
        self.assertEqual(notification.user, self.user)
        self.assertEqual(notification.purpose, EmailNotificationPurpose.LOGIN_2FA)
        self.assertEqual(notification.recipient_email, "buyer@example.com")
        self.assertEqual(notification.status, EmailNotificationStatus.SENT)
        self.assertIsNotNone(notification.sent_at)
        self.assertIn("Your HomeFinder login code", stdout.getvalue())
        self.assertIn("123456", stdout.getvalue())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend")
    def test_inquiry_confirmation_email_uses_shared_persistence_pipeline(self) -> None:
        inquiry = PropertyInquiry.objects.create(
            user=self.user,
            property=self.property,
            message="I would like more details.",
        )
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            with self.captureOnCommitCallbacks(execute=True):
                notification = send_inquiry_confirmation_email(inquiry)

        notification.refresh_from_db()
        self.assertEqual(notification.user, self.user)
        self.assertEqual(notification.purpose, EmailNotificationPurpose.INQUIRY_CONFIRMATION)
        self.assertEqual(notification.recipient_email, "buyer@example.com")
        self.assertEqual(notification.status, EmailNotificationStatus.SENT)
        self.assertIsNotNone(notification.sent_at)
        self.assertIn("We received your HomeFinder inquiry", stdout.getvalue())
        self.assertIn("Central Apartment", stdout.getvalue())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend")
    def test_viewing_confirmation_email_uses_shared_persistence_pipeline(self) -> None:
        viewing_request = ViewingRequest.objects.create(
            user=self.user,
            property=self.property,
            requested_datetime=timezone.now() + timedelta(days=1),
            note="Afternoon preferred.",
        )
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            with self.captureOnCommitCallbacks(execute=True):
                notification = send_viewing_confirmation_email(viewing_request)

        notification.refresh_from_db()
        self.assertEqual(notification.user, self.user)
        self.assertEqual(notification.purpose, EmailNotificationPurpose.VIEWING_CONFIRMATION)
        self.assertEqual(notification.recipient_email, "buyer@example.com")
        self.assertEqual(notification.status, EmailNotificationStatus.SENT)
        self.assertIsNotNone(notification.sent_at)
        self.assertIn("Your HomeFinder viewing request", stdout.getvalue())
        self.assertIn("Central Apartment", stdout.getvalue())

    def test_shared_service_uses_delivery_adapter_boundary(self) -> None:
        adapter = RecordingDeliveryAdapter()
        service = EmailNotificationService(delivery_adapter=adapter)

        with self.captureOnCommitCallbacks(execute=True):
            notification = service.send(self._message(token="999999"))

        notification.refresh_from_db()
        self.assertEqual(notification.status, EmailNotificationStatus.SENT)
        self.assertEqual(len(adapter.messages), 1)
        self.assertEqual(adapter.messages[0].recipient_email, "buyer@example.com")

    def test_notification_attempt_is_pending_before_delivery_result(self) -> None:
        adapter = RecordingDeliveryAdapter()
        service = EmailNotificationService(delivery_adapter=adapter)

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            notification = service.send(self._message())

        notification.refresh_from_db()
        self.assertEqual(notification.status, EmailNotificationStatus.PENDING)
        self.assertEqual(adapter.messages, [])
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        notification.refresh_from_db()
        self.assertEqual(notification.status, EmailNotificationStatus.SENT)
        self.assertIsNotNone(notification.sent_at)

    def test_failed_delivery_keeps_persisted_attempt_with_failed_status_and_logs_diagnostics(self) -> None:
        adapter = RecordingDeliveryAdapter(exception=RuntimeError("delivery unavailable"))
        service = EmailNotificationService(delivery_adapter=adapter)

        with self.assertLogs("homefinder.apps.interactions.services", level="ERROR") as logs:
            with self.captureOnCommitCallbacks(execute=True):
                notification = service.send(self._message(token="123456"))

        notification.refresh_from_db()
        self.assertEqual(notification.purpose, EmailNotificationPurpose.LOGIN_2FA)
        self.assertEqual(notification.recipient_email, "buyer@example.com")
        self.assertEqual(notification.status, EmailNotificationStatus.FAILED)
        self.assertIsNone(notification.sent_at)

        log_record = logs.records[0]
        self.assertEqual(log_record.notification_id, notification.pk)
        self.assertEqual(log_record.purpose, EmailNotificationPurpose.LOGIN_2FA)
        self.assertEqual(log_record.recipient_email, "buyer@example.com")
        self.assertNotIn("123456", log_record.getMessage())
        self.assertNotIn("123456", "\n".join(logs.output))

    def test_zero_delivery_count_marks_failed_and_logs_diagnostics(self) -> None:
        adapter = RecordingDeliveryAdapter(delivered_count=0)
        service = EmailNotificationService(delivery_adapter=adapter)

        with self.assertLogs("homefinder.apps.interactions.services", level="WARNING") as logs:
            with self.captureOnCommitCallbacks(execute=True):
                notification = service.send(self._message())

        notification.refresh_from_db()
        self.assertEqual(notification.status, EmailNotificationStatus.FAILED)
        self.assertIsNone(notification.sent_at)

        log_record = logs.records[0]
        self.assertEqual(log_record.notification_id, notification.pk)
        self.assertEqual(log_record.purpose, EmailNotificationPurpose.LOGIN_2FA)
        self.assertEqual(log_record.recipient_email, "buyer@example.com")
        self.assertIn("zero recipients", log_record.getMessage())

    def test_invalid_messages_raise_validation_error_without_creating_notification(self) -> None:
        invalid_messages = (
            self._message(recipient_email=""),
            self._message(recipient_email="not-an-email"),
            self._message(subject=" "),
            self._message(body=" "),
            self._message(purpose=""),
        )

        for message in invalid_messages:
            with self.subTest(message=message):
                with self.assertRaises(ValidationError):
                    EmailNotificationService().send(message)

        self.assertEqual(EmailNotification.objects.count(), 0)

    def _message(
        self,
        *,
        purpose: EmailNotificationPurpose | str = EmailNotificationPurpose.LOGIN_2FA,
        recipient_email: str = "buyer@example.com",
        subject: str = "Your HomeFinder login code",
        body: str | None = None,
        token: str = "123456",
    ) -> EmailNotificationMessage:
        return EmailNotificationMessage(
            purpose=purpose,
            user=self.user,
            recipient_email=recipient_email,
            subject=subject,
            body=body or f"Use this HomeFinder login code:\n\n{token}",
        )


class EmailNotificationTransactionTests(TransactionTestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email="buyer@example.com", password="secret-pass")

    def test_email_is_not_sent_before_transaction_commit_and_sent_after_commit(self) -> None:
        adapter = RecordingDeliveryAdapter()
        service = EmailNotificationService(delivery_adapter=adapter)

        with transaction.atomic():
            notification = service.send(self._message())
            notification.refresh_from_db()
            self.assertEqual(notification.status, EmailNotificationStatus.PENDING)
            self.assertEqual(adapter.messages, [])

        self.assertEqual(len(adapter.messages), 1)
        notification.refresh_from_db()
        self.assertEqual(notification.status, EmailNotificationStatus.SENT)
        self.assertIsNotNone(notification.sent_at)

    def test_email_is_not_sent_when_transaction_rolls_back(self) -> None:
        adapter = RecordingDeliveryAdapter()
        service = EmailNotificationService(delivery_adapter=adapter)

        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                notification = service.send(self._message())
                notification_id = notification.pk
                notification.refresh_from_db()
                self.assertEqual(notification.status, EmailNotificationStatus.PENDING)
                raise RuntimeError("rollback outer workflow")

        self.assertEqual(adapter.messages, [])
        self.assertFalse(EmailNotification.objects.filter(pk=notification_id).exists())

    def _message(self) -> EmailNotificationMessage:
        return EmailNotificationMessage(
            purpose=EmailNotificationPurpose.LOGIN_2FA,
            user=self.user,
            recipient_email=self.user.email,
            subject="Your HomeFinder login code",
            body="Use this HomeFinder login code:\n\n123456",
        )

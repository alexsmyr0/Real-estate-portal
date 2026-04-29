from __future__ import annotations

import io
from contextlib import redirect_stdout
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.mail.backends.base import BaseEmailBackend
from django.test import TestCase, override_settings
from django.utils import timezone

from homefinder.apps.interactions.models import (
    EmailNotification,
    EmailNotificationPurpose,
    EmailNotificationStatus,
    PropertyInquiry,
    ViewingRequest,
)
from homefinder.apps.interactions.services import (
    send_inquiry_confirmation_email,
    send_login_2fa_email,
    send_viewing_confirmation_email,
)
from homefinder.apps.properties.models import Property, PropertyCategory
from homefinder.apps.users.models import User


class FailingEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages: list[object]) -> int:
        raise RuntimeError("delivery unavailable")


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
            notification = send_viewing_confirmation_email(viewing_request)

        notification.refresh_from_db()
        self.assertEqual(notification.user, self.user)
        self.assertEqual(notification.purpose, EmailNotificationPurpose.VIEWING_CONFIRMATION)
        self.assertEqual(notification.recipient_email, "buyer@example.com")
        self.assertEqual(notification.status, EmailNotificationStatus.SENT)
        self.assertIsNotNone(notification.sent_at)
        self.assertIn("Your HomeFinder viewing request", stdout.getvalue())
        self.assertIn("Central Apartment", stdout.getvalue())

    def test_notification_attempt_is_pending_before_delivery_result(self) -> None:
        observed_statuses: list[str] = []

        def deliver_message(**kwargs: object) -> int:
            observed_statuses.extend(EmailNotification.objects.values_list("status", flat=True))
            return 1

        with patch("homefinder.apps.interactions.services.send_mail", side_effect=deliver_message):
            notification = send_login_2fa_email(user=self.user, token="123456")

        self.assertEqual(
            observed_statuses,
            [EmailNotificationStatus.PENDING],
        )
        notification.refresh_from_db()
        self.assertEqual(notification.status, EmailNotificationStatus.SENT)

    @override_settings(
        EMAIL_BACKEND="tests.interactions.test_email_notifications.FailingEmailBackend"
    )
    def test_failed_delivery_keeps_persisted_attempt_with_failed_status(self) -> None:
        notification = send_login_2fa_email(user=self.user, token="123456")

        notification.refresh_from_db()
        self.assertEqual(notification.purpose, EmailNotificationPurpose.LOGIN_2FA)
        self.assertEqual(notification.recipient_email, "buyer@example.com")
        self.assertEqual(notification.status, EmailNotificationStatus.FAILED)
        self.assertIsNone(notification.sent_at)

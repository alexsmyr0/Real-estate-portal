from __future__ import annotations

import os
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django

django.setup()

from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from homefinder.apps.interactions.models import (
    ActivityLog,
    BookingRequest,
    EmailNotification,
    EmailNotificationPurpose,
    EmailNotificationStatus,
    Payment,
    PropertyInquiry,
    ViewingRequest,
    ViewingRequestStatus,
)
from homefinder.apps.interactions.services import create_viewing_request
from homefinder.apps.properties.models import Property, PropertyCategory, PropertyStatus
from homefinder.apps.users.models import User


@override_settings(
    ALLOWED_HOSTS=["testserver"],
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class ViewingRequestFlowTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.user = User.objects.create_user(
            email="viewer@example.com",
            password="StrongPassword123!",
            full_name="Viewer Example",
        )
        self.other_user = User.objects.create_user(
            email="other-viewer@example.com",
            password="StrongPassword123!",
        )
        self.available_property = self._create_property(
            title="Viewing Ready Listing",
            status=PropertyStatus.AVAILABLE,
            city="Athens",
        )
        self.unavailable_property = self._create_property(
            title="Visible Unavailable Listing",
            status=PropertyStatus.UNAVAILABLE,
            city="Patra",
        )
        self.removed_property = self._create_property(
            title="Removed Viewing Listing",
            status=PropertyStatus.REMOVED,
            city="Larisa",
        )

    def test_property_detail_page_renders_viewing_form_for_visible_property(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(f"/catalog/{self.available_property.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "properties/detail.html")
        self.assertContains(response, "Request a Viewing")
        self.assertContains(response, f"/catalog/{self.available_property.id}/viewing-request/")
        self.assertContains(response, "name=\"requested_datetime\"")
        self.assertContains(response, "type=\"datetime-local\"")

    def test_anonymous_user_sees_auth_gate_and_cannot_submit_viewing_request(self) -> None:
        detail_response = self.client.get(f"/catalog/{self.available_property.id}/?viewing=sent")

        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Sign in to request a viewing")
        self.assertNotContains(detail_response, "Viewing request sent")

        post_response = self.client.post(
            f"/catalog/{self.available_property.id}/viewing-request/",
            {"requested_datetime": self._form_datetime(timezone.now() + timedelta(days=2))},
            follow=True,
        )

        self.assertRedirects(post_response, f"/login/?next=%2Fcatalog%2F{self.available_property.id}%2F")
        self.assertContains(post_response, "Sign in to request a viewing.")
        self.assertEqual(ViewingRequest.objects.count(), 0)
        self.assertEqual(EmailNotification.objects.count(), 0)

    def test_authenticated_user_can_submit_future_viewing_request_and_get_verified_confirmation(self) -> None:
        self.client.force_login(self.user)
        requested_datetime = timezone.now() + timedelta(days=3, hours=2)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/catalog/{self.available_property.id}/viewing-request/",
                {
                    "requested_datetime": self._form_datetime(requested_datetime),
                    "note": "Afternoon works best.",
                },
                follow=True,
            )

        self.assertRedirects(response, f"/catalog/{self.available_property.id}/")
        self.assertContains(response, "Viewing request sent")
        self.assertIsNotNone(response.context["viewing_confirmation"])

        viewing_request = ViewingRequest.objects.get()
        self.assertEqual(viewing_request.user, self.user)
        self.assertEqual(viewing_request.property, self.available_property)
        self.assertEqual(viewing_request.status, ViewingRequestStatus.PENDING)
        self.assertEqual(viewing_request.note, "Afternoon works best.")
        self.assertGreater(viewing_request.requested_datetime, timezone.now())

        notification = EmailNotification.objects.get()
        self.assertEqual(notification.user, self.user)
        self.assertEqual(notification.purpose, EmailNotificationPurpose.VIEWING_CONFIRMATION)
        self.assertEqual(notification.recipient_email, "viewer@example.com")
        self.assertEqual(notification.status, EmailNotificationStatus.SENT)

        activity_log = ActivityLog.objects.get()
        self.assertEqual(activity_log.action, "viewing_requested")
        self.assertEqual(activity_log.user, self.user)
        self.assertEqual(activity_log.entity_type, "viewingrequest")
        self.assertEqual(activity_log.entity_id, viewing_request.id)
        self.assertEqual(activity_log.details["surface"], "detail")

        self.assertEqual(PropertyInquiry.objects.count(), 0)
        self.assertEqual(BookingRequest.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)

    def test_success_confirmation_is_one_time_and_not_query_parameter_driven(self) -> None:
        self.client.force_login(self.user)

        forged_response = self.client.get(f"/catalog/{self.available_property.id}/?viewing=sent")
        self.assertEqual(forged_response.status_code, 200)
        self.assertNotContains(forged_response, "Viewing request sent")

        with self.captureOnCommitCallbacks(execute=True):
            success_response = self.client.post(
                f"/catalog/{self.available_property.id}/viewing-request/",
                {"requested_datetime": self._form_datetime(timezone.now() + timedelta(days=1))},
                follow=True,
            )

        self.assertContains(success_response, "Viewing request sent")
        self.assertEqual(EmailNotification.objects.count(), 1)

        refresh_response = self.client.get(f"/catalog/{self.available_property.id}/")
        self.assertEqual(refresh_response.status_code, 200)
        self.assertNotContains(refresh_response, "Viewing request sent")
        self.assertIsNone(refresh_response.context["viewing_confirmation"])
        self.assertEqual(ViewingRequest.objects.count(), 1)
        self.assertEqual(EmailNotification.objects.count(), 1)

    def test_invalid_viewing_datetimes_return_clear_feedback_without_persistence(self) -> None:
        self.client.force_login(self.user)
        invalid_cases = (
            ({}, "Choose a future date and time for the viewing."),
            ({"requested_datetime": "not-a-date"}, "Enter a valid date and time."),
            (
                {"requested_datetime": self._form_datetime(timezone.now() - timedelta(days=1))},
                "Choose a date and time in the future.",
            ),
            (
                {"requested_datetime": self._form_datetime(timezone.now())},
                "Choose a date and time in the future.",
            ),
        )

        for payload, expected_error in invalid_cases:
            with self.subTest(payload=payload):
                response = self.client.post(
                    f"/catalog/{self.available_property.id}/viewing-request/",
                    payload,
                )

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "properties/detail.html")
                self.assertContains(response, expected_error)
                self.assertEqual(ViewingRequest.objects.count(), 0)
                self.assertEqual(EmailNotification.objects.count(), 0)

    def test_non_visible_property_rejects_viewing_submission(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(
            f"/catalog/{self.removed_property.id}/viewing-request/",
            {"requested_datetime": self._form_datetime(timezone.now() + timedelta(days=1))},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(ViewingRequest.objects.count(), 0)
        self.assertEqual(EmailNotification.objects.count(), 0)

    def test_visible_unavailable_property_can_receive_viewing_request(self) -> None:
        self.client.force_login(self.user)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/catalog/{self.unavailable_property.id}/viewing-request/",
                {"requested_datetime": self._form_datetime(timezone.now() + timedelta(days=4))},
                follow=True,
            )

        self.assertRedirects(response, f"/catalog/{self.unavailable_property.id}/")
        self.assertContains(response, "Viewing request sent")
        self.assertTrue(
            ViewingRequest.objects.filter(
                user=self.user,
                property=self.unavailable_property,
            ).exists()
        )

    def test_removed_property_blocks_new_viewing_requests_but_preserves_existing_records(self) -> None:
        viewing_request = ViewingRequest.objects.create(
            user=self.user,
            property=self.available_property,
            requested_datetime=timezone.now() + timedelta(days=5),
            note="Initial note.",
        )
        self.available_property.status = PropertyStatus.REMOVED
        self.available_property.save(update_fields=["status", "updated_at"])

        viewing_request.note = "Updated after listing removal."
        viewing_request.save(update_fields=["note", "updated_at"])

        viewing_request.refresh_from_db()
        self.assertEqual(viewing_request.note, "Updated after listing removal.")

        self.client.force_login(self.user)
        response = self.client.post(
            f"/catalog/{self.available_property.id}/viewing-request/",
            {"requested_datetime": self._form_datetime(timezone.now() + timedelta(days=6))},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(ViewingRequest.objects.count(), 1)

    def test_notification_delivery_failure_keeps_persisted_viewing_request_and_marks_attempt_failed(self) -> None:
        self.client.force_login(self.user)

        with self.assertLogs("homefinder.apps.interactions.services", level="ERROR"):
            with patch(
                "homefinder.apps.interactions.services.DjangoEmailDeliveryAdapter.deliver",
                side_effect=RuntimeError("mail backend unavailable"),
            ):
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.client.post(
                        f"/catalog/{self.available_property.id}/viewing-request/",
                        {"requested_datetime": self._form_datetime(timezone.now() + timedelta(days=2))},
                        follow=True,
                    )

        self.assertRedirects(response, f"/catalog/{self.available_property.id}/")
        self.assertEqual(ViewingRequest.objects.count(), 1)
        notification = EmailNotification.objects.get()
        self.assertEqual(notification.purpose, EmailNotificationPurpose.VIEWING_CONFIRMATION)
        self.assertEqual(notification.status, EmailNotificationStatus.FAILED)

    def test_logging_failure_does_not_break_viewing_persistence_or_notification(self) -> None:
        self.client.force_login(self.user)

        with self.assertLogs("homefinder.apps.properties.views", level="ERROR"):
            with patch(
                "homefinder.apps.properties.views.log_interaction_activity",
                side_effect=RuntimeError("logger down"),
            ):
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.client.post(
                        f"/catalog/{self.available_property.id}/viewing-request/",
                        {"requested_datetime": self._form_datetime(timezone.now() + timedelta(days=2))},
                        follow=True,
                    )

        self.assertRedirects(response, f"/catalog/{self.available_property.id}/")
        self.assertEqual(ViewingRequest.objects.count(), 1)
        self.assertEqual(EmailNotification.objects.count(), 1)
        self.assertEqual(ActivityLog.objects.count(), 0)

    def test_service_rejects_note_longer_than_500_characters(self) -> None:
        with self.assertRaises(ValidationError) as context:
            create_viewing_request(
                user=self.user,
                property_obj=self.available_property,
                requested_datetime=timezone.now() + timedelta(days=2),
                note="x" * 501,
            )

        self.assertIn("note", context.exception.message_dict)
        self.assertEqual(ViewingRequest.objects.count(), 0)
        self.assertEqual(EmailNotification.objects.count(), 0)

    def test_confirmation_marker_does_not_leak_to_other_user_on_shared_session(self) -> None:
        self.client.force_login(self.user)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                f"/catalog/{self.available_property.id}/viewing-request/",
                {"requested_datetime": self._form_datetime(timezone.now() + timedelta(days=1))},
                follow=True,
            )

        self.client.force_login(self.other_user)
        response = self.client.get(f"/catalog/{self.available_property.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Viewing request sent")
        self.assertIsNone(response.context["viewing_confirmation"])

    def _create_property(self, *, title: str, status: str, city: str) -> Property:
        return Property.objects.create(
            title=title,
            description=f"{title} description",
            category=PropertyCategory.RESIDENTIAL,
            status=status,
            city=city,
            area="Center",
            address_line=f"{city} address",
            price=Decimal("255000.00"),
            bedrooms=2,
            bathrooms=Decimal("1.5"),
        )

    def _form_datetime(self, value: object) -> str:
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.strftime("%Y-%m-%dT%H:%M")

from __future__ import annotations

import io
from contextlib import redirect_stdout
from decimal import Decimal
from urllib.parse import urlencode
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from homefinder.apps.interactions.models import (
    ActivityLog,
    EmailNotification,
    EmailNotificationPurpose,
    EmailNotificationStatus,
    PROPERTY_INQUIRY_MESSAGE_MAX_LENGTH,
    PropertyInquiry,
    PropertyInquiryStatus,
    UserFavorite,
)
from homefinder.apps.interactions.services import (
    EmailNotificationMessage,
    EmailNotificationService,
    create_property_inquiry,
)
from homefinder.apps.properties.models import (
    Amenity,
    Property,
    PropertyCategory,
    PropertyImage,
    PropertyStatus,
)
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


@override_settings(ALLOWED_HOSTS=["testserver"])
class PropertyInquiryFlowTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.user = User.objects.create_user(
            email="buyer@example.com",
            password="password123",
            full_name="Buyer Example",
        )
        self.property = self._create_property(title="Central Inquiry Apartment")
        self.pool = Amenity.objects.create(name="Pool")
        self.property.amenities.add(self.pool)
        PropertyImage.objects.create(
            property=self.property,
            image_url="https://example.com/central-apartment.jpg",
        )
        self.detail_url = reverse("site-property-detail", args=[self.property.id])
        self.inquiry_url = reverse("site-inquiry-create", args=[self.property.id])

    def test_authenticated_user_can_access_detail_inquiry_flow(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "properties/detail.html")
        self.assertContains(response, "Central Inquiry Apartment")
        self.assertContains(response, "Send an inquiry")
        self.assertContains(response, 'name="message"')
        self.assertContains(response, "Pool")

    def test_forged_query_confirmation_does_not_render_success_for_authenticated_user(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(f"{self.detail_url}?inquiry=sent")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "We received your inquiry")
        self.assertNotContains(response, "Inquiry sent. We emailed you a confirmation.")
        self.assertContains(response, "Send an inquiry")
        self.assertContains(response, 'name="message"')
        self.assertEqual(PropertyInquiry.objects.count(), 0)

    def test_anonymous_query_confirmation_still_shows_auth_gating(self) -> None:
        response = self.client.get(f"{self.detail_url}?inquiry=sent")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "We received your inquiry")
        self.assertNotContains(response, "Inquiry sent. We emailed you a confirmation.")
        self.assertContains(response, "Sign in to send an inquiry")
        self.assertNotContains(response, 'name="message"')

    def test_anonymous_user_sees_sign_in_prompt_and_cannot_submit(self) -> None:
        get_response = self.client.get(self.detail_url)

        self.assertEqual(get_response.status_code, 200)
        self.assertContains(get_response, "Sign in to send an inquiry")
        self.assertNotContains(get_response, 'name="message"')

        post_response = self.client.post(self.inquiry_url, {"message": "Please send more details."})

        self.assertEqual(post_response.status_code, 302)
        self.assertEqual(
            post_response["Location"],
            f"{reverse('login-page')}?{urlencode({'next': self.detail_url})}",
        )
        self.assertEqual(PropertyInquiry.objects.count(), 0)
        self.assertEqual(EmailNotification.objects.count(), 0)
        self.assertEqual(ActivityLog.objects.count(), 0)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend")
    def test_valid_submission_persists_confirms_notifies_and_logs(self) -> None:
        self.client.force_login(self.user)
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    self.inquiry_url,
                    {"message": " I would like to know the monthly maintenance costs. "},
                    follow=True,
                )

        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, self.detail_url)
        self.assertContains(response, "Inquiry sent. We emailed you a confirmation.")
        self.assertContains(response, "Send an inquiry")

        inquiry = PropertyInquiry.objects.get()
        self.assertEqual(inquiry.user, self.user)
        self.assertEqual(inquiry.property, self.property)
        self.assertEqual(inquiry.message, "I would like to know the monthly maintenance costs.")
        self.assertEqual(inquiry.status, PropertyInquiryStatus.OPEN)

        notification = EmailNotification.objects.get()
        self.assertEqual(notification.user, self.user)
        self.assertEqual(notification.purpose, EmailNotificationPurpose.INQUIRY_CONFIRMATION)
        self.assertEqual(notification.recipient_email, "buyer@example.com")
        self.assertEqual(notification.status, EmailNotificationStatus.SENT)
        self.assertIn("We received your HomeFinder inquiry", stdout.getvalue())

        activity_log = ActivityLog.objects.get()
        self.assertEqual(activity_log.action, "inquiry_submitted")
        self.assertEqual(activity_log.user, self.user)
        self.assertEqual(activity_log.entity_type, "property_inquiry")
        self.assertEqual(activity_log.entity_id, inquiry.id)
        self.assertEqual(activity_log.details["property_id"], self.property.id)
        self.assertEqual(activity_log.details["surface"], "property_detail")

        refreshed_response = self.client.get(self.detail_url)
        self.assertNotContains(refreshed_response, "Inquiry sent. We emailed you a confirmation.")
        self.assertContains(refreshed_response, "Send an inquiry")

    def test_detail_page_preserves_existing_favorite_state_with_inquiry_section(self) -> None:
        UserFavorite.objects.create(user=self.user, property=self.property)
        self.client.force_login(self.user)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["property"]["is_favorited"])
        self.assertContains(response, "Send an inquiry")
        self.assertContains(response, 'name="message"')

    def test_missing_message_shows_field_error_without_persistence(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(self.inquiry_url, {"message": ""})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "properties/detail.html")
        self.assertContains(response, "Tell us what you would like to know.")
        self.assertContains(response, "Please correct the highlighted fields")
        self.assertTrue(response.context["inquiry_form"].is_bound)
        self.assertEqual(PropertyInquiry.objects.count(), 0)
        self.assertEqual(EmailNotification.objects.count(), 0)
        self.assertEqual(ActivityLog.objects.count(), 0)

    def test_overlong_message_preserves_value_and_shows_field_error(self) -> None:
        self.client.force_login(self.user)
        message = "a" * (PROPERTY_INQUIRY_MESSAGE_MAX_LENGTH + 1)

        response = self.client.post(self.inquiry_url, {"message": message})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Keep your inquiry to {PROPERTY_INQUIRY_MESSAGE_MAX_LENGTH} characters or fewer.")
        self.assertEqual(response.context["inquiry_form"].data["message"], message)
        self.assertEqual(PropertyInquiry.objects.count(), 0)

    def test_invalid_property_returns_not_found_without_persistence(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("site-inquiry-create", args=[999999]),
            {"message": "Is this still available?"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(PropertyInquiry.objects.count(), 0)
        self.assertEqual(EmailNotification.objects.count(), 0)

    def test_removed_property_is_not_visible_or_submittable(self) -> None:
        self.client.force_login(self.user)
        removed_property = self._create_property(
            title="Removed Listing",
            status=PropertyStatus.REMOVED,
        )
        removed_url = reverse("site-property-detail", args=[removed_property.id])
        removed_inquiry_url = reverse("site-inquiry-create", args=[removed_property.id])

        get_response = self.client.get(removed_url)
        post_response = self.client.post(removed_inquiry_url, {"message": "Can I ask about this?"})

        self.assertEqual(get_response.status_code, 404)
        self.assertEqual(post_response.status_code, 404)
        self.assertEqual(PropertyInquiry.objects.count(), 0)
        self.assertEqual(EmailNotification.objects.count(), 0)

    def test_unavailable_public_listing_accepts_inquiry_because_it_is_visible(self) -> None:
        self.client.force_login(self.user)
        unavailable_property = self._create_property(
            title="Unavailable But Public Listing",
            status=PropertyStatus.UNAVAILABLE,
        )
        unavailable_inquiry_url = reverse("site-inquiry-create", args=[unavailable_property.id])

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                unavailable_inquiry_url,
                {"message": "Please let me know if this becomes available again."},
            )

        self.assertEqual(response.status_code, 302)
        inquiry = PropertyInquiry.objects.get()
        self.assertEqual(inquiry.property, unavailable_property)
        self.assertEqual(EmailNotification.objects.count(), 1)
        self.assertEqual(ActivityLog.objects.count(), 1)

    def test_catalog_cards_link_to_detail_flow(self) -> None:
        response = self.client.get(reverse("site-catalog"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.detail_url)
        self.assertContains(response, "View details")

    def test_service_rejects_invalid_inputs_before_side_effects(self) -> None:
        removed_property = self._create_property(
            title="Hidden Service Listing",
            status=PropertyStatus.REMOVED,
        )

        invalid_cases = (
            {"property_obj": self.property, "message": ""},
            {"property_obj": removed_property, "message": "Can I ask about this?"},
            {"property_obj": Property(id=999999), "message": "Can I ask about this?"},
        )

        for invalid_case in invalid_cases:
            with self.subTest(invalid_case=invalid_case):
                with self.assertRaises(ValidationError):
                    create_property_inquiry(
                        user=self.user,
                        notification_service_override=EmailNotificationService(
                            delivery_adapter=RecordingDeliveryAdapter(),
                        ),
                        **invalid_case,
                    )

        self.assertEqual(PropertyInquiry.objects.count(), 0)
        self.assertEqual(EmailNotification.objects.count(), 0)
        self.assertEqual(ActivityLog.objects.count(), 0)

    def test_service_accepts_unsaved_property_id_shape_for_available_property(self) -> None:
        adapter = RecordingDeliveryAdapter()

        with self.captureOnCommitCallbacks(execute=True):
            inquiry = create_property_inquiry(
                user=self.user,
                property_obj=Property(id=self.property.id),
                message="Please share the latest disclosure package.",
                notification_service_override=EmailNotificationService(delivery_adapter=adapter),
            )

        self.assertEqual(inquiry.property, self.property)
        self.assertEqual(inquiry.status, PropertyInquiryStatus.OPEN)
        self.assertEqual(inquiry.message, "Please share the latest disclosure package.")
        self.assertEqual(PropertyInquiry.objects.count(), 1)
        self.assertEqual(EmailNotification.objects.count(), 1)
        self.assertEqual(ActivityLog.objects.count(), 1)
        self.assertEqual(len(adapter.messages), 1)

    def test_service_rejects_removed_property_id_before_side_effects(self) -> None:
        removed_property = self._create_property(
            title="Removed Direct Inquiry Listing",
            status=PropertyStatus.REMOVED,
        )

        with self.assertRaises(ValidationError):
            create_property_inquiry(
                user=self.user,
                property_obj=Property(id=removed_property.id),
                message="Can I ask about this removed listing?",
                notification_service_override=EmailNotificationService(
                    delivery_adapter=RecordingDeliveryAdapter(),
                ),
            )

        self.assertEqual(PropertyInquiry.objects.count(), 0)
        self.assertEqual(EmailNotification.objects.count(), 0)
        self.assertEqual(ActivityLog.objects.count(), 0)

    def test_existing_inquiry_remains_editable_after_property_removal(self) -> None:
        inquiry = PropertyInquiry.objects.create(
            user=self.user,
            property=self.property,
            message="Original inquiry message.",
            status=PropertyInquiryStatus.OPEN,
        )
        Property.objects.filter(pk=self.property.pk).update(status=PropertyStatus.REMOVED)

        inquiry = PropertyInquiry.objects.get(pk=inquiry.pk)
        inquiry.message = "Updated historical inquiry message."
        inquiry.status = PropertyInquiryStatus.IN_PROGRESS
        inquiry.save()

        inquiry.refresh_from_db()
        self.assertEqual(inquiry.message, "Updated historical inquiry message.")
        self.assertEqual(inquiry.status, PropertyInquiryStatus.IN_PROGRESS)
        self.assertEqual(PropertyInquiry.objects.count(), 1)

    def test_logging_failure_is_noop_safe_and_does_not_duplicate_inquiry(self) -> None:
        adapter = RecordingDeliveryAdapter()
        notification_service = EmailNotificationService(delivery_adapter=adapter)

        with patch(
            "homefinder.apps.interactions.activity_logging.ActivityLog.objects.create",
            side_effect=RuntimeError("activity write failed"),
        ):
            with self.assertLogs("homefinder.apps.interactions.activity_logging", level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    inquiry = create_property_inquiry(
                        user=self.user,
                        property_obj=self.property,
                        message="Please send a floor plan.",
                        notification_service_override=notification_service,
                    )

        self.assertEqual(PropertyInquiry.objects.count(), 1)
        self.assertEqual(PropertyInquiry.objects.get(), inquiry)
        self.assertEqual(EmailNotification.objects.count(), 1)
        self.assertEqual(len(adapter.messages), 1)
        self.assertEqual(ActivityLog.objects.count(), 0)

    def test_notification_delivery_failure_keeps_single_inquiry_and_failed_notification(self) -> None:
        adapter = RecordingDeliveryAdapter(exception=RuntimeError("delivery unavailable"))
        notification_service = EmailNotificationService(delivery_adapter=adapter)

        with self.assertLogs("homefinder.apps.interactions.services", level="ERROR"):
            with self.captureOnCommitCallbacks(execute=True):
                inquiry = create_property_inquiry(
                    user=self.user,
                    property_obj=self.property,
                    message="Please send financing details.",
                    notification_service_override=notification_service,
                )

        notification = EmailNotification.objects.get()
        self.assertEqual(PropertyInquiry.objects.count(), 1)
        self.assertEqual(PropertyInquiry.objects.get(), inquiry)
        self.assertEqual(notification.purpose, EmailNotificationPurpose.INQUIRY_CONFIRMATION)
        self.assertEqual(notification.status, EmailNotificationStatus.FAILED)
        self.assertEqual(len(adapter.messages), 1)
        self.assertEqual(ActivityLog.objects.count(), 1)

    def _create_property(
        self,
        *,
        title: str,
        status: str = PropertyStatus.AVAILABLE,
    ) -> Property:
        return Property.objects.create(
            title=title,
            description=f"{title} description",
            category=PropertyCategory.RESIDENTIAL,
            status=status,
            city="Athens",
            area="Center",
            address_line="1 Syntagma Square",
            price=Decimal("250000.00"),
            bedrooms=2,
            bathrooms=Decimal("1.5"),
        )

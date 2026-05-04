"""Interaction-facing service helpers for logging and notifications."""
from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Protocol

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import models, transaction
from django.utils import timezone

from .activity_logging import (
    ActivityLoggingResult as ActivityLoggingResult,
    ActivityLoggingService as ActivityLoggingService,
    activity_logging_service as activity_logging_service,
    log_activity as log_activity,
    log_auth_activity as log_auth_activity,
    log_interaction_activity as log_interaction_activity,
    log_search_activity as log_search_activity,
)
from .models import (
    EmailNotification,
    EmailNotificationPurpose,
    EmailNotificationStatus,
    PropertyInquiry,
    ViewingRequest,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EmailNotificationMessage:
    """Provider-neutral email content plus persistence metadata."""

    purpose: EmailNotificationPurpose
    recipient_email: str
    subject: str
    body: str
    user: models.Model | None = None


class EmailDeliveryAdapter(Protocol):
    def deliver(self, message: EmailNotificationMessage) -> int: ...


class DjangoEmailDeliveryAdapter:
    """Deliver email through Django's configured email backend."""

    def deliver(self, message: EmailNotificationMessage) -> int:
        return send_mail(
            subject=message.subject,
            message=message.body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[message.recipient_email],
            fail_silently=False,
        )


class EmailNotificationService:
    """Persist and deliver MVP email notifications through Django email."""

    def __init__(self, delivery_adapter: EmailDeliveryAdapter | None = None) -> None:
        self.delivery_adapter = delivery_adapter or DjangoEmailDeliveryAdapter()

    def send(self, message: EmailNotificationMessage) -> EmailNotification:
        message = self._validate_message(message)
        notification = EmailNotification.objects.create(
            user=message.user,
            purpose=message.purpose,
            recipient_email=message.recipient_email,
            status=EmailNotificationStatus.PENDING,
        )

        connection = transaction.get_connection()
        transaction.on_commit(lambda: self._deliver(notification.pk, message))

        if not connection.in_atomic_block:
            notification.refresh_from_db()

        return notification

    def _deliver(self, notification_id: int, message: EmailNotificationMessage) -> None:
        try:
            delivered_count = self.delivery_adapter.deliver(message)
        except Exception:
            logger.exception(
                "Email notification delivery failed.",
                extra={
                    "notification_id": notification_id,
                    "purpose": message.purpose,
                    "recipient_email": message.recipient_email,
                },
            )
            self._mark_failed(notification_id)
            return

        if delivered_count:
            self._mark_sent(notification_id)
            return

        logger.warning(
            "Email notification delivery returned zero recipients.",
            extra={
                "notification_id": notification_id,
                "purpose": message.purpose,
                "recipient_email": message.recipient_email,
            },
        )
        self._mark_failed(notification_id)

    def _mark_sent(self, notification_id: int) -> None:
        EmailNotification.objects.filter(
            pk=notification_id,
            status=EmailNotificationStatus.PENDING,
        ).update(
            status=EmailNotificationStatus.SENT,
            sent_at=timezone.now(),
        )

    def _mark_failed(self, notification_id: int) -> None:
        EmailNotification.objects.filter(
            pk=notification_id,
            status=EmailNotificationStatus.PENDING,
        ).update(status=EmailNotificationStatus.FAILED)

    def _validate_message(self, message: EmailNotificationMessage) -> EmailNotificationMessage:
        recipient_email = (message.recipient_email or "").strip()
        subject = (message.subject or "").strip()
        body = (message.body or "").strip()

        if message.purpose not in EmailNotificationPurpose.values:
            raise ValidationError({"purpose": "Email notification purpose is required and must be valid."})
        if not recipient_email:
            raise ValidationError({"recipient_email": "Recipient email is required."})

        validate_email(recipient_email)

        if not subject:
            raise ValidationError({"subject": "Email subject is required."})
        if not body:
            raise ValidationError({"body": "Email body is required."})

        return replace(
            message,
            recipient_email=recipient_email,
            subject=subject,
            body=body,
        )

    def send_login_2fa(self, *, user: models.Model, token: str) -> EmailNotification:
        return self.send(
            EmailNotificationMessage(
                purpose=EmailNotificationPurpose.LOGIN_2FA,
                user=user,
                recipient_email=getattr(user, "email"),
                subject="Your HomeFinder login code",
                body=(
                    "Use this HomeFinder login code to finish signing in:\n\n"
                    f"{token}\n\n"
                    "If you did not request this code, you can ignore this email."
                ),
            )
        )

    def send_inquiry_confirmation(self, inquiry: PropertyInquiry) -> EmailNotification:
        return self.send(
            EmailNotificationMessage(
                purpose=EmailNotificationPurpose.INQUIRY_CONFIRMATION,
                user=inquiry.user,
                recipient_email=inquiry.user.email,
                subject="We received your HomeFinder inquiry",
                body=(
                    f"We received your inquiry for {inquiry.property.title} "
                    f"in {inquiry.property.city}.\n\n"
                    "A HomeFinder team member will review it and follow up."
                ),
            )
        )

    def send_viewing_confirmation(self, viewing_request: ViewingRequest) -> EmailNotification:
        requested_at = timezone.localtime(viewing_request.requested_datetime)
        formatted_datetime = requested_at.strftime("%Y-%m-%d %H:%M %Z").strip()

        return self.send(
            EmailNotificationMessage(
                purpose=EmailNotificationPurpose.VIEWING_CONFIRMATION,
                user=viewing_request.user,
                recipient_email=viewing_request.user.email,
                subject="Your HomeFinder viewing request",
                body=(
                    f"We received your viewing request for {viewing_request.property.title} "
                    f"in {viewing_request.property.city}.\n\n"
                    f"Requested time: {formatted_datetime}\n\n"
                    "A HomeFinder team member will confirm availability."
                ),
            )
        )

    def send_similar_listing_alert(self, *, subscription: models.Model, property_obj: models.Model) -> EmailNotification:
        return self.send(
            EmailNotificationMessage(
                purpose=EmailNotificationPurpose.SIMILAR_LISTING_ALERT,
                user=subscription.user,
                recipient_email=subscription.user.email,
                subject="A similar HomeFinder listing is available",
                body=(
                    f"A listing similar to your saved alert is now available: {property_obj.title} "
                    f"in {property_obj.city}.\n\n"
                    f"Price: {property_obj.price}\n"
                    f"Bedrooms: {property_obj.bedrooms if property_obj.bedrooms is not None else 'Not specified'}\n\n"
                    "Visit HomeFinder to review the listing details."
                ),
            )
        )


notification_service = EmailNotificationService()


def send_login_2fa_email(*, user: models.Model, token: str) -> EmailNotification:
    return notification_service.send_login_2fa(user=user, token=token)


def send_inquiry_confirmation_email(inquiry: PropertyInquiry) -> EmailNotification:
    return notification_service.send_inquiry_confirmation(inquiry)


def send_viewing_confirmation_email(viewing_request: ViewingRequest) -> EmailNotification:
    return notification_service.send_viewing_confirmation(viewing_request)


def send_similar_listing_alert_email(*, subscription: models.Model, property_obj: models.Model) -> EmailNotification:
    return notification_service.send_similar_listing_alert(subscription=subscription, property_obj=property_obj)

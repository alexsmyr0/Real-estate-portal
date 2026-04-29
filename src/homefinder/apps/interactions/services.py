"""Email notification delivery services for interaction-facing workflows."""
from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.core.mail import send_mail
from django.db import models
from django.utils import timezone

from .models import (
    EmailNotification,
    EmailNotificationPurpose,
    EmailNotificationStatus,
    PropertyInquiry,
    ViewingRequest,
)


@dataclass(frozen=True, slots=True)
class EmailNotificationMessage:
    """Provider-neutral email content plus persistence metadata."""

    purpose: EmailNotificationPurpose
    recipient_email: str
    subject: str
    body: str
    user: models.Model | None = None


class EmailNotificationService:
    """Persist and deliver MVP email notifications through Django email."""

    def send(self, message: EmailNotificationMessage) -> EmailNotification:
        notification = EmailNotification.objects.create(
            user=message.user,
            purpose=message.purpose,
            recipient_email=message.recipient_email,
            status=EmailNotificationStatus.PENDING,
        )

        try:
            delivered_count = send_mail(
                subject=message.subject,
                message=message.body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[message.recipient_email],
                fail_silently=False,
            )
        except Exception:
            notification.status = EmailNotificationStatus.FAILED
            notification.save(update_fields=["status"])
            return notification

        if delivered_count:
            notification.status = EmailNotificationStatus.SENT
            notification.sent_at = timezone.now()
            notification.save(update_fields=["status", "sent_at"])
        else:
            notification.status = EmailNotificationStatus.FAILED
            notification.save(update_fields=["status"])

        return notification

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


notification_service = EmailNotificationService()


def send_login_2fa_email(*, user: models.Model, token: str) -> EmailNotification:
    return notification_service.send_login_2fa(user=user, token=token)


def send_inquiry_confirmation_email(inquiry: PropertyInquiry) -> EmailNotification:
    return notification_service.send_inquiry_confirmation(inquiry)


def send_viewing_confirmation_email(viewing_request: ViewingRequest) -> EmailNotification:
    return notification_service.send_viewing_confirmation(viewing_request)

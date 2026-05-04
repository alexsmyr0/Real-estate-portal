from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from homefinder.apps.properties.models import Property, PropertyCategory


class ViewingRequestStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    CONFIRMED = "CONFIRMED", "Confirmed"
    CANCELLED = "CANCELLED", "Cancelled"
    COMPLETED = "COMPLETED", "Completed"


class PropertyInquiryStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    CLOSED = "CLOSED", "Closed"


class BookingRequestStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    CANCELLED = "CANCELLED", "Cancelled"


ALLOWED_BOOKING_STATUS_TRANSITIONS: dict[str, set[str]] = {
    BookingRequestStatus.PENDING: {
        BookingRequestStatus.APPROVED,
        BookingRequestStatus.REJECTED,
        BookingRequestStatus.CANCELLED,
    },
    BookingRequestStatus.APPROVED: {
        BookingRequestStatus.CANCELLED,
    },
    BookingRequestStatus.REJECTED: set(),
    BookingRequestStatus.CANCELLED: set(),
}


class PaymentPurpose(models.TextChoices):
    BOOKING_FEE = "BOOKING_FEE", "Booking fee"
    PREMIUM_SERVICE = "PREMIUM_SERVICE", "Premium service"
    OTHER = "OTHER", "Other"


class PaymentMethod(models.TextChoices):
    CREDIT_CARD = "CREDIT_CARD", "Credit card"
    BANK_TRANSFER = "BANK_TRANSFER", "Bank transfer"


class PaymentStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PAID = "PAID", "Paid"
    FAILED = "FAILED", "Failed"
    REFUNDED = "REFUNDED", "Refunded"


class EmailNotificationPurpose(models.TextChoices):
    LOGIN_2FA = "LOGIN_2FA", "Login 2FA"
    VIEWING_CONFIRMATION = "VIEWING_CONFIRMATION", "Viewing confirmation"
    INQUIRY_CONFIRMATION = "INQUIRY_CONFIRMATION", "Inquiry confirmation"
    BOOKING_UPDATE = "BOOKING_UPDATE", "Booking update"
    SIMILAR_LISTING_ALERT = "SIMILAR_LISTING_ALERT", "Similar listing alert"


class EmailNotificationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    SENT = "SENT", "Sent"
    FAILED = "FAILED", "Failed"


class SimilarListingAlertDispatchStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    SENT = "SENT", "Sent"
    FAILED = "FAILED", "Failed"


class ActivityScope(models.TextChoices):
    AUTH = "AUTH", "Auth"
    SEARCH = "SEARCH", "Search"
    INTERACTION = "INTERACTION", "Interaction"
    TRANSACTION = "TRANSACTION", "Transaction"
    SYSTEM = "SYSTEM", "System"


class UserFavorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_favorites"
        constraints = [
            models.UniqueConstraint(fields=["user", "property"], name="uq_user_favorites_user_property"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.property_id}"


class ViewingRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="viewing_requests")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="viewing_requests")
    requested_datetime = models.DateTimeField()
    status = models.CharField(max_length=16, choices=ViewingRequestStatus.choices, default=ViewingRequestStatus.PENDING)
    note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "viewing_requests"
        ordering = ["-requested_datetime"]

    def __str__(self) -> str:
        return f"ViewingRequest<{self.pk}>"


class PropertyInquiry(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="property_inquiries")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="property_inquiries")
    message = models.TextField()
    status = models.CharField(max_length=16, choices=PropertyInquiryStatus.choices, default=PropertyInquiryStatus.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "property_inquiries"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Inquiry<{self.pk}>"


class BookingRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="booking_requests")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="booking_requests")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=BookingRequestStatus.choices, default=BookingRequestStatus.PENDING)
    note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "booking_requests"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(start_date__isnull=False),
                name="ck_booking_start_date_required",
            ),
            models.CheckConstraint(
                check=models.Q(end_date__isnull=False),
                name="ck_booking_end_date_required",
            ),
            models.CheckConstraint(
                check=models.Q(start_date__isnull=True)
                | models.Q(end_date__isnull=True)
                | models.Q(end_date__gt=models.F("start_date")),
                name="ck_booking_valid_date_range",
            ),
            models.CheckConstraint(
                check=models.Q(status__in=BookingRequestStatus.values),
                name="ck_booking_status_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"BookingRequest<{self.pk}>"

    def clean(self) -> None:
        super().clean()

        errors: dict[str, str] = {}

        if self.property_id is not None and self.property.category != PropertyCategory.RENTAL:
            errors["property"] = "Booking requests are only supported for rental properties."

        if self.start_date is None:
            errors["start_date"] = "Booking start date is required."
        if self.end_date is None:
            errors["end_date"] = "Booking end date is required."
        if self.start_date is not None and self.end_date is not None and self.end_date <= self.start_date:
            errors["end_date"] = "Booking end date must be after the start date."

        if self.user_id is not None and not (self.user.email or "").strip():
            errors["user"] = "Booking requests require a requester with an email address."

        if self.pk is None and self.status != BookingRequestStatus.PENDING:
            errors["status"] = "New booking requests must start as pending."
        elif self.pk is not None:
            previous_status = (
                type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            )
            if previous_status is not None and self.status != previous_status:
                allowed_statuses = ALLOWED_BOOKING_STATUS_TRANSITIONS.get(previous_status, set())
                if self.status not in allowed_statuses:
                    errors["status"] = (
                        f"Booking requests cannot move from {previous_status} to {self.status}."
                    )

        if errors:
            raise ValidationError(errors)

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class Payment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments")
    booking_request = models.ForeignKey(
        BookingRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    payment_purpose = models.CharField(max_length=20, choices=PaymentPurpose.choices, default=PaymentPurpose.OTHER)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=16, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payments"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Payment<{self.pk}>"


class EmailNotification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_notifications",
    )
    purpose = models.CharField(max_length=24, choices=EmailNotificationPurpose.choices)
    recipient_email = models.EmailField()
    status = models.CharField(max_length=16, choices=EmailNotificationStatus.choices, default=EmailNotificationStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "email_notifications"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.purpose}:{self.recipient_email}"


class SimilarListingAlertDispatch(models.Model):
    subscription = models.ForeignKey(
        "properties.ListingAlertSubscription",
        on_delete=models.CASCADE,
        related_name="alert_dispatches",
    )
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="similar_listing_alert_dispatches",
    )
    notification = models.OneToOneField(
        EmailNotification,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="similar_listing_alert_dispatch",
    )
    status = models.CharField(
        max_length=16,
        choices=SimilarListingAlertDispatchStatus.choices,
        default=SimilarListingAlertDispatchStatus.PENDING,
    )
    attempt_count = models.PositiveIntegerField(default=0)
    last_attempted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "similar_listing_alert_dispatches"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["subscription", "property", "status"], name="idx_similar_alert_pair_status"),
            models.Index(fields=["status", "updated_at"], name="idx_sim_alert_status_updated"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["subscription", "property"],
                name="uq_similar_listing_alert_dispatch",
            ),
        ]

    def __str__(self) -> str:
        return f"SimilarListingAlertDispatch<{self.subscription_id}:{self.property_id}>"


class SearchHistory(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="search_history",
    )
    location_city = models.CharField(max_length=100, blank=True)
    min_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    max_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    category = models.CharField(max_length=16, choices=PropertyCategory.choices, blank=True)
    bedrooms_min = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "search_history"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"SearchHistory<{self.pk}>"


class ActivityLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    scope = models.CharField(max_length=16, choices=ActivityScope.choices)
    action = models.CharField(max_length=80)
    entity_type = models.CharField(max_length=80, blank=True)
    entity_id = models.BigIntegerField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "activity_logs"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.scope}:{self.action}"

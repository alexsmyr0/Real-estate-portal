from __future__ import annotations

import logging

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from homefinder.apps.properties.models import PropertyCategory
from homefinder.apps.users.permissions import admin_required

from .activity_logging import log_interaction_activity
from .models import (
    ALLOWED_BOOKING_STATUS_TRANSITIONS,
    INQUIRY_STATUS_ADVANCE_SEQUENCE,
    VIEWING_STATUS_ADVANCE_SEQUENCE,
    BookingRequest,
    BookingRequestStatus,
    PropertyInquiry,
    PropertyInquiryStatus,
    ViewingRequest,
    ViewingRequestStatus,
)
from .services import update_booking_request_status

logger = logging.getLogger(__name__)

BOOKING_STATUS_ADVANCE_PRIORITY = (
    BookingRequestStatus.APPROVED,
    BookingRequestStatus.REJECTED,
    BookingRequestStatus.CANCELLED,
)


@admin_required
@require_http_methods(["GET", "POST"])
def staff_inquiry_management_page(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        return _advance_inquiry_status(request)

    inquiry_rows = [
        _serialize_inquiry_row(inquiry)
        for inquiry in PropertyInquiry.objects.select_related("user", "property").order_by("-created_at", "-id")
    ]
    return render(
        request,
        "interactions/staff_inquiry_list.html",
        {"inquiry_rows": inquiry_rows},
    )


@admin_required
@require_http_methods(["GET", "POST"])
def staff_viewing_management_page(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        return _advance_viewing_status(request)

    viewing_rows = [
        _serialize_viewing_row(viewing_request)
        for viewing_request in ViewingRequest.objects.select_related("user", "property").order_by("-created_at", "-id")
    ]
    return render(
        request,
        "interactions/staff_viewing_list.html",
        {"viewing_rows": viewing_rows},
    )


@admin_required
@require_http_methods(["GET", "POST"])
def staff_booking_management_page(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        return _advance_booking_status(request)

    booking_rows = [
        _serialize_booking_row(booking_request)
        for booking_request in (
            BookingRequest.objects.filter(property__category=PropertyCategory.RENTAL)
            .select_related("user", "property")
            .order_by("-created_at", "-id")
        )
    ]
    return render(
        request,
        "interactions/staff_booking_list.html",
        {"booking_rows": booking_rows},
    )


def _advance_inquiry_status(request: HttpRequest) -> HttpResponse:
    inquiry_id = _parse_positive_int(request.POST.get("inquiry_id"))
    if inquiry_id is None:
        messages.error(request, "Choose a valid inquiry to update.")
        return redirect("staff-interactions-inquiries")

    try:
        with transaction.atomic():
            inquiry = (
                PropertyInquiry.objects.select_for_update().select_related("user", "property").filter(pk=inquiry_id).first()
            )
            if inquiry is None:
                messages.error(request, "The selected inquiry no longer exists.")
                return redirect("staff-interactions-inquiries")

            previous_status = inquiry.status
            next_status = INQUIRY_STATUS_ADVANCE_SEQUENCE.get(previous_status)
            if next_status is None:
                messages.info(request, "This inquiry is already in its final status.")
                return redirect("staff-interactions-inquiries")

            inquiry.status = next_status
            inquiry.full_clean()
            inquiry.save(update_fields=["status", "updated_at"])
    except ValidationError as error:
        messages.error(request, _validation_error_message(error))
        return redirect("staff-interactions-inquiries")

    _safe_log_admin_status_transition(
        action="admin_inquiry_status_advanced",
        user=request.user,
        entity=inquiry,
        previous_status=previous_status,
        next_status=next_status,
    )
    messages.success(
        request,
        f"Inquiry #{inquiry.pk} moved to {_status_label(PropertyInquiryStatus.choices, next_status)}.",
    )
    return redirect("staff-interactions-inquiries")


def _advance_viewing_status(request: HttpRequest) -> HttpResponse:
    viewing_request_id = _parse_positive_int(request.POST.get("viewing_request_id"))
    if viewing_request_id is None:
        messages.error(request, "Choose a valid viewing request to update.")
        return redirect("staff-interactions-viewings")

    try:
        with transaction.atomic():
            viewing_request = (
                ViewingRequest.objects.select_for_update()
                .select_related("user", "property")
                .filter(pk=viewing_request_id)
                .first()
            )
            if viewing_request is None:
                messages.error(request, "The selected viewing request no longer exists.")
                return redirect("staff-interactions-viewings")

            previous_status = viewing_request.status
            next_status = VIEWING_STATUS_ADVANCE_SEQUENCE.get(previous_status)
            if next_status is None:
                messages.info(request, "This viewing request is already in its final status.")
                return redirect("staff-interactions-viewings")

            viewing_request.status = next_status
            viewing_request.full_clean()
            viewing_request.save(update_fields=["status", "updated_at"])
    except ValidationError as error:
        messages.error(request, _validation_error_message(error))
        return redirect("staff-interactions-viewings")

    _safe_log_admin_status_transition(
        action="admin_viewing_status_advanced",
        user=request.user,
        entity=viewing_request,
        previous_status=previous_status,
        next_status=next_status,
    )
    messages.success(
        request,
        f"Viewing request #{viewing_request.pk} moved to {_status_label(ViewingRequestStatus.choices, next_status)}.",
    )
    return redirect("staff-interactions-viewings")


def _advance_booking_status(request: HttpRequest) -> HttpResponse:
    booking_request_id = _parse_positive_int(request.POST.get("booking_request_id"))
    if booking_request_id is None:
        messages.error(request, "Choose a valid booking request to update.")
        return redirect("staff-interactions-bookings")

    try:
        with transaction.atomic():
            booking_request = (
                BookingRequest.objects.select_for_update()
                .filter(pk=booking_request_id, property__category=PropertyCategory.RENTAL)
                .select_related("user", "property")
                .first()
            )
            if booking_request is None:
                messages.error(request, "The selected booking request no longer exists.")
                return redirect("staff-interactions-bookings")

            previous_status = booking_request.status
            next_status = _next_booking_status(previous_status)
            if next_status is None:
                messages.info(request, "This booking request is already in its final status.")
                return redirect("staff-interactions-bookings")

            booking_request = update_booking_request_status(booking_request, status=next_status)
    except ValidationError as error:
        messages.error(request, _validation_error_message(error))
        return redirect("staff-interactions-bookings")

    _safe_log_admin_status_transition(
        action="admin_booking_status_advanced",
        user=request.user,
        entity=booking_request,
        previous_status=previous_status,
        next_status=next_status,
    )
    messages.success(
        request,
        f"Booking request #{booking_request.pk} moved to {_status_label(BookingRequestStatus.choices, next_status)}.",
    )
    return redirect("staff-interactions-bookings")


def _serialize_inquiry_row(inquiry: PropertyInquiry) -> dict[str, object]:
    next_status = INQUIRY_STATUS_ADVANCE_SEQUENCE.get(inquiry.status)
    return {
        "record": inquiry,
        "next_status": next_status,
        "next_status_label": _status_label(PropertyInquiryStatus.choices, next_status),
    }


def _serialize_viewing_row(viewing_request: ViewingRequest) -> dict[str, object]:
    next_status = VIEWING_STATUS_ADVANCE_SEQUENCE.get(viewing_request.status)
    return {
        "record": viewing_request,
        "next_status": next_status,
        "next_status_label": _status_label(ViewingRequestStatus.choices, next_status),
    }


def _serialize_booking_row(booking_request: BookingRequest) -> dict[str, object]:
    next_status = _next_booking_status(booking_request.status)
    return {
        "record": booking_request,
        "next_status": next_status,
        "next_status_label": _status_label(BookingRequestStatus.choices, next_status),
    }


def _next_booking_status(current_status: str) -> str | None:
    allowed_statuses = ALLOWED_BOOKING_STATUS_TRANSITIONS.get(current_status, set())
    for candidate in BOOKING_STATUS_ADVANCE_PRIORITY:
        if candidate in allowed_statuses:
            return candidate
    return None


def _status_label(choices: tuple[tuple[str, str], ...], value: str | None) -> str:
    if value is None:
        return ""
    for choice_value, choice_label in choices:
        if choice_value == value:
            return choice_label
    return value


def _parse_positive_int(raw_value: str | None) -> int | None:
    try:
        parsed_value = int(raw_value or "")
    except (TypeError, ValueError):
        return None
    return parsed_value if parsed_value > 0 else None


def _safe_log_admin_status_transition(
    *,
    action: str,
    user: object,
    entity: object,
    previous_status: str,
    next_status: str,
) -> None:
    try:
        log_interaction_activity(
            action=action,
            user=user,
            entity=entity,
            details={"previous_status": previous_status, "next_status": next_status},
        )
    except Exception:
        logger.exception(
            "Failed to log admin status transition.",
            extra={
                "action": action,
                "entity_pk": getattr(entity, "pk", None),
                "previous_status": previous_status,
                "next_status": next_status,
            },
        )


def _validation_error_message(error: ValidationError) -> str:
    if hasattr(error, "message_dict"):
        for field_messages in error.message_dict.values():
            if field_messages:
                return str(field_messages[0])
    if getattr(error, "messages", None):
        return str(error.messages[0])
    return "The status update could not be completed."

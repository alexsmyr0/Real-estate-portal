from __future__ import annotations

import logging
from decimal import Decimal
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from homefinder.apps.properties.models import ListingAlertSubscription, Property, PropertyCategory
from homefinder.apps.properties.services import PUBLICLY_VISIBLE_PROPERTY_STATUSES, get_personalized_recommendations

from .models import (
    BookingRequest,
    BookingRequestStatus,
    Payment,
    PaymentMethod,
    PaymentPurpose,
    PaymentStatus,
    PropertyInquiry,
    SearchHistory,
    UserFavorite,
    ViewingRequest,
)
from .services import (
    cancel_simulated_payment,
    complete_simulated_payment,
    create_booking_fee_payment,
    fail_simulated_payment,
)

logger = logging.getLogger(__name__)

DASHBOARD_CURRENT_LIMIT = 5
DASHBOARD_OLDER_LIMIT = 5
DASHBOARD_SECTION_LIMIT = DASHBOARD_CURRENT_LIMIT + DASHBOARD_OLDER_LIMIT
SIMULATED_BOOKING_FEE_AMOUNT = Decimal("49.99")
SIMULATED_PAYMENT_ACTIONS = {"complete", "fail", "cancel", "retry"}


@never_cache
@require_http_methods(["GET"])
def dashboard_page(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        messages.warning(request, "Sign in to view your dashboard.")
        login_url = f"{reverse('login-page')}?{urlencode({'next': request.get_full_path()})}"
        return redirect(login_url)

    search_rows = list(
        SearchHistory.objects.filter(user=request.user).order_by("-created_at", "-id")[:DASHBOARD_SECTION_LIMIT],
    )
    favorite_rows = list(
        UserFavorite.objects.filter(
            user=request.user,
            property__status__in=PUBLICLY_VISIBLE_PROPERTY_STATUSES,
        )
        .select_related("property")
        .order_by("-created_at", "-id")[:DASHBOARD_SECTION_LIMIT],
    )
    inquiry_rows = list(
        PropertyInquiry.objects.filter(user=request.user)
        .select_related("property")
        .order_by("-created_at", "-id")[:DASHBOARD_SECTION_LIMIT],
    )
    viewing_rows = list(
        ViewingRequest.objects.filter(user=request.user)
        .select_related("property")
        .order_by("-created_at", "-id")[:DASHBOARD_SECTION_LIMIT],
    )
    alert_rows = list(
        ListingAlertSubscription.objects.filter(user=request.user, is_active=True)
        .select_related("source_property")
        .prefetch_related("amenities")
        .order_by("-created_at", "-id")[:DASHBOARD_SECTION_LIMIT],
    )
    recommended_properties = _safe_get_recommendations(user=request.user)

    return render(
        request,
        "interactions/dashboard.html",
        {
            "searches": _build_section(
                rows=[_serialize_search_history(row) for row in search_rows],
                empty_title="No recent searches yet",
                empty_message="You have not searched yet.",
            ),
            "favorites": _build_section(
                rows=favorite_rows,
                empty_title="No saved properties yet",
                empty_message="You have not saved any properties yet.",
            ),
            "inquiries": _build_section(
                rows=[_serialize_property_activity(row) for row in inquiry_rows],
                empty_title="No inquiries yet",
                empty_message="You have not submitted inquiries yet.",
            ),
            "viewings": _build_section(
                rows=[_serialize_property_activity(row) for row in viewing_rows],
                empty_title="No viewing requests yet",
                empty_message="You have not requested any viewings yet.",
            ),
            "alerts": _build_section(
                rows=[_serialize_alert_subscription(row) for row in alert_rows],
                empty_title="No alert subscriptions yet",
                empty_message="You have not subscribed to similar-listing alerts yet.",
            ),
            "recommended_properties": recommended_properties,
            "dashboard_current_limit": DASHBOARD_CURRENT_LIMIT,
            "dashboard_older_limit": DASHBOARD_OLDER_LIMIT,
        },
    )


def _safe_get_recommendations(*, user: object) -> list[dict[str, object]]:
    try:
        return get_personalized_recommendations(
            user=user,
            request_surface="dashboard",
        )
    except Exception:
        logger.exception(
            "Failed to load personalized recommendations.",
            extra={"request_surface": "dashboard"},
        )
        return []


@never_cache
@require_http_methods(["GET"])
def booking_simulated_payment_page(request: HttpRequest, booking_request_id: int) -> HttpResponse:
    access_redirect = _require_authenticated_user(
        request=request,
        warning_message="Sign in to continue the simulated payment step.",
        next_url=request.get_full_path(),
    )
    if access_redirect is not None:
        return access_redirect

    booking_request = _get_owned_booking_request(request=request, booking_request_id=booking_request_id)
    payment = _latest_booking_payment(booking_request)
    if payment is None:
        if not _is_booking_payable(booking_request):
            raise Http404("Simulated payment is not available for this booking request.")
        payment = _get_or_create_booking_payment(booking_request)

    return _render_booking_payment_page(request=request, booking_request=booking_request, payment=payment)


@never_cache
@require_http_methods(["POST"])
def booking_simulated_payment_action(
    request: HttpRequest,
    booking_request_id: int,
    action: str,
) -> HttpResponse:
    payment_url = reverse("site-booking-simulated-payment", args=[booking_request_id])
    access_redirect = _require_authenticated_user(
        request=request,
        warning_message="Sign in to continue the simulated payment step.",
        next_url=payment_url,
    )
    if access_redirect is not None:
        return access_redirect

    if action not in SIMULATED_PAYMENT_ACTIONS:
        raise Http404("Payment action not found.")

    booking_request = _get_owned_booking_request(request=request, booking_request_id=booking_request_id)
    payment = _latest_booking_payment(booking_request)
    if payment is None:
        if not _is_booking_payable(booking_request):
            raise Http404("Simulated payment is not available for this booking request.")
        payment = _get_or_create_booking_payment(booking_request)

    try:
        if not _is_booking_payable(booking_request):
            raise ValidationError({"booking_request": "This booking is no longer eligible for simulated payment actions."})

        if action == "complete":
            payment = complete_simulated_payment(payment)
            messages.success(request, "Simulated payment completed.")
        elif action == "fail":
            payment = fail_simulated_payment(payment)
            messages.error(request, "Simulated payment failed.")
        elif action == "cancel":
            payment = cancel_simulated_payment(payment)
            messages.warning(request, "Simulated payment was cancelled.")
        elif action == "retry":
            payment = _create_retry_booking_payment(booking_request=booking_request, previous_payment=payment)
            messages.info(request, "A new simulated payment attempt is ready.")
    except ValidationError as error:
        _add_validation_message(request=request, error=error)

    return redirect(payment_url)


def _render_booking_payment_page(
    *,
    request: HttpRequest,
    booking_request: BookingRequest,
    payment: Payment,
) -> HttpResponse:
    return render(
        request,
        "interactions/simulated_payment.html",
        {
            "booking_request": booking_request,
            "payment": payment,
            "payment_status": _serialize_payment_status(payment),
            "payment_is_actionable": _is_booking_payable(booking_request),
            "can_complete_payment": _is_booking_payable(booking_request) and payment.status == PaymentStatus.PENDING,
            "can_fail_payment": _is_booking_payable(booking_request) and payment.status == PaymentStatus.PENDING,
            "can_cancel_payment": _is_booking_payable(booking_request) and payment.status == PaymentStatus.PENDING,
            "can_retry_payment": _is_booking_payable(booking_request)
            and payment.status in {PaymentStatus.FAILED, PaymentStatus.CANCELLED},
        },
    )


def _get_owned_booking_request(*, request: HttpRequest, booking_request_id: int) -> BookingRequest:
    booking_request = (
        BookingRequest.objects.filter(pk=booking_request_id, user=request.user)
        .select_related("property", "user")
        .first()
    )
    if booking_request is None:
        raise Http404("Booking request not found.")
    return booking_request


def _get_or_create_booking_payment(booking_request: BookingRequest) -> Payment:
    with transaction.atomic():
        locked_booking_request = (
            BookingRequest.objects.select_for_update()
            .select_related("property", "user")
            .get(pk=booking_request.pk)
        )
        if not _is_booking_payable(locked_booking_request):
            raise ValidationError({"booking_request": "This booking is not eligible for a simulated payment."})
        existing_payment = _latest_booking_payment(locked_booking_request)
        if existing_payment is not None:
            return existing_payment

        return create_booking_fee_payment(
            booking_request=locked_booking_request,
            amount=SIMULATED_BOOKING_FEE_AMOUNT,
            method=PaymentMethod.CREDIT_CARD,
        )


def _latest_booking_payment(booking_request: BookingRequest) -> Payment | None:
    return (
        Payment.objects.filter(
            booking_request=booking_request,
            user=booking_request.user,
            payment_purpose=PaymentPurpose.BOOKING_FEE,
        )
        .select_related("booking_request", "booking_request__property", "user")
        .order_by("-created_at", "-pk")
        .first()
    )


def _is_booking_payable(booking_request: BookingRequest) -> bool:
    return (
        booking_request.status in {BookingRequestStatus.PENDING, BookingRequestStatus.APPROVED}
        and booking_request.property.category == PropertyCategory.RENTAL
        and booking_request.property.status in PUBLICLY_VISIBLE_PROPERTY_STATUSES
    )


def _create_retry_booking_payment(*, booking_request: BookingRequest, previous_payment: Payment) -> Payment:
    if previous_payment.status not in {PaymentStatus.FAILED, PaymentStatus.CANCELLED}:
        raise ValidationError({"status": "Only failed or cancelled simulated payments can be retried."})

    return create_booking_fee_payment(
        booking_request=booking_request,
        amount=previous_payment.amount,
        method=previous_payment.payment_method,
    )


def _serialize_payment_status(payment: Payment) -> dict[str, str]:
    status_copy = {
        PaymentStatus.PENDING: {
            "label": "Pending",
            "tone": "pending",
            "heading": "Simulated payment pending",
            "message": "Your simulated payment is waiting to be completed.",
        },
        PaymentStatus.COMPLETED: {
            "label": "Completed",
            "tone": "success",
            "heading": "Simulated payment completed",
            "message": "Simulated payment completed. No real payment was processed.",
        },
        PaymentStatus.FAILED: {
            "label": "Failed",
            "tone": "failed",
            "heading": "Simulated payment failed",
            "message": "Simulated payment failed. You may start a new simulated attempt.",
        },
        PaymentStatus.CANCELLED: {
            "label": "Cancelled",
            "tone": "cancelled",
            "heading": "Simulated payment cancelled",
            "message": "Simulated payment was cancelled. You may start a new simulated attempt.",
        },
    }
    return status_copy.get(
        payment.status,
        {
            "label": str(payment.status),
            "tone": "pending",
            "heading": "Simulated payment status",
            "message": "Review the persisted simulated payment status.",
        },
    )


def _add_validation_message(*, request: HttpRequest, error: ValidationError) -> None:
    if hasattr(error, "message_dict"):
        first_messages = next(iter(error.message_dict.values()), [])
        message = first_messages[0] if first_messages else "That simulated payment action is not available."
    else:
        messages_list = getattr(error, "messages", [])
        message = messages_list[0] if messages_list else "That simulated payment action is not available."

    messages.error(request, message)


def _require_authenticated_user(
    request: HttpRequest,
    *,
    warning_message: str,
    next_url: str,
) -> HttpResponse | None:
    if request.user.is_authenticated:
        return None

    messages.warning(request, warning_message)
    login_url = reverse("login-page")
    query_string = urlencode({"next": next_url}) if next_url else ""
    if query_string:
        login_url = f"{login_url}?{query_string}"
    return redirect(login_url)


def _build_section(*, rows: list[object], empty_title: str, empty_message: str) -> dict[str, object]:
    return {
        "current": rows[:DASHBOARD_CURRENT_LIMIT],
        "older": rows[DASHBOARD_CURRENT_LIMIT:DASHBOARD_SECTION_LIMIT],
        "empty_title": empty_title,
        "empty_message": empty_message,
        "shown_count": len(rows),
    }


def _serialize_search_history(search: SearchHistory) -> dict[str, object]:
    criteria = []
    query_params = {}

    if search.location_city:
        criteria.append(f"Location: {search.location_city}")
        query_params["location"] = search.location_city
    if search.category:
        criteria.append(f"Category: {search.get_category_display()}")
        query_params["category"] = search.category
    if search.min_price is not None:
        criteria.append(f"Min price: EUR {search.min_price}")
        query_params["min_price"] = str(search.min_price)
    if search.max_price is not None:
        criteria.append(f"Max price: EUR {search.max_price}")
        query_params["max_price"] = str(search.max_price)
    if search.bedrooms_min is not None:
        criteria.append(f"Bedrooms: {search.bedrooms_min}+")
        query_params["bedrooms_min"] = str(search.bedrooms_min)

    catalog_url = reverse("site-catalog")
    query_string = urlencode(query_params)
    if query_string:
        catalog_url = f"{catalog_url}?{query_string}"

    return {
        "created_at": search.created_at,
        "criteria": criteria or ["All listings"],
        "catalog_url": catalog_url,
    }


def _serialize_property_activity(activity: PropertyInquiry | ViewingRequest) -> dict[str, object]:
    property_obj = activity.property
    is_publicly_visible = _is_publicly_visible_property(property_obj)

    return {
        "created_at": activity.created_at,
        "status_label": activity.get_status_display(),
        "property_title": property_obj.title if is_publicly_visible else "Listing removed",
        "property_city": property_obj.city if is_publicly_visible else "",
        "property_area": property_obj.area if is_publicly_visible else "",
        "property_detail_url": reverse("site-property-detail", args=[property_obj.id]) if is_publicly_visible else "",
        "removed_message": "" if is_publicly_visible else "This listing is no longer available.",
        "message": getattr(activity, "message", ""),
        "note": getattr(activity, "note", ""),
        "requested_datetime": getattr(activity, "requested_datetime", None),
    }


def _is_publicly_visible_property(property_obj: Property) -> bool:
    return property_obj.status in PUBLICLY_VISIBLE_PROPERTY_STATUSES


def _serialize_alert_subscription(subscription: ListingAlertSubscription) -> dict[str, object]:
    source_property = subscription.source_property
    source_is_visible = source_property is not None and _is_publicly_visible_property(source_property)

    criteria: list[str] = []
    if subscription.location_city:
        criteria.append(f"Location: {subscription.location_city}")
    if subscription.category:
        criteria.append(f"Category: {PropertyCategory(subscription.category).label}")
    if subscription.min_price is not None:
        criteria.append(f"Min price: EUR {subscription.min_price}")
    if subscription.max_price is not None:
        criteria.append(f"Max price: EUR {subscription.max_price}")
    if subscription.bedrooms_min is not None:
        criteria.append(f"Bedrooms: {subscription.bedrooms_min}+")
    amenity_names = [amenity.name for amenity in subscription.amenities.all()]
    if amenity_names:
        criteria.append(f"Amenities: {', '.join(amenity_names)}")

    return {
        "created_at": subscription.created_at,
        "criteria": criteria or ["All matching listings"],
        "source_property_title": source_property.title if source_is_visible else "Source listing removed",
        "source_property_detail_url": (
            reverse("site-property-detail", args=[source_property.id]) if source_is_visible else ""
        ),
        "removed_message": "" if source_property is None or source_is_visible else "The source listing is no longer available.",
        "missing_source_message": "The source listing was removed." if source_property is None else "",
    }

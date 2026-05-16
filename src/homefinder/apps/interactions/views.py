from __future__ import annotations

import logging
from decimal import Decimal
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import QuerySet
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from homefinder.apps.properties.models import ListingAlertSubscription, Property, PropertyCategory
from homefinder.apps.properties.services import PUBLICLY_VISIBLE_PROPERTY_STATUSES
from homefinder.apps.users.permissions import require_authenticated_user

from .models import (
    BookingRequest,
    BookingRequestStatus,
    Payment,
    PaymentMethod,
    PaymentPurpose,
    PaymentStatus,
    PropertyInquiry,
    SearchHistory,
    ViewingRequest,
)
from .services import (
    cancel_simulated_payment,
    complete_simulated_payment,
    create_booking_fee_payment,
    fail_simulated_payment,
)

logger = logging.getLogger(__name__)

DASHBOARD_PREVIEW_LIMIT = 3
DASHBOARD_DETAIL_PAGE_SIZE = 20
SIMULATED_BOOKING_FEE_AMOUNT = Decimal("49.99")
SIMULATED_PAYMENT_ACTIONS = {"complete", "fail", "cancel", "retry"}


def _require_dashboard_user(request: HttpRequest) -> HttpResponse | None:
    if request.user.is_authenticated:
        return None
    messages.warning(request, "Sign in to view your dashboard.")
    login_url = f"{reverse('login-page')}?{urlencode({'next': request.get_full_path()})}"
    return redirect(login_url)


def _searches_queryset(user: object) -> QuerySet[SearchHistory]:
    return SearchHistory.objects.filter(user=user).order_by("-created_at", "-id")


def _inquiries_queryset(user: object) -> QuerySet[PropertyInquiry]:
    return (
        PropertyInquiry.objects.filter(user=user)
        .select_related("property")
        .order_by("-created_at", "-id")
    )


def _viewings_queryset(user: object) -> QuerySet[ViewingRequest]:
    return (
        ViewingRequest.objects.filter(user=user)
        .select_related("property")
        .order_by("-created_at", "-id")
    )


def _alerts_queryset(user: object) -> QuerySet[ListingAlertSubscription]:
    return (
        ListingAlertSubscription.objects.filter(user=user, is_active=True)
        .select_related("source_property")
        .prefetch_related("amenities")
        .order_by("-created_at", "-id")
    )


@never_cache
@require_http_methods(["GET"])
def dashboard_page(request: HttpRequest) -> HttpResponse:
    auth_redirect = _require_dashboard_user(request)
    if auth_redirect is not None:
        return auth_redirect

    return render(
        request,
        "interactions/dashboard.html",
        {
            "searches": _preview_section(
                queryset=_searches_queryset(request.user),
                serializer=_serialize_search_history,
                detail_url=reverse("site-dashboard-searches"),
                empty_title="No recent searches yet",
                empty_message="You have not searched yet.",
            ),
            "alerts": _preview_section(
                queryset=_alerts_queryset(request.user),
                serializer=_serialize_alert_subscription,
                detail_url=reverse("site-dashboard-alerts"),
                empty_title="No alert subscriptions yet",
                empty_message="You have not subscribed to similar-listing alerts yet.",
            ),
            "inquiries": _preview_section(
                queryset=_inquiries_queryset(request.user),
                serializer=_serialize_property_activity,
                detail_url=reverse("site-dashboard-inquiries"),
                empty_title="No inquiries yet",
                empty_message="You have not submitted inquiries yet.",
            ),
            "viewings": _preview_section(
                queryset=_viewings_queryset(request.user),
                serializer=_serialize_property_activity,
                detail_url=reverse("site-dashboard-viewings"),
                empty_title="No viewing requests yet",
                empty_message="You have not requested any viewings yet.",
            ),
        },
    )


def _render_dashboard_detail(
    request: HttpRequest,
    *,
    queryset: QuerySet[object],
    serializer: object,
    page_title: str,
    item_template: str,
    empty_title: str,
    empty_message: str,
    empty_action_label: str,
) -> HttpResponse:
    auth_redirect = _require_dashboard_user(request)
    if auth_redirect is not None:
        return auth_redirect

    paginator = Paginator(queryset, DASHBOARD_DETAIL_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    items = [serializer(row) for row in page_obj.object_list]

    return render(
        request,
        "interactions/dashboard_detail.html",
        {
            "page_title": page_title,
            "item_template": item_template,
            "items": items,
            "page_obj": page_obj,
            "total_count": paginator.count,
            "empty_title": empty_title,
            "empty_message": empty_message,
            "empty_action_href": reverse("site-catalog"),
            "empty_action_label": empty_action_label,
        },
    )


@never_cache
@require_http_methods(["GET"])
def dashboard_searches_list(request: HttpRequest) -> HttpResponse:
    return _render_dashboard_detail(
        request,
        queryset=_searches_queryset(request.user) if request.user.is_authenticated else SearchHistory.objects.none(),
        serializer=_serialize_search_history,
        page_title="Recent searches",
        item_template="search",
        empty_title="No recent searches yet",
        empty_message="You have not searched yet.",
        empty_action_label="Start browsing",
    )


@never_cache
@require_http_methods(["GET"])
def dashboard_inquiries_list(request: HttpRequest) -> HttpResponse:
    return _render_dashboard_detail(
        request,
        queryset=_inquiries_queryset(request.user) if request.user.is_authenticated else PropertyInquiry.objects.none(),
        serializer=_serialize_property_activity,
        page_title="Inquiries",
        item_template="inquiry",
        empty_title="No inquiries yet",
        empty_message="You have not submitted inquiries yet.",
        empty_action_label="Find a property",
    )


@never_cache
@require_http_methods(["GET"])
def dashboard_viewings_list(request: HttpRequest) -> HttpResponse:
    return _render_dashboard_detail(
        request,
        queryset=_viewings_queryset(request.user) if request.user.is_authenticated else ViewingRequest.objects.none(),
        serializer=_serialize_property_activity,
        page_title="Viewing requests",
        item_template="viewing",
        empty_title="No viewing requests yet",
        empty_message="You have not requested any viewings yet.",
        empty_action_label="Browse listings",
    )


@never_cache
@require_http_methods(["GET"])
def dashboard_alerts_list(request: HttpRequest) -> HttpResponse:
    return _render_dashboard_detail(
        request,
        queryset=_alerts_queryset(request.user) if request.user.is_authenticated else ListingAlertSubscription.objects.none(),
        serializer=_serialize_alert_subscription,
        page_title="Alert subscriptions",
        item_template="alert",
        empty_title="No alert subscriptions yet",
        empty_message="You have not subscribed to similar-listing alerts yet.",
        empty_action_label="Browse listings",
    )


@never_cache
@require_http_methods(["GET"])
def booking_simulated_payment_page(request: HttpRequest, booking_request_id: int) -> HttpResponse:
    access_redirect = require_authenticated_user(
        request,
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
    access_redirect = require_authenticated_user(
        request,
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


def _preview_section(
    *,
    queryset: QuerySet[object],
    serializer: object,
    detail_url: str,
    empty_title: str,
    empty_message: str,
) -> dict[str, object]:
    total_count = queryset.count()
    preview_rows = list(queryset[:DASHBOARD_PREVIEW_LIMIT])
    items = [serializer(row) for row in preview_rows] if serializer else preview_rows
    return {
        "items": items,
        "total_count": total_count,
        "detail_url": detail_url,
        "empty_title": empty_title,
        "empty_message": empty_message,
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

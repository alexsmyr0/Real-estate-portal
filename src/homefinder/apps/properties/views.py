from __future__ import annotations

import logging

from django import forms
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404, HttpRequest, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from homefinder.apps.users.permissions import admin_required, require_authenticated_user

from homefinder.apps.interactions.forms import PropertyInquiryForm
from homefinder.apps.interactions.models import BookingRequest, UserFavorite, ViewingRequest
from homefinder.apps.interactions.services import (
    create_booking_request,
    create_property_inquiry,
    create_viewing_request,
    log_interaction_activity,
)

from .forms import (
    BookingRequestForm,
    PropertyAmenityInlineFormSet,
    PropertyForm,
    PropertyImageInlineFormSet,
    ViewingRequestForm,
)
from .models import Amenity, ListingAlertSubscription, Property, PropertyCategory, PropertyStatus
from .services import (
    DEFAULT_CATALOG_PAGE,
    PUBLICLY_VISIBLE_PROPERTY_STATUSES,
    build_property_availability_context,
    create_listing_alert_subscription,
    get_monthly_inquiry_and_saved_property_metrics,
    get_monthly_search_trend_metrics,
    get_personalized_recommendations,
    get_visible_property,
    get_visible_property_detail,
    parse_catalog_search_params,
    search_visible_properties,
    serialize_property_for_catalog_card,
    serialize_property_for_detail,
    set_listing_alert_subscription_active,
)

logger = logging.getLogger(__name__)

CATALOG_BEDROOM_FILTER_OPTIONS = (1, 2, 3, 4, 5)
VERIFIED_VIEWING_REQUEST_SESSION_KEY = "verified_viewing_request_id"
VERIFIED_BOOKING_REQUEST_SESSION_KEY = "verified_booking_request_id"
INQUIRY_FORM_AUTO_ID = "inquiry_%s"
VIEWING_FORM_AUTO_ID = "viewing_%s"
BOOKING_FORM_AUTO_ID = "booking_%s"
VALID_STAFF_LISTING_STATUS_FILTERS = {choice for choice, _label in PropertyStatus.choices}


@require_http_methods(["GET"])
def catalog_page(request: HttpRequest) -> HttpResponse:
    search_params = parse_catalog_search_params(request.GET)
    search_results = search_visible_properties(search_params=search_params)
    properties = search_results["properties"]
    _apply_catalog_favorite_state(request=request, properties=properties)

    pagination = search_results["pagination"]
    current_page = pagination["page"]
    total_pages = pagination["total_pages"]

    selected_amenity_ids = set(search_params.amenity_ids)
    selected_amenity_names = {name.casefold() for name in search_params.amenity_names}
    amenity_filter_options = [
        {
            "id": amenity.id,
            "name": amenity.name,
            "is_selected": amenity.id in selected_amenity_ids or amenity.name.casefold() in selected_amenity_names,
        }
        for amenity in Amenity.objects.all()
    ]

    page_links = [
        {
            "number": page_number,
            "is_current": page_number == current_page,
            "query_string": _build_page_query_string(request.GET, page_number),
        }
        for page_number in _visible_page_numbers(current_page=current_page, total_pages=total_pages)
    ]

    return render(
        request,
        "properties/catalog.html",
        {
            "properties": properties,
            "pagination": pagination,
            "active_filters": {
                "location": _first_query_value(request.GET, "location", "location_city", "city"),
                "min_price": _first_query_value(request.GET, "min_price", "price_min"),
                "max_price": _first_query_value(request.GET, "max_price", "price_max"),
                "category": (
                    _first_query_value(request.GET, "category")
                    or (search_params.category or "")
                ).upper(),
                "bedrooms_min": _first_query_value(request.GET, "bedrooms_min", "bedrooms"),
            },
            "category_choices": PropertyCategory.choices,
            "bedrooms_min_choices": CATALOG_BEDROOM_FILTER_OPTIONS,
            "amenity_filter_options": amenity_filter_options,
            "page_links": page_links,
            "previous_page_query": _build_page_query_string(request.GET, current_page - 1)
            if pagination["has_previous"]
            else "",
            "next_page_query": _build_page_query_string(request.GET, current_page + 1)
            if pagination["has_next"]
            else "",
        },
    )


@require_http_methods(["GET"])
def property_detail_page(request: HttpRequest, property_id: int) -> HttpResponse:
    property_obj = get_visible_property(property_id)
    if property_obj is None:
        raise Http404("Property not found.")
    property_payload = serialize_property_for_detail(property_obj)

    recommended_properties = _safe_get_recommendations(
        request=request,
        request_surface="detail",
        source_property=property_obj,
    )

    return _render_property_detail(
        request=request,
        property_payload=property_payload,
        viewing_form=_new_viewing_form(),
        booking_form=_new_booking_form() if _is_rental_property_payload(property_payload) else None,
        viewing_confirmation=_consume_verified_viewing_confirmation(
            request=request,
            property_id=property_id,
        ),
        booking_confirmation=_consume_verified_booking_confirmation(
            request=request,
            property_id=property_id,
        ),
        recommended_properties=recommended_properties,
    )


@require_http_methods(["POST"])
def submit_inquiry_action(request: HttpRequest, property_id: int) -> HttpResponse:
    detail_url = reverse("site-property-detail", args=[property_id])
    guest_redirect = require_authenticated_user(
        request,
        warning_message="Sign in before sending an inquiry.",
        next_url=detail_url,
    )
    if guest_redirect is not None:
        return guest_redirect

    property_obj = get_visible_property(property_id)
    if property_obj is None:
        raise Http404("Property not found.")

    inquiry_form = _new_inquiry_form(data=request.POST)
    if not inquiry_form.is_valid():
        messages.error(request, "Please correct the highlighted fields and send your inquiry again.")
        property_payload = serialize_property_for_detail(property_obj)
        return _render_property_detail(
            request=request,
            property_payload=property_payload,
            viewing_form=_new_viewing_form(),
            inquiry_form=inquiry_form,
        )

    try:
        inquiry = create_property_inquiry(
            user=request.user,
            property_obj=property_obj,
            message=inquiry_form.cleaned_data["message"],
        )
    except ValidationError as error:
        _add_validation_error_to_form(inquiry_form, error)
        messages.error(request, "Please correct the highlighted fields and send your inquiry again.")
        property_payload = serialize_property_for_detail(property_obj)
        return _render_property_detail(
            request=request,
            property_payload=property_payload,
            viewing_form=_new_viewing_form(),
            inquiry_form=inquiry_form,
        )

    messages.success(request, "Inquiry sent. We emailed you a confirmation.")
    return redirect(detail_url)


@require_http_methods(["GET"])
def favorites_page(request: HttpRequest) -> HttpResponse:
    guest_redirect = require_authenticated_user(
        request,
        warning_message="Sign in to view your saved listings.",
        next_url=request.get_full_path(),
    )
    if guest_redirect is not None:
        return guest_redirect

    favorite_rows = (
        UserFavorite.objects.filter(
            user=request.user,
            property__status__in=PUBLICLY_VISIBLE_PROPERTY_STATUSES,
        )
        .select_related("property")
        .prefetch_related("property__images")
        .order_by("-created_at")
    )
    properties = []
    for favorite in favorite_rows:
        property_payload = serialize_property_for_catalog_card(favorite.property)
        property_payload["is_favorited"] = True
        properties.append(property_payload)

    return render(
        request,
        "properties/favorites.html",
        {
            "properties": properties,
        },
    )


@require_http_methods(["POST"])
def add_favorite_action(request: HttpRequest, property_id: int) -> HttpResponse:
    fallback_url = reverse("site-property-detail", args=[property_id])
    redirect_target = _preferred_redirect_target(request=request, fallback_url=fallback_url)
    guest_redirect = require_authenticated_user(
        request,
        warning_message="Sign in to save listings.",
        next_url=redirect_target,
    )
    if guest_redirect is not None:
        return guest_redirect

    property_payload = get_visible_property_detail(property_id)
    if property_payload is None:
        raise Http404("Property not found.")

    created = False
    try:
        _, created = UserFavorite.objects.get_or_create(user=request.user, property_id=property_id)
    except IntegrityError:
        created = False

    if created:
        messages.success(request, "Listing saved to your favorites.")
    else:
        messages.info(request, "This listing is already in your favorites.")

    _safe_log_favorite_action(
        request=request,
        action="favorite_added",
        property_id=property_id,
        details={
            "surface": _preferred_surface(request),
            "result": "created" if created else "already_saved",
        },
    )
    return redirect(redirect_target)


@require_http_methods(["POST"])
def remove_favorite_action(request: HttpRequest, property_id: int) -> HttpResponse:
    fallback_url = reverse("site-property-detail", args=[property_id])
    redirect_target = _preferred_redirect_target(request=request, fallback_url=fallback_url)
    guest_redirect = require_authenticated_user(
        request,
        warning_message="Sign in to manage favorites.",
        next_url=redirect_target,
    )
    if guest_redirect is not None:
        return guest_redirect

    property_payload = get_visible_property_detail(property_id)
    if property_payload is None:
        raise Http404("Property not found.")

    deleted_count, _ = UserFavorite.objects.filter(user=request.user, property_id=property_id).delete()
    deleted = deleted_count > 0

    if deleted:
        messages.success(request, "Listing removed from your favorites.")
    else:
        messages.info(request, "This listing is not currently in your favorites.")

    _safe_log_favorite_action(
        request=request,
        action="favorite_removed",
        property_id=property_id,
        details={
            "surface": _preferred_surface(request),
            "result": "removed" if deleted else "not_found",
        },
    )
    return redirect(redirect_target)


@require_http_methods(["GET"])
def reporting_overview_page(request: HttpRequest) -> HttpResponse:
    access_redirect = _require_reporting_user(request=request, next_url=request.get_full_path())
    if access_redirect is not None:
        return access_redirect

    monthly_summary_metrics = get_monthly_inquiry_and_saved_property_metrics()
    search_trend_metrics = _decorate_search_trend_metrics(get_monthly_search_trend_metrics())

    return render(
        request,
        "properties/reporting_overview.html",
        {
            "monthly_summary_metrics": monthly_summary_metrics,
            "search_trend_metrics": search_trend_metrics,
        },
    )


@require_http_methods(["GET"])
def reporting_search_trends_page(request: HttpRequest) -> HttpResponse:
    access_redirect = _require_reporting_user(request=request, next_url=request.get_full_path())
    if access_redirect is not None:
        return access_redirect

    search_trend_metrics = _decorate_search_trend_metrics(get_monthly_search_trend_metrics())
    return render(
        request,
        "properties/reporting_search_trends.html",
        {
            "search_trend_metrics": search_trend_metrics,
        },
    )


@admin_required
@require_http_methods(["GET"])
def listing_list_page(request: HttpRequest) -> HttpResponse:
    status_filter = _first_query_value(request.GET, "status").upper()

    listings_queryset = _filter_staff_listings_queryset(status_filter=status_filter)
    listing_rows = [
        {
            "listing": listing,
            "availability": build_property_availability_context(listing.status),
        }
        for listing in listings_queryset
    ]

    return render(
        request,
        "properties/listing_list.html",
        {
            "listing_rows": listing_rows,
            "status_choices": PropertyStatus.choices,
            "active_filters": {
                "status": status_filter if status_filter in VALID_STAFF_LISTING_STATUS_FILTERS else "",
            },
        },
    )


@admin_required
@require_http_methods(["GET", "POST"])
def listing_create_page(request: HttpRequest) -> HttpResponse:
    listing = Property()
    form, image_formset, amenity_formset = _build_staff_listing_form_components(
        request=request,
        listing=listing,
    )

    if request.method == "POST":
        if form.is_valid() and image_formset.is_valid() and amenity_formset.is_valid():
            _save_staff_listing(
                form=form,
                image_formset=image_formset,
                amenity_formset=amenity_formset,
                fallback_listed_by=request.user,
            )
            messages.success(request, "Listing created successfully.")
            return redirect("staff-listing-list")

        messages.error(request, "Please correct the highlighted fields and try again.")

    return render(
        request,
        "properties/listing_form.html",
        {
            "form": form,
            "image_formset": image_formset,
            "amenity_formset": amenity_formset,
            "is_create": True,
        },
    )


@admin_required
@require_http_methods(["GET", "POST"])
def listing_edit_page(request: HttpRequest, listing_id: int) -> HttpResponse:
    listing = get_object_or_404(_staff_listing_queryset(), pk=listing_id)
    form, image_formset, amenity_formset = _build_staff_listing_form_components(
        request=request,
        listing=listing,
    )

    if request.method == "POST":
        if form.is_valid() and image_formset.is_valid() and amenity_formset.is_valid():
            _save_staff_listing(
                form=form,
                image_formset=image_formset,
                amenity_formset=amenity_formset,
                fallback_listed_by=request.user,
            )
            messages.success(request, "Listing updated successfully.")
            return redirect("staff-listing-list")

        messages.error(request, "Please correct the highlighted fields and try again.")

    return render(
        request,
        "properties/listing_form.html",
        {
            "form": form,
            "image_formset": image_formset,
            "amenity_formset": amenity_formset,
            "listing": listing,
            "is_create": False,
        },
    )


@admin_required
@require_http_methods(["GET", "POST"])
def listing_delete_page(request: HttpRequest, listing_id: int) -> HttpResponse:
    listing = get_object_or_404(_staff_listing_queryset(), pk=listing_id)

    if request.method == "POST":
        listing_title = listing.title
        listing.delete()
        messages.success(request, f'Listing "{listing_title}" was deleted.')
        return redirect("staff-listing-list")

    return render(
        request,
        "properties/listing_confirm_delete.html",
        {
            "listing": listing,
            "availability": build_property_availability_context(listing.status),
        },
    )


@require_http_methods(["POST"])
def viewing_request_action(request: HttpRequest, property_id: int) -> HttpResponse:
    detail_url = reverse("site-property-detail", args=[property_id])
    guest_redirect = require_authenticated_user(
        request,
        warning_message="Sign in to request a viewing.",
        next_url=detail_url,
    )
    if guest_redirect is not None:
        return guest_redirect

    property_obj = get_visible_property(property_id)
    if property_obj is None:
        raise Http404("Property not found.")

    viewing_form = _new_viewing_form(data=request.POST)
    if not viewing_form.is_valid():
        property_payload = serialize_property_for_detail(property_obj)
        return _render_property_detail(
            request=request,
            property_payload=property_payload,
            viewing_form=viewing_form,
        )

    try:
        viewing_request = create_viewing_request(
            user=request.user,
            property_obj=property_obj,
            requested_datetime=viewing_form.cleaned_data["requested_datetime"],
            note=viewing_form.cleaned_data.get("note", ""),
        )
    except ValidationError as error:
        _add_validation_error_to_form(viewing_form, error)
        property_payload = serialize_property_for_detail(property_obj)
        return _render_property_detail(
            request=request,
            property_payload=property_payload,
            viewing_form=viewing_form,
        )

    request.session[VERIFIED_VIEWING_REQUEST_SESSION_KEY] = viewing_request.pk
    messages.success(request, "Your viewing request was sent.")
    _safe_log_viewing_action(
        request=request,
        viewing_request=viewing_request,
        details={
            "surface": "detail",
            "property_id": property_id,
            "requested_datetime": viewing_request.requested_datetime,
        },
    )
    return redirect(detail_url)


@require_http_methods(["POST"])
def listing_alert_subscription_action(request: HttpRequest, property_id: int) -> HttpResponse:
    detail_url = reverse("site-property-detail", args=[property_id])
    guest_redirect = require_authenticated_user(
        request,
        warning_message="Sign in to get similar-listing alerts.",
        next_url=detail_url,
    )
    if guest_redirect is not None:
        return guest_redirect

    property_obj = get_visible_property(property_id)
    if property_obj is None or property_obj.status != PropertyStatus.UNAVAILABLE:
        raise Http404("Property not found.")

    try:
        subscription, created = _get_or_create_active_alert_subscription(
            user=request.user,
            source_property=property_obj,
        )
    except ValidationError:
        logger.exception(
            "Failed to create similar-listing alert subscription.",
            extra={"property_id": property_id, "user_id": request.user.pk},
        )
        messages.error(request, "We could not create that alert subscription. Please try again.")
        return redirect(detail_url)

    if created:
        messages.success(request, "You are subscribed to similar-listing alerts.")
    else:
        messages.info(request, "You are already subscribed to similar-listing alerts for this property.")

    return redirect(detail_url)


@require_http_methods(["POST"])
def listing_alert_unsubscribe_action(request: HttpRequest, property_id: int) -> HttpResponse:
    detail_url = reverse("site-property-detail", args=[property_id])
    guest_redirect = require_authenticated_user(
        request,
        warning_message="Sign in to manage similar-listing alerts.",
        next_url=detail_url,
    )
    if guest_redirect is not None:
        return guest_redirect

    property_obj = get_visible_property(property_id)
    if property_obj is None or property_obj.status != PropertyStatus.UNAVAILABLE:
        raise Http404("Property not found.")

    active_subscription = _active_alert_subscription_for_user(
        user=request.user,
        source_property_id=property_obj.pk,
    )
    if active_subscription is None:
        messages.info(request, "You were not subscribed to similar-listing alerts for this property.")
        return redirect(detail_url)

    set_listing_alert_subscription_active(active_subscription, is_active=False)
    messages.success(request, "You have been unsubscribed from similar-listing alerts.")
    return redirect(detail_url)


@require_http_methods(["POST"])
def booking_request_action(request: HttpRequest, property_id: int) -> HttpResponse:
    detail_url = reverse("site-property-detail", args=[property_id])
    guest_redirect = require_authenticated_user(
        request,
        warning_message="Sign in to request a booking.",
        next_url=detail_url,
    )
    if guest_redirect is not None:
        return guest_redirect

    property_obj = get_visible_property(property_id)
    if property_obj is None:
        raise Http404("Property not found.")

    if property_obj.category != PropertyCategory.RENTAL:
        messages.error(request, "Booking requests are only available for rental listings.")
        return redirect(detail_url)

    booking_form = _new_booking_form(data=request.POST)
    if not booking_form.is_valid():
        property_payload = serialize_property_for_detail(property_obj)
        return _render_property_detail(
            request=request,
            property_payload=property_payload,
            viewing_form=_new_viewing_form(),
            booking_form=booking_form,
        )

    try:
        booking_request = create_booking_request(
            user=request.user,
            property_obj=property_obj,
            start_date=booking_form.cleaned_data["start_date"],
            end_date=booking_form.cleaned_data["end_date"],
            note=booking_form.cleaned_data.get("note", ""),
        )
    except ValidationError as error:
        _add_validation_error_to_form(booking_form, error)
        property_payload = serialize_property_for_detail(property_obj)
        return _render_property_detail(
            request=request,
            property_payload=property_payload,
            viewing_form=_new_viewing_form(),
            booking_form=booking_form,
        )

    request.session[VERIFIED_BOOKING_REQUEST_SESSION_KEY] = booking_request.pk
    messages.success(request, "Your booking request was sent.")
    _safe_log_booking_action(
        request=request,
        booking_request=booking_request,
        details={
            "surface": "detail",
            "property_id": property_id,
            "start_date": booking_request.start_date,
            "end_date": booking_request.end_date,
        },
    )
    return redirect(detail_url)


def _apply_catalog_favorite_state(*, request: HttpRequest, properties: list[dict[str, object]]) -> None:
    if not properties:
        return

    favorited_property_ids: set[int] = set()
    if request.user.is_authenticated:
        property_ids = [property_payload["id"] for property_payload in properties]
        favorited_property_ids = set(
            UserFavorite.objects.filter(
                user=request.user,
                property_id__in=property_ids,
            ).values_list("property_id", flat=True)
        )

    for property_payload in properties:
        property_payload["is_favorited"] = property_payload["id"] in favorited_property_ids


def _apply_detail_favorite_state(*, request: HttpRequest, property_payload: dict[str, object]) -> None:
    if not request.user.is_authenticated:
        property_payload["is_favorited"] = False
        return

    property_payload["is_favorited"] = UserFavorite.objects.filter(
        user=request.user,
        property_id=property_payload["id"],
    ).exists()


def _apply_detail_alert_subscription_state(*, request: HttpRequest, property_payload: dict[str, object]) -> None:
    property_payload["alert_subscription"] = {
        "can_show": bool(property_payload["availability"]["is_unavailable"]),
        "is_subscribed": False,
    }
    if not request.user.is_authenticated or not property_payload["availability"]["is_unavailable"]:
        return

    active_subscription = _active_alert_subscription_for_user(
        user=request.user,
        source_property_id=int(property_payload["id"]),
    )
    if active_subscription is not None:
        property_payload["alert_subscription"]["is_subscribed"] = True
        property_payload["alert_subscription"]["id"] = active_subscription.pk


def _render_property_detail(
    *,
    request: HttpRequest,
    property_payload: dict[str, object],
    viewing_form: ViewingRequestForm,
    booking_form: BookingRequestForm | None = None,
    viewing_confirmation: ViewingRequest | None = None,
    booking_confirmation: BookingRequest | None = None,
    inquiry_form: PropertyInquiryForm | None = None,
    recommended_properties: list[dict[str, object]] | None = None,
) -> HttpResponse:
    _apply_detail_favorite_state(request=request, property_payload=property_payload)
    _apply_detail_alert_subscription_state(request=request, property_payload=property_payload)
    if booking_form is None and _is_rental_property_payload(property_payload):
        booking_form = _new_booking_form()

    if recommended_properties is None:
        recommended_properties = _safe_get_recommendations(
            request=request,
            request_surface="detail",
            source_property_id=int(property_payload["id"]),
        )

    return render(
        request,
        "properties/detail.html",
        {
            "property": property_payload,
            "category_label": _get_category_label(str(property_payload["category"])),
            "viewing_form": viewing_form,
            "booking_form": booking_form,
            "is_rental_listing": _is_rental_property_payload(property_payload),
            "viewing_confirmation": viewing_confirmation,
            "booking_confirmation": booking_confirmation,
            "inquiry_form": inquiry_form if inquiry_form is not None else _new_inquiry_form(),
            "recommended_properties": recommended_properties,
        },
    )


def _new_inquiry_form(*, data: QueryDict | None = None) -> PropertyInquiryForm:
    return PropertyInquiryForm(data=data, auto_id=INQUIRY_FORM_AUTO_ID)


def _new_viewing_form(*, data: QueryDict | None = None) -> ViewingRequestForm:
    return ViewingRequestForm(data=data, auto_id=VIEWING_FORM_AUTO_ID)


def _new_booking_form(*, data: QueryDict | None = None) -> BookingRequestForm:
    return BookingRequestForm(data=data, auto_id=BOOKING_FORM_AUTO_ID)


def _safe_get_recommendations(
    *,
    request: HttpRequest,
    request_surface: str,
    source_property: Property | None = None,
    source_property_id: int | None = None,
) -> list[dict[str, object]]:
    if source_property is None and source_property_id is not None:
        source_property = get_visible_property(source_property_id)
    try:
        recommendations = get_personalized_recommendations(
            user=request.user,
            request_surface=request_surface,
            source_property=source_property,
        )
    except Exception:
        logger.exception(
            "Failed to load personalized recommendations.",
            extra={"request_surface": request_surface},
        )
        return []

    _apply_catalog_favorite_state(request=request, properties=recommendations)
    return recommendations


def _consume_verified_viewing_confirmation(
    *,
    request: HttpRequest,
    property_id: int,
) -> ViewingRequest | None:
    marker = request.session.pop(VERIFIED_VIEWING_REQUEST_SESSION_KEY, None)
    if not request.user.is_authenticated or marker is None:
        return None

    try:
        marker_id = int(marker)
    except (TypeError, ValueError):
        return None

    return (
        ViewingRequest.objects.filter(
            pk=marker_id,
            user=request.user,
            property_id=property_id,
        )
        .select_related("property", "user")
        .first()
    )


def _consume_verified_booking_confirmation(
    *,
    request: HttpRequest,
    property_id: int,
) -> BookingRequest | None:
    marker = request.session.pop(VERIFIED_BOOKING_REQUEST_SESSION_KEY, None)
    if not request.user.is_authenticated or marker is None:
        return None

    try:
        marker_id = int(marker)
    except (TypeError, ValueError):
        return None

    return (
        BookingRequest.objects.filter(
            pk=marker_id,
            user=request.user,
            property_id=property_id,
        )
        .select_related("property", "user")
        .first()
    )


def _get_or_create_active_alert_subscription(
    *,
    user: object,
    source_property: Property,
) -> tuple[ListingAlertSubscription, bool]:
    # A-12 provides sequential UI idempotency. Race-safe global uniqueness for
    # active alert subscriptions remains owned by the N-04 backend lifecycle.
    active_subscription = _active_alert_subscription_for_user(
        user=user,
        source_property_id=source_property.pk,
    )
    if active_subscription is not None:
        return active_subscription, False

    return create_listing_alert_subscription(user=user, source_property=source_property), True


def _active_alert_subscription_for_user(
    *,
    user: object,
    source_property_id: int,
) -> ListingAlertSubscription | None:
    return (
        ListingAlertSubscription.objects.filter(
            user=user,
            source_property_id=source_property_id,
            is_active=True,
        )
        .order_by("-created_at", "-pk")
        .first()
    )


def _is_rental_property_payload(property_payload: dict[str, object]) -> bool:
    return property_payload.get("category") == PropertyCategory.RENTAL


def _preferred_surface(request: HttpRequest) -> str:
    surface = (request.POST.get("surface", "") or "").strip()[:40]
    return surface or "unknown"


def _preferred_redirect_target(*, request: HttpRequest, fallback_url: str) -> str:
    requested_target = (request.POST.get("next", "") or "").strip()
    if requested_target and url_has_allowed_host_and_scheme(
        url=requested_target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return requested_target
    return fallback_url


def _require_reporting_user(*, request: HttpRequest, next_url: str) -> HttpResponse | None:
    guest_redirect = require_authenticated_user(
        request,
        warning_message="Sign in with a supervisor or admin account to view reporting pages.",
        next_url=next_url,
    )
    if guest_redirect is not None:
        return guest_redirect

    if not _is_reporting_authorized_user(request.user):
        raise PermissionDenied("Reporting access is restricted to supervisor and admin staff roles.")
    return None


def _is_reporting_authorized_user(user: AbstractBaseUser | AnonymousUser) -> bool:
    return bool(getattr(user, "can_view_reports", False))


def _filter_staff_listings_queryset(*, status_filter: str):
    queryset = _staff_listing_queryset().order_by("-created_at")

    if status_filter in VALID_STAFF_LISTING_STATUS_FILTERS:
        queryset = queryset.filter(status=status_filter)

    return queryset


def _build_staff_listing_form_components(
    *,
    request: HttpRequest,
    listing: Property,
) -> tuple[PropertyForm, PropertyImageInlineFormSet, PropertyAmenityInlineFormSet]:
    form_data = request.POST if request.method == "POST" else None
    form = PropertyForm(form_data, instance=listing)
    image_formset = PropertyImageInlineFormSet(form_data, instance=listing, prefix="images")
    amenity_formset = PropertyAmenityInlineFormSet(form_data, instance=listing, prefix="amenities")
    return form, image_formset, amenity_formset


def _save_staff_listing(
    *,
    form: PropertyForm,
    image_formset: PropertyImageInlineFormSet,
    amenity_formset: PropertyAmenityInlineFormSet,
    fallback_listed_by: object,
) -> Property:
    with transaction.atomic():
        listing = form.save(commit=False)
        if listing.listed_by_id is None:
            listing.listed_by = fallback_listed_by
        listing.save()

        image_formset.instance = listing
        amenity_formset.instance = listing
        image_formset.save()
        amenity_formset.save()

    return listing


def _staff_listing_queryset():
    return (
        Property.objects.select_related("listed_by")
        .prefetch_related("images", "amenities")
    )


def _safe_log_favorite_action(
    *,
    request: HttpRequest,
    action: str,
    property_id: int,
    details: dict[str, object],
) -> None:
    try:
        log_interaction_activity(
            action=action,
            user=request.user,
            entity_type="property",
            entity_id=property_id,
            details=details,
        )
    except Exception:
        logger.exception(
            "Failed to log favorite interaction.",
            extra={"action": action, "property_id": property_id},
        )


def _safe_log_viewing_action(
    *,
    request: HttpRequest,
    viewing_request: ViewingRequest,
    details: dict[str, object],
) -> None:
    try:
        log_interaction_activity(
            action="viewing_requested",
            user=request.user,
            entity=viewing_request,
            details=details,
        )
    except Exception:
        logger.exception(
            "Failed to log viewing-request interaction.",
            extra={"viewing_request_id": viewing_request.pk},
        )


def _safe_log_booking_action(
    *,
    request: HttpRequest,
    booking_request: BookingRequest,
    details: dict[str, object],
) -> None:
    try:
        log_interaction_activity(
            action="booking_requested",
            user=request.user,
            entity=booking_request,
            details=details,
        )
    except Exception:
        logger.exception(
            "Failed to log booking-request interaction.",
            extra={"booking_request_id": booking_request.pk},
        )


def _add_validation_error_to_form(form: forms.Form, error: ValidationError) -> None:
    if hasattr(error, "message_dict"):
        for field_name, messages_for_field in error.message_dict.items():
            target_field = field_name if field_name in form.fields else None
            for message in messages_for_field:
                form.add_error(target_field, message)
        return

    form.add_error(None, error)


def _first_query_value(query_params: QueryDict, *keys: str) -> str:
    for key in keys:
        if key in query_params:
            return (query_params.get(key, "") or "").strip()
    return ""


def _get_category_label(category_code: str) -> str:
    try:
        return PropertyCategory(category_code).label
    except ValueError:
        return category_code.title()


def _decorate_search_trend_metrics(search_trend_metrics: list[dict[str, object]]) -> list[dict[str, object]]:
    decorated_metrics: list[dict[str, object]] = []
    for metric in search_trend_metrics:
        top_categories = []
        for category_entry in metric.get("top_categories", []):
            category_code = category_entry.get("category", "")
            top_categories.append(
                {
                    **category_entry,
                    "category_label": _get_category_label(category_code),
                }
            )

        decorated_metrics.append(
            {
                **metric,
                "top_categories": top_categories,
            }
        )

    return decorated_metrics


def _build_page_query_string(query_params: QueryDict, page_number: int) -> str:
    mutable_query = query_params.copy()
    mutable_query.pop("p", None)
    if page_number <= DEFAULT_CATALOG_PAGE:
        mutable_query.pop("page", None)
    else:
        mutable_query["page"] = str(page_number)
    return mutable_query.urlencode()


def _visible_page_numbers(*, current_page: int, total_pages: int) -> range:
    if total_pages <= 0:
        return range(0)
    start_page = max(1, current_page - 2)
    end_page = min(total_pages, current_page + 2)
    return range(start_page, end_page + 1)

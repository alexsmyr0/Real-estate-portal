from __future__ import annotations

import logging
from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import Http404, HttpRequest, HttpResponse, QueryDict
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from homefinder.apps.interactions.forms import PropertyInquiryForm
from homefinder.apps.interactions.models import PropertyInquiry, UserFavorite, ViewingRequest
from homefinder.apps.interactions.services import (
    create_property_inquiry,
    create_viewing_request,
    log_interaction_activity,
)

from .forms import ViewingRequestForm
from .models import Amenity, PropertyCategory
from .services import (
    DEFAULT_CATALOG_PAGE,
    PUBLICLY_VISIBLE_PROPERTY_STATUSES,
    get_visible_property,
    get_visible_property_detail,
    parse_catalog_search_params,
    search_visible_properties,
    serialize_property_for_catalog_card,
    serialize_property_for_detail,
)

logger = logging.getLogger(__name__)

CATALOG_BEDROOM_FILTER_OPTIONS = (1, 2, 3, 4, 5)
INQUIRY_CONFIRMATION_SESSION_KEY = "property_inquiry_confirmation"
VERIFIED_VIEWING_REQUEST_SESSION_KEY = "verified_viewing_request_id"


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
    property_payload = get_visible_property_detail(property_id)
    if property_payload is None:
        raise Http404("Property not found.")

    _apply_detail_favorite_state(request=request, property_payload=property_payload)

    return _render_property_detail(
        request=request,
        property_payload=property_payload,
        viewing_form=ViewingRequestForm(),
        viewing_confirmation=_consume_verified_viewing_confirmation(
            request=request,
            property_id=property_id,
        ),
        inquiry_submitted=_consume_inquiry_confirmation(
            request=request,
            property_id=property_id,
        ),
    )


@require_http_methods(["POST"])
def submit_inquiry_action(request: HttpRequest, property_id: int) -> HttpResponse:
    detail_url = reverse("site-property-detail", args=[property_id])
    guest_redirect = _require_authenticated_user(
        request,
        warning_message="Sign in before sending an inquiry.",
        next_url=detail_url,
    )
    if guest_redirect is not None:
        return guest_redirect

    property_obj = get_visible_property(property_id)
    if property_obj is None:
        raise Http404("Property not found.")

    inquiry_form = PropertyInquiryForm(request.POST)
    if not inquiry_form.is_valid():
        messages.error(request, "Please correct the highlighted fields and send your inquiry again.")
        property_payload = serialize_property_for_detail(property_obj)
        _apply_detail_favorite_state(request=request, property_payload=property_payload)
        return _render_property_detail(
            request=request,
            property_payload=property_payload,
            viewing_form=ViewingRequestForm(),
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
        _apply_detail_favorite_state(request=request, property_payload=property_payload)
        return _render_property_detail(
            request=request,
            property_payload=property_payload,
            viewing_form=ViewingRequestForm(),
            inquiry_form=inquiry_form,
        )

    _store_inquiry_confirmation(request=request, inquiry=inquiry)
    messages.success(request, "Inquiry sent. We emailed you a confirmation.")
    return redirect(detail_url)


@require_http_methods(["GET"])
def favorites_page(request: HttpRequest) -> HttpResponse:
    guest_redirect = _require_authenticated_user(
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
    guest_redirect = _require_authenticated_user(
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
    guest_redirect = _require_authenticated_user(
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


@require_http_methods(["POST"])
def viewing_request_action(request: HttpRequest, property_id: int) -> HttpResponse:
    detail_url = reverse("site-property-detail", args=[property_id])
    guest_redirect = _require_authenticated_user(
        request,
        warning_message="Sign in to request a viewing.",
        next_url=detail_url,
    )
    if guest_redirect is not None:
        return guest_redirect

    property_obj = get_visible_property(property_id)
    if property_obj is None:
        raise Http404("Property not found.")

    viewing_form = ViewingRequestForm(request.POST)
    if not viewing_form.is_valid():
        property_payload = serialize_property_for_detail(property_obj)
        _apply_detail_favorite_state(request=request, property_payload=property_payload)
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
        _apply_detail_favorite_state(request=request, property_payload=property_payload)
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


def _render_property_detail(
    *,
    request: HttpRequest,
    property_payload: dict[str, object],
    viewing_form: ViewingRequestForm,
    viewing_confirmation: ViewingRequest | None = None,
    inquiry_form: PropertyInquiryForm | None = None,
    inquiry_submitted: bool = False,
) -> HttpResponse:
    return render(
        request,
        "properties/detail.html",
        {
            "property": property_payload,
            "category_label": _get_category_label(str(property_payload["category"])),
            "viewing_form": viewing_form,
            "viewing_confirmation": viewing_confirmation,
            "inquiry_form": inquiry_form if inquiry_form is not None else PropertyInquiryForm(),
            "inquiry_submitted": inquiry_submitted,
        },
    )


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


def _store_inquiry_confirmation(*, request: HttpRequest, inquiry: PropertyInquiry) -> None:
    request.session[INQUIRY_CONFIRMATION_SESSION_KEY] = {
        "inquiry_id": inquiry.pk,
        "property_id": inquiry.property_id,
        "user_id": inquiry.user_id,
    }
    request.session.modified = True


def _consume_inquiry_confirmation(*, request: HttpRequest, property_id: int) -> bool:
    marker = request.session.pop(INQUIRY_CONFIRMATION_SESSION_KEY, None)
    if marker is not None:
        request.session.modified = True

    if not request.user.is_authenticated or not isinstance(marker, dict):
        return False

    try:
        inquiry_id = int(marker.get("inquiry_id", 0))
        marker_property_id = int(marker.get("property_id", 0))
        marker_user_id = int(marker.get("user_id", 0))
    except (TypeError, ValueError):
        return False

    if marker_property_id != property_id or marker_user_id != request.user.pk:
        return False

    return PropertyInquiry.objects.filter(
        pk=inquiry_id,
        user=request.user,
        property_id=property_id,
    ).exists()


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

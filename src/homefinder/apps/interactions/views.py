from __future__ import annotations

from urllib.parse import urlencode

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from homefinder.apps.properties.models import Property
from homefinder.apps.properties.services import PUBLICLY_VISIBLE_PROPERTY_STATUSES

from .models import PropertyInquiry, SearchHistory, UserFavorite, ViewingRequest

DASHBOARD_CURRENT_LIMIT = 5
DASHBOARD_OLDER_LIMIT = 5
DASHBOARD_SECTION_LIMIT = DASHBOARD_CURRENT_LIMIT + DASHBOARD_OLDER_LIMIT


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
            "dashboard_current_limit": DASHBOARD_CURRENT_LIMIT,
            "dashboard_older_limit": DASHBOARD_OLDER_LIMIT,
        },
    )


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

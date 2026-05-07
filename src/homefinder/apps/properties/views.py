from __future__ import annotations

from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.http import HttpRequest, HttpResponse, QueryDict
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from homefinder.apps.interactions.forms import PropertyInquiryForm
from homefinder.apps.interactions.services import create_property_inquiry

from .models import Amenity, PropertyCategory
from .services import (
    DEFAULT_CATALOG_PAGE,
    get_visible_property_detail,
    parse_catalog_search_params,
    search_visible_properties,
    visible_properties_queryset,
)

CATALOG_BEDROOM_FILTER_OPTIONS = (1, 2, 3, 4, 5)


def catalog_page(request: HttpRequest) -> HttpResponse:
    search_params = parse_catalog_search_params(request.GET)
    search_results = search_visible_properties(search_params=search_params)

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
            "properties": search_results["properties"],
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


@require_http_methods(["GET", "POST"])
def property_detail_page(request: HttpRequest, property_id: int) -> HttpResponse:
    property_payload = get_visible_property_detail(property_id)
    if property_payload is None:
        raise Http404("Property not found.")

    if request.method == "POST":
        if not request.user.is_authenticated:
            login_url = f"{reverse('login-page')}?{urlencode({'next': request.path})}"
            messages.warning(request, "Sign in before sending an inquiry.")
            return redirect(login_url)

        form = PropertyInquiryForm(request.POST)
        if form.is_valid():
            property_obj = visible_properties_queryset().filter(pk=property_id).first()
            if property_obj is None:
                raise Http404("Property not found.")

            try:
                create_property_inquiry(
                    user=request.user,
                    property_obj=property_obj,
                    message=form.cleaned_data["message"],
                )
            except ValidationError as error:
                _add_validation_error_to_form(form=form, error=error)
                messages.error(request, "Please correct the highlighted fields and send your inquiry again.")
            else:
                messages.success(request, "Inquiry sent. We emailed you a confirmation.")
                detail_url = reverse("property-detail", args=[property_id])
                return redirect(f"{detail_url}?inquiry=sent")
        else:
            messages.error(request, "Please correct the highlighted fields and send your inquiry again.")
    else:
        form = PropertyInquiryForm()

    return _render_property_detail_page(
        request=request,
        property_payload=property_payload,
        form=form,
        inquiry_submitted=request.GET.get("inquiry") == "sent",
    )


def _render_property_detail_page(
    *,
    request: HttpRequest,
    property_payload: dict[str, object],
    form: PropertyInquiryForm,
    inquiry_submitted: bool,
) -> HttpResponse:
    return render(
        request,
        "properties/detail.html",
        {
            "property": property_payload,
            "inquiry_form": form,
            "inquiry_submitted": inquiry_submitted,
            "login_url": f"{reverse('login-page')}?{urlencode({'next': request.path})}",
            "register_url": reverse("register-page"),
        },
    )


def _add_validation_error_to_form(*, form: PropertyInquiryForm, error: ValidationError) -> None:
    if hasattr(error, "message_dict"):
        for field_name, field_errors in error.message_dict.items():
            target_field = field_name if field_name in form.fields else None
            for field_error in field_errors:
                form.add_error(target_field, field_error)
        return

    for field_error in error.messages:
        form.add_error(None, field_error)


def _first_query_value(query_params: QueryDict, *keys: str) -> str:
    for key in keys:
        if key in query_params:
            return (query_params.get(key, "") or "").strip()
    return ""


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

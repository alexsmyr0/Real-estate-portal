from __future__ import annotations

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, JsonResponse, QueryDict
from django.shortcuts import render
from django.urls import reverse

from homefinder.apps.properties.services import parse_catalog_search_params, search_visible_properties

from .forms import CatalogShellFilterForm

def json_error_response(status_code: int, message: str) -> JsonResponse:
    return JsonResponse(
        {
            "status": "error",
            "error": {
                "code": status_code,
                "message": message,
            },
        },
        status=status_code,
    )


def index(_request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {
            "status": "ok",
            "service": "homefinder",
        }
    )


def health(_request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


def site_home(request: HttpRequest) -> HttpResponse:
    if request.GET.get("flash") == "1":
        messages.success(
            request,
            "Shared shell is active. This banner comes from the reusable flash-message partial.",
        )

    return render(request, "core/site_home.html")


def site_catalog(request: HttpRequest) -> HttpResponse:
    filter_form = CatalogShellFilterForm(request.GET or None)
    if filter_form.is_bound:
        filter_form.is_valid()

    search_params = parse_catalog_search_params(request.GET)
    search_results = search_visible_properties(search_params=search_params)
    pagination = search_results["pagination"]

    previous_page_url: str | None = None
    next_page_url: str | None = None
    if pagination["has_previous"]:
        previous_page_url = f'{reverse("site-catalog")}?{_query_with_page(request.GET, pagination["page"] - 1)}'
    if pagination["has_next"]:
        next_page_url = f'{reverse("site-catalog")}?{_query_with_page(request.GET, pagination["page"] + 1)}'

    return render(
        request,
        "core/site_catalog.html",
        {
            "catalog_filter_form": filter_form,
            "properties": search_results["properties"],
            "pagination": pagination,
            "has_active_filters": _has_active_filters(request.GET),
            "previous_page_url": previous_page_url,
            "next_page_url": next_page_url,
        },
    )


def unauthorized_response(message: str = "Unauthorized") -> JsonResponse:
    return json_error_response(401, message)


def bad_request_view(_request: HttpRequest, exception: Exception) -> JsonResponse:
    del exception
    return json_error_response(400, "Bad Request")


def permission_denied_view(_request: HttpRequest, exception: Exception) -> JsonResponse:
    del exception
    return json_error_response(403, "Forbidden")


def page_not_found_view(_request: HttpRequest, exception: Exception) -> JsonResponse:
    del exception
    return json_error_response(404, "Not Found")


def server_error_view(_request: HttpRequest) -> JsonResponse:
    return json_error_response(500, "Internal Server Error")


def _query_with_page(query_params: QueryDict, page: int) -> str:
    updated_query = query_params.copy()
    if page <= 1:
        updated_query.pop("page", None)
    else:
        updated_query["page"] = str(page)
    return updated_query.urlencode()


def _has_active_filters(query_params: QueryDict) -> bool:
    for key, values in query_params.lists():
        if key == "page":
            continue
        for value in values:
            if value.strip():
                return True
    return False

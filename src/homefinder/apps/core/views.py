from __future__ import annotations

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

from homefinder.apps.properties.services import CatalogSearchParams, search_visible_properties

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
    catalog_snapshot = search_visible_properties(search_params=CatalogSearchParams(page=1))
    featured_properties = catalog_snapshot["properties"][:3]
    total_visible_listings = catalog_snapshot["pagination"]["total_items"]

    return render(
        request,
        "core/site_home.html",
        {
            "featured_properties": featured_properties,
            "total_visible_listings": total_visible_listings,
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

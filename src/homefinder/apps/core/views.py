from __future__ import annotations

import logging

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

from homefinder.apps.properties.services import (
    get_featured_visible_properties,
    get_personalized_recommendations,
    visible_properties_queryset,
)

logger = logging.getLogger(__name__)


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


def health(_request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


def site_home(request: HttpRequest) -> HttpResponse:
    featured_properties = get_featured_visible_properties(limit=3)
    total_visible_listings = visible_properties_queryset().count()
    recommended_properties = _safe_get_recommendations(
        user=request.user,
        request_surface="landing",
    )

    return render(
        request,
        "core/site_home.html",
        {
            "featured_properties": featured_properties,
            "total_visible_listings": total_visible_listings,
            "recommended_properties": recommended_properties,
        },
    )


def _safe_get_recommendations(
    *,
    user: object,
    request_surface: str,
) -> list[dict[str, object]]:
    try:
        return get_personalized_recommendations(
            user=user,
            request_surface=request_surface,
        )
    except Exception:
        logger.exception(
            "Failed to load personalized recommendations.",
            extra={"request_surface": request_surface},
        )
        return []


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

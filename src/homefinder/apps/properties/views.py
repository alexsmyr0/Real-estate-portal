from __future__ import annotations

from django.http import HttpRequest, JsonResponse

from homefinder.apps.core.views import json_error_response

from .services import get_visible_property_detail, parse_catalog_search_params, search_visible_properties


def catalog_list(request: HttpRequest) -> JsonResponse:
    search_params = parse_catalog_search_params(request.GET)
    search_results = search_visible_properties(search_params=search_params)

    return JsonResponse(
        {
            "status": "ok",
            "data": search_results,
        }
    )


def catalog_detail(_request: HttpRequest, property_id: int) -> JsonResponse:
    property_payload = get_visible_property_detail(property_id=property_id)
    if property_payload is None:
        return json_error_response(404, "Not Found")

    return JsonResponse(
        {
            "status": "ok",
            "data": {
                "property": property_payload,
            },
        }
    )

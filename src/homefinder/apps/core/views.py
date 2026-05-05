from __future__ import annotations

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

from .forms import ShellContactPreferenceForm

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

    if "intent" in request.GET:
        shell_form = ShellContactPreferenceForm(request.GET)
        if shell_form.is_valid():
            messages.success(request, "Preferences noted. Full save available once account features ship.")
    else:
        shell_form = ShellContactPreferenceForm()

    demo_property = {
        "title": "Athens Garden Loft",
        "city": "Athens",
        "area": "Pangrati",
        "price": "385000.00",
        "bedrooms": 2,
        "bathrooms": 1.5,
        "primary_image_url": None,
        "availability": {
            "label": "Available",
            "is_available": True,
            "is_unavailable": False,
        },
    }

    return render(
        request,
        "core/site_home.html",
        {
            "shell_form": shell_form,
            "demo_property": demo_property,
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

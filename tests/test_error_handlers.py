from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django
django.setup()

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.test import Client, SimpleTestCase, override_settings
from django.urls import path

from homefinder.apps.core.views import (
    bad_request_view,
    health,
    permission_denied_view,
    unauthorized_response,
)


def trigger_400(request: HttpRequest) -> HttpResponse:
    return bad_request_view(request, Exception("bad request"))


def trigger_401(_request: HttpRequest) -> HttpResponse:
    return unauthorized_response()


def trigger_403(request: HttpRequest) -> HttpResponse:
    return permission_denied_view(request, PermissionDenied("forbidden"))


def trigger_500(_request: HttpRequest) -> HttpResponse:
    raise RuntimeError("boom")


urlpatterns = [
    path("api/v1/health/", health, name="health"),
    path("api/v1/_test-400/", trigger_400, name="test-400"),
    path("api/v1/_test-401/", trigger_401, name="test-401"),
    path("api/v1/_test-403/", trigger_403, name="test-403"),
    path("api/v1/_test-error/", trigger_500, name="test-500"),
]

handler400 = "homefinder.apps.core.views.bad_request_view"
handler403 = "homefinder.apps.core.views.permission_denied_view"
handler404 = "homefinder.apps.core.views.page_not_found_view"
handler500 = "homefinder.apps.core.views.server_error_view"


@override_settings(ROOT_URLCONF=__name__, DEBUG=False, ALLOWED_HOSTS=["testserver"])
class ErrorHandlerTests(SimpleTestCase):
    def setUp(self) -> None:
        self.client = Client(raise_request_exception=False)

    def test_health_route_returns_ok_json(self) -> None:
        response = self.client.get("/api/v1/health/")

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "ok"})

    def test_unknown_route_returns_json_404(self) -> None:
        response = self.client.get("/api/v1/unknown-route/")

        self.assertEqual(response.status_code, 404)
        self.assertJSONEqual(
            response.content,
            {
                "status": "error",
                "error": {"code": 404, "message": "Not Found"},
            },
        )

    def test_internal_error_returns_json_500(self) -> None:
        response = self.client.get("/api/v1/_test-error/")

        self.assertEqual(response.status_code, 500)
        self.assertJSONEqual(
            response.content,
            {
                "status": "error",
                "error": {"code": 500, "message": "Internal Server Error"},
            },
        )

    def test_client_errors_return_json(self) -> None:
        expectations = [
            ("/api/v1/_test-400/", 400, "Bad Request"),
            ("/api/v1/_test-401/", 401, "Unauthorized"),
            ("/api/v1/_test-403/", 403, "Forbidden"),
        ]

        for path_value, status_code, message in expectations:
            with self.subTest(path=path_value):
                response = self.client.get(path_value)

                self.assertEqual(response.status_code, status_code)
                self.assertJSONEqual(
                    response.content,
                    {
                        "status": "error",
                        "error": {"code": status_code, "message": message},
                    },
                )

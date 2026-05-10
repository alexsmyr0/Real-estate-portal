from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("homefinder.apps.core.urls")),
    path("", include("homefinder.apps.users.urls")),
    path("", include("homefinder.apps.properties.urls")),
    path("", include("homefinder.apps.interactions.urls")),
]

handler400 = "homefinder.apps.core.views.bad_request_view"
handler403 = "homefinder.apps.core.views.permission_denied_view"
handler404 = "homefinder.apps.core.views.page_not_found_view"
handler500 = "homefinder.apps.core.views.server_error_view"

from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/v1/health/", views.health, name="health"),
    path("site/", views.site_home, name="site-home"),
    path("site/catalog/", views.site_catalog, name="site-catalog"),
]

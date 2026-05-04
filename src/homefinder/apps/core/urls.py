from django.urls import path

from . import views

urlpatterns = [
    path("", views.site_home, name="home"),
    path("api/v1/", views.index, name="index"),
    path("api/v1/health/", views.health, name="health"),
]

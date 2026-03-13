from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/v1/health/", views.health, name="health"),
]

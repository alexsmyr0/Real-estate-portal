from django.urls import path

from . import views

urlpatterns = [
    path("catalog/", views.catalog_page, name="site-catalog"),
    path("catalog/<int:property_id>/", views.property_detail_page, name="site-property-detail"),
]

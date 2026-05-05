from django.urls import path

from . import views

urlpatterns = [
    path("site/catalog/", views.catalog_page, name="site-catalog"),
    path("catalog/", views.catalog_list, name="catalog-list"),
    path("catalog/<int:property_id>/", views.catalog_detail, name="catalog-detail"),
]

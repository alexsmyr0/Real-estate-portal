from django.urls import path

from . import views

urlpatterns = [
    path("catalog/", views.catalog_page, name="site-catalog"),
    path("catalog/<int:property_id>/", views.property_detail_page, name="site-property-detail"),
    path("catalog/<int:property_id>/favorite/", views.add_favorite_action, name="site-favorite-add"),
    path("catalog/<int:property_id>/unfavorite/", views.remove_favorite_action, name="site-favorite-remove"),
    path("saved-listings/", views.favorites_page, name="site-favorites"),
]

from django.urls import path

from . import views

urlpatterns = [
    path("catalog/", views.catalog_page, name="site-catalog"),
    path("catalog/<int:property_id>/", views.property_detail_page, name="site-property-detail"),
    path("catalog/<int:property_id>/favorite/", views.add_favorite_action, name="site-favorite-add"),
    path("catalog/<int:property_id>/unfavorite/", views.remove_favorite_action, name="site-favorite-remove"),
    path("catalog/<int:property_id>/viewing-request/", views.viewing_request_action, name="site-viewing-request"),
    path(
        "catalog/<int:property_id>/similar-listing-alert/",
        views.listing_alert_subscription_action,
        name="site-listing-alert-subscribe",
    ),
    path("catalog/<int:property_id>/booking-request/", views.booking_request_action, name="site-booking-request"),
    path("catalog/<int:property_id>/inquiry/", views.submit_inquiry_action, name="site-inquiry-create"),
    path("saved-listings/", views.favorites_page, name="site-favorites"),
    path("staff/listings/", views.listing_list_page, name="staff-listing-list"),
    path("staff/listings/new/", views.listing_create_page, name="staff-listing-create"),
    path("staff/listings/<int:listing_id>/edit/", views.listing_edit_page, name="staff-listing-edit"),
    path("staff/listings/<int:listing_id>/delete/", views.listing_delete_page, name="staff-listing-delete"),
    path("staff/reports/", views.reporting_overview_page, name="staff-reporting-overview"),
    path(
        "staff/reports/search-trends/",
        views.reporting_search_trends_page,
        name="staff-reporting-search-trends",
    ),
]

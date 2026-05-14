from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.dashboard_page, name="site-dashboard"),
    path("dashboard/searches/", views.dashboard_searches_list, name="site-dashboard-searches"),
    path("dashboard/inquiries/", views.dashboard_inquiries_list, name="site-dashboard-inquiries"),
    path("dashboard/viewings/", views.dashboard_viewings_list, name="site-dashboard-viewings"),
    path("dashboard/alerts/", views.dashboard_alerts_list, name="site-dashboard-alerts"),
    path(
        "bookings/<int:booking_request_id>/simulated-payment/",
        views.booking_simulated_payment_page,
        name="site-booking-simulated-payment",
    ),
    path(
        "bookings/<int:booking_request_id>/simulated-payment/<slug:action>/",
        views.booking_simulated_payment_action,
        name="site-booking-simulated-payment-action",
    ),
]

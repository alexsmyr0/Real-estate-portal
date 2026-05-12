from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.dashboard_page, name="site-dashboard"),
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

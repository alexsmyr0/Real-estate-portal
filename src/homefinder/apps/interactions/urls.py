from django.urls import path

from . import staff_views, views

urlpatterns = [
    path("dashboard/", views.dashboard_page, name="site-dashboard"),
    path(
        "staff/interactions/inquiries/",
        staff_views.staff_inquiry_management_page,
        name="staff-interactions-inquiries",
    ),
    path(
        "staff/interactions/viewings/",
        staff_views.staff_viewing_management_page,
        name="staff-interactions-viewings",
    ),
    path(
        "staff/interactions/bookings/",
        staff_views.staff_booking_management_page,
        name="staff-interactions-bookings",
    ),
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

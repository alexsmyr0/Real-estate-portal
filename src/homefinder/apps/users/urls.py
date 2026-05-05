from django.urls import path

from . import views

urlpatterns = [
    path("auth/register/", views.register, name="auth-register"),
    path("auth/login/", views.login, name="auth-login"),
    path("auth/2fa/", views.two_factor, name="auth-2fa"),
    path("auth/2fa/verify/", views.verify_2fa, name="auth-2fa-verify"),
    path("auth/logout/", views.logout, name="auth-logout"),
]

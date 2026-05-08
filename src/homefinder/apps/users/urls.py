from django.urls import path

from . import views

urlpatterns = [
    path("register/", views.register_page, name="register-page"),
    path("login/", views.login_page, name="login-page"),
    path("login/2fa/", views.verify_2fa_page, name="verify-2fa-page"),
    path("logout/", views.logout_page, name="logout-page"),
    path("auth/register/", views.register, name="auth-register"),
    path("auth/login/", views.login, name="auth-login"),
    path("auth/2fa/verify/", views.verify_2fa, name="auth-2fa-verify"),
    path("auth/logout/", views.logout, name="auth-logout"),
]

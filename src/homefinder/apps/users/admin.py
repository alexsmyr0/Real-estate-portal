from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import ActiveSession, LoginTwoFactorToken, User


@admin.register(User)
class HomeFinderUserAdmin(UserAdmin):
    ordering = ("email",)
    list_display = ("email", "role", "is_active", "is_staff", "is_superuser")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("email", "full_name", "phone")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("full_name", "phone", "role")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Compliance", {"fields": ("email_verified_at", "gdpr_consent_at", "deleted_at")}),
        ("Timestamps", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "role", "is_active", "is_staff"),
            },
        ),
    )
    readonly_fields = ("last_login", "created_at", "updated_at")


@admin.register(LoginTwoFactorToken)
class LoginTwoFactorTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "sent_at", "expires_at", "verified_at", "attempts_used")
    search_fields = ("user__email", "token_hash")


@admin.register(ActiveSession)
class ActiveSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "expires_at")
    search_fields = ("user__email", "session_token_hash")

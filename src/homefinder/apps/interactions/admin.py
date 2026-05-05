from django.contrib import admin

from . import services
from .models import (
    ActivityLog,
    BookingRequest,
    EmailNotification,
    Payment,
    PropertyInquiry,
    SearchHistory,
    SimilarListingAlertDispatch,
    UserFavorite,
    ViewingRequest,
)


@admin.register(PropertyInquiry)
class PropertyInquiryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "user_email",
        "property",
        "property_city",
        "created_at",
        "updated_at",
    )
    list_editable = ("status",)
    list_filter = (
        "status",
        "created_at",
        "property__category",
        "property__city",
    )
    search_fields = (
        "user__email",
        "user__full_name",
        "property__title",
        "property__city",
        "property__area",
        "message",
    )
    autocomplete_fields = ("user", "property")
    list_select_related = ("user", "property")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"
    fieldsets = (
        (
            "Inquiry",
            {
                "fields": (
                    "status",
                    "user",
                    "property",
                    "message",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    @admin.display(description="User email", ordering="user__email")
    def user_email(self, obj: PropertyInquiry) -> str:
        return obj.user.email

    @admin.display(description="City", ordering="property__city")
    def property_city(self, obj: PropertyInquiry) -> str:
        return obj.property.city


@admin.register(ViewingRequest)
class ViewingRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "requested_datetime",
        "user_email",
        "property",
        "property_city",
        "created_at",
        "updated_at",
    )
    list_editable = ("status",)
    list_filter = (
        "status",
        "requested_datetime",
        "created_at",
        "property__category",
        "property__city",
    )
    search_fields = (
        "user__email",
        "user__full_name",
        "property__title",
        "property__city",
        "property__area",
        "note",
    )
    autocomplete_fields = ("user", "property")
    list_select_related = ("user", "property")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "requested_datetime"
    fieldsets = (
        (
            "Viewing Request",
            {
                "fields": (
                    "status",
                    "requested_datetime",
                    "user",
                    "property",
                    "note",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    @admin.display(description="User email", ordering="user__email")
    def user_email(self, obj: ViewingRequest) -> str:
        return obj.user.email

    @admin.display(description="City", ordering="property__city")
    def property_city(self, obj: ViewingRequest) -> str:
        return obj.property.city


@admin.register(BookingRequest)
class BookingRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "start_date",
        "end_date",
        "user_email",
        "property",
        "property_city",
        "created_at",
        "updated_at",
    )
    list_editable = ("status",)
    list_filter = (
        "status",
        "start_date",
        "end_date",
        "created_at",
        "property__category",
        "property__city",
    )
    search_fields = (
        "user__email",
        "user__full_name",
        "property__title",
        "property__city",
        "property__area",
        "note",
    )
    autocomplete_fields = ("user", "property")
    list_select_related = ("user", "property")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "start_date"
    fieldsets = (
        (
            "Booking Request",
            {
                "fields": (
                    "status",
                    "start_date",
                    "end_date",
                    "user",
                    "property",
                    "note",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def save_model(self, request: object, obj: BookingRequest, form: object, change: bool) -> None:
        previous_status = None
        if change:
            previous_status = BookingRequest.objects.filter(pk=obj.pk).values_list("status", flat=True).first()

        if change and previous_status != obj.status:
            services.update_booking_request_status(obj, status=obj.status)
            return

        super().save_model(request, obj, form, change)

        if previous_status is None:
            services.send_booking_update_email(obj)

    @admin.display(description="User email", ordering="user__email")
    def user_email(self, obj: BookingRequest) -> str:
        return obj.user.email

    @admin.display(description="City", ordering="property__city")
    def property_city(self, obj: BookingRequest) -> str:
        return obj.property.city


admin.site.register(UserFavorite)
admin.site.register(Payment)
admin.site.register(EmailNotification)
admin.site.register(SimilarListingAlertDispatch)
admin.site.register(SearchHistory)
admin.site.register(ActivityLog)

from django.contrib import admin

from .models import (
    ActivityLog,
    BookingRequest,
    EmailNotification,
    Payment,
    PropertyInquiry,
    SearchHistory,
    UserFavorite,
    ViewingRequest,
)

admin.site.register(UserFavorite)
admin.site.register(ViewingRequest)
admin.site.register(PropertyInquiry)
admin.site.register(BookingRequest)
admin.site.register(Payment)
admin.site.register(EmailNotification)
admin.site.register(SearchHistory)
admin.site.register(ActivityLog)

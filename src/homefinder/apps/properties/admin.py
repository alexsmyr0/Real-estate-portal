from django.contrib import admin

from .models import (
    Amenity,
    ListingAlertSubscription,
    ListingAlertSubscriptionAmenity,
    Property,
    PropertyAmenity,
    PropertyImage,
)

admin.site.register(Property)
admin.site.register(Amenity)
admin.site.register(PropertyAmenity)
admin.site.register(PropertyImage)
admin.site.register(ListingAlertSubscription)
admin.site.register(ListingAlertSubscriptionAmenity)

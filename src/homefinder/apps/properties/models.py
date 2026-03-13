from __future__ import annotations

from django.conf import settings
from django.db import models


class PropertyCategory(models.TextChoices):
    RESIDENTIAL = "RESIDENTIAL", "Residential"
    COMMERCIAL = "COMMERCIAL", "Commercial"
    RENTAL = "RENTAL", "Rental"


class PropertyStatus(models.TextChoices):
    AVAILABLE = "AVAILABLE", "Available"
    UNAVAILABLE = "UNAVAILABLE", "Unavailable"
    REMOVED = "REMOVED", "Removed"


class Amenity(models.Model):
    name = models.CharField(max_length=80, unique=True)

    class Meta:
        db_table = "amenities"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Property(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=16, choices=PropertyCategory.choices)
    status = models.CharField(max_length=16, choices=PropertyStatus.choices, default=PropertyStatus.AVAILABLE)
    city = models.CharField(max_length=100)
    area = models.CharField(max_length=120, blank=True)
    address_line = models.CharField(max_length=255, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    bedrooms = models.PositiveSmallIntegerField(null=True, blank=True)
    bathrooms = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    listed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="listed_properties",
    )
    amenities = models.ManyToManyField(Amenity, through="PropertyAmenity", related_name="properties", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "properties"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class PropertyAmenity(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE)
    amenity = models.ForeignKey(Amenity, on_delete=models.CASCADE)

    class Meta:
        db_table = "property_amenities"
        constraints = [
            models.UniqueConstraint(fields=["property", "amenity"], name="uq_property_amenities_property_amenity"),
        ]

    def __str__(self) -> str:
        return f"{self.property_id}:{self.amenity_id}"


class PropertyImage(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="images")
    image_url = models.URLField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "property_images"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return self.image_url


class ListingAlertSubscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="listing_alert_subscriptions")
    category = models.CharField(max_length=16, choices=PropertyCategory.choices, blank=True)
    location_city = models.CharField(max_length=100, blank=True)
    min_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    max_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    bedrooms_min = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    amenities = models.ManyToManyField(Amenity, through="ListingAlertSubscriptionAmenity", related_name="listing_alert_subscriptions", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "listing_alert_subscriptions"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"AlertSubscription<{self.pk}>"


class ListingAlertSubscriptionAmenity(models.Model):
    subscription = models.ForeignKey(ListingAlertSubscription, on_delete=models.CASCADE)
    amenity = models.ForeignKey(Amenity, on_delete=models.CASCADE)

    class Meta:
        db_table = "listing_alert_subscription_amenities"
        constraints = [
            models.UniqueConstraint(
                fields=["subscription", "amenity"],
                name="uq_listing_alert_subscription_amenity",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.subscription_id}:{self.amenity_id}"

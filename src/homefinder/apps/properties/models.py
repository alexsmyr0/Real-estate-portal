from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
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
    source_property = models.ForeignKey(
        "Property",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="similar_alert_subscriptions",
    )
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
        indexes = [
            models.Index(fields=["is_active", "category", "location_city"], name="idx_alert_active_category_city"),
            models.Index(fields=["min_price", "max_price"], name="idx_alert_price_range"),
            models.Index(fields=["bedrooms_min"], name="idx_alert_bedrooms_min"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(min_price__isnull=True)
                | models.Q(max_price__isnull=True)
                | models.Q(min_price__lte=models.F("max_price")),
                name="ck_alert_price_bounds",
            ),
            models.CheckConstraint(
                condition=models.Q(bedrooms_min__isnull=True) | models.Q(bedrooms_min__gt=0),
                name="ck_alert_bedrooms_min_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(is_active=False) | models.Q(source_property__isnull=False),
                name="ck_active_alert_has_source_property",
            ),
            models.CheckConstraint(
                condition=models.Q(is_active=False) | (~models.Q(category="") & ~models.Q(location_city="")),
                name="ck_active_alert_has_required_filters",
            ),
        ]

    def __str__(self) -> str:
        return f"AlertSubscription<{self.pk}>"

    def clean(self) -> None:
        super().clean()

        errors: dict[str, str] = {}

        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            errors["max_price"] = "Maximum price must be greater than or equal to minimum price."

        if self.bedrooms_min is not None and self.bedrooms_min <= 0:
            errors["bedrooms_min"] = "Minimum bedrooms must be greater than zero."

        if self.is_active:
            if self.source_property_id is None:
                errors["source_property"] = "Active alert subscriptions require a source property."
            elif self.source_property.status != PropertyStatus.UNAVAILABLE:
                errors["source_property"] = "Active alert subscriptions require an unavailable source property."
            if not (self.category or "").strip():
                errors["category"] = "Active alert subscriptions require a category."
            if not (self.location_city or "").strip():
                errors["location_city"] = "Active alert subscriptions require a city."

        if errors:
            raise ValidationError(errors)

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


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

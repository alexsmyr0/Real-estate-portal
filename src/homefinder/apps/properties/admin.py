from django.contrib import admin
from django.db.models import Count, QuerySet

from .models import (
    Amenity,
    ListingAlertSubscription,
    ListingAlertSubscriptionAmenity,
    Property,
    PropertyAmenity,
    PropertyImage,
)
from .services import PUBLICLY_VISIBLE_PROPERTY_STATUSES, build_property_availability_context


class CatalogVisibilityListFilter(admin.SimpleListFilter):
    title = "catalog visibility"
    parameter_name = "catalog_visibility"

    def lookups(self, request, model_admin):
        return (
            ("visible", "Visible in public catalog"),
            ("hidden", "Hidden from public catalog"),
        )

    def queryset(self, request, queryset):
        if self.value() == "visible":
            return queryset.filter(status__in=PUBLICLY_VISIBLE_PROPERTY_STATUSES)
        if self.value() == "hidden":
            return queryset.exclude(status__in=PUBLICLY_VISIBLE_PROPERTY_STATUSES)
        return queryset


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1
    fields = ("image_url", "created_at")
    readonly_fields = ("created_at",)


class PropertyAmenityInline(admin.TabularInline):
    model = PropertyAmenity
    extra = 1
    autocomplete_fields = ("amenity",)


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "status",
        "catalog_visibility",
        "city",
        "price",
        "bedrooms",
        "listed_by",
        "updated_at",
    )
    list_editable = ("status",)
    list_filter = (
        CatalogVisibilityListFilter,
        "status",
        "category",
        "city",
        "listed_by",
    )
    search_fields = (
        "title",
        "description",
        "city",
        "area",
        "address_line",
        "listed_by__email",
        "listed_by__full_name",
    )
    autocomplete_fields = ("listed_by",)
    readonly_fields = ("catalog_visibility", "created_at", "updated_at")
    fieldsets = (
        (
            "Listing",
            {
                "fields": (
                    "title",
                    "description",
                    "category",
                    "status",
                    "catalog_visibility",
                    "price",
                    "listed_by",
                )
            },
        ),
        (
            "Location",
            {
                "fields": (
                    "city",
                    "area",
                    "address_line",
                )
            },
        ),
        (
            "Details",
            {
                "fields": (
                    "bedrooms",
                    "bathrooms",
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
    inlines = (PropertyAmenityInline, PropertyImageInline)

    @admin.display(description="Catalog visibility", ordering="status")
    def catalog_visibility(self, obj: Property) -> str:
        availability = build_property_availability_context(obj.status)
        if availability.is_publicly_visible:
            return f"Visible ({availability.label})"
        return f"Hidden ({availability.label})"


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ("name", "property_count")
    search_fields = ("name",)
    ordering = ("name",)

    def get_queryset(self, request) -> QuerySet[Amenity]:
        queryset = super().get_queryset(request)
        return queryset.annotate(_property_count=Count("properties", distinct=True))

    @admin.display(description="Listings", ordering="_property_count")
    def property_count(self, obj: Amenity) -> int:
        return getattr(obj, "_property_count", obj.properties.count())


@admin.register(PropertyImage)
class PropertyImageAdmin(admin.ModelAdmin):
    list_display = (
        "property",
        "property_status",
        "property_city",
        "created_at",
        "image_url",
    )
    list_filter = ("property__status", "property__category", "property__city", "created_at")
    search_fields = (
        "property__title",
        "property__city",
        "property__area",
        "image_url",
    )
    autocomplete_fields = ("property",)
    readonly_fields = ("created_at",)

    @admin.display(description="Listing status", ordering="property__status")
    def property_status(self, obj: PropertyImage) -> str:
        return obj.property.status

    @admin.display(description="City", ordering="property__city")
    def property_city(self, obj: PropertyImage) -> str:
        return obj.property.city


admin.site.register(PropertyAmenity)
admin.site.register(ListingAlertSubscription)
admin.site.register(ListingAlertSubscriptionAmenity)

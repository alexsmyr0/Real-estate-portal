from __future__ import annotations

from typing import Any

from django.db.models import Prefetch, QuerySet

from .models import Amenity, Property, PropertyImage, PropertyStatus


def visible_properties_queryset() -> QuerySet[Property]:
    return (
        Property.objects.exclude(status=PropertyStatus.REMOVED)
        .prefetch_related(
            Prefetch(
                "images",
                queryset=PropertyImage.objects.only("property_id", "image_url", "created_at"),
            ),
            Prefetch(
                "amenities",
                queryset=Amenity.objects.only("id", "name"),
            ),
        )
        .order_by("-created_at")
    )


def list_visible_properties() -> list[dict[str, Any]]:
    return [_serialize_catalog_list_item(property_obj) for property_obj in visible_properties_queryset()]


def get_visible_property_detail(property_id: int) -> dict[str, Any] | None:
    property_obj = visible_properties_queryset().filter(pk=property_id).first()
    if property_obj is None:
        return None
    return _serialize_catalog_detail(property_obj)


def _serialize_catalog_list_item(property_obj: Property) -> dict[str, Any]:
    images = list(property_obj.images.all())
    return {
        "id": property_obj.id,
        "title": property_obj.title,
        "category": property_obj.category,
        "status": property_obj.status,
        "city": property_obj.city,
        "area": property_obj.area,
        "price": str(property_obj.price),
        "bedrooms": property_obj.bedrooms,
        "bathrooms": str(property_obj.bathrooms) if property_obj.bathrooms is not None else None,
        "primary_image_url": images[0].image_url if images else None,
    }


def _serialize_catalog_detail(property_obj: Property) -> dict[str, Any]:
    payload = _serialize_catalog_list_item(property_obj)
    payload.update(
        {
            "description": property_obj.description,
            "address_line": property_obj.address_line,
            "image_urls": [image.image_url for image in property_obj.images.all()],
            "amenities": [amenity.name for amenity in property_obj.amenities.all()],
        }
    )
    return payload

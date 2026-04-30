from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.paginator import Paginator
from django.db.models import Prefetch, Q, QuerySet
from django.http import QueryDict

from .models import Amenity, Property, PropertyCategory, PropertyImage, PropertyStatus

CATALOG_PAGE_SIZE = 12
DEFAULT_CATALOG_PAGE = 1
VALID_PROPERTY_CATEGORIES = {choice for choice, _label in PropertyCategory.choices}
PUBLICLY_VISIBLE_PROPERTY_STATUSES = frozenset(
    {
        PropertyStatus.AVAILABLE,
        PropertyStatus.UNAVAILABLE,
    }
)


@dataclass(frozen=True, slots=True)
class PropertyAvailabilityContext:
    status: str
    label: str
    is_available: bool
    is_unavailable: bool
    is_removed: bool
    is_publicly_visible: bool

    def as_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "label": self.label,
            "is_available": self.is_available,
            "is_unavailable": self.is_unavailable,
            "is_removed": self.is_removed,
            "is_publicly_visible": self.is_publicly_visible,
        }


@dataclass(frozen=True, slots=True)
class CatalogSearchParams:
    location: str | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    category: str | None = None
    bedrooms_min: int | None = None
    amenity_ids: tuple[int, ...] = ()
    amenity_names: tuple[str, ...] = ()
    page: int = DEFAULT_CATALOG_PAGE


def is_publicly_visible_property_status(property_status: str) -> bool:
    return property_status in PUBLICLY_VISIBLE_PROPERTY_STATUSES


def build_property_availability_context(property_status: str) -> PropertyAvailabilityContext:
    is_available = property_status == PropertyStatus.AVAILABLE
    is_unavailable = property_status == PropertyStatus.UNAVAILABLE
    is_removed = property_status == PropertyStatus.REMOVED
    try:
        status_label = PropertyStatus(property_status).label
    except ValueError:
        status_label = property_status.title()

    return PropertyAvailabilityContext(
        status=property_status,
        label=status_label,
        is_available=is_available,
        is_unavailable=is_unavailable,
        is_removed=is_removed,
        is_publicly_visible=is_publicly_visible_property_status(property_status),
    )


def visible_properties_queryset() -> QuerySet[Property]:
    return (
        Property.objects.filter(status__in=PUBLICLY_VISIBLE_PROPERTY_STATUSES)
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


def parse_catalog_search_params(query_params: QueryDict) -> CatalogSearchParams:
    location = _normalize_text(
        _first_present_query_value(query_params, "location", "location_city", "city"),
    )
    min_price = _parse_decimal(_first_present_query_value(query_params, "min_price", "price_min"))
    max_price = _parse_decimal(_first_present_query_value(query_params, "max_price", "price_max"))

    if min_price is not None and max_price is not None and min_price > max_price:
        min_price, max_price = max_price, min_price

    category = _normalize_category(_first_present_query_value(query_params, "category"))
    bedrooms_min = _parse_positive_int(_first_present_query_value(query_params, "bedrooms_min", "bedrooms"))
    amenity_ids, amenity_names = _parse_amenity_filters(query_params)
    page = _parse_positive_int(_first_present_query_value(query_params, "page", "p")) or DEFAULT_CATALOG_PAGE

    return CatalogSearchParams(
        location=location,
        min_price=min_price,
        max_price=max_price,
        category=category,
        bedrooms_min=bedrooms_min,
        amenity_ids=amenity_ids,
        amenity_names=amenity_names,
        page=page,
    )


def search_visible_properties(search_params: CatalogSearchParams) -> dict[str, Any]:
    queryset = visible_properties_queryset()
    queryset = _apply_search_filters(queryset=queryset, search_params=search_params)

    paginator = Paginator(queryset, CATALOG_PAGE_SIZE)
    page_obj = paginator.get_page(search_params.page)

    return {
        "properties": [_serialize_catalog_list_item(property_obj) for property_obj in page_obj.object_list],
        "pagination": {
            "page": page_obj.number,
            "per_page": CATALOG_PAGE_SIZE,
            "total_items": paginator.count,
            "total_pages": paginator.num_pages if paginator.count > 0 else 0,
            "has_previous": page_obj.has_previous(),
            "has_next": page_obj.has_next(),
        },
    }


def get_visible_property_detail(property_id: int) -> dict[str, Any] | None:
    property_obj = visible_properties_queryset().filter(pk=property_id).first()
    if property_obj is None:
        return None
    return _serialize_catalog_detail(property_obj)


def _apply_search_filters(queryset: QuerySet[Property], search_params: CatalogSearchParams) -> QuerySet[Property]:
    if search_params.location:
        queryset = queryset.filter(Q(city__icontains=search_params.location) | Q(area__icontains=search_params.location))

    if search_params.min_price is not None:
        queryset = queryset.filter(price__gte=search_params.min_price)

    if search_params.max_price is not None:
        queryset = queryset.filter(price__lte=search_params.max_price)

    if search_params.category:
        queryset = queryset.filter(category=search_params.category)

    if search_params.bedrooms_min is not None:
        queryset = queryset.filter(bedrooms__gte=search_params.bedrooms_min)

    for amenity_id in search_params.amenity_ids:
        queryset = queryset.filter(amenities__id=amenity_id)

    for amenity_name in search_params.amenity_names:
        queryset = queryset.filter(amenities__name__iexact=amenity_name)

    if search_params.amenity_ids or search_params.amenity_names:
        queryset = queryset.distinct()

    return queryset


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip()
    return normalized or None


def _parse_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None

    normalized = value.strip()
    if not normalized:
        return None

    try:
        parsed = Decimal(normalized)
    except InvalidOperation:
        return None

    if parsed < 0:
        return None

    return parsed


def _parse_positive_int(value: str | None) -> int | None:
    if value is None:
        return None

    normalized = value.strip()
    if not normalized:
        return None

    try:
        parsed = int(normalized)
    except ValueError:
        return None

    if parsed <= 0:
        return None

    return parsed


def _normalize_category(value: str | None) -> str | None:
    normalized = _normalize_text(value)
    if normalized is None:
        return None

    candidate = normalized.upper()
    if candidate not in VALID_PROPERTY_CATEGORIES:
        return None

    return candidate


def _first_present_query_value(query_params: QueryDict, *keys: str) -> str | None:
    for key in keys:
        if key in query_params:
            return query_params.get(key)
    return None


def _parse_amenity_filters(query_params: QueryDict) -> tuple[tuple[int, ...], tuple[str, ...]]:
    raw_values = [*query_params.getlist("amenities"), *query_params.getlist("amenity"), *query_params.getlist("amenity_ids")]
    if not raw_values:
        return (), ()

    amenity_ids: list[int] = []
    amenity_names: list[str] = []
    seen_ids: set[int] = set()
    seen_names: set[str] = set()

    for raw_value in raw_values:
        for token in raw_value.split(","):
            normalized = token.strip()
            if not normalized:
                continue

            amenity_id = _parse_positive_int(normalized)
            if amenity_id is not None:
                if amenity_id not in seen_ids:
                    seen_ids.add(amenity_id)
                    amenity_ids.append(amenity_id)
                continue

            normalized_key = normalized.casefold()
            if normalized_key in seen_names:
                continue
            seen_names.add(normalized_key)
            amenity_names.append(normalized)

    return tuple(amenity_ids), tuple(amenity_names)


def _serialize_catalog_list_item(property_obj: Property) -> dict[str, Any]:
    images = list(property_obj.images.all())
    availability_context = build_property_availability_context(property_obj.status)
    return {
        "id": property_obj.id,
        "title": property_obj.title,
        "category": property_obj.category,
        "status": property_obj.status,
        "availability": availability_context.as_payload(),
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

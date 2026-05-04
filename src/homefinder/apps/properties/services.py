from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, Q, QuerySet
from django.http import QueryDict
from django.utils import timezone

from .models import Amenity, ListingAlertSubscription, Property, PropertyCategory, PropertyImage, PropertyStatus

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


def create_listing_alert_subscription(
    *,
    user: Any,
    source_property: Property | None = None,
    category: str | None = None,
    location_city: str | None = None,
    min_price: Decimal | str | None = None,
    max_price: Decimal | str | None = None,
    bedrooms_min: int | str | None = None,
    amenity_ids: Iterable[int] | None = None,
    is_active: bool = True,
) -> ListingAlertSubscription:
    if source_property is not None and source_property.status != PropertyStatus.UNAVAILABLE:
        raise ValidationError({"source_property": "Similar listing alerts can only be anchored to unavailable properties."})

    normalized_category = _normalize_category(category or (source_property.category if source_property else None))
    if normalized_category is None:
        raise ValidationError({"category": "A valid property category is required."})

    normalized_city = _normalize_text(location_city or (source_property.city if source_property else None))
    if normalized_city is None:
        raise ValidationError({"location_city": "A city is required."})

    normalized_min_price = _coerce_decimal(min_price, field_name="min_price")
    normalized_max_price = _coerce_decimal(max_price, field_name="max_price")
    if normalized_min_price is not None and normalized_max_price is not None and normalized_min_price > normalized_max_price:
        raise ValidationError({"max_price": "Maximum price must be greater than or equal to minimum price."})

    default_bedrooms_min = (
        source_property.bedrooms
        if source_property is not None and source_property.bedrooms and source_property.bedrooms > 0
        else None
    )
    normalized_bedrooms_min = _coerce_positive_int(
        bedrooms_min if bedrooms_min is not None else default_bedrooms_min,
        field_name="bedrooms_min",
    )
    normalized_amenity_ids = _normalize_amenity_ids(
        amenity_ids
        if amenity_ids is not None
        else source_property.amenities.values_list("id", flat=True)
        if source_property is not None
        else (),
    )

    with transaction.atomic():
        subscription = ListingAlertSubscription.objects.create(
            user=user,
            source_property=source_property,
            category=normalized_category,
            location_city=normalized_city,
            min_price=normalized_min_price,
            max_price=normalized_max_price,
            bedrooms_min=normalized_bedrooms_min,
            is_active=is_active,
        )
        if normalized_amenity_ids:
            amenities = list(Amenity.objects.filter(pk__in=normalized_amenity_ids))
            found_amenity_ids = {amenity.pk for amenity in amenities}
            missing_amenity_ids = sorted(set(normalized_amenity_ids) - found_amenity_ids)
            if missing_amenity_ids:
                raise ValidationError({"amenity_ids": f"Unknown amenity ids: {missing_amenity_ids}."})
            subscription.amenities.set(amenities)

    return subscription


def set_listing_alert_subscription_active(
    subscription: ListingAlertSubscription,
    *,
    is_active: bool,
) -> ListingAlertSubscription:
    subscription.is_active = is_active
    subscription.save(update_fields=["is_active"])
    return subscription


def listing_matches_alert_subscription(subscription: ListingAlertSubscription, property_obj: Property) -> bool:
    if not subscription.is_active:
        return False

    if property_obj.status != PropertyStatus.AVAILABLE:
        return False

    if not subscription.category or property_obj.category != subscription.category:
        return False

    subscription_city = _normalize_text(subscription.location_city)
    property_city = _normalize_text(property_obj.city)
    if subscription_city is None or property_city is None or subscription_city.casefold() != property_city.casefold():
        return False

    if subscription.min_price is not None and property_obj.price < subscription.min_price:
        return False

    if subscription.max_price is not None and property_obj.price > subscription.max_price:
        return False

    if subscription.bedrooms_min is not None:
        if property_obj.bedrooms is None or property_obj.bedrooms < subscription.bedrooms_min:
            return False

    subscription_amenity_ids = {amenity.id for amenity in subscription.amenities.all()}
    if subscription_amenity_ids:
        property_amenity_ids = {amenity.id for amenity in property_obj.amenities.all()}
        return bool(subscription_amenity_ids & property_amenity_ids)

    return True


def matching_listing_alert_subscriptions(property_obj: Property) -> list[ListingAlertSubscription]:
    if property_obj.status != PropertyStatus.AVAILABLE:
        return []

    property_amenity_ids = list(property_obj.amenities.values_list("id", flat=True))
    candidates = (
        ListingAlertSubscription.objects.filter(
            is_active=True,
            category=property_obj.category,
            location_city__iexact=property_obj.city,
        )
        .filter(Q(min_price__isnull=True) | Q(min_price__lte=property_obj.price))
        .filter(Q(max_price__isnull=True) | Q(max_price__gte=property_obj.price))
        .select_related("user", "source_property")
        .prefetch_related("amenities")
    )
    if property_obj.bedrooms is None:
        candidates = candidates.filter(bedrooms_min__isnull=True)
    else:
        candidates = candidates.filter(Q(bedrooms_min__isnull=True) | Q(bedrooms_min__lte=property_obj.bedrooms))

    candidates = candidates.annotate(
        amenity_count=Count("amenities", distinct=True),
        overlapping_amenity_count=Count(
            "amenities",
            filter=Q(amenities__id__in=property_amenity_ids),
            distinct=True,
        ),
    ).filter(Q(amenity_count=0) | Q(overlapping_amenity_count__gt=0))

    property_obj = Property.objects.prefetch_related("amenities").get(pk=property_obj.pk)
    return [subscription for subscription in candidates if listing_matches_alert_subscription(subscription, property_obj)]


def dispatch_similar_listing_alerts(
    property_obj: Property,
    *,
    notification_service: Any | None = None,
) -> list[Any]:
    from homefinder.apps.interactions.models import (
        SimilarListingAlertDispatch,
        SimilarListingAlertDispatchStatus,
    )
    from homefinder.apps.interactions.services import notification_service as default_notification_service

    service = notification_service or default_notification_service
    dispatches: list[SimilarListingAlertDispatch] = []

    for subscription in matching_listing_alert_subscriptions(property_obj):
        with transaction.atomic():
            dispatch = _get_or_create_retryable_dispatch(subscription=subscription, property_obj=property_obj)
            if dispatch is None or dispatch.status in {
                SimilarListingAlertDispatchStatus.PENDING,
                SimilarListingAlertDispatchStatus.SENT,
            }:
                continue

            notification = service.send_similar_listing_alert(
                subscription=subscription,
                property_obj=property_obj,
            )
            dispatch.notification = notification
            dispatch.status = SimilarListingAlertDispatchStatus.PENDING
            dispatch.attempt_count += 1
            dispatch.last_attempted_at = timezone.now()
            dispatch.save(update_fields=["notification", "status", "attempt_count", "last_attempted_at", "updated_at"])
            transaction.on_commit(lambda dispatch_id=dispatch.pk: _finalize_similar_listing_alert_dispatch(dispatch_id))
            dispatches.append(dispatch)

    return dispatches


def _get_or_create_retryable_dispatch(
    *,
    subscription: ListingAlertSubscription,
    property_obj: Property,
) -> Any | None:
    from homefinder.apps.interactions.models import SimilarListingAlertDispatch, SimilarListingAlertDispatchStatus

    try:
        dispatch = SimilarListingAlertDispatch.objects.select_for_update().get(
            subscription=subscription,
            property=property_obj,
        )
    except SimilarListingAlertDispatch.DoesNotExist:
        try:
            dispatch = SimilarListingAlertDispatch.objects.create(
                subscription=subscription,
                property=property_obj,
                status=SimilarListingAlertDispatchStatus.FAILED,
            )
        except IntegrityError:
            return None

    if dispatch.status in {SimilarListingAlertDispatchStatus.PENDING, SimilarListingAlertDispatchStatus.SENT}:
        return dispatch

    return dispatch


def _finalize_similar_listing_alert_dispatch(dispatch_id: int) -> None:
    from homefinder.apps.interactions.models import (
        EmailNotificationStatus,
        SimilarListingAlertDispatch,
        SimilarListingAlertDispatchStatus,
    )

    dispatch = (
        SimilarListingAlertDispatch.objects.select_related("notification")
        .filter(pk=dispatch_id, status=SimilarListingAlertDispatchStatus.PENDING)
        .first()
    )
    if dispatch is None or dispatch.notification_id is None:
        return

    dispatch.notification.refresh_from_db(fields=["status"])
    if dispatch.notification.status == EmailNotificationStatus.SENT:
        dispatch.status = SimilarListingAlertDispatchStatus.SENT
    elif dispatch.notification.status == EmailNotificationStatus.FAILED:
        dispatch.status = SimilarListingAlertDispatchStatus.FAILED
    else:
        return

    dispatch.save(update_fields=["status", "updated_at"])


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


def get_featured_visible_properties(limit: int = 3) -> list[dict[str, Any]]:
    return [_serialize_catalog_list_item(p) for p in visible_properties_queryset()[:limit]]


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


def _coerce_decimal(value: Decimal | str | None, *, field_name: str) -> Decimal | None:
    if value is None:
        return None

    parsed = _parse_decimal(str(value))
    if parsed is None:
        raise ValidationError({field_name: "Enter a valid non-negative price."})
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


def _coerce_positive_int(value: int | str | None, *, field_name: str) -> int | None:
    if value is None:
        return None

    parsed = _parse_positive_int(str(value))
    if parsed is None:
        raise ValidationError({field_name: "Enter a valid positive integer."})
    return parsed


def _normalize_amenity_ids(amenity_ids: Iterable[int]) -> tuple[int, ...]:
    normalized_ids: list[int] = []
    seen_ids: set[int] = set()
    for amenity_id in amenity_ids:
        parsed = _coerce_positive_int(amenity_id, field_name="amenity_ids")
        if parsed is None or parsed in seen_ids:
            continue
        seen_ids.add(parsed)
        normalized_ids.append(parsed)
    return tuple(normalized_ids)


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

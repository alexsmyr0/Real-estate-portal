from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models.signals import m2m_changed, post_save, pre_delete, pre_save
from django.dispatch import receiver

from .models import ListingAlertSubscription, Property, PropertyStatus
from .services import dispatch_similar_listing_alerts, matching_listing_alert_subscription_ids_for_state

MATERIAL_MATCHING_FIELDS = ("status", "category", "city", "price", "bedrooms")
AMENITY_PRE_CHANGE_ACTIONS = {"pre_add", "pre_remove", "pre_clear"}
AMENITY_POST_CHANGE_ACTIONS = {"post_add", "post_remove", "post_clear"}


@receiver(pre_save, sender=Property)
def capture_previous_listing_match_state(sender: type[Property], instance: Property, **kwargs: object) -> None:
    if instance.pk is None:
        instance._previous_alert_match_state = None
        return

    instance._previous_alert_match_state = (
        Property.objects.filter(pk=instance.pk).values(*MATERIAL_MATCHING_FIELDS).first()
    )


@receiver(post_save, sender=Property)
def dispatch_alerts_for_available_listing(
    sender: type[Property],
    instance: Property,
    created: bool,
    **kwargs: object,
) -> None:
    current_state = _current_alert_match_state(instance.pk)
    if current_state is not None and current_state["status"] == PropertyStatus.AVAILABLE:
        _deactivate_source_property_subscriptions(instance.pk)

    subscription_ids = _subscription_ids_to_dispatch_after_save(
        instance=instance,
        created=created,
        current_state=current_state,
    )
    if subscription_ids:
        _schedule_similar_listing_alert_dispatch(instance, subscription_ids=subscription_ids)


@receiver(pre_delete, sender=Property)
def deactivate_source_property_alerts_before_delete(
    sender: type[Property],
    instance: Property,
    **kwargs: object,
) -> None:
    _deactivate_source_property_subscriptions(instance.pk)


@receiver(m2m_changed, sender=Property.amenities.through)
def dispatch_alerts_after_listing_amenities_change(
    sender: type[object],
    instance: Property,
    action: str,
    **kwargs: object,
) -> None:
    if action in AMENITY_PRE_CHANGE_ACTIONS:
        instance._previous_alert_matching_subscription_ids = _matching_subscription_ids_for_instance(instance)
        return

    if action not in AMENITY_POST_CHANGE_ACTIONS:
        return

    previous_matching_ids = getattr(instance, "_previous_alert_matching_subscription_ids", None)
    if previous_matching_ids is None:
        return

    current_matching_ids = _matching_subscription_ids_for_instance(instance)
    newly_matching_ids = current_matching_ids - previous_matching_ids
    if newly_matching_ids:
        _schedule_similar_listing_alert_dispatch(instance, subscription_ids=newly_matching_ids)


def _schedule_similar_listing_alert_dispatch(
    property_obj: Property,
    *,
    subscription_ids: set[int],
) -> None:
    if property_obj.pk is None or not subscription_ids:
        return

    scoped_subscription_ids = tuple(subscription_ids)
    transaction.on_commit(
        lambda property_id=property_obj.pk, subscription_ids=scoped_subscription_ids: _dispatch_for_property_id(
            property_id,
            subscription_ids=subscription_ids,
        )
    )


def _subscription_ids_to_dispatch_after_save(
    *,
    instance: Property,
    created: bool,
    current_state: dict[str, object] | None,
) -> set[int]:
    if current_state is None or current_state["status"] != PropertyStatus.AVAILABLE:
        return set()

    current_matching_ids = _matching_subscription_ids_for_state(current_state, instance.pk)
    if not current_matching_ids:
        return set()

    if created:
        return current_matching_ids

    previous_state = getattr(instance, "_previous_alert_match_state", None)
    if previous_state is None:
        return set()

    previous_status = previous_state["status"]
    if previous_status != PropertyStatus.AVAILABLE:
        return current_matching_ids

    if not _material_state_changed(previous_state=previous_state, current_state=current_state):
        return set()

    previous_matching_ids = _matching_subscription_ids_for_state(previous_state, instance.pk)
    return current_matching_ids - previous_matching_ids


def _material_state_changed(
    *,
    previous_state: dict[str, object],
    current_state: dict[str, object],
) -> bool:
    return any(
        _normalized_state_value(previous_state[field]) != _normalized_state_value(current_state[field])
        for field in MATERIAL_MATCHING_FIELDS
    )


def _current_alert_match_state(property_id: int | None) -> dict[str, object] | None:
    if property_id is None:
        return None
    return Property.objects.filter(pk=property_id).values(*MATERIAL_MATCHING_FIELDS).first()


def _matching_subscription_ids_for_instance(property_obj: Property) -> set[int]:
    current_state = _current_alert_match_state(property_obj.pk)
    if current_state is None:
        return set()
    return _matching_subscription_ids_for_state(current_state, property_obj.pk)


def _matching_subscription_ids_for_state(state: dict[str, object], property_id: int | None) -> set[int]:
    if property_id is None:
        return set()

    return matching_listing_alert_subscription_ids_for_state(
        property_id=property_id,
        status=str(state["status"]),
        category=str(state["category"]),
        city=str(state["city"]),
        price=state["price"],
        bedrooms=state["bedrooms"],
        amenity_ids=Property.objects.filter(pk=property_id).values_list("amenities__id", flat=True),
    )


def _deactivate_source_property_subscriptions(property_id: int | None) -> None:
    if property_id is None:
        return

    ListingAlertSubscription.objects.filter(source_property_id=property_id, is_active=True).update(is_active=False)


def _normalized_state_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"))
    return value


def _dispatch_for_property_id(property_id: int, *, subscription_ids: tuple[int, ...]) -> None:
    property_obj = Property.objects.filter(pk=property_id).first()
    if property_obj is None or property_obj.status != PropertyStatus.AVAILABLE:
        return

    dispatch_similar_listing_alerts(property_obj, subscription_ids=subscription_ids)

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models.signals import m2m_changed, post_save, pre_save
from django.dispatch import receiver

from .models import Property, PropertyStatus
from .services import dispatch_similar_listing_alerts

MATERIAL_MATCHING_FIELDS = ("status", "category", "city", "price", "bedrooms")


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
    if _should_schedule_after_save(instance=instance, created=created):
        _schedule_similar_listing_alert_dispatch(instance)


@receiver(m2m_changed, sender=Property.amenities.through)
def dispatch_alerts_after_listing_amenities_change(
    sender: type[object],
    instance: Property,
    action: str,
    **kwargs: object,
) -> None:
    if action in {"post_add", "post_remove", "post_clear"}:
        _schedule_similar_listing_alert_dispatch(instance)


def _schedule_similar_listing_alert_dispatch(property_obj: Property) -> None:
    if property_obj.pk is None or property_obj.status != PropertyStatus.AVAILABLE:
        return

    transaction.on_commit(lambda property_id=property_obj.pk: _dispatch_for_property_id(property_id))


def _should_schedule_after_save(*, instance: Property, created: bool) -> bool:
    if instance.status != PropertyStatus.AVAILABLE:
        return False

    if created:
        return True

    previous_state = getattr(instance, "_previous_alert_match_state", None)
    if previous_state is None:
        return False

    previous_status = previous_state["status"]
    if previous_status != PropertyStatus.AVAILABLE:
        return True

    return any(_normalized_state_value(previous_state[field]) != _normalized_state_value(getattr(instance, field)) for field in MATERIAL_MATCHING_FIELDS)


def _normalized_state_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"))
    return value


def _dispatch_for_property_id(property_id: int) -> None:
    property_obj = Property.objects.filter(pk=property_id).first()
    if property_obj is None or property_obj.status != PropertyStatus.AVAILABLE:
        return

    dispatch_similar_listing_alerts(property_obj)

from __future__ import annotations

from django.db import transaction
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from .models import Property, PropertyStatus
from .services import dispatch_similar_listing_alerts


@receiver(post_save, sender=Property)
def dispatch_alerts_for_available_listing(sender: type[Property], instance: Property, **kwargs: object) -> None:
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


def _dispatch_for_property_id(property_id: int) -> None:
    property_obj = Property.objects.filter(pk=property_id).first()
    if property_obj is None or property_obj.status != PropertyStatus.AVAILABLE:
        return

    dispatch_similar_listing_alerts(property_obj)

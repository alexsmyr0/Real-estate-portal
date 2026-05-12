from __future__ import annotations

from django import template
from django.forms.boundfield import BoundField

register = template.Library()


@register.filter
def accessible_widget(field: BoundField) -> str:
    described_by = []
    if field.help_text:
        described_by.append(f"{field.id_for_label}_helptext")
    if field.errors:
        described_by.append(f"{field.id_for_label}_error")

    attrs = {}
    if described_by:
        attrs["aria-describedby"] = " ".join(described_by)
    if field.errors:
        attrs["aria-invalid"] = "true"

    return field.as_widget(attrs=attrs)

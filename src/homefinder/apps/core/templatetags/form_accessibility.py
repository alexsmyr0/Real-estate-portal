from __future__ import annotations

from django import template
from django.forms.boundfield import BoundField

register = template.Library()


@register.filter
def accessible_widget(field: BoundField) -> str:
    described_by = _unique_tokens(field.field.widget.attrs.get("aria-describedby", ""))
    if field.help_text:
        _append_unique(described_by, f"{field.id_for_label}_helptext")
    if field.errors:
        _append_unique(described_by, f"{field.id_for_label}_errors")

    attrs = {}
    if described_by:
        attrs["aria-describedby"] = " ".join(described_by)
    if field.errors:
        attrs["aria-invalid"] = "true"

    return field.as_widget(attrs=attrs)


def _unique_tokens(value: object) -> list[str]:
    tokens: list[str] = []
    for token in str(value or "").split():
        _append_unique(tokens, token)
    return tokens


def _append_unique(tokens: list[str], token: str) -> None:
    if token and token not in tokens:
        tokens.append(token)

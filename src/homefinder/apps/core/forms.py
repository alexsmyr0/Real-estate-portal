from __future__ import annotations

from django import forms

from homefinder.apps.properties.models import PropertyCategory


class CatalogShellFilterForm(forms.Form):
    location = forms.CharField(
        label="Location",
        max_length=120,
        required=False,
    )
    category = forms.ChoiceField(
        label="Category",
        required=False,
        choices=[("", "Any category"), *PropertyCategory.choices],
    )
    min_price = forms.DecimalField(
        label="Minimum price",
        required=False,
        min_value=0,
        max_digits=12,
        decimal_places=2,
    )
    max_price = forms.DecimalField(
        label="Maximum price",
        required=False,
        min_value=0,
        max_digits=12,
        decimal_places=2,
    )
    bedrooms = forms.IntegerField(
        label="Minimum bedrooms",
        required=False,
        min_value=1,
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["location"].widget.attrs.update({"placeholder": "City or area"})
        self.fields["min_price"].widget.attrs.update({"placeholder": "e.g. 250000"})
        self.fields["max_price"].widget.attrs.update({"placeholder": "e.g. 600000"})

        for field in self.fields.values():
            existing_css_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = " ".join(
                class_name for class_name in ("form-control", existing_css_class) if class_name
            )

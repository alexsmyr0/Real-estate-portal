from __future__ import annotations

from datetime import date, datetime
from typing import Any

from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils import timezone

from .models import Property, PropertyAmenity, PropertyImage


class StyledPropertyFormMixin:
    def _apply_control_classes(self) -> None:
        for field in self.fields.values():
            existing_css_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = " ".join(
                class_name for class_name in ("form-control", existing_css_class) if class_name
            )


class PropertyForm(StyledPropertyFormMixin, forms.ModelForm):
    class Meta:
        model = Property
        fields = (
            "title",
            "description",
            "category",
            "status",
            "city",
            "area",
            "address_line",
            "price",
            "bedrooms",
            "bathrooms",
            "listed_by",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "price": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "bedrooms": forms.NumberInput(attrs={"min": "0", "step": "1"}),
            "bathrooms": forms.NumberInput(attrs={"min": "0", "step": "0.5"}),
        }
        help_texts = {
            "status": "Available and unavailable listings stay visible in catalog. Removed listings are hidden.",
            "listed_by": "Optional. Defaults to the current admin if left empty.",
        }

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._apply_control_classes()
        self.fields["title"].widget.attrs["placeholder"] = "Example: Acropolis View Apartment"
        self.fields["city"].widget.attrs["placeholder"] = "Athens"
        self.fields["area"].widget.attrs["placeholder"] = "Koukaki"

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        for field_name in ("title", "description", "city", "area", "address_line"):
            field_value = cleaned_data.get(field_name)
            if isinstance(field_value, str):
                cleaned_data[field_name] = field_value.strip()
        return cleaned_data


class StyledInlineFormSet(BaseInlineFormSet):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        formset_forms = [*self.forms, self.empty_form]
        for inline_form in formset_forms:
            for field_name, field in inline_form.fields.items():
                if field.widget.is_hidden or field_name == "DELETE":
                    continue
                existing_css_class = field.widget.attrs.get("class", "")
                field.widget.attrs["class"] = " ".join(
                    class_name for class_name in ("form-control", existing_css_class) if class_name
                )


class PropertyImageInlineFormSetBase(StyledInlineFormSet):
    default_error_messages = {
        **StyledInlineFormSet.default_error_messages,
        "too_few_forms": "Add at least one image URL for the listing.",
    }


class PropertyAmenityInlineFormSetBase(StyledInlineFormSet):
    default_error_messages = {
        **StyledInlineFormSet.default_error_messages,
        "too_few_forms": "Add at least one amenity for the listing.",
    }

    def clean(self) -> None:
        super().clean()
        if any(self.errors):
            return

        seen_amenity_ids: set[int] = set()
        for inline_form in self.forms:
            cleaned_data = getattr(inline_form, "cleaned_data", None)
            if not cleaned_data or cleaned_data.get("DELETE", False):
                continue

            amenity = cleaned_data.get("amenity")
            if amenity is None:
                continue
            if amenity.pk in seen_amenity_ids:
                raise forms.ValidationError("Select each amenity only once.")
            seen_amenity_ids.add(amenity.pk)


PropertyImageInlineFormSet = inlineformset_factory(
    Property,
    PropertyImage,
    fields=("image_url",),
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
    formset=PropertyImageInlineFormSetBase,
)

PropertyAmenityInlineFormSet = inlineformset_factory(
    Property,
    PropertyAmenity,
    fields=("amenity",),
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
    formset=PropertyAmenityInlineFormSetBase,
)


class ViewingRequestForm(StyledPropertyFormMixin, forms.Form):
    requested_datetime = forms.DateTimeField(
        label="Preferred date and time",
        required=True,
        help_text="Choose a future time.",
        input_formats=("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"),
        error_messages={
            "required": "Choose a future date and time for the viewing.",
            "invalid": "Enter a valid date and time.",
        },
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",
                "autocomplete": "off",
            },
            format="%Y-%m-%dT%H:%M",
        ),
    )
    note = forms.CharField(
        label="Note",
        required=False,
        max_length=500,
        help_text="Optional: share timing preferences or questions for the team.",
        widget=forms.Textarea(attrs={"rows": 4, "maxlength": "500"}),
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._apply_control_classes()
        self.fields["note"].widget.attrs.update({"placeholder": "Afternoons after 15:00 work best."})

    def clean_requested_datetime(self) -> datetime:
        requested_datetime = self.cleaned_data["requested_datetime"]
        if timezone.is_naive(requested_datetime):
            requested_datetime = timezone.make_aware(requested_datetime, timezone.get_current_timezone())

        if requested_datetime <= timezone.now():
            raise forms.ValidationError("Choose a date and time in the future.")

        return requested_datetime


class BookingRequestForm(StyledPropertyFormMixin, forms.Form):
    start_date = forms.DateField(
        label="Start date",
        required=True,
        help_text="Choose today or a future date.",
        input_formats=("%Y-%m-%d",),
        error_messages={
            "required": "Choose a booking start date.",
            "invalid": "Enter a valid booking start date.",
        },
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "autocomplete": "off",
            },
            format="%Y-%m-%d",
        ),
    )
    end_date = forms.DateField(
        label="End date",
        required=True,
        help_text="Choose a date after the start date.",
        input_formats=("%Y-%m-%d",),
        error_messages={
            "required": "Choose a booking end date.",
            "invalid": "Enter a valid booking end date.",
        },
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "autocomplete": "off",
            },
            format="%Y-%m-%d",
        ),
    )
    note = forms.CharField(
        label="Note",
        required=False,
        max_length=500,
        help_text="Optional: share check-in preferences or questions for the host.",
        widget=forms.Textarea(attrs={"rows": 4, "maxlength": "500"}),
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._apply_control_classes()
        today_iso = timezone.localdate().isoformat()
        self.fields["start_date"].widget.attrs["min"] = today_iso
        self.fields["end_date"].widget.attrs["min"] = today_iso
        self.fields["note"].widget.attrs.update(
            {"placeholder": "Arriving late evening; need parking for one car."}
        )

    def clean_start_date(self) -> date:
        start_date = self.cleaned_data["start_date"]
        if start_date < timezone.localdate():
            raise forms.ValidationError("Booking start date must be today or in the future.")
        return start_date

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date is not None and end_date is not None and end_date <= start_date:
            self.add_error("end_date", "Booking end date must be after the start date.")

        return cleaned_data

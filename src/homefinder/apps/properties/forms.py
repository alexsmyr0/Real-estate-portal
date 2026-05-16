from __future__ import annotations

from datetime import date, datetime
from typing import Any

from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils import timezone

from .models import Amenity, Property, PropertyImage


class StyledPropertyFormMixin:
    def _apply_control_classes(self) -> None:
        for field in self.fields.values():
            existing_css_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = " ".join(
                class_name for class_name in ("form-control", existing_css_class) if class_name
            )


class PropertyForm(StyledPropertyFormMixin, forms.ModelForm):
    amenities = forms.ModelMultipleChoiceField(
        queryset=Amenity.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        error_messages={"required": "Select at least one amenity for the listing."},
    )

    class Meta:
        model = Property
        fields = (
            "title",
            "category",
            "price",
            "city",
            "area",
            "address_line",
            "bedrooms",
            "bathrooms",
            "description",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "price": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "bedrooms": forms.NumberInput(attrs={"min": "0", "step": "1"}),
            "bathrooms": forms.NumberInput(attrs={"min": "0", "step": "0.5"}),
        }

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._apply_control_classes()
        self.fields["title"].widget.attrs["placeholder"] = "Example: Acropolis View Apartment"
        self.fields["city"].widget.attrs["placeholder"] = "Athens"
        self.fields["area"].widget.attrs["placeholder"] = "Koukaki"
        self.fields["amenities"].widget.attrs.pop("class", None)
        if self.instance.pk is not None:
            self.fields["amenities"].initial = self.instance.amenities.all()

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        for field_name in ("title", "description", "city", "area", "address_line"):
            field_value = cleaned_data.get(field_name)
            if isinstance(field_value, str):
                cleaned_data[field_name] = field_value.strip()
        return cleaned_data

    def save(self, commit: bool = True) -> Property:
        listing = super().save(commit=commit)
        if commit:
            self._sync_amenities(listing)
        else:
            self._pending_amenities = self.cleaned_data.get("amenities", [])

            original_save_m2m = self.save_m2m

            def save_m2m_with_amenities() -> None:
                original_save_m2m()
                self._sync_amenities(listing)

            self.save_m2m = save_m2m_with_amenities
        return listing

    def _sync_amenities(self, listing: Property) -> None:
        selected_amenities = self.cleaned_data.get("amenities") or []
        listing.amenities.set(selected_amenities)


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


PropertyImageInlineFormSet = inlineformset_factory(
    Property,
    PropertyImage,
    fields=("image_url",),
    extra=0,
    can_delete=True,
    min_num=1,
    validate_min=True,
    formset=PropertyImageInlineFormSetBase,
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

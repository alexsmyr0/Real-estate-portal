from __future__ import annotations

from datetime import date, datetime

from django import forms
from django.utils import timezone


class StyledPropertyFormMixin:
    def _apply_control_classes(self) -> None:
        for field in self.fields.values():
            existing_css_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = " ".join(
                class_name for class_name in ("form-control", existing_css_class) if class_name
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

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._apply_control_classes()

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

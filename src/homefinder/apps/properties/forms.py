from __future__ import annotations

from datetime import datetime

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

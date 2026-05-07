from __future__ import annotations

from typing import Any

from django import forms

from .models import PROPERTY_INQUIRY_MESSAGE_MAX_LENGTH


class StyledInteractionFormMixin:
    def _apply_control_classes(self) -> None:
        for field in self.fields.values():
            existing_css_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = " ".join(
                class_name for class_name in ("form-control", existing_css_class) if class_name
            )


class PropertyInquiryForm(StyledInteractionFormMixin, forms.Form):
    message = forms.CharField(
        label="Message",
        max_length=PROPERTY_INQUIRY_MESSAGE_MAX_LENGTH,
        widget=forms.Textarea,
        help_text="Share the question or context you want the HomeFinder team to review.",
        error_messages={
            "required": "Tell us what you would like to know.",
            "max_length": f"Keep your inquiry to {PROPERTY_INQUIRY_MESSAGE_MAX_LENGTH} characters or fewer.",
        },
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._apply_control_classes()
        self.fields["message"].widget.attrs.update(
            {
                "placeholder": "I am interested in this property and would like to know more about...",
                "rows": 6,
            }
        )

    def clean_message(self) -> str:
        return self.cleaned_data["message"].strip()

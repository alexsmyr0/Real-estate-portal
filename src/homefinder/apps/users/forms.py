from __future__ import annotations

from typing import Any

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import User


class StyledAuthFormMixin:
    def _apply_control_classes(self) -> None:
        for field in self.fields.values():
            existing_css_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = " ".join(
                class_name for class_name in ("form-control", existing_css_class) if class_name
            )


class RegistrationForm(StyledAuthFormMixin, forms.Form):
    email = forms.EmailField(max_length=254, label="Email address")
    password = forms.CharField(widget=forms.PasswordInput, strip=False, label="Password")
    full_name = forms.CharField(max_length=150, required=False, label="Full name")
    phone = forms.CharField(max_length=30, required=False, label="Phone")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._apply_control_classes()
        self.fields["email"].widget.attrs.update({"placeholder": "you@example.com", "autocomplete": "email"})
        self.fields["password"].widget.attrs.update(
            {"placeholder": "Create a strong password", "autocomplete": "new-password"}
        )
        self.fields["full_name"].widget.attrs.update({"placeholder": "Alex Jordan", "autocomplete": "name"})
        self.fields["phone"].widget.attrs.update({"placeholder": "+30 69X XXX XXXX", "autocomplete": "tel"})

    def clean_email(self) -> str:
        raw_email = self.cleaned_data["email"]
        normalized_email = User.objects.normalize_email(raw_email.strip())
        if User.objects.filter(email__iexact=normalized_email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return normalized_email

    def clean(self) -> dict[str, str]:
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        email = cleaned_data.get("email", "")

        if password:
            try:
                validate_password(password, user=User(email=email))
            except DjangoValidationError as error:
                self.add_error("password", error)

        return cleaned_data


class LoginForm(StyledAuthFormMixin, forms.Form):
    email = forms.EmailField(max_length=254, label="Email address")
    password = forms.CharField(widget=forms.PasswordInput, strip=False, label="Password")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._apply_control_classes()
        self.fields["email"].widget.attrs.update({"placeholder": "you@example.com", "autocomplete": "email"})
        self.fields["password"].widget.attrs.update(
            {"placeholder": "Enter your password", "autocomplete": "current-password"}
        )

    def clean_email(self) -> str:
        raw_email = self.cleaned_data["email"]
        return User.objects.normalize_email(raw_email.strip())


class TwoFactorVerificationForm(StyledAuthFormMixin, forms.Form):
    token = forms.CharField(
        min_length=6,
        max_length=6,
        strip=True,
        label="2FA code",
        help_text="Enter the 6-digit code sent to your email.",
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._apply_control_classes()
        self.fields["token"].widget.attrs.update(
            {
                "placeholder": "123456",
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
                "pattern": r"\d{6}",
            }
        )

    def clean_token(self) -> str:
        token = self.cleaned_data["token"].strip()
        if not token.isdigit():
            raise forms.ValidationError("Enter the 6-digit code.")
        return token

from __future__ import annotations

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import User


class RegistrationForm(forms.Form):
    email = forms.EmailField(label="Email address", max_length=254)
    password = forms.CharField(label="Password", widget=forms.PasswordInput, strip=False)
    full_name = forms.CharField(label="Full name", max_length=150, required=False)
    phone = forms.CharField(label="Phone", max_length=30, required=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update(
            {"autocomplete": "email", "placeholder": "alex@example.com"}
        )
        self.fields["password"].widget.attrs.update(
            {"autocomplete": "new-password", "placeholder": "Strong password"}
        )
        self.fields["full_name"].widget.attrs.update(
            {"autocomplete": "name", "placeholder": "Alex Jordan"}
        )
        self.fields["phone"].widget.attrs.update(
            {"autocomplete": "tel", "placeholder": "+30 210 000 0000"}
        )
        _apply_form_control_class(self)

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


class LoginForm(forms.Form):
    email = forms.EmailField(label="Email address", max_length=254)
    password = forms.CharField(label="Password", widget=forms.PasswordInput, strip=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update(
            {"autocomplete": "email", "placeholder": "alex@example.com"}
        )
        self.fields["password"].widget.attrs.update(
            {"autocomplete": "current-password", "placeholder": "Your password"}
        )
        _apply_form_control_class(self)

    def clean_email(self) -> str:
        raw_email = self.cleaned_data["email"]
        return User.objects.normalize_email(raw_email.strip())


class TwoFactorVerificationForm(forms.Form):
    token = forms.CharField(label="Verification code", min_length=6, max_length=6, strip=True)

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["token"].widget.attrs.update(
            {
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
                "pattern": "[0-9]*",
                "placeholder": "123456",
            }
        )
        _apply_form_control_class(self)

    def clean_token(self) -> str:
        token = self.cleaned_data["token"].strip()
        if not token.isdigit():
            raise forms.ValidationError("Enter the 6-digit code.")
        return token


def _apply_form_control_class(form: forms.Form) -> None:
    for field in form.fields.values():
        existing_css_class = field.widget.attrs.get("class", "")
        field.widget.attrs["class"] = " ".join(
            class_name for class_name in ("form-control", existing_css_class) if class_name
        )

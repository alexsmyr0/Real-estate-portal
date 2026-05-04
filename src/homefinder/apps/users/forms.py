from __future__ import annotations

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import User


class RegistrationForm(forms.Form):
    email = forms.EmailField(max_length=254)
    password = forms.CharField(widget=forms.PasswordInput, strip=False)
    full_name = forms.CharField(max_length=150, required=False)
    phone = forms.CharField(max_length=30, required=False)

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
    email = forms.EmailField(max_length=254)
    password = forms.CharField(widget=forms.PasswordInput, strip=False)

    def clean_email(self) -> str:
        raw_email = self.cleaned_data["email"]
        return User.objects.normalize_email(raw_email.strip())


class TwoFactorVerificationForm(forms.Form):
    token = forms.CharField(min_length=6, max_length=6, strip=True)

    def clean_token(self) -> str:
        token = self.cleaned_data["token"].strip()
        if not token.isdigit():
            raise forms.ValidationError("Enter the 6-digit code.")
        return token

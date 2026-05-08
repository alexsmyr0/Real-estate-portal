from __future__ import annotations

from django import forms


class ShellContactPreferenceForm(forms.Form):
    full_name = forms.CharField(
        label="Full name",
        max_length=120,
        required=True,
    )
    email = forms.EmailField(
        label="Email",
        required=True,
    )
    intent = forms.ChoiceField(
        label="Interested in",
        required=True,
        choices=(
            ("BUY", "Buying"),
            ("RENT", "Renting"),
            ("COMMERCIAL", "Commercial"),
        ),
    )
    notes = forms.CharField(
        label="Notes",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["full_name"].widget.attrs.update({"placeholder": "Alex Jordan"})
        self.fields["email"].widget.attrs.update({"placeholder": "alex@example.com"})
        self.fields["notes"].widget.attrs.update({"placeholder": "Preferred area, budget, and timeline..."})

        for field in self.fields.values():
            existing_css_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = " ".join(
                class_name for class_name in ("form-control", existing_css_class) if class_name
            )

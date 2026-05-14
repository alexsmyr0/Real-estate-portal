from __future__ import annotations

import os
from datetime import timedelta
from decimal import Decimal
from html.parser import HTMLParser

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django

django.setup()

from django import forms
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from homefinder.apps.core.templatetags.form_accessibility import accessible_widget
from homefinder.apps.interactions.models import BookingRequest, BookingRequestStatus
from homefinder.apps.properties.models import Property, PropertyCategory, PropertyStatus
from homefinder.apps.users.models import User


class HtmlAttributeCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.labels_for: list[str] = []
        self.described_by_tokens: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            self.ids.append(element_id)
        label_for = attributes.get("for")
        if tag == "label" and label_for:
            self.labels_for.append(label_for)
        described_by = attributes.get("aria-describedby")
        if described_by:
            self.described_by_tokens.extend(described_by.split())


@override_settings(ALLOWED_HOSTS=["testserver"])
class A15CrossFlowHardeningTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.user = User.objects.create_user(
            email="a15-user-with-a-long-address@example.com",
            password="StrongPassword123!",
            full_name="A15 Hardening User",
        )
        self.rental_property = self._create_property(
            title="A15 Rental Listing",
            category=PropertyCategory.RENTAL,
            status=PropertyStatus.AVAILABLE,
        )
        self.unavailable_rental = self._create_property(
            title="A15 Unavailable Rental",
            category=PropertyCategory.RENTAL,
            status=PropertyStatus.UNAVAILABLE,
        )

    def test_shared_shell_navigation_and_flash_messages_expose_accessible_statuses(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(
            f"/catalog/{self.rental_property.id}/favorite/",
            {"next": f"/catalog/{self.rental_property.id}/", "surface": "detail"},
            follow=True,
        )

        self.assertContains(response, 'class="site-shell"')
        self.assertContains(response, 'class="site-header"')
        self.assertContains(response, 'aria-label="Primary"')
        self.assertContains(response, "Dashboard")
        self.assertContains(response, 'action="/logout/"')
        self.assertContains(response, 'role="status"')
        self.assertContains(response, "Listing saved to your favorites.")

    def test_auth_errors_are_associated_with_form_fields_and_summary_alerts(self) -> None:
        response = self.client.post(
            "/register/",
            {
                "email": "new-a15-user@example.com",
                "password": "short",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'role="alert"')
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(response, 'aria-describedby="id_password_errors"')
        self.assertContains(response, 'id="id_password_errors" role="alert"')
        self.assertContains(response, "This password is too short.")

    def test_rental_detail_forms_have_unique_ids_labels_and_aria_targets(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(f"/catalog/{self.rental_property.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="inquiry_message"')
        self.assertContains(response, 'id="viewing_note"')
        self.assertContains(response, 'id="booking_note"')
        self.assertContains(response, 'for="inquiry_message"')
        self.assertContains(response, 'for="viewing_note"')
        self.assertContains(response, 'for="booking_note"')
        self._assert_unique_ids_labels_and_descriptions(response.content.decode())

    def test_invalid_detail_forms_keep_sibling_action_panels_and_accessible_errors(self) -> None:
        self.client.force_login(self.user)

        inquiry_response = self.client.post(
            f"/catalog/{self.rental_property.id}/inquiry/",
            {"message": ""},
        )
        self.assertEqual(inquiry_response.status_code, 200)
        self.assertContains(inquiry_response, "Tell us what you would like to know.")
        self.assertContains(inquiry_response, 'aria-describedby="inquiry_message_helptext inquiry_message_errors"')
        self.assertContains(inquiry_response, 'id="inquiry_message_errors" role="alert"')
        self.assertContains(inquiry_response, "Request a Viewing")
        self.assertContains(inquiry_response, "Request a Rental Booking")
        self.assertContains(inquiry_response, 'name="start_date"')
        self.assertContains(inquiry_response, "Recommended Similar Listings")
        self._assert_unique_ids_labels_and_descriptions(inquiry_response.content.decode())

        viewing_response = self.client.post(
            f"/catalog/{self.unavailable_rental.id}/viewing-request/",
            {"requested_datetime": ""},
        )
        self.assertEqual(viewing_response.status_code, 200)
        self.assertContains(viewing_response, "Choose a future date and time for the viewing.")
        self.assertContains(
            viewing_response,
            'aria-describedby="viewing_requested_datetime_helptext viewing_requested_datetime_errors"',
        )
        self.assertContains(viewing_response, "Similar Listing Alerts")
        self.assertContains(viewing_response, "Subscribe to alerts")
        self.assertContains(viewing_response, "Request a Rental Booking")
        self._assert_unique_ids_labels_and_descriptions(viewing_response.content.decode())

    def test_invalid_booking_errors_preserve_alert_ui_on_unavailable_rentals(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(
            f"/catalog/{self.unavailable_rental.id}/booking-request/",
            {
                "start_date": (timezone.localdate() + timedelta(days=3)).isoformat(),
                "end_date": (timezone.localdate() + timedelta(days=3)).isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Booking end date must be after the start date.")
        self.assertContains(response, 'aria-describedby="booking_end_date_helptext booking_end_date_errors"')
        self.assertContains(response, 'id="booking_end_date_errors" role="alert"')
        self.assertContains(response, "Similar Listing Alerts")
        self.assertContains(response, "Subscribe to alerts")
        self.assertContains(response, "Send an inquiry")
        self.assertContains(response, "Request a Viewing")
        self._assert_unique_ids_labels_and_descriptions(response.content.decode())

    def test_accessible_widget_preserves_and_merges_existing_descriptions_and_attrs(self) -> None:
        class PreservedAttrsForm(forms.Form):
            start_date = forms.DateField(
                help_text="Choose a start date.",
                widget=forms.DateInput(
                    attrs={
                        "aria-describedby": "custom_hint id_start_date_helptext custom_hint",
                        "class": "form-control custom-date",
                        "data-preserved": "yes",
                    }
                ),
            )

        invalid_form = PreservedAttrsForm(data={"start_date": ""}, auto_id="id_%s")
        self.assertFalse(invalid_form.is_valid())

        invalid_html = str(accessible_widget(invalid_form["start_date"]))
        self.assertIn('aria-describedby="custom_hint id_start_date_helptext id_start_date_errors"', invalid_html)
        self.assertIn('aria-invalid="true"', invalid_html)
        self.assertIn('class="form-control custom-date"', invalid_html)
        self.assertIn('data-preserved="yes"', invalid_html)
        self.assertEqual(invalid_html.count("custom_hint"), 1)
        self.assertEqual(invalid_html.count("id_start_date_helptext"), 1)

        valid_form = PreservedAttrsForm(data={"start_date": timezone.localdate().isoformat()}, auto_id="id_%s")
        self.assertTrue(valid_form.is_valid())

        valid_html = str(accessible_widget(valid_form["start_date"]))
        self.assertIn('aria-describedby="custom_hint id_start_date_helptext"', valid_html)
        self.assertNotIn("aria-invalid", valid_html)
        self.assertIn('data-preserved="yes"', valid_html)

    def test_anonymous_recommendation_empty_copy_is_neutral_on_public_surfaces(self) -> None:
        for path in ("/", "/catalog/"):
            with self.subTest(path=path):
                response = self.client.get(path)
                response_text = response.content.decode().lower()

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "No recommendations available yet")
                self.assertContains(response, "Browse listings to discover recommendations.")
                self.assertNotIn("personalized", response_text)
                self.assertNotIn("based on your activity", response_text)

    def test_simulated_payment_status_is_discoverable_without_real_payment_fields(self) -> None:
        booking_request = BookingRequest.objects.create(
            user=self.user,
            property=self.rental_property,
            start_date=timezone.localdate() + timedelta(days=5),
            end_date=timezone.localdate() + timedelta(days=7),
            status=BookingRequestStatus.PENDING,
        )
        self.client.force_login(self.user)

        response = self.client.get(f"/bookings/{booking_request.id}/simulated-payment/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'role="status"')
        self.assertContains(response, "University project demo - no real payment will be processed.")
        self.assertNotContains(response, 'name="card_number"')
        self.assertNotContains(response, 'name="cvv"')
        self.assertNotContains(response, 'name="bank_account"')
        self.assertNotContains(response, 'name="billing_address"')

    def _create_property(self, *, title: str, category: str, status: str) -> Property:
        return Property.objects.create(
            title=title,
            description=f"{title} description",
            category=category,
            status=status,
            city="Athens",
            area="Center",
            address_line="1 Test Street",
            price=Decimal("1200.00"),
            bedrooms=2,
            bathrooms=Decimal("1.5"),
        )

    def _assert_unique_ids_labels_and_descriptions(self, html: str) -> None:
        collector = HtmlAttributeCollector()
        collector.feed(html)
        ids = collector.ids
        id_set = set(ids)

        self.assertEqual(len(ids), len(id_set), sorted(_duplicate_values(ids)))
        for label_target in collector.labels_for:
            self.assertIn(label_target, id_set)
        for described_by_target in collector.described_by_tokens:
            self.assertIn(described_by_target, id_set)


def _duplicate_values(values: list[str]) -> set[str]:
    seen = set()
    duplicates = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates

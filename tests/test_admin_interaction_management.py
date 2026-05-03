from __future__ import annotations

import os
from datetime import timedelta
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django
from django.contrib import admin
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

django.setup()

from homefinder.apps.interactions.models import (  # noqa: E402
    PropertyInquiry,
    PropertyInquiryStatus,
    ViewingRequest,
    ViewingRequestStatus,
)
from homefinder.apps.properties.models import Property, PropertyCategory  # noqa: E402
from homefinder.apps.users.models import User  # noqa: E402


class AdminInteractionManagementTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            email="admin@example.com",
            password="password123",
        )
        self.client.force_login(self.admin_user)

        self.inquiry_user = User.objects.create_user(
            email="inquiry-user@example.com",
            password="password123",
            full_name="Inquiry User",
        )
        self.viewing_user = User.objects.create_user(
            email="viewing-user@example.com",
            password="password123",
            full_name="Viewing User",
        )

        self.athens_property = self._create_property(
            title="Athens Loft",
            city="Athens",
        )
        self.patra_property = self._create_property(
            title="Patra Office",
            city="Patra",
        )

    def test_admin_configuration_is_practical_for_inquiry_and_viewing_management(self) -> None:
        inquiry_admin = admin.site._registry[PropertyInquiry]
        viewing_admin = admin.site._registry[ViewingRequest]

        self.assertEqual(inquiry_admin.list_editable, ("status",))
        self.assertIn("status", inquiry_admin.list_display)
        self.assertIn("property_city", inquiry_admin.list_display)
        self.assertIn("status", inquiry_admin.list_filter)
        self.assertIn("property__city", inquiry_admin.list_filter)
        self.assertIn("user__email", inquiry_admin.search_fields)
        self.assertIn("property__title", inquiry_admin.search_fields)
        self.assertIn("message", inquiry_admin.search_fields)
        self.assertEqual(inquiry_admin.autocomplete_fields, ("user", "property"))

        self.assertEqual(viewing_admin.list_editable, ("status",))
        self.assertIn("requested_datetime", viewing_admin.list_display)
        self.assertIn("property_city", viewing_admin.list_display)
        self.assertIn("status", viewing_admin.list_filter)
        self.assertIn("property__city", viewing_admin.list_filter)
        self.assertIn("user__email", viewing_admin.search_fields)
        self.assertIn("property__title", viewing_admin.search_fields)
        self.assertIn("note", viewing_admin.search_fields)
        self.assertEqual(viewing_admin.autocomplete_fields, ("user", "property"))

    def test_admin_can_update_inquiry_and_viewing_statuses_from_change_views(self) -> None:
        inquiry = PropertyInquiry.objects.create(
            user=self.inquiry_user,
            property=self.athens_property,
            message="Could you share utility costs?",
            status=PropertyInquiryStatus.OPEN,
        )
        viewing_request = ViewingRequest.objects.create(
            user=self.viewing_user,
            property=self.patra_property,
            requested_datetime=timezone.now() + timedelta(days=1),
            status=ViewingRequestStatus.PENDING,
            note="Afternoon slot preferred.",
        )

        inquiry_change_url = reverse("admin:interactions_propertyinquiry_change", args=[inquiry.id])
        inquiry_response = self.client.post(
            inquiry_change_url,
            data={
                "user": str(inquiry.user_id),
                "property": str(inquiry.property_id),
                "message": inquiry.message,
                "status": PropertyInquiryStatus.IN_PROGRESS,
                "_save": "Save",
            },
        )
        self.assertEqual(inquiry_response.status_code, 302)

        inquiry.refresh_from_db()
        self.assertEqual(inquiry.status, PropertyInquiryStatus.IN_PROGRESS)

        viewing_change_url = reverse("admin:interactions_viewingrequest_change", args=[viewing_request.id])
        requested_local = timezone.localtime(viewing_request.requested_datetime)
        viewing_response = self.client.post(
            viewing_change_url,
            data={
                "user": str(viewing_request.user_id),
                "property": str(viewing_request.property_id),
                "requested_datetime_0": requested_local.strftime("%Y-%m-%d"),
                "requested_datetime_1": requested_local.strftime("%H:%M:%S"),
                "status": ViewingRequestStatus.CONFIRMED,
                "note": viewing_request.note,
                "_save": "Save",
            },
        )
        self.assertEqual(viewing_response.status_code, 302)

        viewing_request.refresh_from_db()
        self.assertEqual(viewing_request.status, ViewingRequestStatus.CONFIRMED)

    def test_changelists_support_filtering_and_search_for_staff_interaction_workflows(self) -> None:
        open_inquiry = PropertyInquiry.objects.create(
            user=self.inquiry_user,
            property=self.athens_property,
            message="Need garage details.",
            status=PropertyInquiryStatus.OPEN,
        )
        closed_inquiry = PropertyInquiry.objects.create(
            user=self.viewing_user,
            property=self.patra_property,
            message="Resolved inquiry already.",
            status=PropertyInquiryStatus.CLOSED,
        )
        pending_viewing = ViewingRequest.objects.create(
            user=self.inquiry_user,
            property=self.athens_property,
            requested_datetime=timezone.now() + timedelta(days=1),
            status=ViewingRequestStatus.PENDING,
            note="Morning slot works.",
        )
        cancelled_viewing = ViewingRequest.objects.create(
            user=self.viewing_user,
            property=self.patra_property,
            requested_datetime=timezone.now() + timedelta(days=2),
            status=ViewingRequestStatus.CANCELLED,
            note="Schedule conflict.",
        )

        inquiry_changelist_url = reverse("admin:interactions_propertyinquiry_changelist")
        inquiry_status_filter_response = self.client.get(
            inquiry_changelist_url,
            {"status__exact": PropertyInquiryStatus.CLOSED},
        )
        self.assertEqual(inquiry_status_filter_response.status_code, 200)
        self.assertEqual(
            set(inquiry_status_filter_response.context["cl"].queryset.values_list("id", flat=True)),
            {closed_inquiry.id},
        )

        inquiry_city_filter_response = self.client.get(
            inquiry_changelist_url,
            {"property__city__exact": "Patra"},
        )
        self.assertEqual(inquiry_city_filter_response.status_code, 200)
        self.assertEqual(
            set(inquiry_city_filter_response.context["cl"].queryset.values_list("id", flat=True)),
            {closed_inquiry.id},
        )

        inquiry_search_response = self.client.get(inquiry_changelist_url, {"q": "garage"})
        self.assertEqual(inquiry_search_response.status_code, 200)
        self.assertEqual(
            set(inquiry_search_response.context["cl"].queryset.values_list("id", flat=True)),
            {open_inquiry.id},
        )

        viewing_changelist_url = reverse("admin:interactions_viewingrequest_changelist")
        viewing_status_filter_response = self.client.get(
            viewing_changelist_url,
            {"status__exact": ViewingRequestStatus.CANCELLED},
        )
        self.assertEqual(viewing_status_filter_response.status_code, 200)
        self.assertEqual(
            set(viewing_status_filter_response.context["cl"].queryset.values_list("id", flat=True)),
            {cancelled_viewing.id},
        )

        viewing_city_filter_response = self.client.get(
            viewing_changelist_url,
            {"property__city__exact": "Patra"},
        )
        self.assertEqual(viewing_city_filter_response.status_code, 200)
        self.assertEqual(
            set(viewing_city_filter_response.context["cl"].queryset.values_list("id", flat=True)),
            {cancelled_viewing.id},
        )

        viewing_search_response = self.client.get(viewing_changelist_url, {"q": "Morning"})
        self.assertEqual(viewing_search_response.status_code, 200)
        self.assertEqual(
            set(viewing_search_response.context["cl"].queryset.values_list("id", flat=True)),
            {pending_viewing.id},
        )

    def _create_property(
        self,
        *,
        title: str,
        city: str,
    ) -> Property:
        return Property.objects.create(
            title=title,
            description=f"{title} description",
            category=PropertyCategory.RESIDENTIAL,
            city=city,
            area="Center",
            price=Decimal("250000.00"),
        )

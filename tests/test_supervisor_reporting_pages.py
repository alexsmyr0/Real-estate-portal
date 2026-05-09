from __future__ import annotations

import os
from datetime import datetime, timezone as datetime_timezone
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django

django.setup()

from django.test import Client, TestCase, override_settings

from homefinder.apps.interactions.models import PropertyInquiry, SearchHistory, UserFavorite
from homefinder.apps.properties.models import Property, PropertyCategory, PropertyStatus
from homefinder.apps.properties.services import (
    get_monthly_inquiry_and_saved_property_metrics,
    get_monthly_search_trend_metrics,
)
from homefinder.apps.users.models import User, UserRole


@override_settings(ALLOWED_HOSTS=["testserver"])
class SupervisorReportingPageTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.regular_user = User.objects.create_user(
            email="regular-report-user@example.com",
            password="StrongPassword123!",
            role=UserRole.USER,
        )
        self.supervisor_user = User.objects.create_user(
            email="supervisor-report-user@example.com",
            password="StrongPassword123!",
            role=UserRole.SUPERVISOR,
            is_staff=True,
        )
        self.admin_user = User.objects.create_superuser(
            email="admin-report-user@example.com",
            password="StrongPassword123!",
        )

        self.property = self._create_property()
        self._seed_reporting_data()

    def _create_property(self) -> Property:
        return Property.objects.create(
            title="Reporting Listing",
            description="Reporting listing description",
            category=PropertyCategory.RESIDENTIAL,
            status=PropertyStatus.AVAILABLE,
            city="Athens",
            area="Center",
            address_line="Athens Center 5",
            price=Decimal("220000.00"),
            bedrooms=2,
            bathrooms=Decimal("1.5"),
        )

    def _seed_reporting_data(self) -> None:
        inquiry = PropertyInquiry.objects.create(
            user=self.regular_user,
            property=self.property,
            message="Need more details.",
        )
        inquiry_created_at = datetime(2026, 1, 11, 12, 0, tzinfo=datetime_timezone.utc)
        PropertyInquiry.objects.filter(pk=inquiry.pk).update(
            created_at=inquiry_created_at,
            updated_at=inquiry_created_at,
        )

        favorite = UserFavorite.objects.create(user=self.regular_user, property=self.property)
        UserFavorite.objects.filter(pk=favorite.pk).update(
            created_at=datetime(2026, 1, 15, 14, 0, tzinfo=datetime_timezone.utc),
        )

        search_history = SearchHistory.objects.create(
            user=self.regular_user,
            location_city="Athens",
            category=PropertyCategory.RESIDENTIAL,
            min_price=Decimal("100000.00"),
            max_price=Decimal("249999.00"),
        )
        SearchHistory.objects.filter(pk=search_history.pk).update(
            created_at=datetime(2026, 1, 20, 9, 0, tzinfo=datetime_timezone.utc),
        )

    def test_guest_reporting_requests_redirect_to_login(self) -> None:
        for path in ("/staff/reports/", "/staff/reports/search-trends/"):
            with self.subTest(path=path):
                response = self.client.get(path, follow=True)
                self.assertRedirects(response, f"/login/?next={path.replace('/', '%2F')}")
                self.assertContains(response, "Sign in with a supervisor or admin account to view reporting pages.")

    def test_non_reporting_role_receives_forbidden_responses(self) -> None:
        self.client.force_login(self.regular_user)

        for path in ("/staff/reports/", "/staff/reports/search-trends/"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 403)
                self.assertJSONEqual(
                    response.content,
                    {
                        "status": "error",
                        "error": {
                            "code": 403,
                            "message": "Forbidden",
                        },
                    },
                )

    def test_supervisor_can_view_reporting_overview_without_edit_or_export_controls(self) -> None:
        self.client.force_login(self.supervisor_user)

        response = self.client.get("/staff/reports/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "properties/reporting_overview.html")
        self.assertEqual(
            response.context["monthly_summary_metrics"],
            get_monthly_inquiry_and_saved_property_metrics(),
        )
        self.assertEqual(
            [metric["month"] for metric in response.context["search_trend_metrics"]],
            [metric["month"] for metric in get_monthly_search_trend_metrics()],
        )
        self.assertContains(response, "2026-01")
        self.assertContains(response, "Athens (1)")
        self.assertContains(response, "Residential (1)")
        self.assertContains(response, "100k-249,999 (1)")

        for disallowed_text in ("Edit", "Update", "Delete", "Export", "PDF", "Spreadsheet"):
            with self.subTest(disallowed_text=disallowed_text):
                self.assertNotContains(response, disallowed_text)

    def test_admin_can_view_search_trend_reporting_page(self) -> None:
        self.client.force_login(self.admin_user)

        response = self.client.get("/staff/reports/search-trends/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "properties/reporting_search_trends.html")
        self.assertEqual(
            [metric["month"] for metric in response.context["search_trend_metrics"]],
            [metric["month"] for metric in get_monthly_search_trend_metrics()],
        )
        self.assertContains(response, "Search trend summaries by month")
        self.assertContains(response, "Athens (1)")
        self.assertContains(response, "Residential (1)")
        self.assertContains(response, "100k-249,999 (1)")

    def test_reports_navigation_link_is_visible_only_to_supervisor_and_admin_roles(self) -> None:
        guest_response = self.client.get("/")
        self.assertNotContains(guest_response, 'href="/staff/reports/"')

        self.client.force_login(self.regular_user)
        regular_response = self.client.get("/")
        self.assertNotContains(regular_response, 'href="/staff/reports/"')

        self.client.force_login(self.supervisor_user)
        supervisor_response = self.client.get("/")
        self.assertContains(supervisor_response, 'href="/staff/reports/"')

        self.client.force_login(self.admin_user)
        admin_response = self.client.get("/")
        self.assertContains(admin_response, 'href="/staff/reports/"')

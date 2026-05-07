from __future__ import annotations

import io
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from homefinder.apps.interactions.models import (
    ActivityLog,
    ActivityScope,
    BookingRequest,
    EmailNotification,
    EmailNotificationPurpose,
    PropertyInquiry,
    SearchHistory,
    UserFavorite,
    ViewingRequest,
)
from homefinder.apps.interactions.retention import LOG_RETENTION_DAYS, cleanup_log_retention
from homefinder.apps.properties.models import Property, PropertyCategory
from homefinder.apps.users.models import User


class LogRetentionCleanupTests(TestCase):
    def setUp(self) -> None:
        self.reference_time = timezone.now().replace(microsecond=0)
        self.cutoff = self.reference_time - timedelta(days=LOG_RETENTION_DAYS)
        self.older_than_cutoff = self.cutoff - timedelta(seconds=1)
        self.equal_to_cutoff = self.cutoff
        self.newer_than_cutoff = self.cutoff + timedelta(seconds=1)

        self.user = User.objects.create_user(
            email="buyer@example.com",
            password="secret-pass",
            full_name="Buyer Example",
        )
        self.property = Property.objects.create(
            title="Central Apartment",
            category=PropertyCategory.RESIDENTIAL,
            city="Athens",
            price="250000.00",
        )

    def test_activity_logs_older_than_90_days_are_deleted(self) -> None:
        old_log = self._activity_log(self.older_than_cutoff)
        fresh_log = self._activity_log(self.newer_than_cutoff)

        result = cleanup_log_retention(reference_time=self.reference_time)

        self.assertEqual(result.counts["ActivityLog"], 1)
        self.assertFalse(ActivityLog.objects.filter(pk=old_log.pk).exists())
        self.assertTrue(ActivityLog.objects.filter(pk=fresh_log.pk).exists())

    def test_search_history_older_than_90_days_is_deleted(self) -> None:
        old_history = self._search_history(self.older_than_cutoff)
        fresh_history = self._search_history(self.newer_than_cutoff)

        result = cleanup_log_retention(reference_time=self.reference_time)

        self.assertEqual(result.counts["SearchHistory"], 1)
        self.assertFalse(SearchHistory.objects.filter(pk=old_history.pk).exists())
        self.assertTrue(SearchHistory.objects.filter(pk=fresh_history.pk).exists())

    def test_email_notifications_older_than_90_days_are_deleted(self) -> None:
        old_notification = self._email_notification(self.older_than_cutoff)
        fresh_notification = self._email_notification(self.newer_than_cutoff)

        result = cleanup_log_retention(reference_time=self.reference_time)

        self.assertEqual(result.counts["EmailNotification"], 1)
        self.assertFalse(EmailNotification.objects.filter(pk=old_notification.pk).exists())
        self.assertTrue(EmailNotification.objects.filter(pk=fresh_notification.pk).exists())

    def test_records_newer_than_or_equal_to_cutoff_are_preserved(self) -> None:
        preserved_records = [
            self._activity_log(self.equal_to_cutoff),
            self._activity_log(self.newer_than_cutoff),
            self._search_history(self.equal_to_cutoff),
            self._search_history(self.newer_than_cutoff),
            self._email_notification(self.equal_to_cutoff),
            self._email_notification(self.newer_than_cutoff),
        ]

        result = cleanup_log_retention(reference_time=self.reference_time)

        self.assertEqual(result.total_count, 0)
        for record in preserved_records:
            with self.subTest(model=record.__class__.__name__, pk=record.pk):
                self.assertTrue(record.__class__.objects.filter(pk=record.pk).exists())

    def test_non_target_business_records_are_preserved(self) -> None:
        self._activity_log(self.older_than_cutoff)
        favorite = UserFavorite.objects.create(user=self.user, property=self.property)
        inquiry = PropertyInquiry.objects.create(
            user=self.user,
            property=self.property,
            message="I would like more details.",
        )
        viewing_request = ViewingRequest.objects.create(
            user=self.user,
            property=self.property,
            requested_datetime=self.reference_time + timedelta(days=1),
        )
        booking_property = Property.objects.create(
            title="Retention Rental",
            category=PropertyCategory.RENTAL,
            city="Athens",
            price="1200.00",
        )
        booking_request = BookingRequest.objects.create(
            user=self.user,
            property=booking_property,
            start_date=(self.reference_time + timedelta(days=1)).date(),
            end_date=(self.reference_time + timedelta(days=2)).date(),
        )

        for record in (self.user, self.property, favorite, inquiry, viewing_request, booking_property, booking_request):
            self._set_created_at(record, self.older_than_cutoff)

        cleanup_log_retention(reference_time=self.reference_time)

        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertTrue(Property.objects.filter(pk=self.property.pk).exists())
        self.assertTrue(UserFavorite.objects.filter(pk=favorite.pk).exists())
        self.assertTrue(PropertyInquiry.objects.filter(pk=inquiry.pk).exists())
        self.assertTrue(ViewingRequest.objects.filter(pk=viewing_request.pk).exists())
        self.assertTrue(Property.objects.filter(pk=booking_property.pk).exists())
        self.assertTrue(BookingRequest.objects.filter(pk=booking_request.pk).exists())

    def test_command_reports_deleted_counts_per_model(self) -> None:
        self._activity_log(self.older_than_cutoff)
        self._search_history(self.older_than_cutoff)
        self._email_notification(self.older_than_cutoff)
        stdout = io.StringIO()

        call_command("cleanup_log_retention", stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("ActivityLog deleted=1", output)
        self.assertIn("SearchHistory deleted=1", output)
        self.assertIn("EmailNotification deleted=1", output)
        self.assertIn("total_deleted=3", output)

    def test_dry_run_reports_eligible_records_without_deleting(self) -> None:
        old_log = self._activity_log(self.older_than_cutoff)
        old_history = self._search_history(self.older_than_cutoff)
        old_notification = self._email_notification(self.older_than_cutoff)
        stdout = io.StringIO()

        call_command("cleanup_log_retention", "--dry-run", stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("dry_run=True", output)
        self.assertIn("ActivityLog eligible=1", output)
        self.assertIn("SearchHistory eligible=1", output)
        self.assertIn("EmailNotification eligible=1", output)
        self.assertIn("total_eligible=3", output)
        self.assertTrue(ActivityLog.objects.filter(pk=old_log.pk).exists())
        self.assertTrue(SearchHistory.objects.filter(pk=old_history.pk).exists())
        self.assertTrue(EmailNotification.objects.filter(pk=old_notification.pk).exists())

    def _activity_log(self, created_at) -> ActivityLog:
        activity_log = ActivityLog.objects.create(
            user=self.user,
            scope=ActivityScope.SYSTEM,
            action="retention_test",
        )
        self._set_created_at(activity_log, created_at)
        return activity_log

    def _search_history(self, created_at) -> SearchHistory:
        search_history = SearchHistory.objects.create(user=self.user, location_city="Athens")
        self._set_created_at(search_history, created_at)
        return search_history

    def _email_notification(self, created_at) -> EmailNotification:
        notification = EmailNotification.objects.create(
            user=self.user,
            purpose=EmailNotificationPurpose.LOGIN_2FA,
            recipient_email=self.user.email,
        )
        self._set_created_at(notification, created_at)
        return notification

    def _set_created_at(self, record, created_at) -> None:
        record.__class__.objects.filter(pk=record.pk).update(created_at=created_at)
        record.created_at = created_at

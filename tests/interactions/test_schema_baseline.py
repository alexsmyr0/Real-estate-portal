from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django
from django.apps import apps
from django.contrib import admin
from django.db import models
from django.test import SimpleTestCase

django.setup()

from homefinder.apps.interactions.models import (
    ActivityLog,
    BookingRequest,
    EmailNotification,
    Payment,
    SearchHistory,
)
from homefinder.apps.properties.models import ListingAlertSubscription


class CrossCuttingSchemaBaselineTests(SimpleTestCase):
    def test_n01_domain_models_are_present_with_locked_table_names(self) -> None:
        expected_tables = {
            EmailNotification: "email_notifications",
            SearchHistory: "search_history",
            ActivityLog: "activity_logs",
            ListingAlertSubscription: "listing_alert_subscriptions",
            BookingRequest: "booking_requests",
            Payment: "payments",
        }

        for model, table_name in expected_tables.items():
            with self.subTest(model=model.__name__):
                self.assertIs(apps.get_model(model._meta.app_label, model.__name__), model)
                self.assertEqual(model._meta.db_table, table_name)

    def test_n01_models_remain_registered_in_admin(self) -> None:
        for model in (
            EmailNotification,
            SearchHistory,
            ActivityLog,
            ListingAlertSubscription,
            BookingRequest,
            Payment,
        ):
            with self.subTest(model=model.__name__):
                self.assertTrue(admin.site.is_registered(model))

    def test_n01_baseline_fields_support_deferred_work(self) -> None:
        self.assert_model_has_fields(
            EmailNotification,
            {
                "user": models.ForeignKey,
                "purpose": models.CharField,
                "recipient_email": models.EmailField,
                "status": models.CharField,
                "created_at": models.DateTimeField,
                "sent_at": models.DateTimeField,
            },
        )
        self.assert_model_has_fields(
            SearchHistory,
            {
                "user": models.ForeignKey,
                "location_city": models.CharField,
                "min_price": models.DecimalField,
                "max_price": models.DecimalField,
                "category": models.CharField,
                "bedrooms_min": models.PositiveSmallIntegerField,
                "created_at": models.DateTimeField,
            },
        )
        self.assert_model_has_fields(
            ActivityLog,
            {
                "user": models.ForeignKey,
                "scope": models.CharField,
                "action": models.CharField,
                "entity_type": models.CharField,
                "entity_id": models.BigIntegerField,
                "created_at": models.DateTimeField,
            },
        )
        self.assert_model_has_fields(
            ListingAlertSubscription,
            {
                "user": models.ForeignKey,
                "category": models.CharField,
                "location_city": models.CharField,
                "min_price": models.DecimalField,
                "max_price": models.DecimalField,
                "bedrooms_min": models.PositiveSmallIntegerField,
                "is_active": models.BooleanField,
                "amenities": models.ManyToManyField,
                "created_at": models.DateTimeField,
            },
        )
        self.assert_model_has_fields(
            BookingRequest,
            {
                "user": models.ForeignKey,
                "property": models.ForeignKey,
                "start_date": models.DateField,
                "end_date": models.DateField,
                "status": models.CharField,
                "note": models.CharField,
                "created_at": models.DateTimeField,
                "updated_at": models.DateTimeField,
            },
        )
        self.assert_model_has_fields(
            Payment,
            {
                "user": models.ForeignKey,
                "booking_request": models.ForeignKey,
                "payment_purpose": models.CharField,
                "payment_method": models.CharField,
                "amount": models.DecimalField,
                "status": models.CharField,
                "created_at": models.DateTimeField,
            },
        )

    def assert_model_has_fields(
        self,
        model: type[models.Model],
        expected_fields: dict[str, type[models.Field]],
    ) -> None:
        actual_fields = {field.name: field for field in model._meta.get_fields()}

        for field_name, field_type in expected_fields.items():
            with self.subTest(model=model.__name__, field=field_name):
                self.assertIn(field_name, actual_fields)
                self.assertIsInstance(actual_fields[field_name], field_type)

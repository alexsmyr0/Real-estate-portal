from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

import django
from django.apps import apps
from django.contrib import admin
from django.db import connection, models
from django.test import TestCase

django.setup()

from homefinder.apps.interactions.models import (  # noqa: E402
    ActivityLog,
    ActivityScope,
    BookingRequest,
    BookingRequestStatus,
    EmailNotification,
    EmailNotificationPurpose,
    EmailNotificationStatus,
    Payment,
    PaymentMethod,
    PaymentPurpose,
    PaymentStatus,
    SearchHistory,
)
from homefinder.apps.properties.models import (  # noqa: E402
    ListingAlertSubscription,
    ListingAlertSubscriptionAmenity,
    PropertyCategory,
)


class CrossCuttingSchemaBaselineTests(TestCase):
    N01_MODELS = (
        EmailNotification,
        SearchHistory,
        ActivityLog,
        ListingAlertSubscription,
        BookingRequest,
        Payment,
    )

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

    def test_n01_migrated_tables_exist_in_database(self) -> None:
        migrated_tables = set(connection.introspection.table_names())
        expected_tables = {model._meta.db_table for model in self.N01_MODELS}
        expected_tables.add(ListingAlertSubscriptionAmenity._meta.db_table)

        self.assertLessEqual(expected_tables, migrated_tables)

    def test_n01_models_remain_registered_in_admin(self) -> None:
        for model in self.N01_MODELS:
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
                "details": models.JSONField,
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

    def test_n01_notification_schema_contracts_are_locked(self) -> None:
        self.assert_fk_contract(EmailNotification, "user", on_delete=models.SET_NULL, null=True, blank=True)
        self.assert_field_contract(EmailNotification, "purpose", choices=EmailNotificationPurpose.choices, max_length=24)
        self.assert_field_contract(
            EmailNotification,
            "status",
            choices=EmailNotificationStatus.choices,
            default=EmailNotificationStatus.PENDING,
            max_length=16,
        )
        self.assert_field_contract(EmailNotification, "sent_at", null=True, blank=True)

    def test_n01_logging_schema_contracts_are_locked(self) -> None:
        self.assert_fk_contract(SearchHistory, "user", on_delete=models.SET_NULL, null=True, blank=True)
        self.assert_field_contract(SearchHistory, "category", choices=PropertyCategory.choices, blank=True, max_length=16)
        self.assert_field_contract(SearchHistory, "min_price", null=True, blank=True, max_digits=12, decimal_places=2)
        self.assert_field_contract(SearchHistory, "max_price", null=True, blank=True, max_digits=12, decimal_places=2)
        self.assert_field_contract(SearchHistory, "bedrooms_min", null=True, blank=True)

        self.assert_fk_contract(ActivityLog, "user", on_delete=models.SET_NULL, null=True, blank=True)
        self.assert_field_contract(ActivityLog, "scope", choices=ActivityScope.choices, max_length=16)
        self.assert_field_contract(ActivityLog, "action", max_length=80)
        self.assert_field_contract(ActivityLog, "entity_type", blank=True, max_length=80)
        self.assert_field_contract(ActivityLog, "entity_id", null=True, blank=True)
        self.assert_field_contract(ActivityLog, "details", default=dict, blank=True)

    def test_n01_alert_schema_contracts_are_locked(self) -> None:
        self.assert_fk_contract(ListingAlertSubscription, "user", on_delete=models.CASCADE)
        self.assert_field_contract(
            ListingAlertSubscription,
            "category",
            choices=PropertyCategory.choices,
            blank=True,
            max_length=16,
        )
        self.assert_field_contract(
            ListingAlertSubscription,
            "min_price",
            null=True,
            blank=True,
            max_digits=12,
            decimal_places=2,
        )
        self.assert_field_contract(
            ListingAlertSubscription,
            "max_price",
            null=True,
            blank=True,
            max_digits=12,
            decimal_places=2,
        )
        self.assert_field_contract(ListingAlertSubscription, "bedrooms_min", null=True, blank=True)
        self.assert_field_contract(ListingAlertSubscription, "is_active", default=True)

        amenities = ListingAlertSubscription._meta.get_field("amenities")
        self.assertIsInstance(amenities, models.ManyToManyField)
        self.assertIs(amenities.remote_field.through, ListingAlertSubscriptionAmenity)
        self.assertEqual(ListingAlertSubscriptionAmenity._meta.db_table, "listing_alert_subscription_amenities")

        self.assert_fk_contract(ListingAlertSubscriptionAmenity, "subscription", on_delete=models.CASCADE)
        self.assert_fk_contract(ListingAlertSubscriptionAmenity, "amenity", on_delete=models.CASCADE)

    def test_n01_deferred_commerce_schema_contracts_are_locked(self) -> None:
        self.assert_fk_contract(BookingRequest, "user", on_delete=models.CASCADE)
        self.assert_fk_contract(BookingRequest, "property", on_delete=models.CASCADE)
        self.assert_field_contract(BookingRequest, "start_date", null=True, blank=True)
        self.assert_field_contract(BookingRequest, "end_date", null=True, blank=True)
        self.assert_field_contract(
            BookingRequest,
            "status",
            choices=BookingRequestStatus.choices,
            default=BookingRequestStatus.PENDING,
            max_length=16,
        )
        self.assert_field_contract(BookingRequest, "note", blank=True, max_length=500)

        self.assert_fk_contract(Payment, "user", on_delete=models.CASCADE)
        self.assert_fk_contract(Payment, "booking_request", on_delete=models.SET_NULL, null=True, blank=True)
        self.assert_field_contract(
            Payment,
            "payment_purpose",
            choices=PaymentPurpose.choices,
            default=PaymentPurpose.OTHER,
            max_length=20,
        )
        self.assert_field_contract(Payment, "payment_method", choices=PaymentMethod.choices, max_length=20)
        self.assert_field_contract(Payment, "amount", max_digits=12, decimal_places=2)
        self.assert_field_contract(
            Payment,
            "status",
            choices=PaymentStatus.choices,
            default=PaymentStatus.PENDING,
            max_length=16,
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

    def assert_field_contract(
        self,
        model: type[models.Model],
        field_name: str,
        **expected_attrs: object,
    ) -> None:
        field = model._meta.get_field(field_name)

        for attr_name, expected_value in expected_attrs.items():
            with self.subTest(model=model.__name__, field=field_name, attr=attr_name):
                self.assertEqual(getattr(field, attr_name), expected_value)

    def assert_fk_contract(
        self,
        model: type[models.Model],
        field_name: str,
        *,
        on_delete: object,
        null: bool = False,
        blank: bool = False,
    ) -> None:
        field = model._meta.get_field(field_name)

        with self.subTest(model=model.__name__, field=field_name):
            self.assertIsInstance(field, models.ForeignKey)
            self.assertIs(field.remote_field.on_delete, on_delete)
            self.assertEqual(field.null, null)
            self.assertEqual(field.blank, blank)

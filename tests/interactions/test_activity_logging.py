from __future__ import annotations

from collections.abc import Iterator, Mapping
from decimal import Decimal
from typing import Any
from unittest.mock import patch

from django.test import TestCase

from homefinder.apps.interactions.models import ActivityLog, ActivityScope, SearchHistory
from homefinder.apps.interactions.redaction import REDACTED_DETAIL_VALUE
from homefinder.apps.interactions.services import (
    log_activity,
    log_auth_activity,
    log_interaction_activity,
    log_search_activity,
)
from homefinder.apps.properties.models import Property, PropertyCategory
from homefinder.apps.users.models import User

ACTIVITY_LOGGER = "homefinder.apps.interactions.activity_logging"


class BrokenMapping(Mapping[str, Any]):
    def __getitem__(self, key: str) -> Any:
        raise RuntimeError("broken mapping lookup")

    def __iter__(self) -> Iterator[str]:
        raise RuntimeError("broken mapping iteration")

    def __len__(self) -> int:
        return 1


class BrokenString:
    def __str__(self) -> str:
        raise RuntimeError("broken string conversion")


class ActivityLoggingServiceTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="buyer@example.com",
            password="secret-pass",
            full_name="Buyer Example",
        )
        self.property = Property.objects.create(
            title="Central Apartment",
            category=PropertyCategory.RESIDENTIAL,
            city="Athens",
            price=Decimal("250000.00"),
        )

    def test_auth_login_event_is_stored_with_consistent_entity_reference(self) -> None:
        activity_log = log_auth_activity(
            action="login",
            user=self.user,
            details={"method": "password", "source": "web"},
        )

        self.assertEqual(ActivityLog.objects.count(), 1)
        self.assertIsNotNone(activity_log)
        activity_log.refresh_from_db()
        self.assertEqual(activity_log.scope, ActivityScope.AUTH)
        self.assertEqual(activity_log.action, "login")
        self.assertEqual(activity_log.user, self.user)
        self.assertEqual(activity_log.entity_type, "user")
        self.assertEqual(activity_log.entity_id, self.user.pk)
        self.assertEqual(activity_log.details["method"], "password")
        self.assertEqual(activity_log.details["source"], "web")

    def test_search_event_stores_search_history_and_activity_log(self) -> None:
        result = log_search_activity(
            user=self.user,
            criteria={
                "location_city": " Athens ",
                "min_price": Decimal("100000.00"),
                "max_price": "450000.00",
                "category": "residential",
                "bedrooms_min": "2",
                "sort": "newest",
            },
            details={"surface": "property_search"},
        )

        self.assertEqual(SearchHistory.objects.count(), 1)
        self.assertEqual(ActivityLog.objects.count(), 1)
        self.assertIsNotNone(result.search_history)
        self.assertIsNotNone(result.activity_log)

        search_history = result.search_history
        search_history.refresh_from_db()
        self.assertEqual(search_history.user, self.user)
        self.assertEqual(search_history.location_city, "Athens")
        self.assertEqual(search_history.min_price, Decimal("100000.00"))
        self.assertEqual(search_history.max_price, Decimal("450000.00"))
        self.assertEqual(search_history.category, PropertyCategory.RESIDENTIAL)
        self.assertEqual(search_history.bedrooms_min, 2)

        activity_log = result.activity_log
        activity_log.refresh_from_db()
        self.assertEqual(activity_log.scope, ActivityScope.SEARCH)
        self.assertEqual(activity_log.action, "search_submitted")
        self.assertEqual(activity_log.user, self.user)
        self.assertEqual(activity_log.entity_type, "search_history")
        self.assertEqual(activity_log.entity_id, search_history.pk)
        self.assertEqual(activity_log.details["criteria"]["location_city"], "Athens")
        self.assertEqual(activity_log.details["criteria"]["min_price"], "100000.00")
        self.assertEqual(activity_log.details["criteria"]["max_price"], "450000.00")
        self.assertEqual(activity_log.details["criteria"]["category"], PropertyCategory.RESIDENTIAL)
        self.assertEqual(activity_log.details["criteria"]["bedrooms_min"], 2)
        self.assertEqual(activity_log.details["criteria"]["extra"], {"sort": "newest"})
        self.assertEqual(activity_log.details["surface"], "property_search")

    def test_generic_interaction_event_can_be_logged_through_shared_pipeline(self) -> None:
        activity_log = log_interaction_activity(
            action="favorite_added",
            user=self.user,
            entity=self.property,
            details={"surface": "listing_detail"},
        )

        self.assertEqual(ActivityLog.objects.count(), 1)
        self.assertIsNotNone(activity_log)
        activity_log.refresh_from_db()
        self.assertEqual(activity_log.scope, ActivityScope.INTERACTION)
        self.assertEqual(activity_log.action, "favorite_added")
        self.assertEqual(activity_log.user, self.user)
        self.assertEqual(activity_log.entity_type, "property")
        self.assertEqual(activity_log.entity_id, self.property.pk)
        self.assertEqual(activity_log.details, {"surface": "listing_detail"})

    def test_missing_optional_data_and_invalid_search_values_do_not_crash(self) -> None:
        activity_log = log_activity(
            scope=ActivityScope.INTERACTION,
            action=None,
            details={"price": Decimal("123.45")},
        )
        result = log_search_activity(criteria={"min_price": "not-a-price", "category": "unknown"})

        self.assertIsNotNone(activity_log)
        activity_log.refresh_from_db()
        self.assertIsNone(activity_log.user)
        self.assertEqual(activity_log.scope, ActivityScope.INTERACTION)
        self.assertEqual(activity_log.action, "unspecified")
        self.assertEqual(activity_log.entity_type, "")
        self.assertIsNone(activity_log.entity_id)
        self.assertEqual(activity_log.details, {"price": "123.45"})

        self.assertIsNotNone(result.search_history)
        result.search_history.refresh_from_db()
        self.assertIsNone(result.search_history.user)
        self.assertIsNone(result.search_history.min_price)
        self.assertEqual(result.search_history.category, "")

        self.assertIsNotNone(result.activity_log)
        result.activity_log.refresh_from_db()
        self.assertEqual(result.activity_log.scope, ActivityScope.SEARCH)
        self.assertEqual(result.activity_log.details, {"criteria": {}})

    def test_logging_failures_do_not_break_caller_flow(self) -> None:
        with self.assertLogs(ACTIVITY_LOGGER, level="ERROR"):
            with patch(
                "homefinder.apps.interactions.activity_logging.ActivityLog.objects.create",
                side_effect=RuntimeError("write failed"),
            ):
                activity_log = log_auth_activity(action="login", user=self.user)

        self.assertIsNone(activity_log)
        self.assertEqual(ActivityLog.objects.count(), 0)

        SearchHistory.objects.create(user=self.user, location_city="Athens")
        self.assertEqual(SearchHistory.objects.count(), 1)

    def test_auth_search_and_interaction_logs_share_the_same_structure(self) -> None:
        auth_log = log_auth_activity(action="logout", user=self.user)
        search_result = log_search_activity(user=self.user, location_city="Athens")
        interaction_log = log_interaction_activity(
            action="viewing_requested",
            user=self.user,
            entity=self.property,
        )

        logs = [auth_log, search_result.activity_log, interaction_log]
        for activity_log in logs:
            with self.subTest(activity_log=activity_log):
                self.assertIsNotNone(activity_log)
                activity_log.refresh_from_db()
                self.assertIn(activity_log.scope, ActivityScope.values)
                self.assertTrue(activity_log.action)
                self.assertEqual(activity_log.user, self.user)
                self.assertTrue(activity_log.entity_type)
                self.assertIsNotNone(activity_log.entity_id)
                self.assertIsInstance(activity_log.details, dict)

    def test_malformed_details_are_noop_safe_and_logged_diagnostically(self) -> None:
        with self.assertLogs(ACTIVITY_LOGGER, level="WARNING") as value_logs:
            activity_log = log_interaction_activity(
                action="favorite_added",
                user=self.user,
                entity=self.property,
                details={"bad_value": BrokenString()},
            )

        self.assertIsNotNone(activity_log)
        activity_log.refresh_from_db()
        self.assertEqual(activity_log.scope, ActivityScope.INTERACTION)
        self.assertEqual(activity_log.details, {"bad_value": "<unserializable BrokenString>"})
        self.assertIn("could not be normalized", "\n".join(value_logs.output))

        with self.assertLogs(ACTIVITY_LOGGER, level="WARNING") as mapping_logs:
            mapping_log = log_interaction_activity(
                action="favorite_removed",
                user=self.user,
                entity=self.property,
                details=BrokenMapping(),
            )

        self.assertIsNotNone(mapping_log)
        mapping_log.refresh_from_db()
        self.assertEqual(mapping_log.details, {})
        self.assertIn("details could not be normalized", "\n".join(mapping_logs.output))

        self.assertEqual(User.objects.create_user(email="still-working@example.com").email, "still-working@example.com")

    def test_malformed_search_criteria_are_noop_safe_and_logged_diagnostically(self) -> None:
        with self.assertLogs(ACTIVITY_LOGGER, level="WARNING") as logs:
            result = log_search_activity(user=self.user, criteria=BrokenMapping())

        self.assertIsNotNone(result.search_history)
        self.assertIsNotNone(result.activity_log)
        self.assertEqual(SearchHistory.objects.count(), 1)
        self.assertEqual(ActivityLog.objects.count(), 1)
        self.assertEqual(result.activity_log.details, {"criteria": {}})

        self.assertEqual(User.objects.create_user(email="search-flow@example.com").email, "search-flow@example.com")
        self.assertIn("Search criteria could not be normalized", "\n".join(logs.output))

    def test_search_logging_rolls_back_search_history_when_activity_log_creation_fails(self) -> None:
        with self.assertLogs(ACTIVITY_LOGGER, level="ERROR"):
            with patch(
                "homefinder.apps.interactions.activity_logging.ActivityLog.objects.create",
                side_effect=RuntimeError("activity write failed"),
            ):
                result = log_search_activity(user=self.user, location_city="Athens")

        self.assertIsNone(result.search_history)
        self.assertIsNone(result.activity_log)
        self.assertEqual(SearchHistory.objects.count(), 0)
        self.assertEqual(ActivityLog.objects.count(), 0)

    def test_search_logging_rolls_back_activity_log_when_search_history_creation_fails(self) -> None:
        with self.assertLogs(ACTIVITY_LOGGER, level="ERROR"):
            with patch(
                "homefinder.apps.interactions.activity_logging.SearchHistory.objects.create",
                side_effect=RuntimeError("history write failed"),
            ):
                result = log_search_activity(user=self.user, location_city="Athens")

        self.assertIsNone(result.search_history)
        self.assertIsNone(result.activity_log)
        self.assertEqual(SearchHistory.objects.count(), 0)
        self.assertEqual(ActivityLog.objects.count(), 0)

    def test_invalid_scope_is_dropped_with_warning_and_not_recategorized(self) -> None:
        with self.assertLogs(ACTIVITY_LOGGER, level="WARNING") as logs:
            activity_log = log_activity(
                scope="NOT_A_SCOPE",
                action="bad_scope_event",
                user=self.user,
                details={"surface": "test"},
            )

        self.assertIsNone(activity_log)
        self.assertEqual(ActivityLog.objects.count(), 0)
        self.assertIn("scope is invalid", "\n".join(logs.output))
        self.assertFalse(ActivityLog.objects.filter(scope=ActivityScope.INTERACTION).exists())

    def test_details_default_and_structured_json_are_persisted(self) -> None:
        direct_log = ActivityLog.objects.create(scope=ActivityScope.SYSTEM, action="system_check")
        self.assertEqual(direct_log.details, {})

        activity_log = log_interaction_activity(
            action="listing_compared",
            user=self.user,
            entity=self.property,
            details={
                "surface": "comparison",
                "filters": {"bedrooms_min": 2, "max_price": Decimal("300000.00")},
                "listing_ids": [self.property.pk],
            },
        )

        activity_log.refresh_from_db()
        self.assertEqual(activity_log.details["surface"], "comparison")
        self.assertEqual(activity_log.details["filters"]["bedrooms_min"], 2)
        self.assertEqual(activity_log.details["filters"]["max_price"], "300000.00")
        self.assertEqual(activity_log.details["listing_ids"], [self.property.pk])

    def test_sensitive_auth_details_are_redacted(self) -> None:
        activity_log = log_auth_activity(
            action="login_2fa_verified",
            user=self.user,
            details={
                "method": "password",
                "token": "123456",
                "password": "secret-pass",
                "nested": {"otp": "654321"},
            },
        )

        activity_log.refresh_from_db()
        self.assertEqual(activity_log.details["method"], "password")
        self.assertEqual(activity_log.details["token"], REDACTED_DETAIL_VALUE)
        self.assertEqual(activity_log.details["password"], REDACTED_DETAIL_VALUE)
        self.assertEqual(activity_log.details["nested"]["otp"], REDACTED_DETAIL_VALUE)
        self.assertNotIn("123456", str(activity_log.details))
        self.assertNotIn("654321", str(activity_log.details))

    def test_redaction_policy_covers_common_auth_key_variants_without_redacting_safe_codes(self) -> None:
        activity_log = log_auth_activity(
            action="login_attempt",
            user=self.user,
            details={
                "sessionToken": "session-secret",
                "Authorization": "Bearer secret",
                "verificationCode": "112233",
                "api-key": "api-secret",
                "postal_code": "11526",
                "listing_code": "ATH-001",
            },
        )

        activity_log.refresh_from_db()
        self.assertEqual(activity_log.details["sessionToken"], REDACTED_DETAIL_VALUE)
        self.assertEqual(activity_log.details["Authorization"], REDACTED_DETAIL_VALUE)
        self.assertEqual(activity_log.details["verificationCode"], REDACTED_DETAIL_VALUE)
        self.assertEqual(activity_log.details["api-key"], REDACTED_DETAIL_VALUE)
        self.assertEqual(activity_log.details["postal_code"], "11526")
        self.assertEqual(activity_log.details["listing_code"], "ATH-001")
        self.assertNotIn("session-secret", str(activity_log.details))
        self.assertNotIn("112233", str(activity_log.details))

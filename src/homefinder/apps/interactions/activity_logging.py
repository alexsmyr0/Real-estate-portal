"""No-op-safe activity and search logging pipeline."""
from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import models, transaction

from .models import ActivityLog, ActivityScope, SearchHistory
from .redaction import REDACTED_DETAIL_VALUE, should_redact_activity_detail_key

logger = logging.getLogger(__name__)

SEARCH_CRITERIA_FIELDS = ("location_city", "min_price", "max_price", "category", "bedrooms_min")


@dataclass(frozen=True, slots=True)
class ActivityLoggingResult:
    search_history: SearchHistory | None = None
    activity_log: ActivityLog | None = None


class ActivityLoggingService:
    """No-op-safe persistence boundary for activity and search logging."""

    def log_event(
        self,
        *,
        scope: ActivityScope | str | None,
        action: str | None,
        user: models.Model | None = None,
        entity: models.Model | None = None,
        entity_type: str | None = None,
        entity_id: int | str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> ActivityLog | None:
        try:
            normalized_scope = self._normalize_scope(scope)
            normalized_action = self._normalize_action(action)
            if normalized_scope is None:
                self._log_invalid_scope(scope, normalized_action)
                return None

            normalized_user = self._normalize_user(user)
            resolved_entity_type, resolved_entity_id = self._resolve_entity_reference(
                entity=entity,
                entity_type=entity_type,
                entity_id=entity_id,
            )
            normalized_details = self._normalize_details(details)

            with transaction.atomic():
                return self._create_activity_log(
                    user=normalized_user,
                    scope=normalized_scope,
                    action=normalized_action,
                    entity_type=resolved_entity_type,
                    entity_id=resolved_entity_id,
                    details=normalized_details,
                )
        except Exception:
            logger.exception("Activity logging failed.")
            return None

    def log_auth_event(
        self,
        *,
        action: str | None,
        user: models.Model | None = None,
        entity: models.Model | None = None,
        entity_type: str | None = None,
        entity_id: int | str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> ActivityLog | None:
        return self.log_event(
            scope=ActivityScope.AUTH,
            action=action,
            user=user,
            entity=entity or user,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )

    def log_search_event(
        self,
        *,
        user: models.Model | None = None,
        action: str | None = "search_submitted",
        criteria: Mapping[str, Any] | None = None,
        details: Mapping[str, Any] | None = None,
        **criteria_overrides: Any,
    ) -> ActivityLoggingResult:
        try:
            normalized_user = self._normalize_user(user)
            normalized_action = self._normalize_action(action)
            history_fields, criteria_details = self._normalize_search_criteria(criteria, criteria_overrides)
            event_details = {"criteria": criteria_details}
            event_details.update(self._normalize_details(details))

            with transaction.atomic():
                search_history = SearchHistory.objects.create(user=normalized_user, **history_fields)
                activity_log = self._create_activity_log(
                    user=normalized_user,
                    scope=ActivityScope.SEARCH,
                    action=normalized_action,
                    entity_type="search_history",
                    entity_id=search_history.pk,
                    details=event_details,
                )
        except Exception:
            logger.exception("Search activity logging failed.")
            return ActivityLoggingResult()

        return ActivityLoggingResult(search_history=search_history, activity_log=activity_log)

    def log_interaction_event(
        self,
        *,
        action: str | None,
        user: models.Model | None = None,
        entity: models.Model | None = None,
        entity_type: str | None = None,
        entity_id: int | str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> ActivityLog | None:
        return self.log_event(
            scope=ActivityScope.INTERACTION,
            action=action,
            user=user,
            entity=entity,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )

    def _create_activity_log(
        self,
        *,
        user: models.Model | None,
        scope: ActivityScope | str,
        action: str,
        entity_type: str,
        entity_id: int | None,
        details: dict[str, Any],
    ) -> ActivityLog:
        return ActivityLog.objects.create(
            user=user,
            scope=scope,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )

    def _normalize_search_criteria(
        self,
        criteria: Mapping[str, Any] | None,
        criteria_overrides: Mapping[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        raw_criteria = self._collect_search_criteria(criteria, criteria_overrides)
        history_fields = {
            "location_city": self._normalize_text(
                raw_criteria.get("location_city"),
                max_length=100,
                context="search_criteria.location_city",
            ),
            "min_price": self._normalize_decimal(raw_criteria.get("min_price"), context="search_criteria.min_price"),
            "max_price": self._normalize_decimal(raw_criteria.get("max_price"), context="search_criteria.max_price"),
            "category": self._normalize_category(raw_criteria.get("category")),
            "bedrooms_min": self._normalize_positive_int(
                raw_criteria.get("bedrooms_min"),
                context="search_criteria.bedrooms_min",
            ),
        }
        criteria_details = {
            key: self._to_json_value(value, context=f"search_criteria.{key}")
            for key, value in history_fields.items()
            if not self._is_blank(value)
        }

        extra_criteria = {
            key: value
            for key, value in raw_criteria.items()
            if key not in SEARCH_CRITERIA_FIELDS and not self._is_blank(value)
        }
        if extra_criteria:
            criteria_details["extra"] = self._to_json_value(extra_criteria, context="search_criteria.extra")

        return history_fields, criteria_details

    def _collect_search_criteria(
        self,
        criteria: Mapping[str, Any] | None,
        criteria_overrides: Mapping[str, Any],
    ) -> dict[str, Any]:
        raw_criteria: dict[str, Any] = {}
        if criteria is not None:
            try:
                raw_criteria.update(dict(criteria))
            except Exception:
                logger.warning(
                    "Search criteria could not be normalized.",
                    extra={"criteria_type": type(criteria).__name__},
                )

        raw_criteria.update({key: value for key, value in criteria_overrides.items() if key in SEARCH_CRITERIA_FIELDS})
        return raw_criteria

    def _normalize_scope(self, scope: ActivityScope | str | None) -> str | None:
        value = getattr(scope, "value", scope)
        candidate = self._normalize_text(value, max_length=16, context="scope").upper()
        if candidate in ActivityScope.values:
            return candidate
        return None

    def _log_invalid_scope(self, scope: ActivityScope | str | None, action: str) -> None:
        logger.warning(
            "Activity logging skipped because scope is invalid.",
            extra={
                "invalid_scope": self._safe_text(scope, max_length=80, default="<unavailable>"),
                "activity_action": action,
            },
        )

    def _normalize_action(self, action: str | None) -> str:
        return self._normalize_text(action, max_length=80, context="action") or "unspecified"

    def _normalize_user(self, user: models.Model | None) -> models.Model | None:
        if user is None or not isinstance(user, models.Model):
            return None
        try:
            if not getattr(user, "is_authenticated", True) or getattr(user, "pk", None) is None:
                return None
        except Exception:
            logger.warning("Activity logging user reference could not be normalized.")
            return None
        return user

    def _resolve_entity_reference(
        self,
        *,
        entity: models.Model | None,
        entity_type: str | None,
        entity_id: int | str | None,
    ) -> tuple[str, int | None]:
        resolved_entity_type = self._normalize_text(entity_type, max_length=80, context="entity_type")
        resolved_entity_id = self._normalize_entity_id(entity_id, context="entity_id")

        if entity is not None:
            if not resolved_entity_type:
                resolved_entity_type = self._entity_type_for(entity)
            if resolved_entity_id is None:
                resolved_entity_id = self._normalize_entity_id(getattr(entity, "pk", None), context="entity.pk")

        return resolved_entity_type, resolved_entity_id

    def _entity_type_for(self, entity: models.Model) -> str:
        if isinstance(entity, models.Model):
            return self._normalize_text(entity._meta.model_name, max_length=80, context="entity_type")
        return self._normalize_text(entity.__class__.__name__.lower(), max_length=80, context="entity_type")

    def _normalize_entity_id(self, entity_id: int | str | None, *, context: str) -> int | None:
        if self._is_blank(entity_id):
            return None
        try:
            return int(entity_id)
        except Exception:
            logger.warning(
                "Activity logging entity reference could not be normalized.",
                extra={"value_context": context, "value_type": type(entity_id).__name__},
            )
            return None

    def _normalize_text(self, value: Any, *, max_length: int, context: str) -> str:
        return self._safe_text(value, max_length=max_length, default="", context=context)

    def _normalize_decimal(self, value: Any, *, context: str) -> Decimal | None:
        if self._is_blank(value):
            return None
        try:
            normalized_value = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None
        except Exception:
            logger.warning(
                "Activity logging decimal value could not be normalized.",
                extra={"value_context": context, "value_type": type(value).__name__},
            )
            return None
        if not normalized_value.is_finite():
            return None
        return normalized_value

    def _normalize_positive_int(self, value: Any, *, context: str) -> int | None:
        if self._is_blank(value):
            return None
        try:
            normalized_value = int(value)
        except Exception:
            logger.warning(
                "Activity logging integer value could not be normalized.",
                extra={"value_context": context, "value_type": type(value).__name__},
            )
            return None
        if normalized_value < 0:
            return None
        return normalized_value

    def _normalize_category(self, value: Any) -> str:
        category = self._normalize_text(value, max_length=16, context="search_criteria.category").upper()
        valid_categories = {choice[0] for choice in SearchHistory._meta.get_field("category").choices}
        if category in valid_categories:
            return category
        return ""

    def _normalize_details(self, details: Mapping[str, Any] | None) -> dict[str, Any]:
        if details is None:
            return {}
        normalized_details = self._to_json_value(details, context="details")
        if isinstance(normalized_details, dict):
            return normalized_details
        return {"value": normalized_details}

    def _to_json_value(self, value: Any, *, context: str) -> Any:
        if self._is_sensitive_key(context):
            return REDACTED_DETAIL_VALUE
        if value is None or isinstance(value, str | int | float | bool):
            return value
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, datetime | date | time):
            return value.isoformat()
        if isinstance(value, models.Model):
            return {
                "model": value._meta.label_lower,
                "id": self._normalize_entity_id(getattr(value, "pk", None), context=f"{context}.id"),
            }
        if isinstance(value, Mapping):
            return self._mapping_to_json(value, context=context)
        if isinstance(value, list | tuple | set | frozenset):
            return [self._to_json_value(item, context=context) for item in value]
        return self._safe_text(
            value,
            max_length=500,
            default=f"<unserializable {type(value).__name__}>",
            context=context,
        )

    def _mapping_to_json(self, value: Mapping[Any, Any], *, context: str) -> dict[str, Any]:
        try:
            items = list(value.items())
        except Exception:
            logger.warning(
                "Activity logging details could not be normalized.",
                extra={"value_context": context, "value_type": type(value).__name__},
            )
            return {}

        normalized: dict[str, Any] = {}
        for raw_key, raw_value in items:
            key = self._safe_text(
                raw_key,
                max_length=80,
                default="unavailable_key",
                context=f"{context}.key",
            )
            if not key:
                key = "unavailable_key"
            if self._is_sensitive_key(key):
                normalized[key] = REDACTED_DETAIL_VALUE
                continue
            normalized[key] = self._to_json_value(raw_value, context=key)
        return normalized

    def _safe_text(
        self,
        value: Any,
        *,
        max_length: int,
        default: str,
        context: str = "value",
    ) -> str:
        if value is None:
            return default
        try:
            return str(value).strip()[:max_length]
        except Exception:
            logger.warning(
                "Activity logging value could not be normalized.",
                extra={"value_context": context, "value_type": type(value).__name__},
            )
            return default

    def _is_sensitive_key(self, key: str) -> bool:
        return should_redact_activity_detail_key(key)

    def _is_blank(self, value: Any) -> bool:
        return value is None or (isinstance(value, str) and value == "")


activity_logging_service = ActivityLoggingService()


def log_activity(
    *,
    scope: ActivityScope | str | None,
    action: str | None,
    user: models.Model | None = None,
    entity: models.Model | None = None,
    entity_type: str | None = None,
    entity_id: int | str | None = None,
    details: Mapping[str, Any] | None = None,
) -> ActivityLog | None:
    return activity_logging_service.log_event(
        scope=scope,
        action=action,
        user=user,
        entity=entity,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )


def log_auth_activity(
    *,
    action: str | None,
    user: models.Model | None = None,
    entity: models.Model | None = None,
    entity_type: str | None = None,
    entity_id: int | str | None = None,
    details: Mapping[str, Any] | None = None,
) -> ActivityLog | None:
    return activity_logging_service.log_auth_event(
        action=action,
        user=user,
        entity=entity,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )


def log_search_activity(
    *,
    user: models.Model | None = None,
    action: str | None = "search_submitted",
    criteria: Mapping[str, Any] | None = None,
    details: Mapping[str, Any] | None = None,
    **criteria_overrides: Any,
) -> ActivityLoggingResult:
    return activity_logging_service.log_search_event(
        user=user,
        action=action,
        criteria=criteria,
        details=details,
        **criteria_overrides,
    )


def log_interaction_activity(
    *,
    action: str | None,
    user: models.Model | None = None,
    entity: models.Model | None = None,
    entity_type: str | None = None,
    entity_id: int | str | None = None,
    details: Mapping[str, Any] | None = None,
) -> ActivityLog | None:
    return activity_logging_service.log_interaction_event(
        action=action,
        user=user,
        entity=entity,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )

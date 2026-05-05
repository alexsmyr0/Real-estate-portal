"""Retention cleanup for log-style interaction records."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db import models, transaction
from django.utils import timezone

from .models import ActivityLog, EmailNotification, SearchHistory

logger = logging.getLogger(__name__)

LOG_RETENTION_DAYS = 90


@dataclass(frozen=True, slots=True)
class LogRetentionTarget:
    model: type[models.Model]
    label: str


@dataclass(frozen=True, slots=True)
class LogRetentionCleanupResult:
    cutoff: datetime
    dry_run: bool
    counts: dict[str, int]

    @property
    def total_count(self) -> int:
        return sum(self.counts.values())


LOG_RETENTION_TARGETS = (
    LogRetentionTarget(ActivityLog, "ActivityLog"),
    LogRetentionTarget(SearchHistory, "SearchHistory"),
    LogRetentionTarget(EmailNotification, "EmailNotification"),
)


def get_log_retention_cutoff(reference_time: datetime | None = None) -> datetime:
    """Return the strict 90-day cutoff for log-style retention cleanup."""

    return (reference_time or timezone.now()) - timedelta(days=LOG_RETENTION_DAYS)


def cleanup_log_retention(
    *,
    dry_run: bool = False,
    reference_time: datetime | None = None,
) -> LogRetentionCleanupResult:
    """Delete log-style records older than the 90-day retention cutoff."""

    cutoff = get_log_retention_cutoff(reference_time)
    counts: dict[str, int] = {}

    with transaction.atomic():
        for target in LOG_RETENTION_TARGETS:
            queryset = target.model.objects.filter(created_at__lt=cutoff)
            eligible_count = queryset.count()

            if dry_run:
                counts[target.label] = eligible_count
                continue

            queryset.delete()
            counts[target.label] = eligible_count

    logger.info(
        "Log retention cleanup completed.",
        extra={
            "dry_run": dry_run,
            "cutoff": cutoff.isoformat(),
            "counts": counts,
            "total_count": sum(counts.values()),
        },
    )
    return LogRetentionCleanupResult(cutoff=cutoff, dry_run=dry_run, counts=counts)

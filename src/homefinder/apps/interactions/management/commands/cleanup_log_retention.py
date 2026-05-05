from __future__ import annotations

from django.core.management.base import BaseCommand

from homefinder.apps.interactions.retention import LOG_RETENTION_TARGETS, cleanup_log_retention


class Command(BaseCommand):
    help = "Delete log-style records older than the 90-day retention cutoff."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report eligible records without deleting them.",
        )

    def handle(self, *args: object, **options: object) -> None:
        dry_run = bool(options["dry_run"])
        result = cleanup_log_retention(dry_run=dry_run)
        count_label = "eligible" if dry_run else "deleted"

        self.stdout.write("Log retention cleanup complete.")
        self.stdout.write(f"cutoff={result.cutoff.isoformat()}")
        self.stdout.write(f"dry_run={dry_run}")

        for target in LOG_RETENTION_TARGETS:
            self.stdout.write(f"{target.label} {count_label}={result.counts[target.label]}")

        self.stdout.write(self.style.SUCCESS(f"total_{count_label}={result.total_count}"))

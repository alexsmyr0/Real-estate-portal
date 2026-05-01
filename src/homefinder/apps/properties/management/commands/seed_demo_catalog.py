from __future__ import annotations

from django.core.management.base import BaseCommand

from homefinder.apps.properties.demo_catalog import seed_demo_catalog_dataset


class Command(BaseCommand):
    help = "Load or refresh the repeatable demo property catalog dataset."

    def handle(self, *args: object, **options: object) -> None:
        summary = seed_demo_catalog_dataset()
        self.stdout.write(
            self.style.SUCCESS(
                "Seeded demo catalog dataset. "
                f"properties={summary.properties}, "
                f"amenities={summary.amenities}, "
                f"images={summary.images}"
            )
        )

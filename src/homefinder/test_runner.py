from __future__ import annotations

from django.test.runner import DiscoverRunner


class HomeFinderTestRunner(DiscoverRunner):
    default_test_labels = ("tests", "homefinder.apps.interactions")

    def run_tests(self, test_labels: list[str], **kwargs: object) -> int:
        return super().run_tests(test_labels or list(self.default_test_labels), **kwargs)

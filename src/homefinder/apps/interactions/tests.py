"""Expose interaction tests to Django's default app test discovery."""

from tests.interactions.test_email_notifications import *  # noqa: F401,F403
from tests.interactions.test_schema_baseline import *  # noqa: F401,F403

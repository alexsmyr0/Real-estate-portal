"""
conftest.py — Root pytest configuration for the homefinder test suite.

Forces Django to use an in-memory SQLite database so that no external
MySQL server is required to run the tests.  The override happens before
Django is imported, so pytest-django picks up the SQLite config.
"""
from __future__ import annotations

import os

# Must be set before any Django import.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homefinder.settings")

# Force SQLite in-memory so tests never need a running MySQL instance.
os.environ["DB_SCHEME"] = "sqlite"
os.environ["DB_NAME"] = ":memory:"

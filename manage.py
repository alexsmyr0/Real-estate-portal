#!/usr/bin/env python
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    project_root = Path(__file__).resolve().parent
    src_root = project_root / "src"

    if src_root.is_dir():
        src_path = str(src_root)
        if src_path not in sys.path:
            sys.path.insert(0, src_path)

    default_settings = (
        "homefinder.test_settings"
        if len(sys.argv) > 1 and sys.argv[1] == "test"
        else "homefinder.settings"
    )
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", default_settings)

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

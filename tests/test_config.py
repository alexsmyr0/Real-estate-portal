import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from homefinder.app import create_app
from homefinder.config import load_settings


class ConfigLoadingTests(unittest.TestCase):
    def test_load_settings_uses_defaults_without_env_file(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = load_settings(env_path=Path("/tmp/missing-homefinder.env"))

        self.assertEqual(settings.app_host, "0.0.0.0")
        self.assertEqual(settings.app_port, 8080)
        self.assertTrue(settings.debug)
        self.assertEqual(settings.db_host, "127.0.0.1")
        self.assertEqual(settings.db_port, 3306)
        self.assertEqual(settings.database_url, "mysql://homefinder_app:admin@127.0.0.1:3306/homefinder")

    def test_load_settings_reads_env_values_and_mysql_fallbacks(self) -> None:
        env_contents = "\n".join(
            [
                "APP_PORT=9090",
                "APP_DEBUG=false",
                "DB_HOST=db.local",
                "MYSQL_PORT=3307",
                "MYSQL_DATABASE=homefinder_test",
                "MYSQL_USER=test_user",
                "MYSQL_PASSWORD=secret",
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(env_contents, encoding="utf-8")

            with patch.dict(os.environ, {}, clear=True):
                settings = load_settings(env_path=env_path)

        self.assertEqual(settings.app_port, 9090)
        self.assertFalse(settings.debug)
        self.assertEqual(settings.db_host, "db.local")
        self.assertEqual(settings.db_port, 3307)
        self.assertEqual(settings.db_name, "homefinder_test")
        self.assertEqual(settings.db_user, "test_user")
        self.assertEqual(settings.db_password, "secret")
        self.assertEqual(
            settings.database_url,
            "mysql://test_user:secret@db.local:3307/homefinder_test",
        )

    def test_create_app_exposes_loaded_config(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_PORT": "5050",
                "APP_DEBUG": "false",
                "DB_HOST": "127.0.0.1",
                "MYSQL_DATABASE": "homefinder_dev",
            },
            clear=True,
        ):
            app = create_app()

        self.assertEqual(app.config["APP_PORT"], 5050)
        self.assertFalse(app.config["APP_DEBUG"])
        self.assertEqual(app.config["DB_NAME"], "homefinder_dev")
        self.assertEqual(
            app.config["DATABASE_URL"],
            "mysql://homefinder_app:admin@127.0.0.1:3306/homefinder_dev",
        )


if __name__ == "__main__":
    unittest.main()

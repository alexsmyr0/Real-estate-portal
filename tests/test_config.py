import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from homefinder.config import load_settings


class ConfigLoadingTests(unittest.TestCase):
    def test_load_settings_uses_defaults_without_env_file(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = load_settings(env_path=Path("/tmp/missing-homefinder.env"))

        self.assertEqual(settings.secret_key, "insecure-homefinder-dev-key")
        self.assertEqual(settings.app_host, "0.0.0.0")
        self.assertEqual(settings.app_port, 8080)
        self.assertTrue(settings.debug)
        self.assertEqual(settings.allowed_hosts, ("localhost", "127.0.0.1"))
        self.assertEqual(settings.db_host, "127.0.0.1")
        self.assertEqual(settings.db_port, 3306)
        self.assertEqual(settings.database_url, "mysql://homefinder_app:admin@127.0.0.1:3306/homefinder")
        self.assertEqual(settings.database_engine, "django.db.backends.mysql")
        self.assertEqual(settings.database_config["NAME"], "homefinder")
        self.assertEqual(settings.email_backend, "django.core.mail.backends.console.EmailBackend")
        self.assertEqual(settings.default_from_email, "HomeFinder <no-reply@homefinder.local>")
        self.assertEqual(settings.email_host, "")
        self.assertEqual(settings.email_port, 587)
        self.assertEqual(settings.email_host_user, "")
        self.assertEqual(settings.email_host_password, "")
        self.assertFalse(settings.email_use_tls)
        self.assertFalse(settings.email_use_ssl)
        self.assertEqual(settings.email_timeout, 10)

    def test_load_settings_reads_env_values_and_mysql_fallbacks(self) -> None:
        env_contents = "\n".join(
            [
                "APP_PORT=9090",
                "APP_DEBUG=false",
                "APP_ALLOWED_HOSTS=example.com,api.example.com",
                "DJANGO_SECRET_KEY=test-secret",
                "DB_HOST=db.local",
                "MYSQL_PORT=3307",
                "MYSQL_DATABASE=homefinder_test",
                "MYSQL_USER=test_user",
                "MYSQL_PASSWORD=secret",
                "EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend",
                "DEFAULT_FROM_EMAIL=HomeFinder <hello@example.com>",
                "EMAIL_HOST=smtp.example.com",
                "EMAIL_PORT=2525",
                "EMAIL_HOST_USER=smtp-user",
                "EMAIL_HOST_PASSWORD=smtp-secret",
                "EMAIL_USE_TLS=true",
                "EMAIL_USE_SSL=false",
                "EMAIL_TIMEOUT=15",
            ]
        )

        temp_parent = Path.cwd() / ".tmp"
        temp_parent.mkdir(exist_ok=True)

        with tempfile.TemporaryDirectory(dir=temp_parent) as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(env_contents, encoding="utf-8")

            with patch.dict(os.environ, {}, clear=True):
                settings = load_settings(env_path=env_path)

        self.assertEqual(settings.app_port, 9090)
        self.assertFalse(settings.debug)
        self.assertEqual(settings.allowed_hosts, ("example.com", "api.example.com"))
        self.assertEqual(settings.secret_key, "test-secret")
        self.assertEqual(settings.db_host, "db.local")
        self.assertEqual(settings.db_port, 3307)
        self.assertEqual(settings.db_name, "homefinder_test")
        self.assertEqual(settings.db_user, "test_user")
        self.assertEqual(settings.db_password, "secret")
        self.assertEqual(
            settings.database_url,
            "mysql://test_user:secret@db.local:3307/homefinder_test",
        )
        self.assertEqual(settings.database_engine, "django.db.backends.mysql")
        self.assertEqual(settings.database_config["HOST"], "db.local")
        self.assertEqual(settings.email_backend, "django.core.mail.backends.smtp.EmailBackend")
        self.assertEqual(settings.default_from_email, "HomeFinder <hello@example.com>")
        self.assertEqual(settings.email_host, "smtp.example.com")
        self.assertEqual(settings.email_port, 2525)
        self.assertEqual(settings.email_host_user, "smtp-user")
        self.assertEqual(settings.email_host_password, "smtp-secret")
        self.assertTrue(settings.email_use_tls)
        self.assertFalse(settings.email_use_ssl)
        self.assertEqual(settings.email_timeout, 15)


if __name__ == "__main__":
    unittest.main()

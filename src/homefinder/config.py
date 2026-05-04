from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"

TRUE_VALUES = {"1", "true", "t", "yes", "y", "on"}
FALSE_VALUES = {"0", "false", "f", "no", "n", "off"}


def load_env_file(env_path: Path = DEFAULT_ENV_FILE) -> None:
    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()

        key, separator, value = line.partition("=")
        if not separator:
            continue

        key = key.strip()
        value = value.strip()

        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        os.environ.setdefault(key, value)


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _get_int(name: str, default: int) -> int:
    value = _get_env(name)
    if value is None:
        return default

    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}") from exc


def _get_bool(name: str, default: bool) -> bool:
    value = _get_env(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False

    raise ValueError(f"{name} must be a boolean, got {value!r}")


def _get_list(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = _get_env(name)
    if value is None:
        return default

    items = tuple(item.strip() for item in value.split(",") if item.strip())
    return items or default


def build_database_url(
    scheme: str,
    user: str,
    password: str,
    host: str,
    port: int,
    database_name: str,
) -> str:
    encoded_user = quote(user, safe="")
    encoded_password = quote(password, safe="")
    encoded_database_name = quote(database_name, safe="")

    return f"{scheme}://{encoded_user}:{encoded_password}@{host}:{port}/{encoded_database_name}"


@dataclass(frozen=True, slots=True)
class Settings:
    secret_key: str
    app_host: str
    app_port: int
    debug: bool
    allowed_hosts: tuple[str, ...]
    csrf_trusted_origins: tuple[str, ...]
    time_zone: str
    db_scheme: str
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    database_url: str
    email_backend: str
    default_from_email: str
    email_host: str
    email_port: int
    email_host_user: str
    email_host_password: str
    email_use_tls: bool
    email_use_ssl: bool
    email_timeout: int

    @property
    def database_engine(self) -> str:
        if self.db_scheme in {"sqlite", "sqlite3"}:
            return "django.db.backends.sqlite3"
        if self.db_scheme in {"postgres", "postgresql"}:
            return "django.db.backends.postgresql"
        return "django.db.backends.mysql"

    @property
    def database_config(self) -> dict[str, object]:
        if self.database_engine == "django.db.backends.sqlite3":
            database_name = self.db_name
            if not Path(database_name).is_absolute():
                database_name = str(PROJECT_ROOT / database_name)
            return {
                "ENGINE": self.database_engine,
                "NAME": database_name,
            }

        config: dict[str, object] = {
            "ENGINE": self.database_engine,
            "NAME": self.db_name,
            "USER": self.db_user,
            "PASSWORD": self.db_password,
            "HOST": self.db_host,
            "PORT": self.db_port,
        }

        if self.database_engine == "django.db.backends.mysql":
            config["OPTIONS"] = {"charset": "utf8mb4"}

        return config


def load_settings(env_path: Path | None = None) -> Settings:
    load_env_file(env_path or DEFAULT_ENV_FILE)

    db_scheme = _get_env("DB_SCHEME", "mysql") or "mysql"
    db_host = _get_env("DB_HOST", "127.0.0.1") or "127.0.0.1"
    db_port = _get_int("DB_PORT", _get_int("MYSQL_PORT", 3306))
    db_name = _get_env("DB_NAME", _get_env("MYSQL_DATABASE", "homefinder")) or "homefinder"
    db_user = _get_env("DB_USER", _get_env("MYSQL_USER", "homefinder_app")) or "homefinder_app"
    db_password = _get_env("DB_PASSWORD", _get_env("MYSQL_PASSWORD", "admin")) or "admin"
    database_url = _get_env(
        "DATABASE_URL",
        build_database_url(
            scheme=db_scheme,
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port,
            database_name=db_name,
        ),
    ) or ""

    return Settings(
        secret_key=_get_env("DJANGO_SECRET_KEY", "insecure-homefinder-dev-key") or "insecure-homefinder-dev-key",
        app_host=_get_env("APP_HOST", "0.0.0.0") or "0.0.0.0",
        app_port=_get_int("APP_PORT", 8080),
        debug=_get_bool("APP_DEBUG", True),
        allowed_hosts=_get_list("APP_ALLOWED_HOSTS", ("localhost", "127.0.0.1")),
        csrf_trusted_origins=_get_list("CSRF_TRUSTED_ORIGINS", ()),
        time_zone=_get_env("APP_TIME_ZONE", "UTC") or "UTC",
        db_scheme=db_scheme,
        db_host=db_host,
        db_port=db_port,
        db_name=db_name,
        db_user=db_user,
        db_password=db_password,
        database_url=database_url,
        email_backend=_get_env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
        or "django.core.mail.backends.console.EmailBackend",
        default_from_email=_get_env("DEFAULT_FROM_EMAIL", "HomeFinder <no-reply@homefinder.local>")
        or "HomeFinder <no-reply@homefinder.local>",
        email_host=_get_env("EMAIL_HOST", "") or "",
        email_port=_get_int("EMAIL_PORT", 587),
        email_host_user=_get_env("EMAIL_HOST_USER", "") or "",
        email_host_password=_get_env("EMAIL_HOST_PASSWORD", "") or "",
        email_use_tls=_get_bool("EMAIL_USE_TLS", False),
        email_use_ssl=_get_bool("EMAIL_USE_SSL", False),
        email_timeout=_get_int("EMAIL_TIMEOUT", 10),
    )

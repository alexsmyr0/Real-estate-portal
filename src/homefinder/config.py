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
    app_host: str
    app_port: int
    debug: bool
    db_scheme: str
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    database_url: str


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
        app_host=_get_env("APP_HOST", "0.0.0.0") or "0.0.0.0",
        app_port=_get_int("APP_PORT", 8080),
        debug=_get_bool("APP_DEBUG", True),
        db_scheme=db_scheme,
        db_host=db_host,
        db_port=db_port,
        db_name=db_name,
        db_user=db_user,
        db_password=db_password,
        database_url=database_url,
    )

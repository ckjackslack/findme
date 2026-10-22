"""Configuration: defaults, an optional TOML config file and environment variables.

Precedence (lowest to highest): built-in defaults, config file, environment,
command-line arguments. Exclude patterns are additive across all layers.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, replace
from typing import Any, Mapping

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised only on 3.10
    import tomli as tomllib

from findme.filters import normalize_extensions

DEFAULT_MAX_SIZE = 10 * 1024 * 1024  # 10 MiB


class ConfigError(Exception):
    """Invalid configuration value or unreadable config file."""


@dataclass(frozen=True)
class Settings:
    extensions: frozenset[str] = frozenset()
    excludes: tuple[str, ...] = ()
    default_excludes: bool = True
    ignore_case: bool = False
    max_size: int | None = DEFAULT_MAX_SIZE
    follow_symlinks: bool = False


_SIZE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([kmgt]?)(i?b)?\s*$", re.IGNORECASE)
_SIZE_MULT = {"": 1, "k": 1024, "m": 1024**2, "g": 1024**3, "t": 1024**4}


def parse_size(value: str | int) -> int | None:
    """Parse ``"512"``, ``"64K"``, ``"10M"``, ``"1.5GiB"`` into bytes.

    ``0``, ``"0"``, ``"none"`` and ``"unlimited"`` mean no limit (``None``).
    """
    if isinstance(value, bool):
        raise ConfigError(f"invalid size: {value!r}")
    if isinstance(value, int):
        if value < 0:
            raise ConfigError(f"size must not be negative: {value}")
        return value or None
    text = str(value).strip().lower()
    if text in ("none", "unlimited"):
        return None
    m = _SIZE_RE.match(text)
    if not m:
        raise ConfigError(f"invalid size: {value!r} (try e.g. 512K, 10M, 1G)")
    number = float(m.group(1)) * _SIZE_MULT[m.group(2).lower()]
    return int(number) or None


def _split(value: str, sep: str) -> list[str]:
    return [part.strip() for part in value.split(sep) if part.strip()]


def default_config_path(environ: Mapping[str, str]) -> str | None:
    """``$FINDME_CONFIG``, else ``$XDG_CONFIG_HOME/findme/config.toml``,
    else ``~/.config/findme/config.toml`` (``None`` if no home is known)."""
    if environ.get("FINDME_CONFIG"):
        return environ["FINDME_CONFIG"]
    base = environ.get("XDG_CONFIG_HOME")
    if not base:
        home = environ.get("HOME")
        if not home:
            return None
        base = os.path.join(home, ".config")
    return os.path.join(base, "findme", "config.toml")


def _str_list(data: Mapping[str, Any], key: str) -> list[str]:
    value = data[key]
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return value
    raise ConfigError(f"config key {key!r} must be a string or a list of strings")


def apply_mapping(settings: Settings, data: Mapping[str, Any]) -> Settings:
    """Apply a parsed config-file mapping on top of ``settings``."""
    known = {"extensions", "exclude", "default_excludes", "ignore_case", "max_size", "follow_symlinks"}
    unknown = set(data) - known
    if unknown:
        raise ConfigError(f"unknown config key(s): {', '.join(sorted(unknown))}")
    changes: dict[str, Any] = {}
    if "extensions" in data:
        changes["extensions"] = normalize_extensions(_str_list(data, "extensions"))
    if "exclude" in data:
        changes["excludes"] = settings.excludes + tuple(_str_list(data, "exclude"))
    for key in ("default_excludes", "ignore_case", "follow_symlinks"):
        if key in data:
            if not isinstance(data[key], bool):
                raise ConfigError(f"config key {key!r} must be true or false")
            changes[key] = data[key]
    if "max_size" in data:
        if not isinstance(data["max_size"], (int, str)) or isinstance(data["max_size"], bool):
            raise ConfigError("config key 'max_size' must be a number or a string like '10M'")
        changes["max_size"] = parse_size(data["max_size"])
    return replace(settings, **changes)


def load_config_file(path: str) -> dict[str, Any]:
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: invalid TOML: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"{path}: {exc.strerror or exc}") from exc


def apply_environment(settings: Settings, environ: Mapping[str, str]) -> Settings:
    """Apply ``FINDME_EXTENSIONS`` (comma separated), ``FINDME_EXCLUDE``
    (``os.pathsep`` separated) and ``FINDME_MAX_SIZE``."""
    changes: dict[str, Any] = {}
    if environ.get("FINDME_EXTENSIONS"):
        changes["extensions"] = normalize_extensions([environ["FINDME_EXTENSIONS"]])
    if environ.get("FINDME_EXCLUDE"):
        changes["excludes"] = settings.excludes + tuple(_split(environ["FINDME_EXCLUDE"], os.pathsep))
    if environ.get("FINDME_MAX_SIZE"):
        changes["max_size"] = parse_size(environ["FINDME_MAX_SIZE"])
    return replace(settings, **changes)


def load_settings(
    environ: Mapping[str, str],
    *,
    config_path: str | None = None,
    use_config: bool = True,
) -> Settings:
    """Build settings from defaults, the config file (if any) and environment.

    An explicitly given ``config_path`` must exist; the default location is
    optional.
    """
    settings = Settings()
    if use_config:
        explicit = config_path is not None
        path = config_path if explicit else default_config_path(environ)
        if path and (explicit or os.path.isfile(path)):
            settings = apply_mapping(settings, load_config_file(path))
    return apply_environment(settings, environ)

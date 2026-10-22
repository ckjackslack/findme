"""Pure helpers deciding which paths and file contents are worth searching."""

from __future__ import annotations

import hashlib
import os
from fnmatch import fnmatchcase
from pathlib import PurePosixPath
from typing import Iterable

#: Directories that are almost never what you are looking for: VCS metadata,
#: virtualenvs, installed packages and tool caches. Disable with
#: ``--no-default-excludes``.
DEFAULT_EXCLUDES: tuple[str, ...] = (
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    ".tox",
    ".nox",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "site-packages",
    "dist-packages",
)

#: How many leading bytes are inspected when deciding whether a file is binary.
BINARY_SNIFF_BYTES = 8192


def normalize_extensions(values: Iterable[str]) -> frozenset[str]:
    """Turn ``["py", ".TXT", "md,rst"]`` into ``{"py", "txt", "md", "rst"}``."""
    result: set[str] = set()
    for value in values:
        for part in value.split(","):
            part = part.strip().lstrip(".").lower()
            if part:
                result.add(part)
    return frozenset(result)


def has_extension(filename: str, extensions: frozenset[str]) -> bool:
    """True if ``filename`` ends with one of ``extensions`` (or none are given).

    Multi-part extensions such as ``tar.gz`` work too.
    """
    if not extensions:
        return True
    name = filename.lower()
    return any(name.endswith("." + ext) for ext in extensions)


def _posix(path: str) -> str:
    return path.replace("\\", "/")


def is_excluded(path: str, patterns: Iterable[str], root: str | None = None) -> bool:
    """Decide whether ``path`` is excluded by any of the glob ``patterns``.

    * A pattern without a ``/`` is matched against every single path component,
      so ``node_modules`` or ``*.egg-info`` exclude that directory anywhere.
      When ``root`` is given only the components *below* ``root`` are checked,
      so explicitly searching inside e.g. ``.venv`` still works.
    * A pattern containing ``/`` is matched against the whole path; it also
      excludes everything below a matching directory (``/usr/lib`` excludes
      ``/usr/lib/x/y.py``).
    """
    posix = _posix(path)
    rel = posix if root is None else _posix(os.path.relpath(path, root))
    parts = [p for p in PurePosixPath(rel).parts if p not in (".", "..", "/")]
    for pattern in patterns:
        pattern = _posix(pattern)
        if not pattern:
            continue
        if "/" in pattern.rstrip("/"):
            pat = pattern.rstrip("/")
            if fnmatchcase(posix, pat) or fnmatchcase(posix, pat + "/*"):
                return True
        else:
            pat = pattern.strip("/")
            if any(fnmatchcase(part, pat) for part in parts):
                return True
    return False


def is_binary(data: bytes) -> bool:
    """Heuristic used by grep & co.: a NUL byte near the start means binary."""
    return b"\x00" in data[:BINARY_SNIFF_BYTES]


def decode_text(data: bytes) -> str:
    """Decode as UTF-8 (with BOM support); undecodable bytes become U+FFFD."""
    return data.decode("utf-8-sig", errors="replace")


def content_digest(data: bytes, algorithm: str = "sha256") -> str:
    """Hex digest of ``data`` used to detect identical copies of a file."""
    return hashlib.new(algorithm, data).hexdigest()

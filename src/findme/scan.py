"""Filesystem side of findme: walking directory trees and reading files."""

from __future__ import annotations

import os
import stat
from typing import Callable, Iterable, Iterator

from findme.filters import has_extension, is_excluded

ErrorHandler = Callable[[str, str], None]


class SkipFile(Exception):
    """Raised by readers for files that are deliberately not searched."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _ignore(path: str, message: str) -> None:  # pragma: no cover - trivial
    pass


def iter_files(
    roots: Iterable[str],
    *,
    excludes: Iterable[str] = (),
    extensions: frozenset[str] = frozenset(),
    follow_symlinks: bool = False,
    on_error: ErrorHandler = _ignore,
) -> Iterator[str]:
    """Yield candidate file paths below ``roots`` in a stable, sorted order.

    Excluded directories are pruned (never descended into). Symlinks are
    skipped unless ``follow_symlinks`` is set. A root that is itself a file is
    yielded as-is, regardless of the extension filter.
    """
    excludes = tuple(excludes)
    for root in roots:
        if os.path.isfile(root):
            yield root
            continue
        if not os.path.isdir(root):
            on_error(root, "no such file or directory")
            continue

        def onerror(exc: OSError) -> None:
            on_error(exc.filename or root, exc.strerror or str(exc))

        for dirpath, dirnames, filenames in os.walk(
            root, onerror=onerror, followlinks=follow_symlinks
        ):
            kept = []
            for d in sorted(dirnames):
                full = os.path.join(dirpath, d)
                if is_excluded(full, excludes, root=root):
                    continue
                kept.append(d)
            dirnames[:] = kept

            for name in sorted(filenames):
                full = os.path.join(dirpath, name)
                if not has_extension(name, extensions):
                    continue
                if is_excluded(full, excludes, root=root):
                    continue
                if not follow_symlinks and os.path.islink(full):
                    continue
                yield full


def read_file(path: str, *, max_size: int | None = None) -> bytes:
    """Read a regular file fully, refusing special files and oversized ones.

    Raises :class:`SkipFile` for things that should be skipped silently and
    ``OSError`` for real errors (permissions, races, ...).
    """
    st = os.stat(path)
    if not stat.S_ISREG(st.st_mode):
        # FIFOs, sockets and devices can block forever or never end.
        raise SkipFile("not a regular file")
    if max_size is not None and st.st_size > max_size:
        raise SkipFile("too large")
    with open(path, "rb") as fh:
        return fh.read()

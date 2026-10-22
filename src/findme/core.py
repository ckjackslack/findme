"""Search orchestration: match file contents and group identical copies.

This module does no I/O of its own: it receives an iterable of paths and a
``read`` callable, which makes it trivial to test with in-memory fakes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

from findme.filters import content_digest, decode_text, is_binary
from findme.matcher import LineMatch, Matcher
from findme.scan import SkipFile

Reader = Callable[[str], bytes]


@dataclass
class Hit:
    """A unique matching file, plus any byte-identical copies found later."""

    path: str
    digest: str
    matches: list[LineMatch]
    text: str | None = None
    duplicates: list[str] = field(default_factory=list)


@dataclass
class SearchError:
    path: str
    message: str


@dataclass
class Report:
    hits: list[Hit] = field(default_factory=list)
    searched: int = 0
    skipped: int = 0
    errors: list[SearchError] = field(default_factory=list)

    @property
    def duplicate_count(self) -> int:
        return sum(len(hit.duplicates) for hit in self.hits)

    @property
    def matched_files(self) -> int:
        """Number of matching files including duplicates."""
        return len(self.hits) + self.duplicate_count


def search(
    paths: Iterable[str],
    matcher: Matcher,
    read: Reader,
    *,
    keep_text: bool = False,
    on_hit: Callable[[Hit], None] | None = None,
) -> Report:
    """Search every path and return a :class:`Report`.

    * Empty, binary and skipped files count as ``skipped``.
    * Read errors are collected in ``report.errors`` instead of aborting.
    * A matching file whose content is identical to an earlier hit is recorded
      in that hit's ``duplicates`` instead of producing a new hit.
    * ``on_hit`` is called for each new unique hit as soon as it is found.
    """
    report = Report()
    by_digest: dict[str, Hit] = {}

    for path in paths:
        try:
            data = read(path)
        except SkipFile:
            report.skipped += 1
            continue
        except OSError as exc:
            report.errors.append(SearchError(path, exc.strerror or str(exc)))
            continue

        if not data or is_binary(data):
            report.skipped += 1
            continue

        report.searched += 1
        text = decode_text(data)
        matches = matcher.find(text)
        if not matches:
            continue

        digest = content_digest(data)
        existing = by_digest.get(digest)
        if existing is not None:
            existing.duplicates.append(path)
            continue

        hit = Hit(path, digest, matches, text if keep_text else None)
        by_digest[digest] = hit
        report.hits.append(hit)
        if on_hit is not None:
            on_hit(hit)

    return report

"""Pure text matching: find the lines of a text that contain a phrase."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class LineMatch:
    """A single matching line (1-based line number, line without newline)."""

    lineno: int
    line: str


class Matcher:
    """Matches a phrase (literal by default, or a regular expression) line by line."""

    def __init__(self, phrase: str, *, regex: bool = False, ignore_case: bool = False):
        if not phrase:
            raise ValueError("search phrase must not be empty")
        flags = re.IGNORECASE if ignore_case else 0
        source = phrase if regex else re.escape(phrase)
        try:
            self._re = re.compile(source, flags)
        except re.error as exc:
            raise ValueError(f"invalid regular expression {phrase!r}: {exc}") from exc
        self.phrase = phrase
        self.regex = regex
        self.ignore_case = ignore_case

    def matches_line(self, line: str) -> bool:
        return self._re.search(line) is not None

    def find(self, text: str) -> list[LineMatch]:
        """Return every line of ``text`` that matches, in order."""
        return [
            LineMatch(lineno, line)
            for lineno, line in enumerate(text.splitlines(), start=1)
            if self._re.search(line)
        ]

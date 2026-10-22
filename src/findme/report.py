"""Pure formatting of search results (text and JSON)."""

from __future__ import annotations

import json

from findme.core import Hit, Report

MODES = ("lines", "full", "paths")
RULE = "=" * 80


def format_hit(hit: Hit, mode: str = "lines") -> str:
    """Render one unique hit.

    * ``lines``: the path followed by the matching lines with line numbers.
    * ``full``: the original prototype's output, the whole file between rules.
    * ``paths``: just the path.
    """
    if mode == "paths":
        return hit.path
    if mode == "full":
        body = (hit.text or "").strip("\n")
        return f"{RULE}\n{hit.path}\n{RULE}\n{body}\n{RULE}\n"
    if mode == "lines":
        width = len(str(hit.matches[-1].lineno)) if hit.matches else 1
        lines = [hit.path]
        lines += [f"  {m.lineno:>{width}}: {m.line}" for m in hit.matches]
        return "\n".join(lines) + "\n"
    raise ValueError(f"unknown output mode {mode!r}")


def format_duplicates(report: Report) -> str:
    """List identical copies of each hit, or return ``""`` if there are none."""
    groups = [hit for hit in report.hits if hit.duplicates]
    if not groups:
        return ""
    out = ["Identical copies (shown once above):"]
    for hit in groups:
        out.append(f"  {hit.path}")
        out += [f"    = {dup}" for dup in hit.duplicates]
    return "\n".join(out) + "\n"


def format_summary(report: Report, phrase: str) -> str:
    def plural(n: int, word: str, many: str | None = None) -> str:
        return f"{n} {word if n == 1 else (many or word + 's')}"

    text = (
        f"Searched {plural(report.searched, 'file')}: {phrase!r} found in "
        f"{plural(len(report.hits), 'unique file')}"
    )
    if report.duplicate_count:
        text += f" (+{plural(report.duplicate_count, 'identical copy', 'identical copies')})"
    extras = []
    if report.skipped:
        extras.append(f"{report.skipped} skipped")
    if report.errors:
        extras.append(f"{plural(len(report.errors), 'error')}")
    if extras:
        text += f"; {', '.join(extras)}"
    return text + "."


def report_to_dict(report: Report, phrase: str) -> dict:
    return {
        "phrase": phrase,
        "searched": report.searched,
        "skipped": report.skipped,
        "hits": [
            {
                "path": hit.path,
                "sha256": hit.digest,
                "matches": [{"line": m.lineno, "text": m.line} for m in hit.matches],
                "duplicates": list(hit.duplicates),
            }
            for hit in report.hits
        ],
        "errors": [{"path": e.path, "message": e.message} for e in report.errors],
    }


def format_json(report: Report, phrase: str) -> str:
    return json.dumps(report_to_dict(report, phrase), indent=2, ensure_ascii=False)

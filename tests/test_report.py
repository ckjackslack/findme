import json

import pytest

from findme.core import Hit, Report, SearchError
from findme.matcher import LineMatch
from findme.report import format_duplicates, format_hit, format_json, format_summary


@pytest.fixture
def hit():
    return Hit("a.py", "d1", [LineMatch(3, "x = 1"), LineMatch(12, "y = x")], text="l1\nx = 1\n\n")


def test_format_lines(hit):
    assert format_hit(hit, "lines") == "a.py\n   3: x = 1\n  12: y = x\n"


def test_format_paths(hit):
    assert format_hit(hit, "paths") == "a.py"


def test_format_full(hit):
    out = format_hit(hit, "full")
    assert out.splitlines()[1] == "a.py"
    assert "l1\nx = 1\n=" in out


def test_unknown_mode(hit):
    with pytest.raises(ValueError):
        format_hit(hit, "fancy")


def test_format_duplicates(hit):
    report = Report(hits=[hit, Hit("b.py", "d2", [])])
    assert format_duplicates(report) == ""
    hit.duplicates = ["copy/a.py"]
    assert format_duplicates(report) == "Identical copies (shown once above):\n  a.py\n    = copy/a.py\n"


def test_summary_pluralisation(hit):
    r = Report(hits=[hit], searched=1)
    assert format_summary(r, "x") == "Searched 1 file: 'x' found in 1 unique file."
    hit.duplicates = ["b", "c"]
    r.searched, r.skipped = 5, 2
    r.errors = [SearchError("p", "denied")]
    assert format_summary(r, "x") == (
        "Searched 5 files: 'x' found in 1 unique file (+2 identical copies); 2 skipped, 1 error."
    )


def test_json(hit):
    hit.duplicates = ["b.py"]
    data = json.loads(format_json(Report(hits=[hit], searched=2, errors=[SearchError("p", "m")]), "x"))
    assert data["phrase"] == "x"
    assert data["searched"] == 2
    assert data["hits"][0] == {
        "path": "a.py",
        "sha256": "d1",
        "matches": [{"line": 3, "text": "x = 1"}, {"line": 12, "text": "y = x"}],
        "duplicates": ["b.py"],
    }
    assert data["errors"] == [{"path": "p", "message": "m"}]

import pytest

from findme.core import search
from findme.matcher import Matcher
from findme.scan import SkipFile


def fake_reader(files):
    """Reader backed by a dict: bytes, or an exception instance to raise."""

    def read(path):
        value = files[path]
        if isinstance(value, Exception):
            raise value
        return value

    return read


def run(files, phrase="needle", **kw):
    return search(list(files), Matcher(phrase), fake_reader(files), **kw)


def test_finds_unique_hits_in_order():
    files = {"a": b"needle\n", "b": b"hay\n", "c": b"x\nneedle 2\n"}
    report = run(files)
    assert [h.path for h in report.hits] == ["a", "c"]
    assert report.hits[1].matches[0].lineno == 2
    assert report.searched == 3
    assert report.skipped == 0


def test_identical_copies_are_grouped():
    same = b"the needle\n"
    files = {"a": same, "b": b"other needle\n", "c": same, "d": same}
    report = run(files)
    assert [h.path for h in report.hits] == ["a", "b"]
    assert report.hits[0].duplicates == ["c", "d"]
    assert report.duplicate_count == 2
    assert report.matched_files == 4


def test_non_matching_duplicates_are_not_reported():
    files = {"a": b"hay", "b": b"hay"}
    report = run(files)
    assert report.hits == []
    assert report.duplicate_count == 0


def test_empty_binary_and_skipped_files_are_counted_as_skipped():
    files = {"empty": b"", "bin": b"needle\x00", "big": SkipFile("too large"), "ok": b"needle"}
    report = run(files)
    assert [h.path for h in report.hits] == ["ok"]
    assert report.skipped == 3
    assert report.searched == 1


def test_read_errors_are_collected_not_raised():
    files = {"locked": PermissionError(13, "Permission denied"), "ok": b"needle"}
    report = run(files)
    assert [h.path for h in report.hits] == ["ok"]
    assert len(report.errors) == 1
    assert report.errors[0].path == "locked"
    assert report.errors[0].message == "Permission denied"


def test_keep_text_and_on_hit_callback():
    seen = []
    report = run({"a": b"needle\nmore\n"}, keep_text=True, on_hit=seen.append)
    assert seen == report.hits
    assert report.hits[0].text == "needle\nmore\n"
    assert run({"a": b"needle"}).hits[0].text is None


def test_undecodable_bytes_do_not_prevent_matching():
    report = run({"a": b"\xff\xfe junk needle"})
    assert len(report.hits) == 1


@pytest.mark.parametrize("phrase", ["NEEDLE", "Needle"])
def test_ignore_case_matcher(phrase):
    report = search(["a"], Matcher(phrase, ignore_case=True), fake_reader({"a": b"needle"}))
    assert len(report.hits) == 1

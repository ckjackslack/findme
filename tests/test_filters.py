import hashlib

import pytest

from findme.filters import (
    DEFAULT_EXCLUDES,
    content_digest,
    decode_text,
    has_extension,
    is_binary,
    is_excluded,
    normalize_extensions,
)


def test_normalize_extensions():
    assert normalize_extensions(["py", ".TXT", "md, rst", ""]) == {"py", "txt", "md", "rst"}
    assert normalize_extensions([]) == frozenset()


@pytest.mark.parametrize(
    "name, exts, expected",
    [
        ("a.py", {"py"}, True),
        ("a.PY", {"py"}, True),
        ("a.pyc", {"py"}, False),
        ("py", {"py"}, False),
        ("archive.tar.gz", {"tar.gz"}, True),
        ("anything", set(), True),
    ],
)
def test_has_extension(name, exts, expected):
    assert has_extension(name, frozenset(exts)) is expected


@pytest.mark.parametrize(
    "path, patterns, expected",
    [
        ("/home/me/proj/node_modules/x.js", ["node_modules"], True),
        ("/home/me/proj/cachetools/x.py", ["cache"], False),  # no substring matches
        ("/home/me/proj/foo.egg-info/PKG", ["*.egg-info"], True),
        ("/usr/lib/python3/x.py", ["/usr/lib"], True),
        ("/usr/lib", ["/usr/lib/"], True),
        ("/usr/libexec/x", ["/usr/lib"], False),
        ("/home/me/a/build/b.py", ["*/build/*"], True),
        ("src/a.py", [], False),
        ("src/a.py", [""], False),
    ],
)
def test_is_excluded(path, patterns, expected):
    assert is_excluded(path, patterns) is expected


def test_is_excluded_only_checks_components_below_root():
    assert not is_excluded("/x/.venv/lib/a.py", [".venv"], root="/x/.venv")
    assert is_excluded("/x/.venv/lib/a.py", [".venv"], root="/x")


def test_default_excludes_cover_vcs_and_venvs():
    for name in (".git", ".venv", "node_modules", "site-packages", "__pycache__"):
        assert name in DEFAULT_EXCLUDES


def test_is_binary():
    assert is_binary(b"abc\x00def")
    assert not is_binary(b"plain text\n")
    assert not is_binary(b"")


def test_decode_text_tolerates_bad_bytes_and_bom():
    assert decode_text(b"\xef\xbb\xbfhello") == "hello"
    assert decode_text(b"caf\xe9 ok") == "caf� ok"


def test_content_digest_is_sha256():
    assert content_digest(b"abc") == hashlib.sha256(b"abc").hexdigest()
    assert content_digest(b"abc", "md5") == hashlib.md5(b"abc").hexdigest()

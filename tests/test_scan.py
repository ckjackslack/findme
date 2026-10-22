import os

import pytest

from findme.filters import DEFAULT_EXCLUDES
from findme.scan import SkipFile, iter_files, read_file


@pytest.fixture
def tree(tmp_path):
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "a.py").write_text("a")
    (tmp_path / "src" / "b.txt").write_text("b")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config.py").write_text("x")
    (tmp_path / "node_modules" / "m").mkdir(parents=True)
    (tmp_path / "node_modules" / "m" / "i.py").write_text("x")
    (tmp_path / "z.py").write_text("z")
    return tmp_path


def rel(paths, root):
    return [os.path.relpath(p, root) for p in paths]


def test_walks_sorted_and_prunes_excluded_dirs(tree):
    found = rel(iter_files([str(tree)], excludes=DEFAULT_EXCLUDES), tree)
    assert found == ["z.py", "src/b.txt", "src/pkg/a.py"]


def test_extension_filter(tree):
    found = rel(iter_files([str(tree)], excludes=DEFAULT_EXCLUDES, extensions=frozenset({"py"})), tree)
    assert found == ["z.py", "src/pkg/a.py"]


def test_no_excludes_walks_everything(tree):
    found = rel(iter_files([str(tree)]), tree)
    assert ".git/config.py" in found
    assert "node_modules/m/i.py" in found


def test_explicit_file_root_is_yielded(tree):
    f = str(tree / "src" / "b.txt")
    assert list(iter_files([f], extensions=frozenset({"py"}))) == [f]


def test_missing_root_reports_error(tmp_path):
    errors = []
    out = list(iter_files([str(tmp_path / "nope")], on_error=lambda p, m: errors.append((p, m))))
    assert out == []
    assert errors and errors[0][0].endswith("nope")


def test_symlinks_skipped_unless_followed(tmp_path):
    (tmp_path / "real.py").write_text("x")
    (tmp_path / "link.py").symlink_to(tmp_path / "real.py")
    assert rel(iter_files([str(tmp_path)]), tmp_path) == ["real.py"]
    assert rel(iter_files([str(tmp_path)], follow_symlinks=True), tmp_path) == ["link.py", "real.py"]


def test_read_file(tmp_path):
    f = tmp_path / "f"
    f.write_bytes(b"hello")
    assert read_file(str(f)) == b"hello"
    assert read_file(str(f), max_size=5) == b"hello"
    with pytest.raises(SkipFile, match="too large"):
        read_file(str(f), max_size=4)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs mkfifo")
def test_read_file_refuses_fifo(tmp_path):
    fifo = tmp_path / "pipe"
    os.mkfifo(fifo)
    with pytest.raises(SkipFile, match="regular"):
        read_file(str(fifo))


def test_read_file_missing_raises_oserror(tmp_path):
    with pytest.raises(OSError):
        read_file(str(tmp_path / "missing"))

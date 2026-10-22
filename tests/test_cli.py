import io
import json
import os

import pytest

from findme import __version__
from findme.cli import EXIT_ERROR, EXIT_FOUND, EXIT_NOT_FOUND, main

CODE = "import csv\n\ndef load_portfolio(path):\n    return path\n"


@pytest.fixture
def tree(tmp_path, monkeypatch):
    (tmp_path / "projects" / "stocks").mkdir(parents=True)
    (tmp_path / "backup").mkdir()
    (tmp_path / "projects" / "stocks" / "portfolio.py").write_text(CODE)
    (tmp_path / "backup" / "portfolio.py").write_text(CODE)
    (tmp_path / "projects" / "README.md").write_text("# My Portfolio\n")
    (tmp_path / ".venv" / "lib").mkdir(parents=True)
    (tmp_path / ".venv" / "lib" / "dep.py").write_text("portfolio = 1\n")
    (tmp_path / "data.bin").write_bytes(b"portfolio\x00\x01")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def run(*argv, env=None):
    out, err = io.StringIO(), io.StringIO()
    code = main(list(argv), environ=env if env is not None else {}, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def test_default_lines_output_with_duplicates(tree):
    code, out, err = run("portfolio", "-e", "py")
    assert code == EXIT_FOUND
    first = os.path.join(".", "backup", "portfolio.py")
    copy = os.path.join(".", "projects", "stocks", "portfolio.py")
    assert out.startswith(f"{first}\n  3: def load_portfolio(path):\n")
    assert "Identical copies" in out and f"= {copy}" in out
    assert ".venv" not in out
    assert "found in 1 unique file (+1 identical copy)" in err


def test_files_only_and_ignore_case(tree):
    code, out, _ = run("PORTFOLIO", "-i", "-l")
    assert code == EXIT_FOUND
    assert out.splitlines() == [
        os.path.join(".", "backup", "portfolio.py"),
        os.path.join(".", "projects", "README.md"),
    ]


def test_case_sensitive_by_default(tree):
    code, out, _ = run("Portfolio", "-l")
    assert out.splitlines() == [os.path.join(".", "projects", "README.md")]


def test_full_mode_prints_whole_file(tree):
    code, out, _ = run(r"def \w+_portfolio", "-r", "--full", "projects")
    assert code == EXIT_FOUND
    assert "import csv" in out and "=" * 80 in out


def test_json_mode(tree):
    code, out, err = run("portfolio", "-e", "py", "--json", "-q")
    data = json.loads(out)
    assert code == EXIT_FOUND
    assert err == ""
    assert len(data["hits"]) == 1
    assert len(data["hits"][0]["duplicates"]) == 1
    assert data["hits"][0]["matches"][0]["line"] == 3


def test_no_default_excludes_and_custom_exclude(tree):
    _, out, _ = run("portfolio", "-l", "-e", "py", "--no-default-excludes", "-x", "backup")
    lines = out.splitlines()
    assert os.path.join(".", ".venv", "lib", "dep.py") in lines
    assert not any("backup" in line for line in lines)


def test_not_found_exit_code(tree):
    code, out, err = run("zzz-not-here")
    assert code == EXIT_NOT_FOUND
    assert out == ""
    assert "found in 0 unique files" in err


def test_max_size_skips_large_files(tree):
    code, out, err = run("portfolio", "--max-size", "10", "-l")
    assert code == EXIT_NOT_FOUND
    assert "skipped" in err


@pytest.mark.parametrize(
    "argv, message",
    [
        (["(", "-r"], "invalid regular expression"),
        (["x", "does-not-exist"], "no such file or directory"),
        (["x", "--max-size", "lots"], "invalid size"),
        (["x", "--config", "missing.toml"], "missing.toml"),
    ],
)
def test_errors_exit_2_with_message(tree, argv, message):
    code, out, err = run(*argv)
    assert code == EXIT_ERROR
    assert err.startswith("findme: error:") and message in err


def test_bad_config_key(tree):
    (tree / "c.toml").write_text("color = true\n")
    code, _, err = run("x", "--config", "c.toml")
    assert code == EXIT_ERROR and "unknown config key" in err


def test_config_file_and_env(tree):
    (tree / "c.toml").write_text('extensions = ["md"]\nignore_case = true\n')
    code, out, _ = run("portfolio", "-l", "--config", "c.toml")
    assert out.splitlines() == [os.path.join(".", "projects", "README.md")]
    _, out, _ = run("portfolio", "-l", "-e", "py", env={"FINDME_EXCLUDE": "backup"})
    assert out.splitlines() == [os.path.join(".", "projects", "stocks", "portfolio.py")]


def test_default_config_location_from_xdg(tree):
    cfg = tree / "xdg" / "findme"
    cfg.mkdir(parents=True)
    (cfg / "config.toml").write_text('extensions = ["md"]\n')
    env = {"XDG_CONFIG_HOME": str(tree / "xdg")}
    _, out, _ = run("Portfolio", "-l", env=env)
    assert out.splitlines() == [os.path.join(".", "projects", "README.md")]
    _, out, _ = run("portfolio", "-l", "-e", "py", "--no-config", env=env)
    assert len(out.splitlines()) == 1


def test_verbose_reports_walk_errors(tree, monkeypatch):
    import findme.cli as cli

    def fake_iter(roots, on_error, **kw):
        on_error("/secret", "Permission denied")
        yield "projects/README.md"

    monkeypatch.setattr(cli, "iter_files", fake_iter)
    code, out, err = run("Portfolio", "-v")
    assert code == EXIT_FOUND
    assert "findme: /secret: Permission denied" in err
    assert "1 error" in err


def test_unreadable_file_does_not_crash(tree, monkeypatch):
    import findme.cli as cli

    def fake_read(path, max_size=None):
        raise PermissionError(13, "Permission denied", path)

    monkeypatch.setattr(cli, "read_file", fake_read)
    code, _, err = run("portfolio", "-v")
    assert code == EXIT_NOT_FOUND
    assert "Permission denied" in err


def test_version_and_help(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"], environ={})
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["--help"], environ={})
    assert "identical copies" in capsys.readouterr().out.lower()


def test_missing_phrase_is_usage_error(capsys):
    with pytest.raises(SystemExit) as exc:
        main([], environ={})
    assert exc.value.code == 2

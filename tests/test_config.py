import pytest

from findme.config import (
    DEFAULT_MAX_SIZE,
    ConfigError,
    Settings,
    apply_environment,
    apply_mapping,
    default_config_path,
    load_settings,
    parse_size,
)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("512", 512),
        ("64K", 65536),
        ("10M", 10 * 1024**2),
        ("10mb", 10 * 1024**2),
        ("1.5GiB", int(1.5 * 1024**3)),
        ("0", None),
        ("unlimited", None),
        (2048, 2048),
        (0, None),
    ],
)
def test_parse_size(value, expected):
    assert parse_size(value) == expected


@pytest.mark.parametrize("value", ["abc", "10X", "-1", -5, True, ""])
def test_parse_size_invalid(value):
    with pytest.raises(ConfigError):
        parse_size(value)


def test_default_config_path():
    assert default_config_path({"FINDME_CONFIG": "/c.toml", "HOME": "/h"}) == "/c.toml"
    assert default_config_path({"XDG_CONFIG_HOME": "/x", "HOME": "/h"}) == "/x/findme/config.toml"
    assert default_config_path({"HOME": "/h"}) == "/h/.config/findme/config.toml"
    assert default_config_path({}) is None


def test_apply_mapping():
    s = apply_mapping(
        Settings(excludes=("a",)),
        {
            "extensions": ["py", ".md"],
            "exclude": "build",
            "ignore_case": True,
            "default_excludes": False,
            "follow_symlinks": True,
            "max_size": "1K",
        },
    )
    assert s.extensions == {"py", "md"}
    assert s.excludes == ("a", "build")
    assert s.ignore_case and s.follow_symlinks and not s.default_excludes
    assert s.max_size == 1024


@pytest.mark.parametrize(
    "data",
    [{"nope": 1}, {"ignore_case": "yes"}, {"exclude": [1]}, {"max_size": True}, {"max_size": [1]}],
)
def test_apply_mapping_rejects_bad_values(data):
    with pytest.raises(ConfigError):
        apply_mapping(Settings(), data)


def test_apply_environment():
    s = apply_environment(
        Settings(excludes=("a",)),
        {"FINDME_EXTENSIONS": "py, txt", "FINDME_EXCLUDE": "b:c:", "FINDME_MAX_SIZE": "2K"},
    )
    assert s.extensions == {"py", "txt"}
    assert s.excludes == ("a", "b", "c")
    assert s.max_size == 2048
    assert apply_environment(Settings(), {}) == Settings()


def test_load_settings_layers(tmp_path):
    cfg = tmp_path / "findme" / "config.toml"
    cfg.parent.mkdir()
    cfg.write_text('extensions = ["md"]\nexclude = ["from-file"]\n')
    env = {"XDG_CONFIG_HOME": str(tmp_path), "FINDME_EXCLUDE": "from-env", "FINDME_EXTENSIONS": "py"}
    s = load_settings(env)
    assert s.excludes == ("from-file", "from-env")
    assert s.extensions == {"py"}  # env overrides file
    assert load_settings(env, use_config=False).excludes == ("from-env",)


def test_load_settings_missing_default_file_is_fine(tmp_path):
    s = load_settings({"XDG_CONFIG_HOME": str(tmp_path)})
    assert s == Settings()
    assert s.max_size == DEFAULT_MAX_SIZE


def test_load_settings_explicit_missing_file_errors(tmp_path):
    with pytest.raises(ConfigError):
        load_settings({}, config_path=str(tmp_path / "missing.toml"))


def test_load_settings_invalid_toml(tmp_path):
    bad = tmp_path / "bad.toml"
    bad.write_text("this is = = not toml")
    with pytest.raises(ConfigError, match="invalid TOML"):
        load_settings({}, config_path=str(bad))

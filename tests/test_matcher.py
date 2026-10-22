import pytest

from findme.matcher import LineMatch, Matcher


def test_literal_match_returns_line_numbers():
    m = Matcher("portfolio")
    text = "a\nmy portfolio\nb\nportfolio again\n"
    assert m.find(text) == [LineMatch(2, "my portfolio"), LineMatch(4, "portfolio again")]


def test_literal_is_case_sensitive_by_default():
    assert Matcher("Port").find("port\nPort\n") == [LineMatch(2, "Port")]


def test_ignore_case():
    assert [x.lineno for x in Matcher("PORT", ignore_case=True).find("port\nPort\nx")] == [1, 2]


def test_literal_special_characters_are_not_regex():
    m = Matcher("a.b(")
    assert m.find("axb(\na.b(\n") == [LineMatch(2, "a.b(")]


def test_regex_mode():
    m = Matcher(r"def \w+_hash", regex=True)
    assert m.find("def compute_hash():\ndef other():\n") == [LineMatch(1, "def compute_hash():")]


def test_invalid_regex_raises_value_error():
    with pytest.raises(ValueError, match="invalid regular expression"):
        Matcher("(", regex=True)


def test_empty_phrase_rejected():
    with pytest.raises(ValueError):
        Matcher("")


def test_handles_crlf_and_no_trailing_newline():
    assert Matcher("x").find("a\r\nx\r\nlast x") == [LineMatch(2, "x"), LineMatch(3, "last x")]


def test_matches_line():
    m = Matcher("foo")
    assert m.matches_line("a foo b")
    assert not m.matches_line("bar")

"""Fast, deterministic tests for the curator's guards and parsing (no services)."""

from calliope.curator import _parse, is_degenerate

GOOD = "x" * 300 + "\n## English\n- rule\n## German\n- regel\n## Shared\n- s"


def test_degenerate_empty():
    assert is_degenerate("", GOOD) is True


def test_degenerate_too_short():
    assert is_degenerate("## English ## German", GOOD) is True


def test_degenerate_missing_language_headers():
    assert is_degenerate("y" * 400, GOOD) is True


def test_not_degenerate_good_guide():
    assert is_degenerate(GOOD, GOOD) is False


def test_parse_with_changelog():
    changelog, guide = _parse("CHANGELOG: added a hedging rule\n## English\n- avoid hedging")
    assert changelog == "added a hedging rule"
    assert guide.startswith("## English")


def test_parse_without_changelog():
    changelog, guide = _parse("## English\n- avoid hedging")
    assert "## English" in guide
    assert changelog  # falls back to a default

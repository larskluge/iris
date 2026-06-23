"""Fast tests for seed assembly + language splitting (no model)."""

from calliope.models import CorpusRecord
from calliope.seed import assemble_guide, split_by_lang


def test_assemble_guide_has_sections():
    g = assemble_guide("- en stuff", "- de stuff", 3, 5)
    assert "## English" in g and "## German" in g and "## Shared" in g
    assert "3 emails + 5 messages" in g


def test_split_by_lang():
    recs = [
        CorpusRecord(kind="message", text="Hello, how are you doing today?"),
        CorpusRecord(kind="message", text="Hallo, wie geht es dir heute so?"),
    ]
    buckets = split_by_lang(recs)
    assert len(buckets["en"]) == 1
    assert len(buckets["de"]) == 1

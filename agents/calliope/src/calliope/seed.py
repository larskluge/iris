"""Distill an initial voice_style_guide from the sent corpus (M1).

Splits records by language, asks the model to extract concrete style rules per
language, and assembles the sectioned guide written to the agent's Letta block
as version 1.
"""

from calliope import ollama
from calliope.config import Settings
from calliope.lettaclient import LettaClient
from calliope.models import CorpusRecord
from calliope.store import Store

try:
    from langdetect import detect
except ImportError:  # pragma: no cover
    def detect(_):  # type: ignore
        return "en"


def _lang(text: str) -> str:
    try:
        return "de" if detect(text) == "de" else "en"
    except Exception:
        return "en"


def split_by_lang(records: list[CorpusRecord]) -> dict[str, list[CorpusRecord]]:
    buckets: dict[str, list[CorpusRecord]] = {"en": [], "de": []}
    for r in records:
        buckets[_lang(r.text)].append(r)
    return buckets


def _section(settings: Settings, language: str, recs: list[CorpusRecord]) -> str:
    if not recs:
        return f"- (no {language} samples in the corpus yet)"
    samples = "\n---\n".join(f"[{r.kind}] {r.text[:500]}" for r in recs)
    prompt = (
        f"Analyze these messages the user wrote in {language}. Extract their writing VOICE "
        "as concrete, specific rules a ghostwriter could follow. Output ONLY these labelled "
        "bullet groups, nothing else:\n"
        "- Tone & register:\n- Sentence rhythm & length:\n- Openings/sign-offs:\n"
        "- Favored phrasings:\n- Phrases to avoid:\n\n"
        f"Samples:\n{samples}"
    )
    return ollama.generate(
        settings, system="You are a precise writing-style analyst.", user=prompt, num_predict=900
    ).strip()


def assemble_guide(en_section: str, de_section: str, n_email: int, n_msg: int) -> str:
    return (
        f"# Voice style guide (seeded from {n_email} emails + {n_msg} messages)\n\n"
        f"## English\n{en_section}\n\n"
        f"## German\n{de_section}\n\n"
        "## Shared\n"
        "- Lead with the point; put the ask in the first two sentences.\n"
        "- Group related thoughts; one paragraph per topic.\n"
    )


def build_style_guide(settings: Settings, records: list[CorpusRecord], *, per_lang_samples: int = 24) -> str:
    buckets = split_by_lang(records)
    en = _section(settings, "English", buckets["en"][:per_lang_samples])
    de = _section(settings, "German", buckets["de"][:per_lang_samples])
    n_email = sum(1 for r in records if r.kind == "email")
    n_msg = sum(1 for r in records if r.kind == "message")
    return assemble_guide(en, de, n_email, n_msg)


def seed_agent(settings: Settings, letta: LettaClient, agent, store: Store, records: list[CorpusRecord]) -> str:
    guide = build_style_guide(settings, records)
    letta.set_block(agent.id, "voice_style_guide", guide)
    store.ensure_schema()
    store.record_version(store.next_version(), guide, "seeded from mycelium corpus")
    return guide

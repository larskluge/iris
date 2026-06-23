"""The curator — Calliope's self-learning engine (R9 / §7.5).

Reads accumulated EditRecords, asks the model to rewrite the voice_style_guide
incorporating the consistent preferences they reveal, bumps a version with a
changelog, and rejects degenerate rewrites. Steering instructions map almost
directly to rules; diffs catch the unspoken habits.
"""

from calliope import ollama
from calliope.config import Settings
from calliope.lettaclient import LettaClient
from calliope.models import CurationResult, EditRecord
from calliope.store import Store

_EXPECTED_HEADERS = ("English", "German")


def is_degenerate(new_guide: str, old_guide: str) -> bool:
    """Reject empty/too-short rewrites or ones that dropped the language structure."""
    text = (new_guide or "").strip()
    if len(text) < 100:
        return True
    if len(text) < 0.5 * len(old_guide):
        return True
    return not all(h.lower() in text.lower() for h in _EXPECTED_HEADERS)


def _format_edits(edits: list[EditRecord]) -> str:
    blocks = []
    for i, e in enumerate(edits, 1):
        steer = "; ".join(e.steering) if e.steering else "(no explicit instruction)"
        blocks.append(
            f"Edit {i} [{e.lang}]:\n  steering: {steer}\n"
            f"  first draft: {e.first_draft[:400]}\n  final: {e.final[:400]}"
        )
    return "\n\n".join(blocks)


def _parse(out: str) -> tuple[str, str]:
    """Split the model output into (changelog, guide)."""
    changelog = "updated from recent edits"
    lines = out.splitlines()
    for idx, line in enumerate(lines):
        if line.strip().upper().startswith("CHANGELOG:"):
            changelog = line.split(":", 1)[1].strip() or changelog
            guide = "\n".join(lines[idx + 1 :]).strip()
            return changelog, guide
    return changelog, out.strip()


def curate(settings: Settings, letta: LettaClient, agent, store: Store) -> CurationResult | None:
    """Curate the style guide from uncurated edits. Returns None if there's nothing to learn."""
    edits = store.uncurated()
    if not edits:
        return None

    # Only learn from edits that carry signal — explicit steering or an actual
    # draft->final change. No-op accepts (drafted, accepted as-is) are acknowledged
    # but must not churn the style-guide version.
    signal = [e for e in edits if e.steering or (e.diff and e.diff.strip())]
    if not signal:
        store.mark_all_curated()
        return None

    old = letta.get_block(agent.id, "voice_style_guide")
    if store.latest_version() is None:
        store.record_version(1, old, "seed")

    prompt = (
        "Here is the CURRENT writing style guide:\n\n"
        f"{old}\n\n"
        "Here are recent EDITS the user made to drafts — their steering instructions and "
        "the change from first draft to final. Each reflects a real, repeated preference:\n\n"
        f"{_format_edits(signal)}\n\n"
        "Rewrite the COMPLETE style guide. Keep its section structure (English / German / "
        "Shared). Fold in the consistent preferences shown (e.g. turn a repeated steering "
        "instruction into an explicit rule). Keep existing valid rules; stay concise.\n\n"
        "Output exactly:\n"
        "CHANGELOG: <one short line on what you changed>\n"
        "<the complete updated style guide>"
    )
    out = ollama.chat(
        settings,
        [
            {"role": "system", "content": "You maintain a concise personal writing style guide."},
            {"role": "user", "content": prompt},
        ],
        num_predict=2000,
    )
    changelog, new_guide = _parse(out)

    if is_degenerate(new_guide, old):
        latest = store.latest_version()
        return CurationResult(
            version=latest.version if latest else 1,
            changelog="(rejected degenerate rewrite; kept prior version)",
            changed=False,
        )

    version = store.next_version()
    store.record_version(version, new_guide, changelog)
    letta.set_block(agent.id, "voice_style_guide", new_guide)
    store.mark_all_curated()
    return CurationResult(version=version, changelog=changelog, changed=True)


def rollback(letta: LettaClient, agent, store: Store, target_version: int) -> int:
    """Restore a prior style-guide version as a new version. Returns the new version number."""
    target = store.get_version(target_version)
    if target is None:
        raise ValueError(f"no style-guide version {target_version}")
    version = store.next_version()
    store.record_version(version, target.value, f"rollback to v{target_version}")
    letta.set_block(agent.id, "voice_style_guide", target.value)
    return version

"""ChatSession — the interactive chat slice, decoupled from terminal I/O so it
can be driven directly by tests (R9 learning capture lives here).

Memory (persona, voice_style_guide) comes from Letta; generation runs via direct
Ollama. A session tracks the first draft, the current draft, and the steering
trajectory, and turns an accepted session into an EditRecord.
"""

import difflib

from calliope import ollama
from calliope.config import Settings
from calliope.errors import EmptyInputError, NoDraftError
from calliope.lettaclient import LettaClient
from calliope.models import EditRecord
from calliope.prompts import build_system_prompt


def _diff(a: str, b: str) -> str:
    return "".join(
        difflib.unified_diff(
            a.splitlines(keepends=True), b.splitlines(keepends=True),
            fromfile="first_draft", tofile="final",
        )
    )


class ChatSession:
    def __init__(self, settings: Settings, letta: LettaClient, agent):
        self.s = settings
        self.letta = letta
        self.agent = agent
        self.persona = letta.get_block(agent.id, "persona")
        self.style_guide = letta.get_block(agent.id, "voice_style_guide")
        self.lang = "en"
        self.messages: list[dict] = []
        self.first_draft: str | None = None
        self.current_draft: str | None = None
        self.steering: list[str] = []

    def _system(self, target_lang: str | None = None) -> str:
        return build_system_prompt(self.persona, self.style_guide, target_lang)

    def send(self, user_text: str) -> str:
        """A brief (first turn) or a steering instruction (later turns) -> a draft."""
        if not user_text or not user_text.strip():
            raise EmptyInputError("Tell me what to write — recipient and intent.")
        if self.first_draft is not None:
            self.steering.append(user_text.strip())
        self.messages.append({"role": "user", "content": user_text})
        draft = ollama.chat(self.s, [{"role": "system", "content": self._system()}, *self.messages])
        self.messages.append({"role": "assistant", "content": draft})
        if self.first_draft is None:
            self.first_draft = draft
        self.current_draft = draft
        return draft

    def hand_edit(self, edited_text: str) -> None:
        """The user pasted their own version — the strongest 'what' signal."""
        if not edited_text or not edited_text.strip():
            raise EmptyInputError("Paste the edited text.")
        if self.first_draft is None:
            self.first_draft = edited_text
        self.steering.append("[hand-edit]")
        self.messages.append({"role": "assistant", "content": edited_text})
        self.current_draft = edited_text

    def translate(self, target_lang: str) -> str:
        if self.current_draft is None:
            raise NoDraftError("Nothing to translate yet — ask for a draft first.")
        out = ollama.chat(
            self.s,
            [
                {"role": "system", "content": self._system(target_lang=target_lang)},
                {
                    "role": "user",
                    "content": "Translate the following into the target language, "
                    "preserving my voice and intent — not a literal rendering:\n\n"
                    + self.current_draft,
                },
            ],
        )
        self.current_draft = out
        self.lang = target_lang
        return out

    def accept(self) -> EditRecord:
        if self.first_draft is None or self.current_draft is None:
            raise NoDraftError("Nothing to accept yet — ask for a draft first.")
        return EditRecord(
            lang=self.lang,
            first_draft=self.first_draft,
            final=self.current_draft,
            diff=_diff(self.first_draft, self.current_draft),
            steering=list(self.steering),
        )

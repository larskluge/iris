"""Calliope's identity + memory plane (R8).

Letta holds the durable `calliope` agent and its core-memory blocks
(`persona`, `voice_style_guide`) in Postgres, surviving restarts and model
swaps. Draft/translate generation deliberately does NOT go through Letta's
agentic tool-calling loop (see `calliope.ollama`): a local Gemma-via-Ollama
model is not a reliable tool-caller, so Letta is used as the memory store and
generation is driven directly with that memory injected. This is the §12
"A2A ⇄ Letta bridge" spike resolution for P0.
"""

from letta_client import Letta

from calliope.config import Settings


class LettaClient:
    def __init__(self, settings: Settings):
        self.s = settings
        self.client = Letta(base_url=settings.letta_base_url)

    def ensure_agent(self, name: str = "calliope", persona: str = "", voice_style_guide: str = ""):
        """Return the named agent, creating it (with the two core blocks) if absent."""
        existing = list(self.client.agents.list(name=name))
        if existing:
            return existing[0]
        return self.client.agents.create(
            name=name,
            model=f"ollama/{self.s.model}",
            embedding="letta/letta-free",
            memory_blocks=[
                {"label": "persona", "value": persona},
                {"label": "voice_style_guide", "value": voice_style_guide},
            ],
            include_base_tools=False,
            tools=[],
        )

    def get_block(self, agent_id: str, label: str) -> str:
        block = self.client.agents.blocks.retrieve(agent_id=agent_id, block_label=label)
        return block.value or ""

    def set_block(self, agent_id: str, label: str, value: str) -> None:
        self.client.agents.blocks.update(agent_id=agent_id, block_label=label, value=value)

    def delete_agent(self, agent_id: str) -> None:
        self.client.agents.delete(agent_id)

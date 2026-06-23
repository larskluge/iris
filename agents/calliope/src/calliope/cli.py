"""`calliope` CLI — the interactive chat front door (a thin I/O loop over ChatSession)."""

import typer

from calliope.config import Settings
from calliope.errors import CalliopeError
from calliope.lettaclient import LettaClient
from calliope.prompts import DEFAULT_PERSONA, DEFAULT_STYLE_GUIDE
from calliope.session import ChatSession

app = typer.Typer(help="Calliope — your self-learning copywriter.", no_args_is_help=True)


def _ensure_agent(settings: Settings, letta: LettaClient):
    return letta.ensure_agent(
        "calliope", persona=DEFAULT_PERSONA, voice_style_guide=DEFAULT_STYLE_GUIDE
    )


@app.command()
def chat():
    """Open an interactive drafting session (sync to the Letta agent)."""
    settings = Settings()
    letta = LettaClient(settings)
    session = ChatSession(settings, letta, _ensure_agent(settings, letta))
    typer.echo(
        "Calliope ready. Describe what to write.\n"
        "Commands: /translate <lang> · /edit · /accept · /status · /quit"
    )
    while True:
        try:
            line = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            typer.echo("\nbye")
            return
        if not line:
            continue
        try:
            if line in ("/quit", "/q", "/exit"):
                return
            if line == "/status":
                typer.echo(
                    f"style guide: {len(session.style_guide)} chars · "
                    f"steering captured: {len(session.steering)} · lang: {session.lang}"
                )
            elif line == "/accept":
                rec = session.accept()
                typer.echo("\n--- accepted ---\n" + rec.final)
                typer.echo(f"(captured {len(rec.steering)} steering note(s) for learning)")
                return
            elif line.startswith("/translate"):
                parts = line.split()
                lang = parts[1] if len(parts) > 1 else "de"
                typer.echo("\ncalliope>\n" + session.translate(lang))
            elif line == "/edit":
                typer.echo("paste your edited version; end with a single '.' on its own line:")
                buf = []
                while (paste := input()) != ".":
                    buf.append(paste)
                session.hand_edit("\n".join(buf))
                typer.echo("(captured your edit)")
            else:
                typer.echo("\ncalliope>\n" + session.send(line))
        except CalliopeError as e:
            typer.echo(f"[calliope] {e}")


@app.command()
def status():
    """Show Calliope's current memory state."""
    settings = Settings()
    letta = LettaClient(settings)
    agent = _ensure_agent(settings, letta)
    sg = letta.get_block(agent.id, "voice_style_guide")
    typer.echo(f"agent: {agent.name} ({agent.id})")
    typer.echo(f"model: {settings.model}")
    typer.echo(f"voice_style_guide: {len(sg)} chars")
    typer.echo(sg[:400] + ("…" if len(sg) > 400 else ""))


def main():
    app()

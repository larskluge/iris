"""`calliope` CLI — the interactive chat front door (a thin I/O loop over ChatSession),
plus the learning commands (`learn`, `rollback`) and `status`."""

import typer

from calliope import corpus, curator
from calliope import seed as seeder
from calliope.config import Settings
from calliope.errors import CalliopeError
from calliope.lettaclient import LettaClient
from calliope.prompts import DEFAULT_PERSONA, DEFAULT_STYLE_GUIDE
from calliope.session import ChatSession
from calliope.store import Store

app = typer.Typer(help="Calliope — your self-learning copywriter.", no_args_is_help=True)


def _wire():
    settings = Settings()
    letta = LettaClient(settings)
    agent = letta.ensure_agent(
        "calliope", persona=DEFAULT_PERSONA, voice_style_guide=DEFAULT_STYLE_GUIDE
    )
    store = Store(settings, agent.id)
    store.ensure_schema()
    return settings, letta, store, agent


@app.command()
def chat():
    """Open an interactive drafting session (sync to the Letta agent)."""
    settings, letta, store, agent = _wire()
    session = ChatSession(settings, letta, agent)
    typer.echo(
        "Calliope ready. Describe what to write.\n"
        "Commands: /translate <lang> · /edit · /accept · /learn · /status · /quit"
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
                latest = store.latest_version()
                ver = f"v{latest.version} ({latest.changelog})" if latest else "starter (unseeded)"
                typer.echo(f"style guide: {ver} · steering this session: {len(session.steering)} · lang: {session.lang}")
            elif line == "/accept":
                rec = session.accept()
                store.append_edit(rec)
                typer.echo("\n--- accepted ---\n" + rec.final)
                pending = store.count_uncurated()
                if pending >= settings.curate_threshold:
                    res = curator.curate(settings, letta, agent, store)
                    if res and res.changed:
                        typer.echo(f"(learned → style guide v{res.version}: {res.changelog})")
                else:
                    typer.echo(f"(captured; {pending}/{settings.curate_threshold} edits until I curate — /learn to curate now)")
                return
            elif line == "/learn":
                res = curator.curate(settings, letta, agent, store)
                typer.echo(f"(learned → v{res.version}: {res.changelog})" if res and res.changed else "(nothing new to learn)")
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
def learn():
    """Curate the style guide from accepted edits now."""
    settings, letta, store, agent = _wire()
    res = curator.curate(settings, letta, agent, store)
    typer.echo(f"learned → v{res.version}: {res.changelog}" if res and res.changed else "nothing new to learn")


@app.command()
def rollback(version: int):
    """Restore a prior style-guide version (recorded as a new version)."""
    settings, letta, store, agent = _wire()
    new_version = curator.rollback(letta, agent, store, version)
    typer.echo(f"rolled back to v{version} (recorded as v{new_version})")


@app.command()
def seed(limit: int = 200, kind: str = "email,message"):
    """Seed the voice style guide from your sent mail/messages (mycelium)."""
    settings, letta, store, agent = _wire()
    kinds = tuple(k.strip() for k in kind.split(","))
    records = corpus.read_corpus(settings, kinds=kinds, limit=limit)
    if not records:
        typer.echo("no corpus records found — check CALLIOPE_MYCELIUM_PG_DSN and the self identifiers")
        raise typer.Exit(1)
    guide = seeder.seed_agent(settings, letta, agent, store, records)
    typer.echo(f"seeded voice_style_guide from {len(records)} records ({len(guide)} chars). Try `calliope status`.")


@app.command()
def status():
    """Show Calliope's current memory state."""
    settings, letta, store, agent = _wire()
    sg = letta.get_block(agent.id, "voice_style_guide")
    latest = store.latest_version()
    typer.echo(f"agent: {agent.name} ({agent.id})")
    typer.echo(f"model: {settings.model}")
    typer.echo(f"style guide: {'v' + str(latest.version) + ' — ' + latest.changelog if latest else 'starter (unseeded)'} · {len(sg)} chars")
    typer.echo(f"pending edits to curate: {store.count_uncurated()}")


def main():
    app()

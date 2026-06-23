from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the Calliope agent and its services.

    All values are local-only (R13): nothing here points at a cloud vendor.
    Override via CALLIOPE_-prefixed env vars or a local .env file.
    """

    model_config = SettingsConfigDict(env_prefix="CALLIOPE_", env_file=".env", extra="ignore")

    # Native Ollama model server (Metal) — reached on the host.
    ollama_base_url: str = "http://localhost:11434"
    model: str = "gemma4:31b-mlx"

    # Control-plane services (podman compose).
    pg_dsn: str = "postgresql://calliope:calliope@localhost:5434/calliope"
    nats_url: str = "nats://localhost:4222"
    letta_base_url: str = "http://localhost:8283"

    # Learning loop: curate the style guide after this many uncurated edits.
    curate_threshold: int = 5

    # mycelium read models (read-only seed corpus). Default = local dev DB; point
    # at mycelium_prod on outpost (readonly role / SSH tunnel) for the real seed.
    mycelium_pg_dsn: str = "postgresql://postgres:postgres@localhost:5433/mycelium_dev"
    mycelium_self_emails: list[str] = [
        "l@larskluge.com", "me@aekym.com", "la@aekym.com", "andreas@aekym.com",
    ]
    mycelium_self_names: list[str] = ["Lars", "Lars Kluge"]

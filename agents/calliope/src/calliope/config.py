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

    # mycelium_prod (read-only seed corpus) via SSH tunnel to outpost — resolved in M1.
    mycelium_ssh_host: str = "outpost"
    mycelium_pg_dsn: str = "postgresql://readonly@localhost:6543/mycelium_prod"

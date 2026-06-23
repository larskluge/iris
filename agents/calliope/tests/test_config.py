from calliope.config import Settings


def test_settings_defaults():
    s = Settings()
    assert s.ollama_base_url == "http://localhost:11434"
    assert s.model == "gemma4:31b-mlx"
    assert s.pg_dsn.startswith("postgresql://")
    assert s.nats_url.startswith("nats://")

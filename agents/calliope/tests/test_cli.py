def test_cli_wired():
    from calliope import cli

    assert callable(cli.main)
    names = {c.callback.__name__ for c in cli.app.registered_commands}
    assert {"chat", "status"} <= names

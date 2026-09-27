from burp.config import DEFAULT_DB_PATH, DEFAULT_MODEL, Settings, load_env


def test_load_env_reads_values_and_skips_comments(tmp_path, monkeypatch):
    monkeypatch.delenv("BURP_TEST_A", raising=False)
    monkeypatch.delenv("BURP_TEST_B", raising=False)
    env = tmp_path / ".env"
    env.write_text('# comment\n\nBURP_TEST_A=one\nBURP_TEST_B="two words"\n')
    load_env(env)
    import os

    assert os.environ["BURP_TEST_A"] == "one"
    assert os.environ["BURP_TEST_B"] == "two words"


def test_load_env_does_not_override_existing_variables(tmp_path, monkeypatch):
    monkeypatch.setenv("BURP_TEST_A", "from-shell")
    env = tmp_path / ".env"
    env.write_text("BURP_TEST_A=from-file\n")
    load_env(env)
    import os

    assert os.environ["BURP_TEST_A"] == "from-shell"


def test_load_env_ignores_missing_file(tmp_path):
    load_env(tmp_path / "missing.env")


def test_settings_defaults(monkeypatch):
    for key in ("ANTHROPIC_API_KEY", "BURP_MODEL", "TELEGRAM_ALLOWED_USER_IDS", "BURP_DB_PATH"):
        monkeypatch.delenv(key, raising=False)
    settings = Settings.from_env()
    assert settings.anthropic_api_key is None
    assert settings.model == DEFAULT_MODEL
    assert settings.telegram_allowed_user_ids == frozenset()
    assert settings.db_path == DEFAULT_DB_PATH


def test_settings_parse_allowed_user_ids(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "12, 34,")
    assert Settings.from_env().telegram_allowed_user_ids == frozenset({12, 34})

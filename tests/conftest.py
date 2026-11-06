"""Shared pytest fixtures.

Puts the project root on `sys.path` so `olit`, `keep_alive` and friends import
the same way they do at runtime, and points the config/persistence paths at a
temp directory so tests never touch real bot data.
"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    """A Flask test client for keep_alive, isolated from real config files."""
    import keep_alive

    # Redirect every config file into the temp dir before loading.
    for attr, name in [
        ("GUILD_COMMANDS_FILE", "guild_commands.json"),
        ("AUTOMOD_FILE", "automod_config.json"),
        ("AUTOMOD_ENABLED_FILE", "automod_enabled.json"),
        ("ALLOWED_USERS_FILE", "allowed_users.json"),
        ("WELCOME_CHANNELS_FILE", "welcome_channels.json"),
        ("API_LOGS_FILE", "api_logs.json"),
    ]:
        monkeypatch.setattr(keep_alive, attr, str(tmp_path / name))

    # Don't let tests push config to GitHub.
    monkeypatch.setattr(keep_alive, "commit_to_github", lambda *a, **k: None)

    keep_alive.load_all_data()
    keep_alive.app.config["TESTING"] = True
    with keep_alive.app.test_client() as client:
        yield client, keep_alive

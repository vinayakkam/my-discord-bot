"""The bot's own calls to its per-guild API routes must authenticate.

Those routes sit behind require_guild_access. The bot used to call them with no
credentials, got 401 every time, and silently fell back to an empty automod
list, no exempt users and the local command file. These tests route the bot's
requests.get through the real Flask app, so the real decorator decides.
"""

import pytest

GUILD = "123"
KEY = "test-operator-key"  # the api_client fixture sets keep_alive.API_KEY to this


class _Response:
    def __init__(self, flask_response):
        self.status_code = flask_response.status_code
        self._json = flask_response.get_json()

    def json(self):
        return self._json


@pytest.fixture
def bot_api(api_client, monkeypatch):
    """main's API helpers wired to the in-process Flask app."""
    client, keep_alive = api_client
    import main

    def fake_get(url, headers=None, timeout=None):
        path = url[len(main.API_BASE_URL):]
        return _Response(client.get(path, headers=headers or {}))

    monkeypatch.setattr(main.requests, "get", fake_get)
    monkeypatch.setattr(main, "API_KEY", KEY)
    monkeypatch.setattr(main, "load_commands_from_file", lambda guild_id: {"from": "file"})

    keep_alive.guild_commands[GUILD] = {"hello": {"response": "hi"}}
    keep_alive.automod_config[GUILD] = ["badword"]
    keep_alive.allowed_users[GUILD] = ["42"]
    return main


def test_guild_commands_load_from_the_api(bot_api):
    assert bot_api.fetch_guild_commands(GUILD) == {"hello": {"response": "hi"}}


def test_automod_words_load_from_the_api(bot_api):
    assert bot_api.fetch_automod_words(GUILD) == ["badword"]


def test_allowed_users_load_from_the_api(bot_api):
    assert bot_api.fetch_allowed_users(GUILD) == ["42"]


def test_without_the_key_the_api_refuses_and_the_bot_falls_back(bot_api, monkeypatch):
    """Documents the old failure: no key means 401 and the fallbacks."""
    monkeypatch.setattr(bot_api, "API_KEY", None)
    assert bot_api.fetch_guild_commands(GUILD) == {"from": "file"}
    assert bot_api.fetch_automod_words(GUILD) == []
    assert bot_api.fetch_allowed_users(GUILD) == []


def test_api_headers_carry_the_operator_key_only_when_set(monkeypatch):
    import main

    monkeypatch.setattr(main, "API_KEY", KEY)
    assert main._api_headers() == {"X-API-Key": KEY}
    monkeypatch.setattr(main, "API_KEY", None)
    assert main._api_headers() == {}

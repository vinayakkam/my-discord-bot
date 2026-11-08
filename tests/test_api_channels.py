"""Tests for the guild/channel listing endpoints the dashboard dropdown uses."""

import asyncio
import threading
import types

import pytest


class _FakeGuild:
    def __init__(self, gid, name, channels):
        self.id = gid
        self.name = name
        self.member_count = 10
        self.icon = None
        self._channels = channels

    async def fetch_channels(self):
        return self._channels


class _FakeChannel:
    def __init__(self, cid, name, type_value, position=0, category=None):
        self.id = cid
        self.name = name
        self.type = types.SimpleNamespace(value=type_value)
        self.position = position
        self.category = category
        self.category_id = category.id if category else None


class _FakeBot:
    """Stands in for the discord.py Bot, with a real loop on a real thread."""

    def __init__(self, guilds, loop):
        self.guilds = guilds
        self.loop = loop

    def get_guild(self, gid):
        return next((g for g in self.guilds if g.id == gid), None)


@pytest.fixture
def bot_loop():
    """A background asyncio loop, mimicking the bot's own thread."""
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    yield loop
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=5)


@pytest.fixture
def wired(api_client, bot_loop):
    client, keep_alive = api_client
    general = _FakeChannel(1, "general", 0, position=1)
    news = _FakeChannel(2, "news", 5, position=2)
    voice = _FakeChannel(3, "Voice", 2, position=3)
    guild = _FakeGuild(123, "Test Guild", [general, news, voice])
    keep_alive.bot_instance = _FakeBot([guild], bot_loop)
    yield client, keep_alive
    keep_alive.bot_instance = None


def _auth(keep_alive):
    return {"X-API-Key": keep_alive.API_KEY}


def test_channels_lists_text_channels(wired):
    client, keep_alive = wired
    resp = client.get("/api/channels/123", headers=_auth(keep_alive))
    assert resp.status_code == 200, resp.data
    data = resp.get_json()
    names = [c["name"] for c in data["channels"]]
    # Text (0) and announcement (5) only -- no voice channels.
    assert names == ["general", "news"]
    assert all(isinstance(c["id"], str) for c in data["channels"])


def test_channels_404_for_unknown_guild(wired):
    client, keep_alive = wired
    resp = client.get("/api/channels/999", headers=_auth(keep_alive))
    assert resp.status_code == 404


def test_guilds_endpoint_lists_servers(wired):
    client, keep_alive = wired
    resp = client.get("/api/guilds", headers=_auth(keep_alive))
    assert resp.status_code == 200, resp.data
    data = resp.get_json()
    assert data["count"] == 1
    assert data["guilds"][0]["name"] == "Test Guild"
    assert data["guilds"][0]["id"] == "123"


def test_guilds_503_without_bot(api_client):
    client, keep_alive = api_client
    keep_alive.bot_instance = None
    resp = client.get("/api/guilds", headers=_auth(keep_alive))
    assert resp.status_code == 503


def test_guild_endpoints_require_authorization(wired):
    """No credentials, or a bad operator key, means no answer.

    A wrong key is not treated as a distinct "forbidden" case any more: it
    simply is not a credential, so the request falls through to the Discord
    check and is told to sign in.
    """
    client, keep_alive = wired
    assert client.get("/api/channels/123").status_code == 401
    assert client.get(
        "/api/channels/123", headers={"X-API-Key": "wrong"}
    ).status_code == 401


def test_cors_preflight_allows_auth_headers(wired):
    """The dashboard's cross-origin calls must get their auth header past the preflight."""
    client, _ = wired
    resp = client.options(
        "/api/channels/123",
        headers={
            "Origin": "https://olittechnologies.co.in",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-API-Key, Authorization",
        },
    )
    assert resp.status_code in (200, 204)
    allowed = resp.headers.get("Access-Control-Allow-Headers", "").lower()
    assert "x-api-key" in allowed
    assert "authorization" in allowed

"""Authorization tests for the dashboard API.

The dashboard is a static site, so anything it ships is public. These tests pin
down the rules that replaced the old shared-key scheme:

* a guild endpoint answers only the people who administer that guild;
* the operator key is a server-to-server credential and still sees everything;
* the public status route exposes aggregates and nothing identifying.
"""

import pytest


MANAGED = "123"
UNMANAGED = "456"


def _operator(keep_alive):
    return {"X-API-Key": keep_alive.API_KEY}


def _discord(token="tok-abc"):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def logged_in(api_client, monkeypatch):
    """A client whose Discord token verifies as managing MANAGED only.

    Patches the Discord round trip, not the decorator, so the real
    require_guild_access() logic is what the tests exercise.
    """
    client, keep_alive = api_client
    calls = []

    def fake_lookup(token):
        calls.append(token)
        return True, frozenset({MANAGED})

    monkeypatch.setattr(keep_alive, "discord_managed_guilds", fake_lookup)
    return client, keep_alive, calls


# ── Credentials are required at all ──────────────────────────────────────────
@pytest.mark.parametrize("path", [
    "/api/config/123",
    "/api/commands/123",
    "/api/automod/123",
    "/api/automod_enabled/123",
    "/api/allowed_users/123",
    "/api/welcome_channel/123",
])
def test_guild_reads_reject_anonymous_callers(api_client, path):
    """These five routes used to answer anybody, with no credentials at all."""
    client, _keep_alive = api_client
    assert client.get(path).status_code == 401


def test_public_status_needs_no_credentials(api_client):
    client, _keep_alive = api_client
    resp = client.get("/api/public/status")
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True


def test_public_status_exposes_only_aggregates(api_client):
    """Guard against a future field that would name a server or a person."""
    client, keep_alive = api_client
    keep_alive.guild_commands["999"] = {"secretcmd": {"response": "hi"}}

    body = client.get("/api/public/status").get_data(as_text=True)

    assert "999" not in body
    assert "secretcmd" not in body
    payload = client.get("/api/public/status").get_json()
    assert payload["totals"]["custom_commands"] == 1
    assert set(payload["totals"]) == {"servers", "custom_commands", "filtered_words"}


# ── Discord-verified access ──────────────────────────────────────────────────
def test_managed_guild_is_readable(logged_in):
    client, _keep_alive, calls = logged_in
    resp = client.get(f"/api/config/{MANAGED}", headers=_discord())
    assert resp.status_code == 200, resp.data
    assert resp.get_json()["config"]["guild_id"] == MANAGED
    assert calls == ["tok-abc"]


def test_unmanaged_guild_is_refused(logged_in):
    client, _keep_alive, _calls = logged_in
    resp = client.get(f"/api/config/{UNMANAGED}", headers=_discord())
    assert resp.status_code == 403
    # The message must not reveal whether that server exists.
    assert UNMANAGED not in resp.get_json()["error"]


def test_write_to_unmanaged_guild_is_refused(logged_in):
    client, keep_alive, _calls = logged_in
    resp = client.post(
        "/api/add_command",
        json={"guild_id": UNMANAGED, "command": "evil", "response": "nope"},
        headers=_discord(),
    )
    assert resp.status_code == 403
    assert UNMANAGED not in keep_alive.guild_commands


def test_write_to_managed_guild_succeeds(logged_in):
    client, keep_alive, _calls = logged_in
    resp = client.post(
        "/api/add_command",
        json={"guild_id": MANAGED, "command": "rules", "response": "be nice"},
        headers=_discord(),
    )
    assert resp.status_code == 200, resp.data
    assert "rules" in keep_alive.guild_commands[MANAGED]


def test_expired_discord_token_is_rejected(api_client, monkeypatch):
    client, keep_alive = api_client
    monkeypatch.setattr(
        keep_alive, "discord_managed_guilds",
        lambda token: (False, "Your Discord login has expired -- sign in again"))
    resp = client.get(f"/api/config/{MANAGED}", headers=_discord())
    assert resp.status_code == 401
    assert "expired" in resp.get_json()["error"]


def test_guilds_route_lists_only_managed_servers(logged_in, monkeypatch):
    """The server list used to disclose every guild the bot was in."""
    client, keep_alive, _calls = logged_in

    class _Guild:
        def __init__(self, gid, name):
            self.id = int(gid)
            self.name = name
            self.member_count = 3
            self.icon = None

    def fake_run(coro_factory, timeout=None):
        managed = keep_alive.flask_g.managed_guilds
        guilds = [_Guild(MANAGED, "Mine"), _Guild(UNMANAGED, "Someone else's")]
        return True, [
            {"id": str(g.id), "name": g.name, "member_count": g.member_count, "icon": None}
            for g in guilds if managed is None or str(g.id) in managed
        ]

    monkeypatch.setattr(keep_alive, "run_on_bot_loop", fake_run)
    resp = client.get("/api/guilds", headers=_discord())
    assert resp.status_code == 200, resp.data
    names = [g["name"] for g in resp.get_json()["guilds"]]
    assert names == ["Mine"]


# ── Logs are scoped and redacted ─────────────────────────────────────────────
def _seed_logs(keep_alive):
    keep_alive.api_logs.extend([
        {"timestamp": "t1", "endpoint": "/api/add_command", "method": "POST",
         "guild_id": MANAGED, "data": "{'token': 'mine'}", "ip": "10.0.0.1"},
        {"timestamp": "t2", "endpoint": "/api/add_command", "method": "POST",
         "guild_id": UNMANAGED, "data": "{'token': 'theirs'}", "ip": "10.0.0.2"},
    ])


def test_logs_are_scoped_to_the_callers_guild(logged_in):
    client, keep_alive, _calls = logged_in
    _seed_logs(keep_alive)

    resp = client.get(f"/api/logs?guild_id={MANAGED}", headers=_discord())
    assert resp.status_code == 200, resp.data
    body = resp.get_data(as_text=True)
    entries = resp.get_json()["logs"]

    assert len(entries) == 1
    # No other server's traffic, and no IP or request body for one's own.
    assert "theirs" not in body
    assert "10.0.0." not in body
    assert set(entries[0]) == {"timestamp", "endpoint", "method"}


def test_logs_refuse_a_guild_the_caller_does_not_manage(logged_in):
    client, keep_alive, _calls = logged_in
    _seed_logs(keep_alive)
    resp = client.get(f"/api/logs?guild_id={UNMANAGED}", headers=_discord())
    assert resp.status_code == 403


def test_operator_key_sees_full_log_entries(api_client):
    client, keep_alive = api_client
    _seed_logs(keep_alive)
    resp = client.get(f"/api/logs?guild_id={MANAGED}", headers=_operator(keep_alive))
    assert resp.status_code == 200
    entries = resp.get_json()["logs"]
    assert len(entries) == 2
    assert entries[0]["ip"] == "10.0.0.1"


def test_log_entries_record_their_guild(api_client):
    """Scoping only works if writes tag the entry with a guild."""
    client, keep_alive = api_client
    client.post(
        "/api/add_command",
        json={"guild_id": MANAGED, "command": "hi", "response": "there"},
        headers=_operator(keep_alive),
    )
    assert keep_alive.api_logs[-1]["guild_id"] == MANAGED


# ── Operator-only routes ─────────────────────────────────────────────────────
def test_stats_needs_the_operator_key(logged_in):
    """Cross-server totals are not a dashboard user's business."""
    client, _keep_alive, _calls = logged_in
    assert client.get("/api/stats", headers=_discord()).status_code == 401
    assert client.get("/api/stats").status_code == 401


def test_stats_answers_the_operator_key(api_client):
    client, keep_alive = api_client
    resp = client.get("/api/stats", headers=_operator(keep_alive))
    assert resp.status_code == 200
    assert "total_custom_commands" in resp.get_json()["stats"]


def test_verified_guilds_are_cached_per_token(api_client, monkeypatch):
    """One Discord round trip should serve a burst of dashboard calls."""
    client, keep_alive = api_client
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append(url)

        class _Resp:
            status_code = 200

            @staticmethod
            def json():
                return [{"id": MANAGED, "owner": True, "permissions": "0"}]

        return _Resp()

    monkeypatch.setattr(keep_alive.requests, "get", fake_get)
    keep_alive._guild_access_cache.clear()

    for _ in range(3):
        assert client.get(f"/api/config/{MANAGED}", headers=_discord("cache-me")).status_code == 200

    assert len(calls) == 1
    keep_alive._guild_access_cache.clear()


def test_manage_guild_permission_grants_access(api_client, monkeypatch):
    """Not just owners: the Manage Server bit is enough."""
    client, keep_alive = api_client

    def fake_get(url, headers=None, timeout=None):
        class _Resp:
            status_code = 200

            @staticmethod
            def json():
                return [
                    {"id": MANAGED, "owner": False, "permissions": str(0x20)},
                    {"id": UNMANAGED, "owner": False, "permissions": "0"},
                ]

        return _Resp()

    monkeypatch.setattr(keep_alive.requests, "get", fake_get)
    keep_alive._guild_access_cache.clear()

    assert client.get(f"/api/config/{MANAGED}", headers=_discord("perm")).status_code == 200
    assert client.get(f"/api/config/{UNMANAGED}", headers=_discord("perm")).status_code == 403
    keep_alive._guild_access_cache.clear()

"""Regression tests for the dashboard's welcome-channel settings.

These cover the bug where setting a welcome channel from the website appeared
to do nothing.
"""

import json


def _auth(keep_alive):
    return {"X-API-Key": keep_alive.API_KEY}


def test_set_welcome_channel_accepts_json(api_client):
    client, keep_alive = api_client
    resp = client.post(
        "/api/welcome_channel",
        json={"guild_id": "123", "channel_id": "456"},
        headers=_auth(keep_alive),
    )
    assert resp.status_code == 200, resp.data
    assert resp.get_json()["success"] is True
    # Stored under an int key, matching get_welcome_channel_id().
    assert keep_alive.welcome_channels[123] == 456


def test_set_welcome_channel_accepts_form_post(api_client):
    """The dashboard has posted form-encoded bodies; that used to raise a 415."""
    client, keep_alive = api_client
    resp = client.post(
        "/api/welcome_channel",
        data={"guild_id": "777", "channel_id": "888"},
        headers=_auth(keep_alive),
    )
    assert resp.status_code == 200, resp.data
    assert keep_alive.welcome_channels[777] == 888


def test_set_welcome_channel_rejects_missing_ids(api_client):
    client, keep_alive = api_client
    resp = client.post(
        "/api/welcome_channel", json={}, headers=_auth(keep_alive)
    )
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_set_welcome_channel_rejects_non_numeric(api_client):
    client, keep_alive = api_client
    resp = client.post(
        "/api/welcome_channel",
        json={"guild_id": "abc", "channel_id": "def"},
        headers=_auth(keep_alive),
    )
    assert resp.status_code == 400


def test_welcome_channel_survives_save_and_reload(api_client):
    """Int keys in memory, string keys on disk -- the round trip must hold."""
    client, keep_alive = api_client
    client.post(
        "/api/welcome_channel",
        json={"guild_id": "555", "channel_id": "666"},
        headers=_auth(keep_alive),
    )
    # Simulate a bot restart.
    keep_alive.welcome_channels.clear()
    keep_alive.load_all_data()
    assert keep_alive.get_welcome_channel_id(555) == 666
    assert keep_alive.get_welcome_channel_id("555") == 666


def test_get_welcome_channel_reads_back(api_client):
    client, keep_alive = api_client
    client.post(
        "/api/welcome_channel",
        json={"guild_id": "999", "channel_id": "111"},
        headers=_auth(keep_alive),
    )
    resp = client.get("/api/welcome_channel/999")
    assert resp.get_json()["channel_id"] == "111"


def test_channels_endpoint_reports_503_without_bot(api_client):
    """Without set_bot_instance() the picker cannot be populated; say so."""
    client, keep_alive = api_client
    keep_alive.bot_instance = None
    resp = client.get("/api/channels/123", headers=_auth(keep_alive))
    assert resp.status_code == 503
    assert "not connected" in resp.get_json()["error"].lower()


def test_channel_id_zero_clears_the_setting(api_client):
    """The dashboard's Remove button posts channel_id "0" to unset it."""
    client, keep_alive = api_client
    client.post(
        "/api/welcome_channel",
        json={"guild_id": "321", "channel_id": "654"},
        headers=_auth(keep_alive),
    )
    assert keep_alive.welcome_channels[321] == 654

    resp = client.post(
        "/api/welcome_channel",
        json={"guild_id": "321", "channel_id": "0"},
        headers=_auth(keep_alive),
    )
    assert resp.status_code == 200, resp.data
    body = resp.get_json()
    assert body["success"] is True
    assert body["channel_id"] is None
    assert 321 not in keep_alive.welcome_channels
    assert keep_alive.get_welcome_channel_id(321) is None


def test_clear_survives_reload(api_client):
    client, keep_alive = api_client
    client.post("/api/welcome_channel", json={"guild_id": "4", "channel_id": "5"},
                headers=_auth(keep_alive))
    client.post("/api/welcome_channel", json={"guild_id": "4", "channel_id": "0"},
                headers=_auth(keep_alive))
    keep_alive.load_all_data()
    assert keep_alive.get_welcome_channel_id(4) is None


def test_config_endpoint_exposes_welcome_channel(api_client):
    """The dashboard reads config.welcome_channel to render current state."""
    client, keep_alive = api_client
    client.post("/api/welcome_channel", json={"guild_id": "88", "channel_id": "99"},
                headers=_auth(keep_alive))
    resp = client.get("/api/config/88", headers=_auth(keep_alive))
    assert resp.status_code == 200, resp.data
    assert resp.get_json()["config"]["welcome_channel"] == 99

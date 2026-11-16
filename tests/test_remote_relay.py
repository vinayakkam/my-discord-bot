"""Tests for the GitPilot remote-control relay.

The relay is a blind router: it must move sealed blobs between two paired
devices and nothing more. These tests pin down the parts that protect the host
(caps, expiry, rate limits, the kill switch) and the parts that protect the
pairing (each side's secret can only poll its own mailbox).
"""

import pytest

import remote_relay


@pytest.fixture
def relay(monkeypatch):
    """A test client for the relay blueprint on its own throwaway Flask app."""
    from flask import Flask

    remote_relay.reset_for_tests()
    monkeypatch.setenv("REMOTE_RELAY_ENABLED", "1")
    app = Flask(__name__)
    app.register_blueprint(remote_relay.bp)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
    remote_relay.reset_for_tests()


def register(client):
    res = client.post("/remote/register")
    assert res.status_code == 200
    body = res.get_json()
    return body["id"], body["secret"], body["peerSecret"]


def send(client, cid, secret, body="sealed"):
    return client.post("/remote/send", json={"id": cid, "secret": secret, "body": body})


def poll(client, cid, secret, since=0):
    return client.get(f"/remote/poll?id={cid}&secret={secret}&since={since}")


# ── Routing ──────────────────────────────────────────────────────────────────

def test_register_gives_two_distinct_secrets(relay):
    cid, secret, peer = register(relay)
    assert cid and secret and peer
    assert secret != peer
    # Second registration is a different channel.
    other_id, _, _ = register(relay)
    assert other_id != cid


def test_phone_sends_and_pc_polls(relay):
    cid, secret, peer = register(relay)
    assert send(relay, cid, peer, "command-blob").get_json()["n"] == 1

    got = poll(relay, cid, secret).get_json()
    assert [m["body"] for m in got["messages"]] == ["command-blob"]
    assert got["last"] == 1


def test_pc_sends_and_phone_polls(relay):
    cid, secret, peer = register(relay)
    send(relay, cid, secret, "result-blob")

    assert [m["body"] for m in poll(relay, cid, peer).get_json()["messages"]] == ["result-blob"]


def test_a_side_cannot_read_what_it_wrote(relay):
    """The phone writes into the PC's mailbox, so polling its own finds nothing."""
    cid, secret, peer = register(relay)
    send(relay, cid, peer, "command-blob")

    assert poll(relay, cid, peer).get_json()["messages"] == []
    # Still waiting for the PC.
    assert len(poll(relay, cid, secret).get_json()["messages"]) == 1


def test_polling_deletes_messages(relay):
    cid, secret, peer = register(relay)
    send(relay, cid, peer, "once")

    assert len(poll(relay, cid, secret).get_json()["messages"]) == 1
    assert poll(relay, cid, secret).get_json()["messages"] == []


def test_since_filters_a_racing_retry(relay):
    cid, secret, peer = register(relay)
    send(relay, cid, peer, "first")
    send(relay, cid, peer, "second")

    got = poll(relay, cid, secret, since=1).get_json()
    assert [m["body"] for m in got["messages"]] == ["second"]
    assert got["last"] == 2


def test_sequence_numbers_rise_per_mailbox(relay):
    cid, secret, peer = register(relay)
    assert send(relay, cid, peer).get_json()["n"] == 1
    assert send(relay, cid, peer).get_json()["n"] == 2
    # The other direction counts on its own.
    assert send(relay, cid, secret).get_json()["n"] == 1


def test_channels_are_isolated(relay):
    first, first_secret, first_peer = register(relay)
    second, second_secret, _ = register(relay)
    send(relay, first, first_peer, "for-the-first-pc")

    assert poll(relay, second, second_secret).get_json()["messages"] == []
    assert len(poll(relay, first, first_secret).get_json()["messages"]) == 1


# ── Authorization ────────────────────────────────────────────────────────────

def test_wrong_secret_is_refused(relay):
    cid, _secret, _peer = register(relay)
    assert send(relay, cid, "not-the-secret").status_code == 403
    assert poll(relay, cid, "not-the-secret").status_code == 403


def test_unknown_id_is_refused(relay):
    _cid, secret, _peer = register(relay)
    assert send(relay, "no-such-channel", secret).status_code == 404
    assert poll(relay, "no-such-channel", secret).status_code == 404


def test_missing_fields_are_refused(relay):
    cid, secret, _peer = register(relay)
    assert relay.post("/remote/send", json={"id": cid}).status_code == 400
    assert relay.post("/remote/send", json={"id": cid, "secret": secret}).status_code == 400
    assert relay.get("/remote/poll?id=" + cid).status_code == 400
    assert poll(relay, cid, secret, since="abc").status_code == 400


def test_unregister_drops_the_channel(relay):
    cid, secret, peer = register(relay)
    send(relay, cid, peer, "pending")

    assert relay.post("/remote/unregister", json={"id": cid, "secret": "wrong"}).status_code == 403
    assert relay.post("/remote/unregister", json={"id": cid, "secret": secret}).status_code == 200
    assert poll(relay, cid, secret).status_code == 404
    # Unregistering twice is not an error: the phone may retry.
    assert relay.post("/remote/unregister", json={"id": cid, "secret": secret}).status_code == 200
    assert remote_relay._queued_bytes == 0


# ── Claiming a known channel (pairing that survives a restart) ────────────────

def claim(client, cid="chan-abcdefghijklmno", secret="pc-secret-abcdefghij", peer="phone-secret-abcdef"):
    return client.post("/remote/register", json={"id": cid, "secret": secret, "peerSecret": peer})


def test_a_pair_can_put_its_own_channel_back(relay):
    """The whole point: the relay forgets everything on restart, the pairing must not."""
    res = claim(relay)
    assert res.status_code == 200
    body = res.get_json()
    assert body["id"] == "chan-abcdefghijklmno"
    assert body["restored"] is True

    # It works straight away, with the secrets both sides derived for themselves.
    send(relay, "chan-abcdefghijklmno", "phone-secret-abcdef", "command")
    got = poll(relay, "chan-abcdefghijklmno", "pc-secret-abcdefghij").get_json()
    assert [m["body"] for m in got["messages"]] == ["command"]


def test_claiming_the_same_channel_twice_is_harmless(relay):
    claim(relay)
    send(relay, "chan-abcdefghijklmno", "phone-secret-abcdef", "waiting")

    # Both sides may claim at once after a restart; the second must not wipe the first.
    assert claim(relay).status_code == 200
    got = poll(relay, "chan-abcdefghijklmno", "pc-secret-abcdefghij").get_json()
    assert len(got["messages"]) == 1


def test_a_channel_cannot_be_taken_from_its_owners(relay):
    claim(relay)

    stolen = claim(relay, secret="attacker-secretxxxxx", peer="attacker-peerxxxxxxx")

    assert stolen.status_code == 403
    # And the real pair still works.
    assert send(relay, "chan-abcdefghijklmno", "phone-secret-abcdef").status_code == 200


def test_claimed_values_have_to_look_like_secrets(relay):
    assert claim(relay, cid="short").status_code == 400
    assert claim(relay, secret="short").status_code == 400
    assert claim(relay, cid="has spaces and !!").status_code == 400
    assert claim(relay, cid="x" * 65).status_code == 400
    # Reusing one value for both roles would let either side drain its own queue.
    assert claim(relay, secret="same-secret-aaaaaaaa", peer="same-secret-aaaaaaaa").status_code == 400


def test_registering_without_a_body_still_invents_everything(relay):
    cid, secret, peer = register(relay)

    assert cid and secret != peer
    assert relay.post("/remote/register").get_json()["restored"] is False


# ── Presence (is the computer on?) ───────────────────────────────────────────

def test_presence_says_when_the_other_side_last_looked(relay):
    cid, secret, peer = register(relay)

    # Nobody has polled yet.
    assert relay.get(f"/remote/presence?id={cid}&secret={peer}").get_json()["peerSeen"] is None

    poll(relay, cid, secret)  # the computer checks for commands

    seen = relay.get(f"/remote/presence?id={cid}&secret={peer}").get_json()["peerSeen"]
    assert seen is not None and seen < 5


def test_polling_reports_the_other_side_too(relay):
    cid, secret, peer = register(relay)
    relay.get(f"/remote/presence?id={cid}&secret={peer}")  # the phone is open

    assert poll(relay, cid, secret).get_json()["peerSeen"] is not None


def test_presence_needs_the_right_secret_and_channel(relay):
    cid, _secret, _peer = register(relay)

    assert relay.get(f"/remote/presence?id={cid}&secret=wrong").status_code == 403
    assert relay.get("/remote/presence?id=nosuch&secret=x").status_code == 404
    assert relay.get("/remote/presence").status_code == 400


def test_presence_is_rate_limited_like_everything_else(relay, monkeypatch):
    cid, secret, _peer = register(relay)
    monkeypatch.setattr(remote_relay, "CALLS_PER_CHANNEL", 1)

    assert relay.get(f"/remote/presence?id={cid}&secret={secret}").status_code == 200
    assert relay.get(f"/remote/presence?id={cid}&secret={secret}").status_code == 429


# ── Host protection ──────────────────────────────────────────────────────────

def test_oversized_body_is_refused(relay):
    cid, _secret, peer = register(relay)
    too_big = "x" * (remote_relay.MAX_BODY_BYTES + 1)

    assert send(relay, cid, peer, too_big).status_code == 413
    assert remote_relay._queued_bytes == 0


def test_mailbox_keeps_only_the_newest_messages(relay):
    cid, secret, peer = register(relay)
    for i in range(remote_relay.MAX_MSGS_PER_BOX + 5):
        send(relay, cid, peer, f"m{i}")

    bodies = [m["body"] for m in poll(relay, cid, secret).get_json()["messages"]]
    assert len(bodies) == remote_relay.MAX_MSGS_PER_BOX
    assert bodies[0] == "m5"  # the first five were dropped
    assert bodies[-1] == f"m{remote_relay.MAX_MSGS_PER_BOX + 4}"


def test_global_cap_drops_the_oldest_message(relay, monkeypatch):
    monkeypatch.setattr(remote_relay, "GLOBAL_MAX_BYTES", 300)
    first, first_secret, first_peer = register(relay)
    second, second_secret, second_peer = register(relay)

    send(relay, first, first_peer, "a" * 200)
    send(relay, second, second_peer, "b" * 200)  # needs room: drops the first

    assert poll(relay, first, first_secret).get_json()["messages"] == []
    assert len(poll(relay, second, second_secret).get_json()["messages"]) == 1
    assert remote_relay._queued_bytes == 0


def test_queued_bytes_returns_to_zero_after_a_poll(relay):
    cid, secret, peer = register(relay)
    send(relay, cid, peer, "y" * 1000)
    assert remote_relay._queued_bytes == 1000

    poll(relay, cid, secret)
    assert remote_relay._queued_bytes == 0


def test_stale_messages_expire(relay, monkeypatch):
    cid, secret, peer = register(relay)
    send(relay, cid, peer, "too-old")

    clock = [remote_relay._now() + remote_relay.MSG_TTL + 1]
    monkeypatch.setattr(remote_relay, "_now", lambda: clock[0])

    assert poll(relay, cid, secret).get_json()["messages"] == []
    assert remote_relay._queued_bytes == 0


def test_a_channel_nobody_polls_is_dropped(relay, monkeypatch):
    cid, secret, peer = register(relay)
    send(relay, cid, peer, "abandoned")

    clock = [remote_relay._now() + remote_relay.CHANNEL_TTL + 1]
    monkeypatch.setattr(remote_relay, "_now", lambda: clock[0])

    assert poll(relay, cid, secret).status_code == 404
    assert remote_relay._queued_bytes == 0


def test_registration_is_rate_limited_per_ip(relay, monkeypatch):
    monkeypatch.setattr(remote_relay, "REGISTER_PER_IP", 3)
    for _ in range(3):
        assert relay.post("/remote/register").status_code == 200

    assert relay.post("/remote/register").status_code == 429


def test_calls_are_rate_limited_per_channel(relay, monkeypatch):
    cid, secret, peer = register(relay)
    monkeypatch.setattr(remote_relay, "CALLS_PER_CHANNEL", 2)

    assert send(relay, cid, peer).status_code == 200
    assert poll(relay, cid, secret).status_code == 200
    assert send(relay, cid, peer).status_code == 429


def test_relay_full_is_refused(relay, monkeypatch):
    monkeypatch.setattr(remote_relay, "MAX_CHANNELS", 1)
    register(relay)

    assert relay.post("/remote/register").status_code == 503


def test_kill_switch_turns_every_endpoint_off(relay, monkeypatch):
    cid, secret, peer = register(relay)
    monkeypatch.setenv("REMOTE_RELAY_ENABLED", "0")

    assert relay.post("/remote/register").status_code == 503
    assert relay.get(f"/remote/presence?id={cid}&secret={secret}").status_code == 503
    assert send(relay, cid, peer).status_code == 503
    assert poll(relay, cid, secret).status_code == 503
    assert relay.post("/remote/unregister", json={"id": cid, "secret": secret}).status_code == 503


def test_health_reports_counts_only(relay):
    cid, _secret, peer = register(relay)
    send(relay, cid, peer, "z" * 50)

    body = relay.get("/remote/health").get_json()
    assert body["channels"] == 1
    assert body["queuedBytes"] == 50
    assert body["limits"]["maxBodyBytes"] == remote_relay.MAX_BODY_BYTES
    # No id, secret or payload anywhere in the answer.
    assert cid not in relay.get("/remote/health").get_data(as_text=True)


def test_relay_is_registered_on_the_real_app():
    """keep_alive.py must mount the blueprint, or nothing above is reachable."""
    import keep_alive

    rules = {str(rule) for rule in keep_alive.app.url_map.iter_rules()}
    assert "/remote/register" in rules
    assert "/remote/send" in rules
    assert "/remote/poll" in rules
    assert "/remote/unregister" in rules

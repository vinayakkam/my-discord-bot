"""GitPilot remote-control relay.

A blind message router between two devices that have already paired out of band
(a QR code shown on the PC, scanned by the phone). The relay never sees anything
readable: every body it stores is a sealed envelope whose key lives only on the
two devices. It routes opaque blobs and forgets them.

Because of that, the code can be public. The only thing an attacker who knows an
id can do is waste bandwidth or drop a queue -- never read, forge or replay a
command -- so everything here is about staying small and bounded rather than
about secrecy.

Hard rules for this host (EnderCloud, 720 MiB RAM, 3 GiB disk):

* no new pip packages -- Flask and the standard library only
* no database and no disk writes: state is in memory and is meant to be lost
* no WebSocket and no long-poll: either would pin a worker thread per device
* a global ceiling on queued bytes, so this feature cannot grow into the box
* no payload, id or secret ever reaches a log

Protocol
--------

One registration is one *pairing channel* with two mailboxes: ``pc`` (messages
waiting for the computer) and ``phone`` (messages waiting for the phone). Each
side proves which end of the channel it is with its own secret:

    POST /remote/register   -> {id, secret, peer_secret}   (optionally claiming known ones)
    POST /remote/send       {id, secret, body}        -> {ok, n}
    GET  /remote/poll       ?id=&secret=&since=       -> {ok, messages, last, peerSeen}
    GET  /remote/presence   ?id=&secret=               -> {ok, peerSeen}
    POST /remote/unregister {id, secret}              -> {ok}

``secret`` identifies the sender's role: the computer keeps ``secret``, the phone
gets ``peer_secret`` in the QR code. A side always *sends into the other side's
mailbox* and *polls its own*, so one secret can never drain the queue it writes
to. ``since`` is the last sequence number the caller has already seen; polled
messages are deleted, so it only matters when a reply races a retry.

Everything here is in memory, so a restart forgets every channel -- and a channel
nobody polls for an hour is dropped on purpose. That used to mean a phone had to
be paired again after the computer was off overnight. So ``register`` also takes
an id and its two secrets: a paired phone and computer both derive those from the
pairing key only they share, and either side can put the channel back exactly as
it was. Claiming an id that already exists with the same secrets is a no-op; with
different ones it is refused, so a channel can never be taken from its owners.
"""

from __future__ import annotations

import os
import secrets
import time
from threading import Lock

from flask import Blueprint, jsonify, request

# ── Limits ────────────────────────────────────────────────────────────────────
# Sized so the whole feature cannot hold more than GLOBAL_MAX_BYTES of payload:
# a command or a status snapshot is a few KiB, so 16 waiting messages is already
# generous for a phone that has been offline for a minute.

MAX_BODY_BYTES = 64 * 1024        # one sealed envelope
MAX_MSGS_PER_BOX = 16             # oldest dropped past this
GLOBAL_MAX_BYTES = 2 * 1024 * 1024  # everything queued, all channels together
MAX_CHANNELS = 256                # registrations held at once

MSG_TTL = 300                     # 5 min: a command older than this is stale
CHANNEL_TTL = 3600                # 1 h without a poll and the channel is gone

REGISTER_PER_IP = 10              # registrations ...
REGISTER_WINDOW = 3600            # ... per hour per IP
CALLS_PER_CHANNEL = 600           # send+poll calls ...
CALLS_WINDOW = 60                 # ... per minute per channel (3 s polling = 20)

# ── State ─────────────────────────────────────────────────────────────────────
# _channels: id -> {
#     "secret": str, "peer_secret": str, "created": float, "seen": float,
#     "boxes": {"pc": [(n, bytes, stamp)], "phone": [...]},
#     "next": {"pc": int, "phone": int},
#     "polled": {"pc": float|None, "phone": float|None},
# }
#
# "polled" is how each side knows the other is there: the computer polls every few seconds while
# remote control is on, so a recent poll means GitPilot is running. It is a timestamp, never an
# address or anything identifying.
# All of it is rebuilt from scratch after a restart; the devices re-pair nothing,
# they just see one failed call. _lock guards every mutation; the critical
# sections are a few dict operations long.

_lock = Lock()
_channels: dict[str, dict] = {}
_queued_bytes = 0
_rate: dict[str, tuple[float, int]] = {}  # key -> (window start, calls)

MAILBOXES = ("pc", "phone")

bp = Blueprint("remote_relay", __name__)


def _enabled() -> bool:
    """The kill switch: turns this feature off without touching the bot."""
    return os.getenv("REMOTE_RELAY_ENABLED", "1") not in ("0", "false", "False")


def _now() -> float:
    return time.time()


def _client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "?"


def _rate_ok(key: str, limit: int, window: int) -> bool:
    """Fixed-window counter. Called with _lock held."""
    now = _now()
    start, count = _rate.get(key, (now, 0))
    if now - start >= window:
        _rate[key] = (now, 1)
        return True
    if count >= limit:
        return False
    _rate[key] = (start, count + 1)
    return True


def _prune(now: float) -> None:
    """Drop stale messages and dead channels. Called with _lock held."""
    global _queued_bytes
    for cid in list(_channels):
        channel = _channels[cid]
        if now - channel["seen"] > CHANNEL_TTL:
            for box in MAILBOXES:
                for _, body, _stamp in channel["boxes"][box]:
                    _queued_bytes -= len(body)
            del _channels[cid]
            continue
        for box in MAILBOXES:
            kept = []
            for n, body, stamp in channel["boxes"][box]:
                if now - stamp > MSG_TTL:
                    _queued_bytes -= len(body)
                else:
                    kept.append((n, body, stamp))
            channel["boxes"][box] = kept
    if len(_rate) > 4096:  # pathological: forget the window and start over
        _rate.clear()


def _role(channel: dict, secret: str) -> str | None:
    """Which end of the channel this secret is, if any."""
    if secrets.compare_digest(secret, channel["secret"]):
        return "pc"
    if secrets.compare_digest(secret, channel["peer_secret"]):
        return "phone"
    return None


def _other(role: str) -> str:
    return "phone" if role == "pc" else "pc"


def _peer_seen(channel: dict, role: str, now: float):
    """Seconds since the other side last looked for messages, or None if it never has."""
    when = channel.get("polled", {}).get(_other(role))
    return None if when is None else round(now - when, 1)


def _body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _fail(status: int, error: str):
    return jsonify({"ok": False, "error": error}), status


# ── Endpoints ─────────────────────────────────────────────────────────────────

def _valid_token(value, name):
    """A client-chosen id or secret: printable, unguessable, and not enormous."""
    if not isinstance(value, str):
        return f"{name} must be text"
    if not 16 <= len(value) <= 64:
        return f"{name} must be 16 to 64 characters"
    if not all(c.isalnum() or c in "-_" for c in value):
        return f"{name} may only contain letters, digits, - and _"
    return None


@bp.route("/remote/register", methods=["POST"])
def register():
    """
    Open a pairing channel, or put a known one back.

    With no body the relay invents the id and both secrets: that is a first pairing, where the
    computer has nothing to go on yet. With ``{id, secret, peerSecret}`` it claims exactly those,
    which is how a paired pair rebuilds its channel after this process restarted or the channel
    went idle -- both sides derive the same three values from their pairing key.
    """
    if not _enabled():
        return _fail(503, "disabled")
    ip = _client_ip()
    data = _body()
    claimed = any(k in data for k in ("id", "secret", "peerSecret"))

    if claimed:
        cid = data.get("id")
        secret = data.get("secret")
        peer = data.get("peerSecret")
        for value, name in ((cid, "id"), (secret, "secret"), (peer, "peerSecret")):
            problem = _valid_token(value, name)
            if problem:
                return _fail(400, problem)
        if secret == peer:
            return _fail(400, "the two secrets must differ")

    with _lock:
        now = _now()
        _prune(now)
        if not _rate_ok(f"reg:{ip}", REGISTER_PER_IP, REGISTER_WINDOW):
            return _fail(429, "too many registrations")

        if claimed:
            existing = _channels.get(cid)
            if existing is not None:
                # Already there. Only the pair that owns it may say so.
                if not (
                    secrets.compare_digest(secret, existing["secret"])
                    and secrets.compare_digest(peer, existing["peer_secret"])
                ):
                    return _fail(403, "that channel belongs to someone else")
                existing["seen"] = now
                return jsonify({"ok": True, "id": cid, "secret": secret, "peerSecret": peer, "restored": False})
        else:
            cid = secrets.token_urlsafe(12)
            secret = secrets.token_urlsafe(24)
            peer = secrets.token_urlsafe(24)

        if len(_channels) >= MAX_CHANNELS:
            return _fail(503, "relay full")
        _channels[cid] = {
            "secret": secret,
            "peer_secret": peer,
            "created": now,
            "seen": now,
            "boxes": {box: [] for box in MAILBOXES},
            "next": {box: 1 for box in MAILBOXES},
            "polled": {box: None for box in MAILBOXES},
        }
        return jsonify({"ok": True, "id": cid, "secret": secret, "peerSecret": peer, "restored": claimed})


@bp.route("/remote/send", methods=["POST"])
def send():
    """Append one sealed envelope to the *other* side's mailbox."""
    if not _enabled():
        return _fail(503, "disabled")
    data = _body()
    cid = data.get("id")
    secret = data.get("secret")
    body = data.get("body")
    if not isinstance(cid, str) or not isinstance(secret, str) or not isinstance(body, str):
        return _fail(400, "id, secret and body are required")
    raw = body.encode("utf-8", "replace")
    if len(raw) > MAX_BODY_BYTES:
        return _fail(413, "message too large")

    global _queued_bytes
    with _lock:
        now = _now()
        _prune(now)
        channel = _channels.get(cid)
        if channel is None:
            return _fail(404, "unknown id")
        if not _rate_ok(f"ch:{cid}", CALLS_PER_CHANNEL, CALLS_WINDOW):
            return _fail(429, "too many calls")
        role = _role(channel, secret)
        if role is None:
            return _fail(403, "wrong secret")

        box = channel["boxes"][_other(role)]
        while len(box) >= MAX_MSGS_PER_BOX:
            _queued_bytes -= len(box.pop(0)[1])
        while _queued_bytes + len(raw) > GLOBAL_MAX_BYTES:
            if not _drop_oldest_locked():
                return _fail(503, "relay full")

        n = channel["next"][_other(role)]
        channel["next"][_other(role)] = n + 1
        box.append((n, raw, now))
        _queued_bytes += len(raw)
        channel["seen"] = now
        return jsonify({"ok": True, "n": n})


def _drop_oldest_locked() -> bool:
    """Make room at the global cap by dropping the oldest message anywhere."""
    global _queued_bytes
    oldest = None
    for channel in _channels.values():
        for box in MAILBOXES:
            if channel["boxes"][box]:
                candidate = (channel["boxes"][box][0][2], channel, box)
                if oldest is None or candidate[0] < oldest[0]:
                    oldest = candidate
    if oldest is None:
        return False
    _, channel, box = oldest
    _queued_bytes -= len(channel["boxes"][box].pop(0)[1])
    return True


@bp.route("/remote/poll", methods=["GET"])
def poll():
    """Take everything waiting in the caller's own mailbox."""
    if not _enabled():
        return _fail(503, "disabled")
    cid = request.args.get("id", "")
    secret = request.args.get("secret", "")
    try:
        since = int(request.args.get("since", "0"))
    except ValueError:
        return _fail(400, "since must be a number")
    if not cid or not secret:
        return _fail(400, "id and secret are required")

    global _queued_bytes
    with _lock:
        now = _now()
        _prune(now)
        channel = _channels.get(cid)
        if channel is None:
            return _fail(404, "unknown id")
        if not _rate_ok(f"ch:{cid}", CALLS_PER_CHANNEL, CALLS_WINDOW):
            return _fail(429, "too many calls")
        role = _role(channel, secret)
        if role is None:
            return _fail(403, "wrong secret")

        channel["seen"] = now
        channel.setdefault("polled", {})[role] = now
        messages = []
        last = since
        for n, raw, _stamp in channel["boxes"][role]:
            _queued_bytes -= len(raw)
            if n > since:
                messages.append({"n": n, "body": raw.decode("utf-8", "replace")})
                last = max(last, n)
        channel["boxes"][role] = []
        return jsonify({
            "ok": True,
            "messages": messages,
            "last": last,
            "peerSeen": _peer_seen(channel, role, now),
        })


@bp.route("/remote/presence", methods=["GET"])
def presence():
    """
    How long ago the other side looked for messages.

    The phone asks this to show whether the computer is on: GitPilot polls every few seconds while
    remote control is on, so a recent poll means it is running and reachable. It is far cheaper
    than sending a command just to find out, which matters on a small host -- nothing is queued,
    nothing is read, nothing is written but one timestamp.
    """
    if not _enabled():
        return _fail(503, "disabled")
    cid = request.args.get("id", "")
    secret = request.args.get("secret", "")
    if not cid or not secret:
        return _fail(400, "id and secret are required")

    with _lock:
        now = _now()
        channel = _channels.get(cid)
        if channel is None:
            return _fail(404, "unknown id")
        if not _rate_ok(f"ch:{cid}", CALLS_PER_CHANNEL, CALLS_WINDOW):
            return _fail(429, "too many calls")
        role = _role(channel, secret)
        if role is None:
            return _fail(403, "wrong secret")
        # Asking counts as being here, so the other side sees this one too.
        channel.setdefault("polled", {})[role] = now
        channel["seen"] = now
        return jsonify({"ok": True, "peerSeen": _peer_seen(channel, role, now)})


@bp.route("/remote/unregister", methods=["POST"])
def unregister():
    """Forget a channel: the phone has been removed in GitPilot's settings."""
    if not _enabled():
        return _fail(503, "disabled")
    data = _body()
    cid = data.get("id")
    secret = data.get("secret")
    if not isinstance(cid, str) or not isinstance(secret, str):
        return _fail(400, "id and secret are required")

    global _queued_bytes
    with _lock:
        channel = _channels.get(cid)
        if channel is None:
            return jsonify({"ok": True})  # already gone; nothing to say
        if _role(channel, secret) is None:
            return _fail(403, "wrong secret")
        for box in MAILBOXES:
            for _, raw, _stamp in channel["boxes"][box]:
                _queued_bytes -= len(raw)
        del _channels[cid]
        return jsonify({"ok": True})


@bp.route("/remote/health", methods=["GET"])
def health():
    """Counts only -- no ids, no bodies. Useful when the phone can't connect."""
    with _lock:
        return jsonify({
            "ok": True,
            "enabled": _enabled(),
            "channels": len(_channels),
            "queuedBytes": _queued_bytes,
            "limits": {
                "maxBodyBytes": MAX_BODY_BYTES,
                "maxMessagesPerMailbox": MAX_MSGS_PER_BOX,
                "globalMaxBytes": GLOBAL_MAX_BYTES,
                "maxChannels": MAX_CHANNELS,
                "messageTtlSeconds": MSG_TTL,
                "channelTtlSeconds": CHANNEL_TTL,
            },
        })


def reset_for_tests() -> None:
    """Drop all state. Tests only -- nothing in the app calls this."""
    global _queued_bytes
    with _lock:
        _channels.clear()
        _rate.clear()
        _queued_bytes = 0

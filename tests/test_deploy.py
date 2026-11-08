"""Tests for the webhook deploy.

A deploy used to run `git pull`, which aborted every time because the bot
rewrites tracked config files while it runs. It resets onto the remote branch
instead -- and because the reset discards whatever is not in that commit, the
pieces that protect the host's runtime state are what matter most here:

* `_snapshot_runtime_state()` copies config/ and data/ aside first;
* `_restore_runtime_state()` puts back files the reset deleted, but only the
  ones git now ignores. `data/` was tracked once, so the first deploy after it
  was untracked would otherwise have wiped the host's live galaxy saves.
"""

import os
import subprocess

import pytest


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)


@pytest.fixture
def checkout(tmp_path, monkeypatch, api_client):
    """A real git repo laid out like the host's checkout, as the cwd."""
    _client, keep_alive = api_client

    repo = tmp_path / "checkout"
    (repo / "config").mkdir(parents=True)
    (repo / "data").mkdir()
    (repo / "persistent").mkdir()

    # data/ is ignored, config/ is not -- the arrangement this all turns on.
    (repo / ".gitignore").write_text("/data/\npersistent/\n__pycache__/\n", encoding="utf-8")
    (repo / "config" / "guild_commands.json").write_text('{"1": {}}', encoding="utf-8")
    (repo / "data" / "galaxy_data.json").write_text('{"42": {"credits": 4242}}', encoding="utf-8")

    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "test")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")

    monkeypatch.chdir(repo)
    # The module's paths are relative, so they resolve against this cwd.
    monkeypatch.setattr(keep_alive, "PRE_DEPLOY_DIR", os.path.join("persistent", "pre_deploy"))
    return repo, keep_alive


def test_snapshot_copies_config_and_data(checkout):
    repo, keep_alive = checkout

    snapshot, copied = keep_alive._snapshot_runtime_state()

    assert snapshot is not None
    assert copied == 2
    assert os.path.isfile(os.path.join(snapshot, "config", "guild_commands.json"))
    assert os.path.isfile(os.path.join(snapshot, "data", "galaxy_data.json"))


def test_restore_puts_back_an_ignored_file_the_reset_removed(checkout):
    """The galaxy saves must survive a deploy that stops tracking them."""
    repo, keep_alive = checkout
    snapshot, _copied = keep_alive._snapshot_runtime_state()

    live = repo / "data" / "galaxy_data.json"
    live.unlink()                      # what reset --hard does to an untracked-now path
    assert not live.exists()

    keep_alive._restore_runtime_state(snapshot)

    assert live.exists(), "the host's galaxy saves were not restored"
    assert '"credits": 4242' in live.read_text(encoding="utf-8")


def test_restore_leaves_a_tracked_file_deleted(checkout):
    """A config file deliberately removed upstream must stay removed."""
    repo, keep_alive = checkout
    snapshot, _copied = keep_alive._snapshot_runtime_state()

    tracked = repo / "config" / "guild_commands.json"
    tracked.unlink()

    keep_alive._restore_runtime_state(snapshot)

    assert not tracked.exists(), "resurrected a tracked file the reset removed"


def test_restore_does_not_overwrite_a_surviving_file(checkout):
    """Whatever the reset left in place is newer than the snapshot."""
    repo, keep_alive = checkout
    snapshot, _copied = keep_alive._snapshot_runtime_state()

    live = repo / "data" / "galaxy_data.json"
    live.write_text('{"42": {"credits": 99999}}', encoding="utf-8")

    keep_alive._restore_runtime_state(snapshot)

    assert '"credits": 99999' in live.read_text(encoding="utf-8")


def test_restore_is_safe_without_a_snapshot(checkout):
    """A failed snapshot must not take the deploy down with it."""
    _repo, keep_alive = checkout
    keep_alive._restore_runtime_state(None)
    keep_alive._restore_runtime_state("persistent/pre_deploy/does-not-exist")


def test_snapshots_are_pruned(checkout):
    """The host has a small disk."""
    _repo, keep_alive = checkout
    monkey_keep = 3
    original = keep_alive.KEEP_PRE_DEPLOY_SNAPSHOTS
    keep_alive.KEEP_PRE_DEPLOY_SNAPSHOTS = monkey_keep
    try:
        made = []
        for i in range(6):
            # The directory name is second-resolution, so force distinct ones.
            target = os.path.join(keep_alive.PRE_DEPLOY_DIR, f"2026010{i}-000000")
            os.makedirs(target, exist_ok=True)
            made.append(target)
        keep_alive._prune_pre_deploy_snapshots()
        remaining = sorted(os.listdir(keep_alive.PRE_DEPLOY_DIR))
        assert len(remaining) == monkey_keep
        # The newest are the ones kept.
        assert remaining == sorted(os.path.basename(m) for m in made)[-monkey_keep:]
    finally:
        keep_alive.KEEP_PRE_DEPLOY_SNAPSHOTS = original


def test_clean_pycache_removes_compiled_files(checkout):
    repo, keep_alive = checkout
    cache = repo / "olit" / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "stale.cpython-313.pyc").write_bytes(b"\x00")

    keep_alive._clean_pycache()

    assert not cache.exists()


def test_deploy_records_its_outcome(checkout):
    """The restart is how a deploy ends, so the result has to be on disk."""
    _repo, keep_alive = checkout
    keep_alive._record_deploy("failed", "git fetch failed: boom", None)

    recorded = keep_alive.load_last_deploy()
    assert recorded["status"] == "failed"
    assert "boom" in recorded["detail"]


def test_deploy_aborts_outside_a_git_checkout(tmp_path, monkeypatch, api_client):
    """No git repo means no deploy, and no os._exit either."""
    _client, keep_alive = api_client
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(keep_alive, "PRE_DEPLOY_DIR", os.path.join("persistent", "pre_deploy"))
    monkeypatch.setattr(keep_alive, "LAST_DEPLOY_FILE",
                        os.path.join("persistent", "last_deploy.json"))

    def boom(code):
        raise AssertionError("deploy exited the process after aborting")

    monkeypatch.setattr(keep_alive.os, "_exit", boom)

    keep_alive.deploy_and_restart()

    assert keep_alive.load_last_deploy()["status"] == "failed"


def test_deploy_does_not_run_git_pull():
    """Regression: `git pull` is what aborted on every modified runtime file."""
    import ast
    import inspect

    import keep_alive

    tree = ast.parse(inspect.getsource(keep_alive.deploy_and_restart))
    args = [
        a.value for node in ast.walk(tree) if isinstance(node, ast.Call)
        for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)
    ]
    assert "pull" not in args, "the deploy runs git pull again"
    assert "fetch" in args and "reset" in args

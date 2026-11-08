"""Tests for galaxy save handling and the reset commands.

There is deliberately no backup feature here any more. The saves were once
mirrored off-host because Render's filesystem was ephemeral and a redeploy
wiped them. The current host keeps its disk, and mirroring them into git is
what left the checkout permanently modified so every `git pull` deploy aborted
with "your local changes would be overwritten by merge".

`data/` is untracked now, like `persistent/`: the saves live on the host and
nothing copies them anywhere. Config files are a separate matter -- the
dashboard still commits `config/` through the GitHub Contents API, and that is
tested in tests/test_api_auth.py and tests/test_api_welcome.py.
"""

import sys
import types

import pytest


@pytest.fixture
def galaxy(tmp_path, monkeypatch):
    """galaxy_keeper pointed at a temp data dir."""
    # A stub keep_alive, so importing the Flask module cannot reach the real
    # one, and so any call to commit_to_github from here is observable.
    uploads = []

    def fake_commit(path, content, message):
        uploads.append(path)
        return True, f"{path} committed"

    fake_keep_alive = types.ModuleType("keep_alive")
    fake_keep_alive.commit_to_github = fake_commit
    monkeypatch.setitem(sys.modules, "keep_alive", fake_keep_alive)

    import galaxy_keeper as g

    monkeypatch.setattr(g, "_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(g, "GALAXY_FILE", str(tmp_path / "galaxy_data.json"))
    monkeypatch.setattr(g, "WORLD_FILE", str(tmp_path / "world_data.json"))
    monkeypatch.setattr(g, "SCORES_FILE", str(tmp_path / "galaxy_scores.json"))
    monkeypatch.setattr(g, "_galaxy", {"1": {"credits": 150}})
    monkeypatch.setattr(g, "_world", {})

    g._uploads = uploads
    return g, uploads


# ── The backup feature must stay gone ────────────────────────────────────────
def test_no_backup_machinery_remains():
    """Re-adding this is what put data/ back in git and broke deploys."""
    import galaxy_keeper as g

    for attr in ("_backup_saves", "daily_galaxy_backup", "_BACKUP_TARGETS",
                 "_BACKUP_STATE_FILE", "_BACKUP_DIR", "_git_push"):
        assert not hasattr(g, attr), f"the galaxy backup is back: {attr}"


def test_galaxy_does_not_upload_saves_or_shell_out():
    """Checked against the parsed module, so prose about the old behaviour is fine."""
    import ast
    import inspect

    import galaxy_keeper as g

    tree = ast.parse(inspect.getsource(g))

    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "subprocess" not in imported, "galaxy_keeper imports subprocess again"

    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # subprocess.<anything>(...)
        if getattr(getattr(node.func, "value", None), "id", None) == "subprocess":
            bad.append("subprocess call")
        # commit_to_github(...) or <mod>.commit_to_github(...)
        if (getattr(node.func, "id", None) == "commit_to_github"
                or getattr(node.func, "attr", None) == "commit_to_github"):
            bad.append("commit_to_github call")
    assert not bad, f"the off-host save backup is back: {sorted(set(bad))}"


def test_saving_does_not_upload_anything(galaxy):
    g, uploads = galaxy
    g._save_all()
    assert uploads == [], "saving a galaxy file sent it to the GitHub API"


def test_forcebackup_command_is_gone():
    """The command is removed, so it must not be left in the help catalog."""
    from olit import registry

    assert "forcebackup" not in registry.catalogued_names(include_hidden=True)


# ── Saves still round-trip on disk ───────────────────────────────────────────
def test_saves_round_trip_to_disk(galaxy):
    """The host's disk is the only copy now, so writing must actually work."""
    g, _ = galaxy
    g._galaxy["42"] = g._default_user(42)
    g._galaxy["42"]["credits"] = 4242
    g._save_all()

    reloaded = g._load_json(g.GALAXY_FILE)
    assert reloaded["42"]["credits"] == 4242


# ── Reset ─────────────────────────────────────────────────────────────────────

def test_reset_user_clears_progress(galaxy):
    g, _ = galaxy
    g._galaxy["77"] = g._default_user(77)
    g._galaxy["77"]["credits"] = 999999
    g._galaxy["77"]["discovered"] = {(1, 2), (3, 4)}

    assert g.reset_user(77) is True
    fresh = g._galaxy["77"]
    assert fresh["credits"] == g._default_user(77)["credits"]
    assert len(fresh["discovered"]) == 0


def test_reset_user_reports_when_there_was_nothing(galaxy):
    g, _ = galaxy
    assert g.reset_user(12345) is False


def test_reset_user_also_clears_their_galaxy_score(galaxy):
    g, _ = galaxy
    g._save_json(g.SCORES_FILE, {"88": 5000, "99": 1})
    g._galaxy["88"] = g._default_user(88)

    g.reset_user(88)
    remaining = g._load_json(g.SCORES_FILE)
    assert "88" not in remaining
    assert remaining.get("99") == 1, "reset must not touch other players"


def test_reset_all_clears_everyone_but_keeps_the_world(galaxy):
    g, _ = galaxy
    g._galaxy.update({"1": g._default_user(1), "2": g._default_user(2)})
    g._world["0,0"] = {"name": "Nebula Nursery"}

    assert g.reset_all_users() == 2
    assert g._galaxy == {}
    # Sectors are shared world state, not per-player progress.
    assert "0,0" in g._world


def test_reset_all_clears_the_score_file(galaxy):
    g, _ = galaxy
    g._save_json(g.SCORES_FILE, {"1": 10, "2": 20})
    g._galaxy["1"] = g._default_user(1)

    g.reset_all_users()
    assert g._load_json(g.SCORES_FILE) == {}

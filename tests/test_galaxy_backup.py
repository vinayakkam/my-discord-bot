"""Tests for the galaxy save backup.

The behaviour being protected: the backup commits through the GitHub Contents
API (never `git push`), and only uploads files whose contents actually changed.
"""

import sys
import types

import pytest


@pytest.fixture
def galaxy(tmp_path, monkeypatch):
    """galaxy_keeper pointed at a temp data dir, with the API call recorded."""
    calls = []

    def fake_commit(path, content, message):
        calls.append({"path": path, "content": content, "message": message})
        return True, f"{path} committed"

    fake_keep_alive = types.ModuleType("keep_alive")
    fake_keep_alive.commit_to_github = fake_commit
    monkeypatch.setitem(sys.modules, "keep_alive", fake_keep_alive)

    import galaxy_keeper as g

    monkeypatch.setattr(g, "_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(g, "GALAXY_FILE", str(tmp_path / "galaxy_data.json"))
    monkeypatch.setattr(g, "WORLD_FILE", str(tmp_path / "world_data.json"))
    monkeypatch.setattr(g, "SCORES_FILE", str(tmp_path / "galaxy_scores.json"))
    monkeypatch.setattr(g, "_BACKUP_STATE_FILE", str(tmp_path / "backup_state.json"))
    monkeypatch.setattr(g, "_BACKUP_TARGETS", (
        str(tmp_path / "galaxy_data.json"),
        str(tmp_path / "world_data.json"),
        str(tmp_path / "galaxy_scores.json"),
    ))
    monkeypatch.setattr(g, "_galaxy", {"1": {"credits": 150}})
    monkeypatch.setattr(g, "_world", {})

    return g, calls


def test_first_backup_uploads_the_save_files(galaxy):
    g, calls = galaxy
    result = g._backup_saves("first")
    assert "committed" in result
    assert calls, "nothing was sent to the API"
    names = {c["path"].rsplit("\\", 1)[-1].rsplit("/", 1)[-1] for c in calls}
    assert "galaxy_data.json" in names


def test_unchanged_files_are_not_recommitted(galaxy):
    """An idle day must cost zero commits."""
    g, calls = galaxy
    g._backup_saves("first")
    calls.clear()

    result = g._backup_saves("second")
    assert calls == [], "re-committed files that had not changed"
    assert "no changes" in result


def test_changed_file_is_recommitted(galaxy):
    g, calls = galaxy
    g._backup_saves("first")
    calls.clear()

    g._galaxy["1"]["credits"] = 99999
    g._backup_saves("third")

    assert len(calls) == 1, "expected exactly the changed file"
    assert "galaxy_data.json" in calls[0]["path"]


def test_force_ignores_the_change_check(galaxy):
    """!forcebackup must upload regardless, for manual recovery."""
    g, calls = galaxy
    g._backup_saves("first")
    before = len(calls)
    calls.clear()

    g._backup_saves("forced", force=True)
    assert len(calls) == before, "force=True should re-upload everything"


def test_failed_upload_is_retried_next_run(galaxy, monkeypatch):
    """A digest must only be recorded after a successful upload."""
    g, calls = galaxy

    import keep_alive

    def failing(path, content, message):
        calls.append({"path": path})
        return False, "HTTP 403: forbidden"

    monkeypatch.setattr(keep_alive, "commit_to_github", failing)
    result = g._backup_saves("attempt-1")
    assert "FAILED" in result
    attempted = len(calls)
    calls.clear()

    # Still failing, so it must try again rather than consider itself done.
    g._backup_saves("attempt-2")
    assert len(calls) == attempted, "a failed file was marked as backed up"


def test_backup_never_shells_out_to_git():
    """Regression: the old backup ran `git push` on a 24h timer.

    Checked against the parsed module rather than its text, so prose in
    comments and docstrings explaining the old behaviour cannot trip it.
    """
    import ast
    import inspect

    import galaxy_keeper as g

    assert not hasattr(g, "_git_push"), "the git-push backup is back"

    tree = ast.parse(inspect.getsource(g))

    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "subprocess" not in imported, "galaxy_keeper imports subprocess again"

    calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and getattr(
            getattr(n.func, "value", None), "id", None) == "subprocess"
    ]
    assert not calls, "a subprocess call is back in galaxy_keeper"


def test_missing_files_are_reported_not_fatal(galaxy):
    g, calls = galaxy
    result = g._backup_saves("missing")
    # galaxy_scores.json is never written by this fixture.
    assert "no file yet" in result


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

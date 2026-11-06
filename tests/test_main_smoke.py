"""Smoke tests that import main.py and inspect the fully assembled bot.

This only works because main.py's runtime side effects are behind
`if __name__ == "__main__"`. Importing it registers every command without
starting the Flask thread or connecting to Discord.
"""

import pytest
from discord.ext import commands

from olit import registry


@pytest.fixture(scope="module")
def live_bot():
    """The real bot object from main.py, with every feature registered."""
    import main
    return main.bot


# ── Wiring ────────────────────────────────────────────────────────────────────

def test_main_imports_without_connecting(live_bot):
    assert isinstance(live_bot, commands.Bot)
    assert live_bot.command_prefix == "!"


def test_bot_instance_is_handed_to_the_api_thread():
    """keep_alive needs this or every gateway-backed endpoint 503s."""
    import keep_alive
    import main

    assert keep_alive.bot_instance is main.bot


def test_required_intents_are_enabled(live_bot):
    assert live_bot.intents.message_content, "prefix commands need message_content"
    assert live_bot.intents.members, "welcome messages need the members intent"
    assert live_bot.intents.guilds


def test_exactly_one_handler_per_event(live_bot):
    """A second @bot.event for the same name replaces the first silently.

    main.py used to define on_command_error twice.
    """
    import main
    import inspect

    source = inspect.getsource(main)
    for event in ("on_message", "on_ready", "on_command_error",
                  "on_member_join", "on_command"):
        # Count only real definitions, not ones inside string literals.
        count = sum(
            1 for line in source.splitlines()
            if line.strip().startswith(f"async def {event}(")
        )
        assert count <= 1, f"{event} is defined {count} times; the last one wins"


def test_on_message_still_dispatches_prefix_commands(live_bot):
    """Without process_commands() at the end of on_message, every ! command dies."""
    import main
    import inspect

    source = inspect.getsource(main.on_message)
    assert "process_commands" in source


# ── Command hygiene ───────────────────────────────────────────────────────────

def test_no_duplicate_command_names(live_bot):
    names = [c.name for c in live_bot.commands]
    duplicates = {n for n in names if names.count(n) > 1}
    assert not duplicates, f"duplicate command names: {sorted(duplicates)}"


def test_no_duplicate_slash_command_names(live_bot):
    names = [c.name for c in live_bot.tree.get_commands()]
    duplicates = {n for n in names if names.count(n) > 1}
    assert not duplicates, f"duplicate slash commands: {sorted(duplicates)}"


def test_every_command_has_a_callback(live_bot):
    for command in live_bot.commands:
        assert callable(command.callback), f"!{command.name} has no callback"


def test_help_is_our_implementation(live_bot):
    """Regression: `!help` used to be removed and never replaced, so it did nothing."""
    cmd = live_bot.get_command("help")
    assert cmd is not None, "!help is not registered at all"
    assert cmd.callback.__module__ == "olit.features.helpcmd"


def test_olithelp_alias_preserved(live_bot):
    assert live_bot.get_command("olithelp") is live_bot.get_command("help")


# ── The catalog must match reality ────────────────────────────────────────────

def test_every_registered_command_is_documented(live_bot):
    """Every command on the real bot appears in olit/registry.py.

    If this fails, add the new command to the catalog so `!help` lists it.
    """
    documented = registry.catalogued_names(include_hidden=True)
    registered = {c.name for c in live_bot.commands}

    undocumented = sorted(registered - documented)
    assert not undocumented, (
        "registered but missing from olit/registry.py: " + ", ".join(undocumented)
    )


# space_tweets registers its cog via bot.loop.create_task, so its commands only
# exist once the bot has logged in and setup_hook has run. They cannot be seen
# by an offline import, unlike every other feature module.
_LOGIN_DEFERRED = {
    "spacenow", "spacestatus", "spacetoggle", "spacediag", "spacedebug",
}


def test_catalog_has_no_phantom_commands(live_bot):
    """Every catalogued command actually exists on the bot."""
    registered = set()
    for command in live_bot.commands:
        registered.add(command.name)
        registered.update(command.aliases)

    phantom = sorted(
        cmd.name for cmd in registry.all_commands(include_hidden=True)
        if cmd.name not in registered and cmd.name not in _LOGIN_DEFERRED
    )
    assert not phantom, (
        "documented in olit/registry.py but not registered: " + ", ".join(phantom)
    )


def test_space_commands_exist_in_their_cog():
    """Cover the login-deferred commands by inspecting the cog class directly."""
    from space_tweets import SpaceTweetsCog

    defined = {
        attr.name
        for attr in SpaceTweetsCog.__dict__.values()
        if hasattr(attr, "name")
    }
    missing = sorted(_LOGIN_DEFERRED - defined)
    assert not missing, f"documented space commands not found in the cog: {missing}"


def test_galaxy_commands_register_at_import(live_bot):
    """Regression: setup_galaxy ran inside on_ready, so a reconnect re-registered
    the same commands and raised CommandRegistrationError."""
    for name in ("galaxy", "gscan", "gstats", "shipyard", "story"):
        assert live_bot.get_command(name) is not None, f"!{name} not registered"


def test_setup_hook_is_overridden(live_bot):
    """One-time async setup belongs in setup_hook, not on_ready."""
    assert live_bot.setup_hook.__name__ == "setup_hook"


def test_on_ready_does_not_do_one_time_setup():
    """on_ready fires on every reconnect; it must stay side-effect free."""
    import inspect

    import main

    source = inspect.getsource(main.on_ready)
    for forbidden in ("tree.sync", "setup_galaxy", "setup_space_tweets",
                      "daily_galaxy_backup.start"):
        assert forbidden not in source, (
            f"{forbidden} is in on_ready and will re-run on every reconnect"
        )


def test_slash_commands_are_documented(live_bot):
    documented = registry.catalogued_names(include_hidden=True)
    # The emoji-reaction slash commands are guild-specific utilities.
    exempt = {"appbcbash", "appbceq", "appbaa", "appsheriff"}
    undocumented = sorted(
        {c.name for c in live_bot.tree.get_commands()} - documented - exempt
    )
    assert not undocumented, f"undocumented slash commands: {undocumented}"


def test_single_score_store(live_bot):
    """main.py defined `scores` and `add_score` twice with different key types."""
    import main

    from olit import storage

    assert main.scores is storage.scores, "main has its own score dict"
    assert main.add_score is storage.add_score, "main has its own add_score"


def test_score_keys_are_strings():
    """JSON keys are strings; an int-keyed entry would never reload."""
    from olit import storage

    assert all(isinstance(k, str) for k in storage.scores)

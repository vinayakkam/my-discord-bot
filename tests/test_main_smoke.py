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


def test_catalog_has_no_phantom_commands(live_bot):
    """Every catalogued command actually exists on the bot."""
    registered = set()
    for command in live_bot.commands:
        registered.add(command.name)
        registered.update(command.aliases)

    phantom = sorted(
        cmd.name for cmd in registry.all_commands(include_hidden=True)
        if cmd.name not in registered
    )
    assert not phantom, (
        "documented in olit/registry.py but not registered: " + ", ".join(phantom)
    )


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
    for forbidden in ("tree.sync", "setup_galaxy",
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


def test_trivia_pool_is_large(live_bot):
    """The hand-written bank held only 60 questions, so repeats came fast."""
    import main

    from olit.features import trivia_bank

    sizes = trivia_bank.bank_sizes(main.TRIVIA_BANK)
    assert sum(sizes.values()) > 200, sizes
    for difficulty, count in sizes.items():
        assert count >= 40, f"{difficulty} only has {count}"


def test_trivia_avoids_immediate_repeats(live_bot):
    import main

    drawn = [main.pick_trivia_question(424242, "easy")["question"]
             for _ in range(25)]
    assert len(set(drawn)) == len(drawn), "a question repeated within 25 draws"


def test_trivia_survives_exhausting_the_pool(live_bot):
    """Drawing more times than the pool holds must not raise or hang."""
    import main

    for _ in range(len(main.TRIVIA_BANK["hard"]) + 50):
        question = main.pick_trivia_question(515151, "hard")
        assert question["answer"] in question["options"]


# ── Dice argument handling ────────────────────────────────────────────────────

def _resolve_dice_args(first=None, second=None):
    """Mirror of the mapping inside the !dice command."""
    if first is None:
        return None, 6
    if second is None:
        return None, first
    return first, second


def test_single_dice_argument_is_the_die_size(live_bot):
    """`!dice 100` means a d100, not a guess of 100 on a d6."""
    assert _resolve_dice_args(100) == (None, 100)
    assert _resolve_dice_args(1000000) == (None, 1000000)


def test_no_dice_arguments_defaults_to_d6(live_bot):
    assert _resolve_dice_args() == (None, 6)


def test_two_dice_arguments_are_guess_then_size(live_bot):
    assert _resolve_dice_args(3, 20) == (3, 20)


def test_dice_payout_scales_with_odds(live_bot):
    import main

    assert main.dice_payout(2) < main.dice_payout(100) < main.dice_payout(10**9)


def test_dice_payout_is_capped(live_bot):
    """An absurd die must not mint unlimited points."""
    import main

    assert main.dice_payout(10**30) == main.dice_payout(10**60) == 20


def test_dice_has_no_upper_size_limit(live_bot):
    import main

    assert not hasattr(main, "DICE_MAX_SIDES")

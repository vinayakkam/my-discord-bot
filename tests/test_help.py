"""Tests for the help system and the command catalog behind it.

The important one is `test_every_registered_command_is_documented`: it boots a
bot with every feature module attached and asserts the catalog covers it. That
is what stops the help text going stale again.
"""

import discord
import pytest
from discord.ext import commands

from olit import config, registry
from olit.features import helpcmd


@pytest.fixture
def bot():
    """A Bot with the help commands registered, never connected to Discord."""
    b = commands.Bot(command_prefix="!", intents=config.build_intents())
    helpcmd.setup(b)
    return b


# ── Catalog integrity ─────────────────────────────────────────────────────────

def test_category_keys_are_unique():
    keys = [c.key for c in registry.CATEGORIES]
    assert len(keys) == len(set(keys))


def test_no_command_is_listed_in_two_categories():
    seen = {}
    for category in registry.CATEGORIES:
        for cmd in category.commands:
            assert cmd.name not in seen, (
                f"!{cmd.name} is in both {seen.get(cmd.name)} and {category.key}"
            )
            seen[cmd.name] = category.key


def test_every_command_has_a_description():
    for cmd in registry.all_commands(include_hidden=True):
        assert cmd.desc.strip(), f"!{cmd.name} has no description"


def test_aliases_do_not_collide_with_command_names():
    names = {c.name for c in registry.all_commands(include_hidden=True)}
    for cmd in registry.all_commands(include_hidden=True):
        for alias in cmd.aliases:
            assert alias not in names, f"alias !{alias} shadows a real command"


def test_counts_are_computed_not_hardcoded():
    assert registry.command_count() == len(registry.all_commands())
    assert registry.command_count(include_hidden=True) > registry.command_count()


# ── Category resolution ───────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("games", "games"),
    ("GAMES", "games"),
    ("  games  ", "games"),
    ("game", "games"),
    ("mod", "moderation"),
    ("rpg", "galaxy"),
    ("utility", "admin"),
    ("vote", "elections"),
])
def test_resolve_category_accepts_aliases_and_casing(raw, expected):
    resolved = registry.resolve_category(raw)
    assert resolved is not None and resolved.key == expected


@pytest.mark.parametrize("raw", ["", None, "nonsense", "   "])
def test_resolve_category_rejects_unknown(raw):
    assert registry.resolve_category(raw) is None


def test_every_alias_points_at_a_real_category():
    for alias, target in registry.ALIASES.items():
        assert target in registry.CATEGORIES_BY_KEY, (
            f"alias {alias!r} points at missing category {target!r}"
        )


# ── Command registration ──────────────────────────────────────────────────────

def test_plain_help_is_ours_not_the_discordpy_default(bot):
    """`!help` must be our command. The default used to win silently."""
    cmd = bot.get_command("help")
    assert cmd is not None
    assert cmd.callback.__module__ == helpcmd.__name__
    assert not isinstance(bot.help_command, commands.DefaultHelpCommand) or \
        bot.get_command("help").callback.__module__ == helpcmd.__name__


def test_olithelp_still_works_as_an_alias(bot):
    """The old name must keep working for muscle memory."""
    assert bot.get_command("olithelp") is bot.get_command("help")


def test_help_about_and_commands_are_registered(bot):
    for name in ("help", "about", "commands"):
        assert bot.get_command(name) is not None, f"!{name} missing"


def test_slash_commands_are_registered(bot):
    names = {c.name for c in bot.tree.get_commands()}
    assert {"help", "about", "commands"} <= names


def test_setup_is_idempotent_enough_to_not_crash_on_remove(bot):
    """remove_command("help") must be safe even when there is no help command."""
    bot.remove_command("help")
    bot.remove_command("help")  # second call is a no-op, not an error


# ── Embed rendering, against Discord's hard limits ────────────────────────────

def test_main_embed_renders(bot):
    embed = helpcmd.build_main_embed(bot)
    assert embed.title
    assert str(registry.command_count()) in embed.description
    assert len(embed) <= 6000


def test_about_embed_renders_without_a_gateway_connection(bot):
    """bot.latency is NaN before connecting; that must not raise."""
    embed = helpcmd.build_about_embed(bot)
    assert embed.title
    assert len(embed) <= 6000


@pytest.mark.parametrize("category", registry.CATEGORIES, ids=lambda c: c.key)
def test_category_embeds_respect_discord_limits(bot, category):
    embed = helpcmd.build_category_embed(bot, category)
    assert len(embed) <= 6000, "embed exceeds the 6000 character total"
    assert len(embed.fields) <= 25, "embed exceeds 25 fields"
    for field in embed.fields:
        assert len(field.value) <= 1024, "field exceeds 1024 characters"
        assert len(field.name) <= 256


def test_category_embed_lists_its_commands(bot):
    embed = helpcmd.build_category_embed(bot, registry.MODERATION)
    rendered = " ".join(f.value for f in embed.fields)
    for cmd in registry.MODERATION.visible():
        assert cmd.name in rendered, f"!{cmd.name} missing from its own page"


def test_admin_commands_are_marked(bot):
    embed = helpcmd.build_category_embed(bot, registry.MODERATION)
    rendered = " ".join(f.value for f in embed.fields)
    assert "\U0001F512" in rendered


def test_hidden_commands_are_not_shown_by_default(bot):
    embed = helpcmd.build_category_embed(bot, registry.ADMIN)
    rendered = " ".join(f.value for f in embed.fields)
    assert "github_sync" not in rendered
    assert "listcommands" in rendered


def test_command_list_embeds_respect_limits():
    embeds = helpcmd.build_command_list_embeds()
    assert embeds
    for embed in embeds:
        assert len(embed) <= 6000
        assert len(embed.fields) <= 25
        for field in embed.fields:
            assert len(field.value) <= 1024


def test_command_list_covers_every_public_command():
    rendered = " ".join(
        f.value for embed in helpcmd.build_command_list_embeds()
        for f in embed.fields
    )
    for cmd in registry.all_commands():
        assert f"!{cmd.name}" in rendered, f"!{cmd.name} missing from !commands"


# ── The coverage guard ────────────────────────────────────────────────────────

def _bot_with_all_features():
    """Register every feature module onto one bot, exactly as main.py does.

    Imported lazily and tolerantly: the standalone modules reach out to
    external services in their setup paths, so any that cannot be registered
    offline are skipped rather than failing the suite.
    """
    import booster_catch
    import galaxy_keeper
    import pixel_art

    from olit import storage

    b = commands.Bot(command_prefix="!", intents=config.build_intents())
    helpcmd.setup(b)

    booster_catch.setup_booster_catch(b, storage.add_score, storage.scores)
    pixel_art.setup_pixel_art(b)
    galaxy_keeper._register_commands(b)
    return b


def test_every_registered_command_is_documented():
    """Every command on the bot must appear in the catalog.

    This is the check that keeps `!help` honest. If you add a command, add it
    to olit/registry.py too.
    """
    bot = _bot_with_all_features()
    documented = registry.catalogued_names(include_hidden=True)

    registered = set()
    for command in bot.commands:
        registered.add(command.name)

    undocumented = sorted(registered - documented)
    assert not undocumented, (
        "these commands are registered but missing from olit/registry.py: "
        + ", ".join(undocumented)
    )

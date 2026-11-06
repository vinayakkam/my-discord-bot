"""The help system: !help, !olithelp, /help, !about and !commands.

Everything rendered here comes from `olit.registry.CATEGORIES`, so the help
text cannot drift from the commands that actually exist.

Two things were wrong with the previous implementation:

1. `commands.Bot` installs a default `help` command unless you remove it. The
   custom help was registered as `!olithelp`, so plain `!help` -- what people
   actually type -- produced discord.py's bare default listing. We now call
   `bot.remove_command("help")` and own `!help`, keeping `!olithelp` as an
   alias so the old name still works.
2. The category list, command names and the counts in the embeds were
   hardcoded string literals that had gone stale.
"""

from typing import List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from olit import registry

# How many commands go into one embed field before we start a new one. Discord
# caps a field value at 1024 characters, and these lines run ~60-90 chars.
_COMMANDS_PER_FIELD = 8

# How long the interactive menu stays clickable.
_VIEW_TIMEOUT = 300


def _chunk(items: List, size: int) -> List[List]:
    """Split `items` into consecutive lists of at most `size` entries."""
    return [items[i:i + size] for i in range(0, len(items), size)]


def _render_command(cmd: registry.Cmd) -> str:
    """One command as a help line: signature, admin marker, description."""
    marker = " \U0001F512" if cmd.admin else ""
    line = f"`{cmd.signature}`{marker}\n• {cmd.desc}"
    if cmd.aliases:
        alias_text = ", ".join(f"`!{a}`" for a in cmd.aliases)
        line += f"\n• Also: {alias_text}"
    return line


def build_category_embed(bot: commands.Bot, category: registry.Category,
                         include_hidden: bool = False) -> discord.Embed:
    """Render one category page."""
    shown = category.visible(include_hidden=include_hidden)

    embed = discord.Embed(
        title=f"{category.emoji} {category.title}",
        description=f"{category.blurb}\n\n**{len(shown)} commands** in this category.",
        color=discord.Color.blurple(),
    )

    # Group into fields so no single field exceeds Discord's 1024-char cap.
    for index, group in enumerate(_chunk(shown, _COMMANDS_PER_FIELD)):
        embed.add_field(
            name="​" if index else "Commands",
            value="\n\n".join(_render_command(c) for c in group),
            inline=False,
        )

    if any(c.admin for c in shown):
        embed.set_footer(text="\U0001F512 needs elevated permissions")
    return embed


def build_main_embed(bot: commands.Bot) -> discord.Embed:
    """Render the landing page: live stats plus the category index."""
    total = registry.command_count()
    categories = len(registry.CATEGORIES)

    # Counts are computed, never hardcoded, so they stay honest.
    guild_count = len(bot.guilds)
    try:
        user_count = len({m.id for m in bot.get_all_members()})
    except Exception:
        user_count = 0

    embed = discord.Embed(
        title="\U0001F680 OLIT Bot — Mission Control",
        description=(
            "Your space-themed Discord companion: minigames, launch "
            "simulations, a galaxy RPG, moderation and server management.\n\n"
            f"**{total}** commands across **{categories}** categories.\n"
            f"Serving **{guild_count}** servers and **{user_count}** members.\n\n"
            "Pick a category below, or run `!help <category>` directly."
        ),
        color=discord.Color.blurple(),
    )

    # Two-column index of categories with their command counts.
    for group in _chunk(registry.CATEGORIES, 6):
        embed.add_field(
            name="​",
            value="\n".join(
                f"{c.emoji} **{c.title}** — "
                f"{len(c.visible())} · `!help {c.key}`"
                for c in group
            ),
            inline=True,
        )

    if bot.user is not None:
        embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="!help <category> · !about · !commands")
    return embed


def build_about_embed(bot: commands.Bot) -> discord.Embed:
    """Render the !about page."""
    total = registry.command_count()
    embed = discord.Embed(
        title="\U0001F680 About OLIT Bot",
        description=(
            "**OLIT Bot** (Launch Tower) is the official bot of "
            "OLIT Technologies — a space-themed, multi-purpose Discord bot.\n\n"
            f"It currently offers **{total}** commands across "
            f"**{len(registry.CATEGORIES)}** categories."
        ),
        color=discord.Color.blurple(),
    )

    for category in registry.CATEGORIES:
        if category.key == "help":
            continue
        embed.add_field(
            name=f"{category.emoji} {category.title}",
            value=f"{category.blurb}\n`!help {category.key}`",
            inline=True,
        )

    embed.add_field(
        name="\U0001F517 Links",
        value=(
            "Website: https://olittechnologies.co.in\n"
            "Use `!dev` to contact the developer."
        ),
        inline=False,
    )

    if bot.user is not None:
        embed.set_thumbnail(url=bot.user.display_avatar.url)
    # bot.latency is NaN until the first gateway heartbeat lands.
    latency = bot.latency
    if latency == latency and latency != float("inf"):
        embed.set_footer(text=f"Latency {round(latency * 1000)}ms")
    return embed


def build_command_list_embeds(include_hidden: bool = False) -> List[discord.Embed]:
    """Render the flat `!commands` listing, split across embeds if needed."""
    embeds: List[discord.Embed] = []
    current = discord.Embed(
        title="\U0001F4DC All Commands",
        description=(
            f"**{registry.command_count(include_hidden)}** commands. "
            "Use `!help <category>` for details."
        ),
        color=discord.Color.blurple(),
    )

    for category in registry.CATEGORIES:
        shown = category.visible(include_hidden=include_hidden)
        if not shown:
            continue
        value = ", ".join(f"`!{c.name}`" for c in shown)
        # Discord caps a field at 1024 characters.
        for part in _chunk(value.split(", "), 25):
            text = ", ".join(part)
            # An embed holds at most 25 fields; start a new one past that.
            if len(current.fields) >= 25:
                embeds.append(current)
                current = discord.Embed(color=discord.Color.blurple())
            current.add_field(
                name=f"{category.emoji} {category.title}",
                value=text,
                inline=False,
            )

    embeds.append(current)
    return embeds


class HelpView(discord.ui.View):
    """Interactive category picker for the help command.

    A dropdown rather than one button per category: there are 11 categories,
    and a view only holds 25 components across 5 rows, so buttons would not
    scale as categories are added.
    """

    def __init__(self, bot: commands.Bot, invoker_id: Optional[int] = None):
        super().__init__(timeout=_VIEW_TIMEOUT)
        self.bot = bot
        # Only the person who ran the command may drive the menu. None means
        # anyone can (used for the slash command in shared channels).
        self.invoker_id = invoker_id
        self.message: Optional[discord.Message] = None

        self.add_item(_CategorySelect(bot))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Stop other people hijacking someone else's help menu."""
        if self.invoker_id is None or interaction.user.id == self.invoker_id:
            return True
        await interaction.response.send_message(
            "That menu belongs to someone else — run `!help` to get your own.",
            ephemeral=True,
        )
        return False

    async def on_timeout(self) -> None:
        """Grey out the controls so a dead menu looks dead."""
        for item in self.children:
            item.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                # The message may have been deleted; nothing to do.
                pass

    @discord.ui.button(label="Home", emoji="\U0001F3E0",
                       style=discord.ButtonStyle.secondary, row=1)
    async def home(self, interaction: discord.Interaction,
                   button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=build_main_embed(self.bot), view=self
        )

    @discord.ui.button(label="About", emoji="ℹ️",
                       style=discord.ButtonStyle.secondary, row=1)
    async def about(self, interaction: discord.Interaction,
                    button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=build_about_embed(self.bot), view=self
        )


class _CategorySelect(discord.ui.Select):
    """Dropdown listing every help category."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__(
            placeholder="Choose a category…",
            options=[
                discord.SelectOption(
                    label=category.title,
                    value=category.key,
                    emoji=category.emoji,
                    description=f"{len(category.visible())} commands",
                )
                for category in registry.CATEGORIES
            ],
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        category = registry.CATEGORIES_BY_KEY.get(self.values[0])
        if category is None:
            await interaction.response.edit_message(
                embed=build_main_embed(self.bot), view=self.view
            )
            return
        await interaction.response.edit_message(
            embed=build_category_embed(self.bot, category), view=self.view
        )


def setup(bot: commands.Bot) -> None:
    """Register the help commands on `bot`."""

    # discord.py adds its own `help` command in the Bot constructor. Without
    # this, that default silently wins and `!help` shows a bare listing.
    bot.remove_command("help")

    @bot.command(name="help", aliases=["olithelp"])
    async def help_prefix(ctx: commands.Context, *, category: str = None):
        """Show the interactive help menu, or one category directly."""
        view = HelpView(bot, invoker_id=ctx.author.id)

        resolved = registry.resolve_category(category)
        if category and resolved is None:
            # Unknown category: say so rather than silently showing Home.
            embed = build_main_embed(bot)
            embed.insert_field_at(
                0,
                name="⚠️ Unknown category",
                value=(
                    f"No category called `{discord.utils.escape_markdown(category)}`. "
                    "Pick one below."
                ),
                inline=False,
            )
        elif resolved is not None:
            embed = build_category_embed(bot, resolved)
        else:
            embed = build_main_embed(bot)

        view.message = await ctx.send(embed=embed, view=view)

    @bot.tree.command(name="help",
                      description="Show all bot commands and features")
    @app_commands.describe(category="Jump straight to one category")
    @app_commands.choices(category=[
        app_commands.Choice(name=c.title, value=c.key)
        for c in registry.CATEGORIES
    ])
    async def help_slash(interaction: discord.Interaction,
                         category: Optional[app_commands.Choice[str]] = None):
        """Slash version of the help menu."""
        view = HelpView(bot, invoker_id=interaction.user.id)
        resolved = registry.resolve_category(category.value) if category else None
        embed = (
            build_category_embed(bot, resolved) if resolved
            else build_main_embed(bot)
        )
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @bot.command(name="about")
    async def about_prefix(ctx: commands.Context):
        """What the bot is and what it can do."""
        await ctx.send(embed=build_about_embed(bot))

    @bot.tree.command(name="about", description="Learn more about OLIT Bot")
    async def about_slash(interaction: discord.Interaction):
        await interaction.response.send_message(embed=build_about_embed(bot))

    @bot.command(name="commands")
    async def commands_prefix(ctx: commands.Context):
        """Flat list of every command, grouped by category."""
        for embed in build_command_list_embeds():
            await ctx.send(embed=embed)

    @bot.tree.command(name="commands",
                      description="List all bot commands by category")
    async def commands_slash(interaction: discord.Interaction):
        embeds = build_command_list_embeds()
        await interaction.response.send_message(embed=embeds[0])
        for extra in embeds[1:]:
            await interaction.followup.send(embed=extra)

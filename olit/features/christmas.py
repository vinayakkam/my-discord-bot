"""The Grinch Christmas event: a multi-round reaction game.

Replaces the original single-button, single-round version, which ran for five
seconds, awarded no points at all (unlike every other game in the bot) and
auto-started on every message in December.

How a game runs now:

- Three rounds. The timer tightens each round (5s, 4s, 3s) and the number of
  decoy buttons grows, so later rounds test accuracy as well as speed.
- Each round shows one real "Stop the Grinch!" button among shuffled decoys.
  The first player to hit the real one takes the round; hitting a decoy knocks
  that player out for the remainder of the round.
- Winning a round pays a base score, a speed bonus scaled by how much of the
  timer was left, and a streak bonus for consecutive round wins.
- Reaction times, win/loss records and personal bests persist, and
  `!grinchboard` ranks players.
"""

import asyncio
import random
import time
from typing import Dict, List, Optional

import discord
from discord.ext import commands

from olit import storage

# ── Tuning ────────────────────────────────────────────────────────────────────

# Seconds allowed per round. The length of this list is the number of rounds.
ROUND_TIMERS = (5.0, 4.0, 3.0)

# Decoy buttons per round, parallel to ROUND_TIMERS.
ROUND_DECOYS = (1, 2, 3)

# Points for taking a round, before bonuses.
BASE_ROUND_POINTS = 2

# Maximum extra points for a fast click, scaled by the fraction of time left.
MAX_SPEED_BONUS = 3

# Extra points per consecutive round won by the same player.
STREAK_BONUS = 2

# Points for winning the overall game.
GAME_WIN_POINTS = 5

# Where per-player Grinch records live.
STATS_FILE = "persistent/grinch_stats.json"

FESTIVE_IMAGE = (
    "https://img.freepik.com/free-vector/flat-christmas-season-celebration-"
    "background_23-2149872289.jpg?semt=ais_hybrid&w=740&q=80"
)

# Labels for the decoy buttons. Clicking one of these loses the round.
DECOY_LABELS = [
    ("Feed the Grinch", "\U0001F36A"),
    ("Pet the Grinch", "\U0001F43E"),
    ("Join the Grinch", "\U0001F608"),
    ("Hide the sleigh", "\U0001F6F7"),
    ("Blame the elves", "\U0001F9DD"),
    ("Unplug the lights", "\U0001F4A1"),
]

# Animation frames: the Grinch's sack fills as time runs out.
SACK_FRAMES = [
    "\U0001F385 \U0001F381\U0001F381\U0001F381\U0001F381\U0001F381  \U0001F608",
    "\U0001F385 \U0001F381\U0001F381\U0001F381\U0001F381  \U0001F608\U0001F381",
    "\U0001F385 \U0001F381\U0001F381\U0001F381  \U0001F608\U0001F381\U0001F381",
    "\U0001F385 \U0001F381\U0001F381  \U0001F608\U0001F381\U0001F381\U0001F381",
    "\U0001F385 \U0001F381  \U0001F608\U0001F381\U0001F381\U0001F381\U0001F381",
    "\U0001F385   \U0001F608\U0001F381\U0001F381\U0001F381\U0001F381\U0001F381",
]


# ── Stats persistence ─────────────────────────────────────────────────────────

def load_stats() -> Dict[str, dict]:
    """Read the Grinch record book, keyed by stringified user ID."""
    data = storage.read_json(STATS_FILE, {})
    return data if isinstance(data, dict) else {}


# Live record book. Mutated in place so other modules keep a valid reference.
_stats: Dict[str, dict] = load_stats()


def _blank_record() -> dict:
    return {
        "games_played": 0,
        "games_won": 0,
        "rounds_won": 0,
        "decoys_hit": 0,
        "best_ms": None,
        "total_points": 0,
    }


def get_record(user_id) -> dict:
    """Return a player's record, creating a blank one if needed."""
    return _stats.setdefault(str(user_id), _blank_record())


def save_stats() -> bool:
    return storage.write_json(STATS_FILE, _stats)


def record_round_win(user_id, reaction_ms: int, points: int) -> None:
    """Log a round win and update the player's personal best."""
    record = get_record(user_id)
    record["rounds_won"] += 1
    record["total_points"] += points
    if record["best_ms"] is None or reaction_ms < record["best_ms"]:
        record["best_ms"] = reaction_ms


def record_decoy_hit(user_id) -> None:
    get_record(user_id)["decoys_hit"] += 1


def record_game_finished(participants, winner_id: Optional[int]) -> None:
    """Log participation for everyone and the win for the victor."""
    for user_id in participants:
        get_record(user_id)["games_played"] += 1
    if winner_id is not None:
        record = get_record(winner_id)
        record["games_won"] += 1
        record["total_points"] += GAME_WIN_POINTS
    save_stats()


# ── Round view ────────────────────────────────────────────────────────────────

class _RoundView(discord.ui.View):
    """One round: a real button plus decoys, first correct click wins."""

    def __init__(self, round_index: int, timeout: float, decoys: int):
        super().__init__(timeout=timeout)
        self.round_index = round_index
        self.started_at = time.monotonic()

        self.winner: Optional[discord.User] = None
        self.reaction_ms: Optional[int] = None
        # Players who hit a decoy and are out for this round.
        self.eliminated: set = set()
        self.decoy_hits: List[discord.User] = []
        self.message: Optional[discord.Message] = None

        # Build the button row, then shuffle so the real button moves around.
        buttons: List[discord.ui.Button] = [_RealButton()]
        for label, emoji in random.sample(DECOY_LABELS, k=min(decoys, len(DECOY_LABELS))):
            buttons.append(_DecoyButton(label=label, emoji=emoji))
        random.shuffle(buttons)
        for button in buttons:
            self.add_item(button)

    def finish(self, user: discord.User) -> int:
        """Record the winning click and return their reaction time in ms."""
        elapsed_ms = int((time.monotonic() - self.started_at) * 1000)
        self.winner = user
        self.reaction_ms = elapsed_ms
        for child in self.children:
            child.disabled = True
        return elapsed_ms

    def time_left_fraction(self) -> float:
        """How much of the round timer was still unused, between 0 and 1."""
        if not self.timeout:
            return 0.0
        used = time.monotonic() - self.started_at
        return max(0.0, min(1.0, 1.0 - (used / self.timeout)))

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class _RealButton(discord.ui.Button):
    """The button that actually stops the Grinch."""

    def __init__(self):
        super().__init__(
            label="Stop the Grinch!",
            emoji="\U0001F6D1",
            style=discord.ButtonStyle.primary,
        )

    async def callback(self, interaction: discord.Interaction):
        view: _RoundView = self.view

        if view.winner is not None:
            await interaction.response.send_message(
                "Too slow — this round is already over.", ephemeral=True
            )
            return

        if interaction.user.id in view.eliminated:
            await interaction.response.send_message(
                "You already hit a decoy — sit this round out.", ephemeral=True
            )
            return

        reaction_ms = view.finish(interaction.user)
        await interaction.response.edit_message(view=view)
        await interaction.followup.send(
            f"\U0001F6D1 {interaction.user.mention} stopped the Grinch in "
            f"**{reaction_ms} ms**!"
        )
        view.stop()


class _DecoyButton(discord.ui.Button):
    """A wrong button. Clicking it drops the player out of the round."""

    def __init__(self, label: str, emoji: str):
        super().__init__(label=label, emoji=emoji,
                         style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        view: _RoundView = self.view

        if view.winner is not None:
            await interaction.response.send_message(
                "This round is already over.", ephemeral=True
            )
            return

        if interaction.user.id in view.eliminated:
            await interaction.response.send_message(
                "You are already out for this round.", ephemeral=True
            )
            return

        view.eliminated.add(interaction.user.id)
        view.decoy_hits.append(interaction.user)
        record_decoy_hit(interaction.user.id)
        await interaction.response.send_message(
            f"\U0001F648 Wrong move — **{self.label}** helped the Grinch. "
            "You're out for this round.",
            ephemeral=True,
        )


# ── Embeds ────────────────────────────────────────────────────────────────────

def build_round_embed(round_index: int, total_rounds: int, timeout: float,
                      decoys: int, frame: str = SACK_FRAMES[0]) -> discord.Embed:
    """The live embed shown while a round is in progress."""
    embed = discord.Embed(
        title=f"\U0001F384 The Grinch strikes — Round {round_index}/{total_rounds}",
        description=(
            f"Hit **Stop the Grinch!** within **{timeout:g}s**.\n"
            + (f"Beware: **{decoys}** decoy button"
               f"{'s' if decoys != 1 else ''} will cost you the round.\n"
               if decoys else "")
            + f"\n{frame}"
        ),
        color=0xE63946,
    )
    embed.set_footer(text="Faster clicks score more · streaks pay extra")
    return embed


def build_round_result_embed(view: _RoundView, points: int,
                             streak: int) -> discord.Embed:
    """The embed shown once a round resolves."""
    if view.winner is None:
        embed = discord.Embed(
            title="\U0001F608 The Grinch got this one",
            description="Nobody stopped him in time.",
            color=0x6C757D,
        )
    else:
        bonus_note = f" (+{STREAK_BONUS * (streak - 1)} streak)" if streak > 1 else ""
        embed = discord.Embed(
            title="\U0001F6D1 Round saved!",
            description=(
                f"{view.winner.mention} reacted in **{view.reaction_ms} ms** "
                f"and scored **{points}** points{bonus_note}."
            ),
            color=0x2ECC71,
        )
    if view.decoy_hits:
        embed.add_field(
            name="Fell for a decoy",
            value=", ".join(u.display_name for u in view.decoy_hits),
            inline=False,
        )
    return embed


def build_final_embed(round_wins: Dict[int, int],
                      names: Dict[int, str],
                      best_times: Dict[int, int],
                      total_rounds: int) -> discord.Embed:
    """The end-of-game scoreboard."""
    if not round_wins:
        embed = discord.Embed(
            title="\U0001F608 The Grinch stole Christmas",
            description="Not a single round went to the humans. Brutal.",
            color=0x6C757D,
        )
        embed.set_image(url=FESTIVE_IMAGE)
        return embed

    ranked = sorted(round_wins.items(), key=lambda kv: kv[1], reverse=True)
    top_id, top_wins = ranked[0]

    embed = discord.Embed(
        title="\U0001F389 Christmas is saved!",
        description=(
            f"**{names.get(top_id, 'Someone')}** takes the game with "
            f"**{top_wins}/{total_rounds}** rounds "
            f"and earns **+{GAME_WIN_POINTS}** bonus points."
        ),
        color=0x2ECC71,
    )

    embed.add_field(
        name="Scoreboard",
        value="\n".join(
            f"`{position}.` {names.get(user_id, 'Unknown')} — "
            f"{wins} round{'s' if wins != 1 else ''}"
            + (f" · best {best_times[user_id]} ms"
               if user_id in best_times else "")
            for position, (user_id, wins) in enumerate(ranked, start=1)
        ),
        inline=False,
    )
    embed.set_image(url=FESTIVE_IMAGE)
    embed.set_footer(text="!grinchboard for all-time rankings")
    return embed


# ── Animation ─────────────────────────────────────────────────────────────────

async def animate_round(message: discord.Message, view: _RoundView,
                        round_index: int, total_rounds: int,
                        timeout: float, decoys: int) -> None:
    """Advance the sack animation until the round ends.

    Frames are paced to span the round's timer, so the sack fills up roughly as
    time runs out.
    """
    interval = max(0.5, timeout / len(SACK_FRAMES))
    try:
        for frame in SACK_FRAMES[1:]:
            await asyncio.sleep(interval)
            if view.winner is not None or view.is_finished():
                return
            try:
                await message.edit(
                    embed=build_round_embed(round_index, total_rounds, timeout,
                                            decoys, frame),
                    view=view,
                )
            except discord.HTTPException:
                return
    except asyncio.CancelledError:
        return


# ── Game runner ───────────────────────────────────────────────────────────────

# channel_id -> True while a game is running there.
active_games: Dict[int, bool] = {}


def score_round(view: _RoundView, streak: int) -> int:
    """Points for a won round: base, plus speed, plus streak."""
    speed_bonus = round(MAX_SPEED_BONUS * view.time_left_fraction())
    return BASE_ROUND_POINTS + speed_bonus + STREAK_BONUS * max(0, streak - 1)


async def run_game(channel: discord.abc.Messageable,
                   invoked_by: Optional[discord.Member] = None) -> None:
    """Play a full multi-round Grinch game in `channel`."""
    channel_id = getattr(channel, "id", None)
    if channel_id is None:
        return
    if active_games.get(channel_id):
        return

    active_games[channel_id] = True
    total_rounds = len(ROUND_TIMERS)

    round_wins: Dict[int, int] = {}
    names: Dict[int, str] = {}
    best_times: Dict[int, int] = {}
    participants: set = set()
    last_winner_id: Optional[int] = None
    streak = 0

    try:
        for index, (timeout, decoys) in enumerate(zip(ROUND_TIMERS, ROUND_DECOYS),
                                                  start=1):
            view = _RoundView(index, timeout, decoys)
            message = await channel.send(
                embed=build_round_embed(index, total_rounds, timeout, decoys),
                view=view,
            )
            view.message = message

            animation = asyncio.create_task(
                animate_round(message, view, index, total_rounds, timeout, decoys)
            )
            await view.wait()
            animation.cancel()
            try:
                await animation
            except asyncio.CancelledError:
                pass

            participants.update(view.eliminated)
            for user in view.decoy_hits:
                names[user.id] = user.display_name

            points = 0
            if view.winner is not None:
                winner_id = view.winner.id
                participants.add(winner_id)
                names[winner_id] = view.winner.display_name

                # Streak counts consecutive rounds taken by the same player.
                streak = streak + 1 if last_winner_id == winner_id else 1
                last_winner_id = winner_id

                points = score_round(view, streak)
                round_wins[winner_id] = round_wins.get(winner_id, 0) + 1

                reaction_ms = view.reaction_ms or 0
                if (winner_id not in best_times
                        or reaction_ms < best_times[winner_id]):
                    best_times[winner_id] = reaction_ms

                storage.add_score(winner_id, points)
                record_round_win(winner_id, reaction_ms, points)
            else:
                # A missed round breaks any streak.
                streak = 0
                last_winner_id = None

            try:
                await message.edit(
                    embed=build_round_result_embed(view, points, streak),
                    view=None,
                )
            except discord.HTTPException:
                pass

            # Breathing room between rounds.
            if index < total_rounds:
                await asyncio.sleep(2.0)

        overall_winner = (
            max(round_wins.items(), key=lambda kv: kv[1])[0]
            if round_wins else None
        )
        if overall_winner is not None:
            storage.add_score(overall_winner, GAME_WIN_POINTS)
        record_game_finished(participants, overall_winner)

        await channel.send(
            embed=build_final_embed(round_wins, names, best_times, total_rounds)
        )

    except Exception as exc:
        print(f"[GRINCH] Game in channel {channel_id} failed: {exc}")
    finally:
        active_games[channel_id] = False


# ── Leaderboard ───────────────────────────────────────────────────────────────

def build_leaderboard_embed(bot: commands.Bot, guild: Optional[discord.Guild],
                            limit: int = 10) -> discord.Embed:
    """All-time Grinch rankings, restricted to the current guild's members."""
    entries = []
    for raw_id, record in _stats.items():
        try:
            user_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if guild is not None and guild.get_member(user_id) is None:
            continue
        if not record.get("rounds_won") and not record.get("games_played"):
            continue
        entries.append((user_id, record))

    entries.sort(
        key=lambda item: (item[1].get("games_won", 0),
                          item[1].get("rounds_won", 0),
                          item[1].get("total_points", 0)),
        reverse=True,
    )

    embed = discord.Embed(
        title="\U0001F384 Grinch Hall of Fame",
        color=0x2ECC71,
    )

    if not entries:
        embed.description = "Nobody has played yet. Run `!merrychristmas`."
        return embed

    medals = {1: "\U0001F947", 2: "\U0001F948", 3: "\U0001F949"}
    lines = []
    for position, (user_id, record) in enumerate(entries[:limit], start=1):
        member = guild.get_member(user_id) if guild else None
        name = member.display_name if member else f"User {user_id}"
        best = record.get("best_ms")
        lines.append(
            f"{medals.get(position, f'`{position}.`')} **{name}** — "
            f"{record.get('games_won', 0)} wins · "
            f"{record.get('rounds_won', 0)} rounds · "
            f"{record.get('total_points', 0)} pts"
            + (f" · best {best} ms" if best else "")
        )

    embed.description = "\n".join(lines)
    embed.set_footer(text=f"{len(entries)} players ranked")
    return embed


def build_personal_embed(member: discord.Member) -> discord.Embed:
    """One player's Grinch record."""
    record = _stats.get(str(member.id))
    embed = discord.Embed(
        title=f"\U0001F384 Grinch record — {member.display_name}",
        color=0x2ECC71,
    )
    if not record:
        embed.description = "No games played yet. Run `!merrychristmas`."
        return embed

    played = record.get("games_played", 0)
    won = record.get("games_won", 0)
    win_rate = f"{(won / played * 100):.0f}%" if played else "n/a"

    embed.add_field(name="Games won", value=f"{won}/{played} ({win_rate})")
    embed.add_field(name="Rounds won", value=str(record.get("rounds_won", 0)))
    embed.add_field(name="Points earned", value=str(record.get("total_points", 0)))
    best = record.get("best_ms")
    embed.add_field(name="Best reaction", value=f"{best} ms" if best else "n/a")
    embed.add_field(name="Decoys hit", value=str(record.get("decoys_hit", 0)))
    embed.set_thumbnail(url=member.display_avatar.url)
    return embed


# ── Registration ──────────────────────────────────────────────────────────────

def setup(bot: commands.Bot) -> None:
    """Register the Christmas commands on `bot`.

    The December auto-trigger stays in main.py's on_message, which calls
    run_game() directly.
    """

    @bot.command(name="merrychristmas")
    async def merrychristmas(ctx: commands.Context):
        """Start a Grinch game on demand, inside the event window."""
        # main.py owns the date check so the window constants live in one place.
        gate = getattr(bot, "christmas_window_check", None)
        if gate is not None and not gate():
            await ctx.reply(
                "\U0001F384 The Grinch event runs from **1 to 25 December** (IST). "
                "Check back then!"
            )
            return

        if active_games.get(ctx.channel.id):
            await ctx.reply("A Grinch game is already running in this channel.")
            return

        await run_game(ctx.channel, invoked_by=ctx.author)

    @bot.command(name="grinchboard", aliases=["grinchstats"])
    async def grinchboard(ctx: commands.Context, member: discord.Member = None):
        """All-time Grinch rankings, or one player's record."""
        if member is not None:
            await ctx.send(embed=build_personal_embed(member))
        else:
            await ctx.send(embed=build_leaderboard_embed(bot, ctx.guild))

    @bot.command(name="christmashelp")
    async def christmashelp(ctx: commands.Context):
        """Explain how the Grinch event works."""
        embed = discord.Embed(
            title="\U0001F384 Grinch Event \u2014 How it works",
            description=(
                f"**{len(ROUND_TIMERS)} rounds.** The timer shrinks each round "
                f"({', '.join(f'{t:g}s' for t in ROUND_TIMERS)}) and more decoy "
                "buttons appear."
            ),
            color=0xE63946,
        )
        embed.add_field(
            name="Winning a round",
            value=(
                "Be first to hit **Stop the Grinch!**. Hitting a decoy knocks "
                "you out for that round only."
            ),
            inline=False,
        )
        embed.add_field(
            name="Scoring",
            value=(
                f"\u2022 **{BASE_ROUND_POINTS}** points per round won\n"
                f"\u2022 up to **+{MAX_SPEED_BONUS}** for a fast reaction\n"
                f"\u2022 **+{STREAK_BONUS}** per extra consecutive round won\n"
                f"\u2022 **+{GAME_WIN_POINTS}** for taking the most rounds"
            ),
            inline=False,
        )
        embed.add_field(
            name="Commands",
            value=(
                "`!merrychristmas` start a game\n"
                "`!grinchboard` all-time rankings\n"
                "`!grinchboard @user` one player's record"
            ),
            inline=False,
        )
        embed.set_footer(text="Runs 1-25 December (IST). Also triggers at random in chat.")
        await ctx.send(embed=embed)

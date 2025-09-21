from keep_alive import keep_alive
keep_alive()
import discord
from discord.ext import commands
from typing import Dict, Set
import logging
from dotenv import load_dotenv
from datetime import timedelta
import os
import time
import random
import json
import asyncio

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = os.getenv("GUILD_ID")

GUILD = discord.Object(id=int(GUILD_ID)) if GUILD_ID else None

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content=True
intents.members=True

bot=commands.Bot(command_prefix='!',intents=intents)


@bot.event
async def on_ready():
    await bot.tree.sync(guild=GUILD)  # instant for this server
    print(f"✅ Synced slash commands to {GUILD_ID}")
    print(f"Logged in as {bot.user}")

# Dictionary mapping guild (server) IDs to their welcome channel IDs
welcome_channels = {
    1411425019434766499: 1411426415450263585,  # Example: Server A channel
    1210475350119813120: 1418594720774619218,  # Example: Server B channel
    # Add more servers here
}

@bot.event
async def on_member_join(member: discord.Member):
    """Send an embed welcome message with profile pic to the correct channel per server."""

    guild_id = member.guild.id
    channel_id = welcome_channels.get(guild_id)

    if channel_id:
        channel = member.guild.get_channel(channel_id)
    else:
        channel = member.guild.system_channel  # fallback to system channel
    if not channel:
        return  # no channel found, do nothing

    # Make the embed
    embed = discord.Embed(
        title=f"🎉 Welcome to {member.guild.name}!",
        description=(
            f"Hey {member.mention}, welcome aboard! We’re excited to have you here.\n\n"
            f"Take a look at the rules, introduce yourself, and enjoy your stay 🚀"
        ),
        color=discord.Color.blurple()
    )
    embed.set_thumbnail(url=member.display_avatar.url)  # user's profile picture
    embed.set_footer(text=f"You’re member #{len(member.guild.members)} in {member.guild.name}!")

    await channel.send(embed=embed)
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if "scrub" in message.content.lower():
        await message.delete()

    await bot.process_commands(message)


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Trigger → list of 3 custom emoji IDs
    triggers = {
        "appbcbash": [
            1414192630165667872,
            1414188725163790336,
            1414192628010061824
        ],
        "appbceq": [1414188725163790336],
        "appbaa": [1414192630165667872],
        "appsheriff": [1414192628010061824]
    }

    content = message.content.lower()
    for word, emoji_ids in triggers.items():
        if word in content:
            for emoji_id in emoji_ids:
                emoji = bot.get_emoji(emoji_id)
                if emoji:
                    try:
                        await message.add_reaction(emoji)
                    except discord.Forbidden:
                        print("Missing permission: Add Reactions or Read Message History")
                    except discord.HTTPException:
                        print(f"Could not react with emoji ID {emoji_id}")

    await bot.process_commands(message)
@bot.command()
async def hello(ctx):
    await ctx.send(f"Hello I am Launch Tower")
@bot.command()
async def catch(ctx):
    await ctx.send(f"You know who didn't get any catch without any issues its Booster 16 ")
@bot.command()
async def vent(ctx):
    await ctx.send(f"I am venting whieeeeee 💨💨💨")

@bot.command()
async def explore(ctx):
    await ctx.send(f"Hey stop bothering me it will come soon™️")

GUILD_IDS = [
    1411425019434766499,  # Replace with your first guild ID
    1397218218535424090,
    1210475350119813120,# Replace with your second guild ID
    # Add more guild IDs as needed
]

# Convert guild IDs to discord.Object instances
GUILDS = [discord.Object(id=guild_id) for guild_id in GUILD_IDS]

@bot.command(name="ping")
async def ping(ctx):
    start = time.perf_counter()

    # Send initial response
    message = await ctx.send("🏓 Pong...")

    end = time.perf_counter()
    response_time = (end - start) * 1000  # ms
    ws_latency = bot.latency * 1000       # WebSocket latency (ms)
    micro_latency = (end - start) * 1000  # Processing latency (same as response_time here)

    # Create embed
    embed = discord.Embed(
        title="pong! 🏓",
        color=discord.Color.red()
    )

    embed.add_field(name="⏳ Time", value=f"{int(response_time)} ms", inline=False)
    embed.add_field(name="✨ Micro", value=f"{int(micro_latency)} ms", inline=False)
    embed.add_field(name="📡 WS", value=f"{int(ws_latency)} ms", inline=False)

    embed.set_footer(text=f"{ctx.author} • {time.strftime('%I:%M %p')}")

    # Edit original response to show embed
    await message.edit(content=None, embed=embed)

@bot.tree.command(name="ping", description="Check the bot's latency")
async def ping(interaction: discord.Interaction):
    start = time.perf_counter()

    # Send initial response
    await interaction.response.send_message("🏓 Pong...")

    end = time.perf_counter()
    response_time = (end - start) * 1000  # ms
    ws_latency = bot.latency * 1000       # WebSocket latency (ms)
    micro_latency = (end - start) * 1000  # Processing latency (same as response_time here)

    # Create embed
    embed = discord.Embed(
        title="pong! 🏓",
        color=discord.Color.red()
    )

    embed.add_field(name="⏳ Time", value=f"{int(response_time)} ms", inline=False)
    embed.add_field(name="✨ Micro", value=f"{int(micro_latency)} ms", inline=False)
    embed.add_field(name="📡 WS", value=f"{int(ws_latency)} ms", inline=False)

    embed.set_footer(text=f"{interaction.user} • {time.strftime('%I:%M %p')}")

    # Edit original response to show embed
    await interaction.edit_original_response(content=None, embed=embed)

'''@bot.tree.command(name="ping", description="Check the bot's latency", guild=GUILD)
async def ping(interaction: discord.Interaction):
    start = time.perf_counter()

    # Send initial response
    await interaction.response.send_message("🏓 Pong...", ephemeral=True)

    end = time.perf_counter()
    response_time = (end - start) * 1000  # ms
    ws_latency = bot.latency * 1000       # WebSocket latency (ms)
    micro_latency = (end - start) * 1000  # Processing latency (same as response_time here)

    # Create embed
    embed = discord.Embed(
        title="pong! 🏓",
        color=discord.Color.red()
    )

    embed.add_field(name="⏳ Time", value=f"{int(response_time)} ms", inline=False)
    embed.add_field(name="✨ Micro", value=f"{int(micro_latency)} ms", inline=False)
    embed.add_field(name="📡 WS", value=f"{int(ws_latency)} ms", inline=False)

    embed.set_footer(text=f"{interaction.user} • {time.strftime('%I:%M %p')}")

    # Edit original response to show embed
    await interaction.edit_original_response(content=None, embed=embed)'''

# In-memory scoreboard: {user_id: score}
scores = {}

def add_score(user_id, points=1):
    """Increment a user's score."""
    scores[user_id] = scores.get(user_id, 0) + points

# -----------------------------------
# 1️⃣ Rock Paper Scissors
# -----------------------------------
class RPSView(discord.ui.View):
    def __init__(self, ctx, timeout=30):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.user = ctx.author
        self.options = ["rock", "paper", "scissors"]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only the invoking user can click."""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "⚠️ This RPS session isn’t yours.", ephemeral=True
            )
            return False
        return True

    async def play(self, interaction, user_choice):
        bot_choice = random.choice(self.options)
        if user_choice == bot_choice:
            result = "It's a draw! 🤝"
            color = discord.Color.yellow()
        elif (
            (user_choice == "rock" and bot_choice == "scissors")
            or (user_choice == "paper" and bot_choice == "rock")
            or (user_choice == "scissors" and bot_choice == "paper")
        ):
            result = "You win! 🎉 (+1 point)"
            add_score(interaction.user.id, 1)
            color = discord.Color.green()
        else:
            result = "You lose! 😢"
            color = discord.Color.red()

        embed = discord.Embed(
            title="🪨📄✂️ Rock Paper Scissors",
            color=color
        )
        embed.add_field(name="Your Choice", value=user_choice.capitalize())
        embed.add_field(name="Bot's Choice", value=bot_choice.capitalize())
        embed.add_field(name="Result", value=result, inline=False)

        # Disable buttons after click
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🪨 Rock", style=discord.ButtonStyle.primary)
    async def rock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play(interaction, "rock")

    @discord.ui.button(label="📄 Paper", style=discord.ButtonStyle.primary)
    async def paper(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play(interaction, "paper")

    @discord.ui.button(label="✂️ Scissors", style=discord.ButtonStyle.primary)
    async def scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play(interaction, "scissors")


@bot.command(name="rps")
async def rps(ctx):
    """Start an interactive Rock-Paper-Scissors game with buttons."""
    embed = discord.Embed(
        title="🪨📄✂️ Rock Paper Scissors",
        description=f"{ctx.author.mention}, click a button below to play!",
        color=discord.Color.blurple()
    )
    view = RPSView(ctx)
    await ctx.send(embed=embed, view=view)

# -----------------------------------
# 2️⃣ Coin Flip
# -----------------------------------
class CoinFlipView(discord.ui.View):
    def __init__(self, ctx, timeout=30):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.user = ctx.author

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the user who started the game can press the button."""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "⚠️ This coin flip session isn’t yours.", ephemeral=True
            )
            return False
        return True

    async def flip_coin(self, interaction, guess):
        result = random.choice(["heads", "tails"])
        if guess == result:
            desc = f"It’s **{result.capitalize()}**! You guessed right 🎉 (+1 point)"
            add_score(interaction.user.id, 1)
            color = discord.Color.green()
        else:
            desc = f"It’s **{result.capitalize()}**! You guessed wrong 😢"
            color = discord.Color.red()

        embed = discord.Embed(
            title="🪙 Coin Flip",
            description=desc,
            color=color
        )

        # Disable all buttons after click
        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🪙 Heads", style=discord.ButtonStyle.primary)
    async def heads(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.flip_coin(interaction, "heads")

    @discord.ui.button(label="🪙 Tails", style=discord.ButtonStyle.secondary)
    async def tails(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.flip_coin(interaction, "tails")


@bot.command(name="coinflip")
async def coinflip(ctx):
    """Interactive Coin Flip with UI buttons."""
    embed = discord.Embed(
        title="🪙 Coin Flip",
        description=f"{ctx.author.mention}, choose **Heads** or **Tails** below!",
        color=discord.Color.gold()
    )
    view = CoinFlipView(ctx)
    await ctx.send(embed=embed, view=view)

# -----------------------------------
# 3️⃣ Dice Roll
# -----------------------------------
@bot.command(name="dice")
async def dice(ctx, guess: int = None, sides: int = 6):
    """Roll a dice. Usage: !dice [guess] [sides]"""
    if sides <= 1:
        embed = discord.Embed(
            title="🎲 Dice Roll",
            description="Please use at least 2 sides.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    result = random.randint(1, sides)

    if guess and 1 <= guess <= sides:
        if guess == result:
            desc = f"You rolled **{result}**. 🎉 You guessed correctly (+1 point)"
            add_score(ctx.author.id, 1)
        else:
            desc = f"You rolled **{result}**. 😢 You guessed wrong."
    else:
        desc = f"You rolled **{result}**."

    embed = discord.Embed(
        title="🎲 Dice Roll",
        description=desc,
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

# -----------------------------------
# 4️⃣ Number Guessing
# -----------------------------------
class GuessModal(discord.ui.Modal, title="🔢 Number Guessing Game"):
    def __init__(self, ctx, number):
        super().__init__()
        self.ctx = ctx
        self.number = number

        self.guess_input = discord.ui.TextInput(
            label="Enter your guess (1-10):",
            style=discord.TextStyle.short,
            placeholder="Type a number between 1 and 10",
            required=True,
            max_length=2
        )
        self.add_item(self.guess_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            guess_num = int(self.guess_input.value)
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid number! Please type a valid integer.", ephemeral=True
            )
            return

        if guess_num == self.number:
            embed = discord.Embed(
                title="🎉 Correct!",
                description=f"You guessed it! The number was **{self.number}** (+1 point).",
                color=discord.Color.green()
            )
            add_score(interaction.user.id, 1)
        else:
            embed = discord.Embed(
                title="😢 Wrong Guess",
                description=f"Nope, the number was **{self.number}**.",
                color=discord.Color.red()
            )

        await interaction.response.edit_message(embed=embed, view=None)


class GuessView(discord.ui.View):
    def __init__(self, ctx, number):
        super().__init__(timeout=15)
        self.ctx = ctx
        self.number = number

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "⚠️ This guessing session isn’t yours.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Make a Guess", style=discord.ButtonStyle.primary, emoji="🎲")
    async def make_guess(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = GuessModal(self.ctx, self.number)
        await interaction.response.send_modal(modal)


@bot.command(name="guess")
async def guess(ctx):
    number = random.randint(1, 10)

    embed = discord.Embed(
        title="🔢 Number Guessing Game",
        description=f"I picked a number between **1 and 10**.\nClick below to make your guess!",
        color=discord.Color.purple()
    )

    view = GuessView(ctx, number)
    await ctx.send(embed=embed, view=view)

# -----------------------------------
# 5️⃣ Scoreboard Commands
# -----------------------------------
LEADER_ROLE_MAP = {
    1411425019434766499: 1415720279631593573,  # Server 1 -> Leader Role ID
    1210475350119813120: 1418973555953238057,
    1397218218535424090: 1419273410122612737# Server 2 -> Leader Role ID
    # Add more servers and their leader role IDs here
    # 1234567890123456789: 9876543210987654321,  # Server 3 -> Leader Role ID
    # 5555555555555555555: 4444444444444444444,  # Server 4 -> Leader Role ID
}


@bot.command(name="leaderboard")
async def leaderboard(ctx):
    """
    Show the leaderboard for this server and auto-assign Leader role.
    - Displays server name in header
    - Shows player avatars
    - Assigns Leader role to the top scorer in this server
    - Uses server-specific Leader role mapping
    """

    # Filter only scores of members in the current server
    guild = ctx.guild
    guild_id = guild.id
    guild_member_ids = [member.id for member in guild.members]
    guild_scores = {uid: pts for uid, pts in scores.items() if int(uid) in guild_member_ids}

    if not guild_scores:
        no_scores_embed = discord.Embed(
            title="📊 Leaderboard",
            description="⚠️ No scores available for this server yet.\n\nStart playing games to appear on the leaderboard!",
            color=discord.Color.orange()
        )
        if guild.icon:
            no_scores_embed.set_thumbnail(url=guild.icon.url)
        no_scores_embed.add_field(name="Available Games", value="`!trivia` • `!unscramble`", inline=False)
        await ctx.send(embed=no_scores_embed)
        return

    # Sort scores (highest first)
    sorted_scores = sorted(guild_scores.items(), key=lambda x: x[1], reverse=True)
    top_10 = sorted_scores[:10]

    # Beautify leaderboard text with medals and formatting
    leaderboard_text = ""
    medal_emojis = ["🥇", "🥈", "🥉"]

    for i, (user_id, score) in enumerate(top_10, start=1):
        member = guild.get_member(int(user_id))
        if member:  # Only display if still in server
            # Use medal emojis for top 3, numbers for the rest
            if i <= 3:
                position_indicator = medal_emojis[i - 1]
            else:
                position_indicator = f"**{i}.**"

            # Add crown emoji for the leader
            leader_indicator = " 👑" if i == 1 else ""

            leaderboard_text += f"{position_indicator} **{member.display_name}**{leader_indicator} — **{score:,}** point{'s' if score != 1 else ''}\n"

    embed = discord.Embed(
        title=f"🏆 Leaderboard — {guild.name}",
        description=leaderboard_text,
        color=discord.Color.gold(),
        timestamp=ctx.message.created_at
    )

    # Add server stats
    total_players = len(guild_scores)
    total_points = sum(guild_scores.values())
    embed.add_field(name="📈 Server Stats",
                    value=f"**{total_players}** player{'s' if total_players != 1 else ''}\n**{total_points:,}** total points",
                    inline=True)

    # Show if leader role assignment is configured
    leader_role_id = LEADER_ROLE_MAP.get(guild_id)
    if leader_role_id:
        leader_role = guild.get_role(leader_role_id)
        role_status = "✅ Configured" if leader_role else "❌ Role not found"
    else:
        role_status = "❌ Not configured"

    embed.add_field(name="👑 Leader Role", value=role_status, inline=True)
    embed.add_field(name="🎮 Games", value="`!trivia` • `!unscramble`", inline=True)

    # Thumbnail as server icon
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    embed.set_footer(text=f"Requested by {ctx.author.name}")

    await ctx.send(embed=embed)

    # 🟩 Handle Leader role assignment automatically in this server
    if guild_id not in LEADER_ROLE_MAP:
        info_embed = discord.Embed(
            title="ℹ️ Leader Role Not Configured",
            description=f"This server doesn't have a Leader role configured.\n\nTo set up automatic leader role assignment, add server ID `{guild_id}` to the role mapping.",
            color=discord.Color.blue()
        )
        info_embed.add_field(name="Server ID", value=f"`{guild_id}`", inline=True)
        info_embed.add_field(name="Current Leader", value=f"{guild.get_member(int(sorted_scores[0][0])).mention}",
                             inline=True)
        await ctx.send(embed=info_embed)
        return

    try:
        # Get the configured Leader role ID for this server
        leader_role_id = LEADER_ROLE_MAP[guild_id]

        # Get the top user ID
        top_user_id = int(sorted_scores[0][0])
        top_member = guild.get_member(top_user_id)

        # Get the Leader role
        role = guild.get_role(leader_role_id)
        if role is None:
            error_embed = discord.Embed(
                title="❌ Leader Role Error",
                description=f"Leader role with ID `{leader_role_id}` not found in **{guild.name}**.",
                color=discord.Color.red()
            )
            error_embed.add_field(name="Server ID", value=f"`{guild_id}`", inline=True)
            error_embed.add_field(name="Expected Role ID", value=f"`{leader_role_id}`", inline=True)
            error_embed.add_field(name="Solution", value="Create the role or update the role mapping", inline=False)
            await ctx.send(embed=error_embed)
            return

        # Track role changes
        role_removed_from = []
        role_assignment_failed = False

        # Remove role from everyone else who has it
        for member in guild.members:
            if role in member.roles and member.id != top_user_id:
                try:
                    await member.remove_roles(role, reason="No longer the leaderboard leader")
                    role_removed_from.append(member.display_name)
                except discord.Forbidden:
                    error_embed = discord.Embed(
                        title="❌ Permission Error",
                        description="I lack permission to remove the Leader role from some members.",
                        color=discord.Color.red()
                    )
                    error_embed.add_field(name="Required Permission", value="Manage Roles", inline=True)
                    error_embed.add_field(name="Role Position", value="Bot role must be higher than Leader role",
                                          inline=True)
                    await ctx.send(embed=error_embed)
                    return
                except Exception as e:
                    print(f"Error removing role from {member.name}: {e}")

        # Add role to the top player if not already assigned
        if top_member and role not in top_member.roles:
            try:
                await top_member.add_roles(role, reason="New leaderboard leader")

                # Success message
                success_embed = discord.Embed(
                    title="👑 New Leader Crowned!",
                    description=f"🎉 {top_member.mention} is now the **{role.name}** of **{guild.name}**!",
                    color=discord.Color.gold(),
                    timestamp=ctx.message.created_at
                )
                success_embed.add_field(name="🏆 Score", value=f"{sorted_scores[0][1]:,} points", inline=True)
                success_embed.add_field(name="🎯 Role", value=role.mention, inline=True)

                if role_removed_from:
                    success_embed.add_field(
                        name="📋 Role Updates",
                        value=f"Role removed from: {', '.join(role_removed_from[:3])}" +
                              (f" and {len(role_removed_from) - 3} others" if len(role_removed_from) > 3 else ""),
                        inline=False
                    )

                success_embed.set_thumbnail(url=top_member.display_avatar.url)
                await ctx.send(embed=success_embed)

            except discord.Forbidden:
                error_embed = discord.Embed(
                    title="❌ Permission Error",
                    description="I lack permission to assign the Leader role.",
                    color=discord.Color.red()
                )
                error_embed.add_field(name="Required Permission", value="Manage Roles", inline=True)
                error_embed.add_field(name="Role Hierarchy", value="Bot role must be higher than Leader role",
                                      inline=True)
                error_embed.add_field(name="Current Leader",
                                      value=f"{top_member.mention} ({sorted_scores[0][1]:,} points)", inline=False)
                await ctx.send(embed=error_embed)
            except Exception as e:
                error_embed = discord.Embed(
                    title="❌ Unexpected Error",
                    description=f"Failed to assign Leader role: `{str(e)}`",
                    color=discord.Color.red()
                )
                await ctx.send(embed=error_embed)

        elif top_member and role in top_member.roles:
            # Leader already has the role
            already_leader_embed = discord.Embed(
                title="👑 Leader Confirmed",
                description=f"{top_member.mention} remains the **{role.name}** of **{guild.name}**!",
                color=discord.Color.green()
            )
            already_leader_embed.add_field(name="🏆 Score", value=f"{sorted_scores[0][1]:,} points", inline=True)
            already_leader_embed.add_field(name="🎯 Status", value="Still leading!", inline=True)
            already_leader_embed.set_thumbnail(url=top_member.display_avatar.url)

            if role_removed_from:
                already_leader_embed.add_field(
                    name="📋 Role Updates",
                    value=f"Role removed from: {', '.join(role_removed_from[:3])}" +
                          (f" and {len(role_removed_from) - 3} others" if len(role_removed_from) > 3 else ""),
                    inline=False
                )

            await ctx.send(embed=already_leader_embed)

    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Leader Role Assignment Failed",
            description=f"An unexpected error occurred: `{str(e)}`",
            color=discord.Color.red()
        )
        error_embed.add_field(name="Server", value=guild.name, inline=True)
        error_embed.add_field(name="Leader Role ID", value=f"`{LEADER_ROLE_MAP.get(guild_id, 'Not configured')}`",
                              inline=True)
        await ctx.send(embed=error_embed)


# Optional: Command to check/manage role mappings (Master only)
@bot.command(name="role_mapping")
async def role_mapping(ctx, action: str = None, server_id: int = None, role_id: int = None):
    """Manage Leader role mappings. Usage: !role_mapping [list/add/remove] [server_id] [role_id]"""
    author_id = int(ctx.author.id)

    # Only master can manage role mappings
    if author_id != MASTER_ID:
        error_embed = discord.Embed(
            title="❌ Access Denied",
            description="Only the master user can manage role mappings.",
            color=discord.Color.red()
        )
        return await ctx.send(embed=error_embed)

    if action is None or action.lower() == "list":
        # Show current mappings
        mapping_embed = discord.Embed(
            title="👑 Leader Role Mappings",
            description="Current server → role mappings:",
            color=discord.Color.blue()
        )

        if not LEADER_ROLE_MAP:
            mapping_embed.description = "No role mappings configured."
        else:
            mapping_text = ""
            for guild_id, role_id in LEADER_ROLE_MAP.items():
                guild = bot.get_guild(guild_id)
                guild_name = guild.name if guild else f"Unknown Server ({guild_id})"

                if guild:
                    role = guild.get_role(role_id)
                    role_name = role.name if role else f"Unknown Role ({role_id})"
                    status = "✅" if role else "❌"
                else:
                    role_name = f"Role ID: {role_id}"
                    status = "❓"

                mapping_text += f"{status} **{guild_name}**\n└ Role: {role_name} (`{role_id}`)\n\n"

            mapping_embed.description = mapping_text

        mapping_embed.set_footer(text="Use !role_mapping add [server_id] [role_id] to add mappings")
        await ctx.send(embed=mapping_embed)

    elif action.lower() == "add":
        if server_id is None or role_id is None:
            await ctx.send("❌ Usage: `!role_mapping add [server_id] [role_id]`")
            return

        LEADER_ROLE_MAP[server_id] = role_id

        # Try to get server and role info
        guild = bot.get_guild(server_id)
        guild_name = guild.name if guild else f"Server ID: {server_id}"

        if guild:
            role = guild.get_role(role_id)
            role_name = role.name if role else f"Role ID: {role_id}"
            status = "✅ Valid" if role else "⚠️ Role not found"
        else:
            role_name = f"Role ID: {role_id}"
            status = "⚠️ Server not accessible"

        add_embed = discord.Embed(
            title="✅ Role Mapping Added",
            description=f"Added mapping for **{guild_name}**",
            color=discord.Color.green()
        )
        add_embed.add_field(name="Server ID", value=f"`{server_id}`", inline=True)
        add_embed.add_field(name="Role", value=role_name, inline=True)
        add_embed.add_field(name="Status", value=status, inline=True)
        await ctx.send(embed=add_embed)

    elif action.lower() == "remove":
        if server_id is None:
            await ctx.send("❌ Usage: `!role_mapping remove [server_id]`")
            return

        if server_id in LEADER_ROLE_MAP:
            removed_role_id = LEADER_ROLE_MAP.pop(server_id)
            guild = bot.get_guild(server_id)
            guild_name = guild.name if guild else f"Server ID: {server_id}"

            remove_embed = discord.Embed(
                title="🗑️ Role Mapping Removed",
                description=f"Removed mapping for **{guild_name}**",
                color=discord.Color.orange()
            )
            remove_embed.add_field(name="Server ID", value=f"`{server_id}`", inline=True)
            remove_embed.add_field(name="Removed Role ID", value=f"`{removed_role_id}`", inline=True)
            await ctx.send(embed=remove_embed)
        else:
            await ctx.send(f"❌ No mapping found for server ID `{server_id}`.")

    else:
        help_embed = discord.Embed(
            title="❓ Role Mapping Help",
            description="**Usage:** `!role_mapping [action] [parameters]`",
            color=discord.Color.blue()
        )
        help_embed.add_field(name="📋 List Mappings", value="`!role_mapping list`", inline=False)
        help_embed.add_field(name="➕ Add Mapping", value="`!role_mapping add [server_id] [role_id]`", inline=False)
        help_embed.add_field(name="➖ Remove Mapping", value="`!role_mapping remove [server_id]`", inline=False)
        await ctx.send(embed=help_embed)




# 60 Space Trivia Questions (20 each difficulty)
TRIVIA_QUESTIONS = {
    "easy": [
        {"question": "Which planet is closest to the Sun?", "options": ["Mercury", "Venus", "Earth"],
         "answer": "Mercury"},
        {"question": "Which planet is known as the Red Planet?", "options": ["Mars", "Venus", "Jupiter"],
         "answer": "Mars"},
        {"question": "What galaxy is Earth located in?", "options": ["Milky Way", "Andromeda", "Triangulum"],
         "answer": "Milky Way"},
        {"question": "Which planet has rings visible from Earth?", "options": ["Saturn", "Jupiter", "Neptune"],
         "answer": "Saturn"},
        {"question": "Which planet has the Great Red Spot?", "options": ["Jupiter", "Mars", "Saturn"],
         "answer": "Jupiter"},
        {"question": "What is the smallest planet in our solar system?", "options": ["Mercury", "Mars", "Venus"],
         "answer": "Mercury"},
        {"question": "What is the Sun mostly made of?", "options": ["Hydrogen", "Oxygen", "Helium"],
         "answer": "Hydrogen"},
        {"question": "Which planet is famous for its rings?", "options": ["Saturn", "Uranus", "Neptune"],
         "answer": "Saturn"},
        {"question": "Which is the third planet from the Sun?", "options": ["Earth", "Venus", "Mars"],
         "answer": "Earth"},
        {"question": "Which is the hottest planet?", "options": ["Venus", "Mercury", "Mars"], "answer": "Venus"},
        {"question": "What is the Moon's gravitational pull compared to Earth?", "options": ["1/6th", "1/2", "1/10th"],
         "answer": "1/6th"},
        {"question": "Which planet rotates on its side?", "options": ["Uranus", "Neptune", "Venus"],
         "answer": "Uranus"},
        {"question": "Which planet has the fastest rotation?", "options": ["Jupiter", "Saturn", "Earth"],
         "answer": "Jupiter"},
        {"question": "What's the name of Earth's only natural satellite?", "options": ["Moon", "Phobos", "Europa"],
         "answer": "Moon"},
        {"question": "Which planet has Olympus Mons?", "options": ["Mars", "Earth", "Venus"], "answer": "Mars"},
        {"question": "How many planets are in the Solar System?", "options": ["8", "9", "7"], "answer": "8"},
        {"question": "Which planet has a day longer than its year?", "options": ["Venus", "Mercury", "Mars"],
         "answer": "Venus"},
        {"question": "Who was the first human in space?", "options": ["Yuri Gagarin", "Neil Armstrong", "Buzz Aldrin"],
         "answer": "Yuri Gagarin"},
        {"question": "What is the name of our star?", "options": ["Sun", "Sirius", "Proxima"], "answer": "Sun"},
        {"question": "What do we call a large rock in space?", "options": ["Asteroid", "Comet", "Meteor"],
         "answer": "Asteroid"},
    ],
    "medium": [
        {"question": "Which planet has the most moons?", "options": ["Saturn", "Jupiter", "Neptune"],
         "answer": "Saturn"},
        {"question": "What's the name of the first artificial satellite?",
         "options": ["Sputnik 1", "Explorer 1", "Vostok 1"], "answer": "Sputnik 1"},
        {"question": "Which planet is tilted at 98 degrees?", "options": ["Uranus", "Neptune", "Saturn"],
         "answer": "Uranus"},
        {"question": "How many planets have rings?", "options": ["4", "2", "1"], "answer": "4"},
        {"question": "Which dwarf planet is in the asteroid belt?", "options": ["Ceres", "Pluto", "Eris"],
         "answer": "Ceres"},
        {"question": "Which planet has the fastest winds?", "options": ["Neptune", "Saturn", "Mars"],
         "answer": "Neptune"},
        {"question": "Which space telescope launched in 1990?", "options": ["Hubble", "Kepler", "Chandra"],
         "answer": "Hubble"},
        {"question": "What's the largest planet?", "options": ["Jupiter", "Saturn", "Neptune"], "answer": "Jupiter"},
        {"question": "What's the coldest planet?", "options": ["Neptune", "Uranus", "Pluto"], "answer": "Neptune"},
        {"question": "Which mission first landed humans on the Moon?",
         "options": ["Apollo 11", "Apollo 12", "Apollo 10"], "answer": "Apollo 11"},
        {"question": "Which planet has methane lakes?", "options": ["Titan (moon)", "Mars", "Venus"],
         "answer": "Titan (moon)"},
        {"question": "What's the name of Mars' largest moon?", "options": ["Phobos", "Deimos", "Europa"],
         "answer": "Phobos"},
        {"question": "What does NASA stand for?",
         "options": ["National Aeronautics and Space Administration", "National Aerospace and Space Association",
                     "New Aeronautics Space Agency"], "answer": "National Aeronautics and Space Administration"},
        {"question": "Which probe left the solar system first?", "options": ["Voyager 1", "Voyager 2", "Pioneer 10"],
         "answer": "Voyager 1"},
        {"question": "What's the densest planet?", "options": ["Earth", "Jupiter", "Venus"], "answer": "Earth"},
        {"question": "Which planet has the tallest known mountain?", "options": ["Mars", "Venus", "Mercury"],
         "answer": "Mars"},
        {"question": "What's the most common type of star?", "options": ["Red Dwarf", "White Dwarf", "Blue Giant"],
         "answer": "Red Dwarf"},
        {"question": "What's the boundary of a black hole called?",
         "options": ["Event Horizon", "Singularity", "Accretion Disk"], "answer": "Event Horizon"},
        {"question": "What is the main gas of Neptune?", "options": ["Hydrogen", "Methane", "Oxygen"],
         "answer": "Methane"},
        {"question": "Which planet's day is about 10 hours long?", "options": ["Jupiter", "Mars", "Saturn"],
         "answer": "Jupiter"},
    ],
    "hard": [
        {"question": "Which moon has the highest albedo (reflectivity)?",
         "options": ["Enceladus", "Europa", "Ganymede"], "answer": "Enceladus"},
        {"question": "What's the average distance from Earth to the Sun?",
         "options": ["1 AU", "93 million miles", "Both"], "answer": "Both"},
        {"question": "Which planet has a hexagon-shaped storm?", "options": ["Saturn", "Jupiter", "Neptune"],
         "answer": "Saturn"},
        {"question": "What's the densest moon?", "options": ["Io", "Europa", "Titan"], "answer": "Io"},
        {"question": "Which spacecraft carried the Golden Record?", "options": ["Voyager", "Pioneer", "New Horizons"],
         "answer": "Voyager"},
        {"question": "What's the most volcanically active body?", "options": ["Io", "Earth", "Venus"], "answer": "Io"},
        {"question": "How long does sunlight take to reach Earth?", "options": ["8 minutes", "5 minutes", "10 minutes"],
         "answer": "8 minutes"},
        {"question": "Which exoplanet was the first discovered?", "options": ["51 Pegasi b", "Kepler-22b", "Proxima b"],
         "answer": "51 Pegasi b"},
        {"question": "What's the approximate age of the Universe?",
         "options": ["13.8 billion years", "10 billion years", "15 billion years"], "answer": "13.8 billion years"},
        {"question": "What's the smallest exoplanet discovered (as of now)?",
         "options": ["Kepler-37b", "Proxima b", "TRAPPIST-1d"], "answer": "Kepler-37b"},
        {"question": "Which star is closest to our Solar System?",
         "options": ["Proxima Centauri", "Alpha Centauri A", "Barnard's Star"], "answer": "Proxima Centauri"},
        {"question": "What's at the center of the Milky Way?",
         "options": ["Black Hole", "Neutron Star", "Dark Matter Cloud"], "answer": "Black Hole"},
        {"question": "What element powers the Sun?", "options": ["Hydrogen fusion", "Helium fusion", "Oxygen burning"],
         "answer": "Hydrogen fusion"},
        {"question": "Which mission landed on Titan?", "options": ["Huygens", "Viking", "New Horizons"],
         "answer": "Huygens"},
        {"question": "Which planet has a moon called Triton?", "options": ["Neptune", "Uranus", "Saturn"],
         "answer": "Neptune"},
        {"question": "Which galaxy is colliding with the Milky Way?",
         "options": ["Andromeda", "Triangulum", "Whirlpool"], "answer": "Andromeda"},
        {"question": "Which type of star explodes as a supernova?",
         "options": ["Massive Star", "Brown Dwarf", "Red Dwarf"], "answer": "Massive Star"},
        {"question": "What's the approximate escape velocity from Earth?",
         "options": ["11.2 km/s", "7.9 km/s", "15 km/s"], "answer": "11.2 km/s"},
        {"question": "Which moon has a subsurface ocean beneath its ice crust?",
         "options": ["Europa", "Enceladus", "Callisto"], "answer": "Europa"},
        {"question": "What's the name of the region of icy bodies beyond Neptune?",
         "options": ["Kuiper Belt", "Oort Cloud", "Asteroid Belt"], "answer": "Kuiper Belt"},
    ],
}

LETTERS = ["A", "B", "C"]


class TriviaDifficultyDropdown(discord.ui.Select):
    def __init__(self, ctx):
        self.ctx = ctx
        options = [
            discord.SelectOption(label="Easy", description="1 point per correct answer", emoji="🟩"),
            discord.SelectOption(label="Medium", description="2 points per correct answer", emoji="🟨"),
            discord.SelectOption(label="Hard", description="3 points per correct answer", emoji="🟥"),
        ]
        super().__init__(placeholder="Select Difficulty", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ This is not your trivia session.", ephemeral=True)
            return

        difficulty = self.values[0].lower()
        await interaction.response.defer()  # acknowledge

        await interaction.edit_original_response(content=f"🎲 Loading {difficulty.capitalize()} question…", view=None)
        await send_trivia_question(self.ctx, difficulty)


class TriviaDifficultyView(discord.ui.View):
    def __init__(self, ctx, timeout=60):
        super().__init__(timeout=timeout)
        self.add_item(TriviaDifficultyDropdown(ctx))


class AnswerButtons(discord.ui.View):
    def __init__(self, ctx, correct_letter, points, letter_to_option, q, difficulty):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.correct_letter = correct_letter
        self.points = points
        self.letter_to_option = letter_to_option
        self.q = q
        self.difficulty = difficulty
        for L in LETTERS:
            if L in letter_to_option:
                self.add_item(AnswerButton(L, self))

    async def disable_all(self, interaction):
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)


class AnswerButton(discord.ui.Button):
    def __init__(self, letter, parent_view):
        self.letter = letter
        self.parent_view = parent_view
        super().__init__(label=f"{letter}) {parent_view.letter_to_option[letter]}", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        view = self.parent_view
        if interaction.user != view.ctx.author:
            await interaction.response.send_message("❌ This is not your trivia session.", ephemeral=True)
            return

        chosen = self.letter
        chosen_answer = view.letter_to_option[chosen]
        correct_letter = view.correct_letter
        points = view.points
        q = view.q

        await view.disable_all(interaction)  # disables buttons immediately

        # Create difficulty color mapping
        difficulty_colors = {
            "easy": discord.Color.green(),
            "medium": discord.Color.orange(),
            "hard": discord.Color.red()
        }

        if chosen == correct_letter:
            add_score(interaction.user.id, points)
            total = scores.get(str(interaction.user.id), 0)
            result_embed = discord.Embed(
                title="✅ Correct!",
                description=f"**{chosen}) {chosen_answer}**\n\n+{points} point{'s' if points > 1 else ''}!\nTotal points: **{total}**",
                color=discord.Color.green()
            )
            result_embed.set_thumbnail(url=interaction.user.display_avatar.url)
        else:
            result_embed = discord.Embed(
                title="❌ Wrong Answer",
                description=f"You chose: **{chosen}) {chosen_answer}**\nCorrect answer: **{correct_letter}) {q['answer']}**",
                color=discord.Color.red()
            )
            result_embed.set_thumbnail(url=interaction.user.display_avatar.url)

        # Add question info to result
        result_embed.add_field(name="Question", value=q['question'], inline=False)
        result_embed.add_field(name="Difficulty", value=f"{view.difficulty.upper()}", inline=True)
        result_embed.add_field(name="Points Value", value=f"{points} point{'s' if points > 1 else ''}", inline=True)
        result_embed.set_footer(text=f"Trivia game for {view.ctx.author.name}")

        await interaction.response.edit_message(embed=result_embed, view=TriviaPlayAgainView(view.ctx))


class TriviaPlayAgainView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.add_item(TriviaPlayAgainButton(ctx))


class TriviaPlayAgainButton(discord.ui.Button):
    def __init__(self, ctx):
        self.ctx = ctx
        super().__init__(label="Play Again", style=discord.ButtonStyle.success, emoji="🔄")

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ This is not your trivia session.", ephemeral=True)
            return

        # Create new difficulty selection embed
        embed = discord.Embed(
            title="🎓 Space Trivia Challenge",
            description="**Welcome back to Space Trivia!**\n\nChoose your difficulty level:\n\n🟩 **Easy** - Basic space knowledge (1 point)\n🟨 **Medium** - Intermediate space facts (2 points)\n🟥 **Hard** - Advanced space science (3 points)",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=self.ctx.author.display_avatar.url)
        embed.add_field(name="🚀 Ready for another challenge?", value="Select your difficulty below!", inline=False)

        await interaction.response.edit_message(embed=embed, view=TriviaDifficultyView(self.ctx))


async def send_trivia_question(ctx, difficulty):
    q = random.choice(TRIVIA_QUESTIONS[difficulty])

    options = q["options"][:3]
    random.shuffle(options)
    letter_to_option = {LETTERS[i]: options[i] for i in range(len(options))}
    correct_letter = next((L for L, O in letter_to_option.items()
                           if O.lower() == q["answer"].lower()), None)
    points = 1 if difficulty == "easy" else 2 if difficulty == "medium" else 3

    # Create difficulty color mapping
    difficulty_colors = {
        "easy": discord.Color.green(),
        "medium": discord.Color.orange(),
        "hard": discord.Color.red()
    }

    question_text = f"**Difficulty: {difficulty.upper()} ({points} point{'s' if points > 1 else ''})**\n\n{q['question']}\n\n" + \
                    "\n".join([f"**{L})** {O}" for L, O in letter_to_option.items()])

    embed = discord.Embed(
        title="🎓 Space Trivia Question",
        description=question_text,
        color=difficulty_colors[difficulty]
    )

    embed.add_field(name="⏰ Time Limit", value="30 seconds", inline=True)
    embed.add_field(name="📊 Points", value=f"+{points} if correct", inline=True)
    embed.add_field(name="🎮 Player", value=ctx.author.mention, inline=True)

    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    embed.set_footer(text=f"Trivia for {ctx.author.name}")

    view = AnswerButtons(ctx, correct_letter, points, letter_to_option, q, difficulty)
    await ctx.send(embed=embed, view=view)


# === Main command ===
@bot.command(name="trivia")
async def trivia(ctx):
    """Launch the trivia UI."""
    embed = discord.Embed(
        title="🎓 Space Trivia Challenge",
        description="**Welcome to Space Trivia!**\n\nTest your knowledge of space, planets, and the universe!\n\n🟩 **Easy** - Basic space knowledge (1 point)\n🟨 **Medium** - Intermediate space facts (2 points)\n🟥 **Hard** - Advanced space science (3 points)",
        color=discord.Color.blurple()
    )

    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    embed.add_field(name="🚀 How to Play", value="Select difficulty → Answer the question → Earn points!", inline=False)
    embed.add_field(name="⏰ Time Limit", value="30 seconds per question", inline=True)
    embed.add_field(name="🎮 Your Game", value=f"Started by {ctx.author.mention}", inline=True)

    await ctx.send(embed=embed, view=TriviaDifficultyView(ctx))



# -----------------------------------
# 7️⃣ Math Quiz
# -----------------------------------
class MathQuizModal(discord.ui.Modal, title="🧮 Math Quiz Answer"):
    def __init__(self, ctx, answer):
        super().__init__()
        self.ctx = ctx
        self.answer = answer

        self.answer_input = discord.ui.TextInput(
            label="Your Answer:",
            style=discord.TextStyle.short,
            placeholder="Enter your answer here",
            required=True
        )
        self.add_item(self.answer_input)

    async def on_submit(self, interaction: discord.Interaction):
        # Validate answer input
        try:
            user_answer = int(self.answer_input.value.strip())
        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter a valid integer!", ephemeral=True
            )
            return

        if user_answer == self.answer:
            add_score(interaction.user.id, 1)
            total_points = scores.get(str(interaction.user.id), 0)
            embed = discord.Embed(
                title="✅ Correct!",
                description=f"You solved it! (+1 point)\nTotal points: **{total_points}**",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ Wrong",
                description=f"The correct answer was **{self.answer}**.",
                color=discord.Color.red()
            )

        await interaction.response.edit_message(embed=embed, view=None)


class MathQuizView(discord.ui.View):
    def __init__(self, ctx, answer):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.answer = answer

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "⚠️ This quiz isn’t for you.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Answer Question", style=discord.ButtonStyle.primary, emoji="✏️")
    async def answer_question(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MathQuizModal(self.ctx, self.answer)
        await interaction.response.send_modal(modal)


@bot.command(name="mathquiz")
async def mathquiz(ctx):
    """Ask a random math question with UI and modal input"""
    a = random.randint(-20, 20)
    b = random.randint(-20, 20)

    op = random.choice(["+", "-", "*", "//"])
    if op == "//":
        while b == 0:
            b = random.randint(-20, 20)

    question = f"{a} {op} {b}"
    answer = eval(question)

    op_name = {"//": "÷ (integer division)", "+": "+", "-": "-", "*": "×"}[op]

    embed = discord.Embed(
        title="🧮 Math Quiz",
        description=f"Solve: **{a} {op_name} {b}**\nClick below to answer!",
        color=discord.Color.gold()
    )

    view = MathQuizView(ctx, answer)
    await ctx.send(embed=embed, view=view)

# -----------------------------------
# 8️⃣ Word Unscramble
# -----------------------------------
UNSCRAMBLE_WORDS = {
    "easy": [
        # Basic / short
        "apple", "table", "house", "water", "train",
        "light", "music", "chair", "stone", "river",
        "green", "mouse", "bread", "heart", "dance",
        "sleep", "dream", "cloud", "plant", "happy",
        "book", "tree", "fish", "dog", "cat",
        "rain", "wind", "snow", "milk", "sand",
        "moon", "sun", "star", "ship", "car",
        "road", "lamp", "door", "pen", "map",
        "king", "queen", "town", "hill", "farm"
    ],
    "medium": [
        # Slightly longer / common
        "guitar", "rabbit", "coffee", "bridge", "engine",
        "flight", "anchor", "circle", "silver", "window",
        "school", "castle", "camera", "driver", "orange",
        "forest", "planet", "stream", "silent", "volcano",
        "desert", "rocket", "garden", "market", "purple",
        "pirate", "jungle", "island", "winter", "spring",
        "autumn", "summer", "mirror", "ladder", "artist",
        "doctor", "hunter", "wizard", "pencil", "dragon",
        "castle", "shield", "bridge", "farmer", "butter"
    ],
    "hard": [
        # Long / technical / space
        "astronaut", "satellite", "microphone", "laboratory", "imagination",
        "kaleidoscope", "transmission", "encyclopedia", "revolution", "phenomenon",
        "synchronous", "cryptography", "electricity", "mathematics", "biodiversity",
        "holographic", "spacesuit", "gravity", "telescope", "universe",
        "asterism", "supernova", "blackhole", "quasar", "pulsar",
        "constellation", "interstellar", "photosynthesis", "thermodynamics", "nanotechnology",
        "spectroscopy", "electromagnetic", "astrobiology", "cybersecurity", "hyperspace",
        "geosynchronous", "planetarium", "cosmology", "observatory", "radiotelescope",
        "neuroscience", "biotechnology", "computational", "relativity", "astrophysics"
    ]
}


def make_scrambled(word: str, max_attempts: int = 40) -> str | None:
    """Return a scrambled permutation of `word` that is not identical to `word`."""
    if not word or len(word) <= 1:
        return None
    if len(set(word.lower())) == 1:
        return None
    chars = list(word)
    for _ in range(max_attempts):
        random.shuffle(chars)
        scrambled = ''.join(chars)
        if scrambled.lower() != word.lower():
            return scrambled
    for _ in range(max_attempts):
        scrambled = ''.join(random.sample(word, len(word)))
        if scrambled.lower() != word.lower():
            return scrambled
    return None


class UnscrambleModal(discord.ui.Modal, title="Unscramble the Word"):
    def __init__(self, ctx, word: str, points: int):
        super().__init__()
        self.ctx = ctx
        self.word = word
        self.points = points

        self.answer_input = discord.ui.TextInput(
            label="Your answer",
            placeholder="Type the unscrambled word here",
            required=True,
            max_length=100
        )
        self.add_item(self.answer_input)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your game.", ephemeral=True)
            return

        guess = self.answer_input.value.strip().lower()
        if guess == self.word.lower():
            add_score(self.ctx.author.id, self.points)
            total = scores.get(str(self.ctx.author.id), 0)
            embed = discord.Embed(
                title="✅ Correct!",
                description=f"You unscrambled it! **{self.word.upper()}**\n\n+{self.points} point(s)\nTotal points: **{total}**",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=self.ctx.author.display_avatar.url)
        else:
            embed = discord.Embed(
                title="❌ Wrong",
                description=f"The correct word was **{self.word.upper()}**.\nBetter luck next time!",
                color=discord.Color.red()
            )
            embed.set_thumbnail(url=self.ctx.author.display_avatar.url)
        await interaction.response.edit_message(embed=embed, view=None)


class UnscrambleView(discord.ui.View):
    def __init__(self, ctx, word: str, points: int, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.word = word
        self.points = points
        self.message: discord.Message | None = None

    @discord.ui.button(label="Unscramble", style=discord.ButtonStyle.primary, emoji="🔤")
    async def unscramble_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your game.", ephemeral=True)
            return
        modal = UnscrambleModal(self.ctx, self.word, self.points)
        await interaction.response.send_modal(modal)

    async def on_timeout(self):
        try:
            if self.message:
                timeout_embed = discord.Embed(
                    title="⏳ Timeout",
                    description=f"You took too long to answer!\nThe correct word was **{self.word.upper()}**",
                    color=discord.Color.orange()
                )
                timeout_embed.set_thumbnail(url=self.ctx.author.display_avatar.url)
                await self.message.edit(embed=timeout_embed, view=None)
        except Exception:
            pass


class DifficultyDropdown(discord.ui.Select):
    def __init__(self, ctx):
        self.ctx = ctx
        options = [
            discord.SelectOption(label="Easy", description="Simple words (1 point)", emoji="🟩"),
            discord.SelectOption(label="Medium", description="Medium words (2 points)", emoji="🟨"),
            discord.SelectOption(label="Hard", description="Hard words (3 points)", emoji="🟥"),
        ]
        super().__init__(placeholder="Choose difficulty", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This dropdown isn't for you.", ephemeral=True)
            return

        difficulty = self.values[0].lower()
        points = 1 if difficulty == "easy" else 2 if difficulty == "medium" else 3

        # Pick a word
        word, scrambled = None, None
        attempts = 0
        while attempts < 60:
            candidate = random.choice(UNSCRAMBLE_WORDS[difficulty])
            s = make_scrambled(candidate)
            if s:
                word = candidate
                scrambled = s
                break
            attempts += 1

        if not scrambled:  # fallback
            word = random.choice(UNSCRAMBLE_WORDS[difficulty])
            scrambled = ''.join(random.sample(word, len(word)))

        # Create difficulty color mapping
        difficulty_colors = {
            "easy": discord.Color.green(),
            "medium": discord.Color.orange(),
            "hard": discord.Color.red()
        }

        embed = discord.Embed(
            title="🔤 Word Unscramble",
            description=f"**Difficulty: {difficulty.upper()} ({points} point{'s' if points > 1 else ''})**\n\nUnscramble this word:\n\n**`{scrambled.upper()}`**\n\n*Click the button below to submit your answer!*",
            color=difficulty_colors[difficulty]
        )

        embed.add_field(name="🎯 Word Length", value=f"{len(word)} letters", inline=True)
        embed.add_field(name="⏰ Time Limit", value="60 seconds", inline=True)
        embed.add_field(name="📊 Points", value=f"+{points} if correct", inline=True)

        embed.set_thumbnail(url=self.ctx.author.display_avatar.url)
        embed.set_footer(text=f"Game for {self.ctx.author.name}")

        # Create the view and edit the message
        view = UnscrambleView(self.ctx, word, points)
        await interaction.response.edit_message(embed=embed, view=view)

        # Get the message object after editing
        try:
            view.message = await interaction.original_response()
        except:
            # Fallback: try to get message from followup
            view.message = interaction.message


class DifficultyView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.add_item(DifficultyDropdown(ctx))

    async def on_timeout(self):
        try:
            timeout_embed = discord.Embed(
                title="⏳ Selection Timeout",
                description="You took too long to select a difficulty level.",
                color=discord.Color.orange()
            )
            # This will only work if we stored the message reference
            # We'll handle this in the command
        except Exception:
            pass


@bot.command(name="unscramble")
async def unscramble(ctx):
    """Start the unscramble game with a difficulty dropdown."""
    embed = discord.Embed(
        title="🔤 Word Unscramble Game",
        description="**Welcome to the Word Unscramble Challenge!**\n\nChoose your difficulty level below:\n\n🟩 **Easy** - Simple words (1 point)\n🟨 **Medium** - Moderate words (2 points)\n🟥 **Hard** - Difficult words (3 points)",
        color=discord.Color.blurple()
    )

    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    embed.add_field(name="📝 How to Play", value="Select difficulty → Unscramble the word → Earn points!", inline=False)
    embed.add_field(name="⏰ Time Limit", value="60 seconds per word", inline=True)
    embed.add_field(name="🎮 Your Game", value=f"Started by {ctx.author.mention}", inline=True)

    view = DifficultyView(ctx)
    message = await ctx.send(embed=embed, view=view)

    # Store message reference for timeout handling
    view.message = message

@bot.command(name="starship")
async def starship(ctx):
    """
    Interactive Starship success predictor with UI.
    """

    # --- Question Bank ---
    questions = [
        {
            "title": "Weather at launch",
            "options": [
                ("Excellent (clear, low wind)", "excellent", 0.20),
                ("Moderate (some wind/clouds)", "moderate", 0.0),
                ("Poor (high wind/storm)", "poor", -0.20),
            ]
        },
        {
            "title": "Vehicle condition",
            "options": [
                ("Freshly inspected & nominal", "fresh", 0.15),
                ("Refurb / marginal", "refurb", 0.0),
                ("Unknown / rushed", "unknown", -0.15),
            ]
        },
        {
            "title": "Payload mass",
            "options": [
                ("Light (< planned)", "light", 0.10),
                ("Nominal (as-planned)", "nominal", 0.0),
                ("Heavy (> planned)", "heavy", -0.10),
            ]
        },
        {
            "title": "Recent test experience",
            "options": [
                ("Many successful recent tests", "many", 0.15),
                ("Some tests, mixed results", "some", 0.0),
                ("Few/no tests recently", "few", -0.15),
            ]
        }
    ]

    # store answers
    answers = {}

    # --- UI View ---
    class StarshipView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)

            # dynamically create dropdowns for each question
            for q in questions:
                select = discord.ui.Select(
                    placeholder=q["title"],
                    min_values=1,
                    max_values=1,
                    options=[
                        discord.SelectOption(label=text, value=value)
                        for (text, value, weight) in q["options"]
                    ],
                    custom_id=q["title"]  # so we know which question
                )
                select.callback = self.make_callback(select, q)
                self.add_item(select)

            # Add submit button
            submit_button = discord.ui.Button(label="Submit Answers", style=discord.ButtonStyle.green)
            submit_button.callback = self.submit
            self.add_item(submit_button)

        def make_callback(self, select, q):
            async def callback(interaction: discord.Interaction):
                selected_value = select.values[0]
                answers[q["title"]] = selected_value
                await interaction.response.defer()  # just acknowledge silently
            return callback

        async def submit(self, interaction: discord.Interaction):
            # ensure all answered
            if len(answers) < len(questions):
                await interaction.response.send_message(
                    "⚠️ Please answer all questions before submitting.",
                    ephemeral=True
                )
                return

            # --- Compute result ---
            base = 0.55
            total_weight = 0.0
            explanation_lines = []

            for q in questions:
                user_value = answers.get(q["title"])
                for (text, val, weight) in q["options"]:
                    if val == user_value:
                        total_weight += weight
                        sign = "+" if weight > 0 else ""
                        explanation_lines.append(
                            f"**{q['title']}** — {val.capitalize()} ({sign}{weight:+.2f})"
                        )
                        break

            # apply randomness
            prob = base + total_weight + random.uniform(-0.08, 0.08)
            prob = max(0.01, min(0.99, prob))
            percent = int(round(prob * 100))

            embed = discord.Embed(
                title="🚀 Starship Success Predictor",
                description=f"Predicted chance of a successful flight: **{percent}%**",
                color=discord.Color.blue()
            )
            embed.add_field(name="Quick breakdown", value="\n".join(explanation_lines), inline=False)
            embed.set_footer(text=f"Baseline: {int(base*100)}% + factors + randomness")

            await interaction.response.edit_message(content=None, embed=embed, view=None)

            # Give a participation point if add_score exists
            try:
                if 'add_score' in globals():
                    add_score(ctx.author.id, 1)
            except Exception:
                pass

    view = StarshipView()

    await ctx.send(
        embed=discord.Embed(
            title="🚀 Starship Launch Predictor",
            description="Answer the dropdowns below then click **Submit Answers**.",
            color=discord.Color.dark_teal()
        ),
        view=view
    )



TESTS = [
    {"name": "Heat Shield Tile Test", "desc": "Tests thermal protection system integrity", "emoji": "🛡️"},
    {"name": "Propellant Tank Pressure Test", "desc": "Validates fuel system pressure handling", "emoji": "⛽"},
    {"name": "RCS Thruster Test", "desc": "Checks reaction control system functionality", "emoji": "🚀"},
    {"name": "Vacuum Engine Static Fire", "desc": "Tests main engine performance in vacuum", "emoji": "🔥"},
    {"name": "Flight Control Surfaces Test", "desc": "Validates aerodynamic control systems", "emoji": "✈️"}
]


@bot.command(name="predict")
async def predict(ctx, *, ship_name: str = None):
    """
    Chat-only Starship mission simulation.
    Use !predict S38 or !predict <shipname>
    """
    if not ship_name:
        await ctx.send("❌ Please provide a ship name. Example: `!predict S38`")
        return

    await ctx.send(embed=discord.Embed(
        title=f"🚀 Starship Mission Simulation",
        description=f"Commander {ctx.author.mention}, starting simulation for **{ship_name}**.\n\n"
                    f"You will be asked **{len(TESTS)} test results**. Reply with:\n"
                    "`success`, `partial`, or `failure`.\nYou have 20 seconds per test.",
        color=discord.Color.blue()
    ))

    user_answers = {}

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    # ask each test
    for test in TESTS:
        embed = discord.Embed(
            title=f"{test['emoji']} {test['name']}",
            description=f"{test['desc']}\n\nReply with: `success` / `partial` / `failure`",
            color=discord.Color.dark_blue()
        )
        await ctx.send(embed=embed)

        try:
            msg = await bot.wait_for('message', timeout=20.0, check=check)
            answer = msg.content.lower()
            if answer not in ["success", "partial", "failure"]:
                answer = "failure"
        except asyncio.TimeoutError:
            await ctx.send(f"⏰ Timeout for **{test['name']}** — counting as failure.")
            answer = "failure"

        user_answers[test['name']] = answer

    # scoring
    base_scores = {"success": 3, "partial": 1, "failure": 0}
    score = sum(base_scores[val] for val in user_answers.values())
    max_score = len(TESTS) * 3
    base_chance = int((score / max_score) * 100)
    final_chance = max(5, min(95, base_chance + random.randint(-8, 12)))

    # summary counts
    success_count = list(user_answers.values()).count('success')
    partial_count = list(user_answers.values()).count('partial')
    failure_count = list(user_answers.values()).count('failure')

    # outcome classification
    if final_chance >= 80:
        outcome = "🟢 HIGH CONFIDENCE"
        color = discord.Color.green()
        outcome_msg = "Excellent test results indicate high mission success probability!"
    elif final_chance >= 60:
        outcome = "🟡 MODERATE CONFIDENCE"
        color = discord.Color.gold()
        outcome_msg = "Good test results with some areas for improvement."
    elif final_chance >= 40:
        outcome = "🟠 LOW CONFIDENCE"
        color = discord.Color.orange()
        outcome_msg = "Mixed results suggest elevated mission risk."
    else:
        outcome = "🔴 CRITICAL CONCERNS"
        color = discord.Color.red()
        outcome_msg = "Poor test results indicate significant mission risk."

    # build result embed
    result_embed = discord.Embed(
        title=f"🚀 Mission Analysis: {ship_name}",
        description=(f"🟢 Successes: **{success_count}**\n"
                     f"⚠️ Partials: **{partial_count}**\n"
                     f"❌ Failures: **{failure_count}**\n\n"
                     f"**Mission Confidence:** {outcome}\n"
                     f"**Predicted Success Probability:** `{final_chance}%`\n\n"
                     f"*{outcome_msg}*"),
        color=color
    )

    # detailed breakdown
    breakdown = ""
    emojis = {"success": "✅", "partial": "⚠️", "failure": "❌"}
    for test in TESTS:
        res = user_answers[test['name']]
        breakdown += f"{emojis[res]} {test['name']}\n"
    result_embed.add_field(name="📋 Test Results", value=breakdown, inline=False)

    await ctx.send(embed=result_embed)



player_states = {}  # user_id -> {fuel, food, research, turns, active}


# ======= Mission UI View =======
class MissionView(discord.ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=None)
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Restrict button presses to mission owner."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "⚠️ These buttons belong to someone else. Start your own with `!mission`.",
                ephemeral=True
            )
            return False
        return True

    def disable_all(self):
        """Disable all buttons after mission ends."""
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

    @discord.ui.button(label="🚀 Launch", style=discord.ButtonStyle.primary)
    async def launch(self, interaction: discord.Interaction, button: discord.ui.Button):
        await mission_launch(interaction, self)

    @discord.ui.button(label="⛽ Refuel", style=discord.ButtonStyle.success)
    async def refuel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await mission_refuel(interaction, self)

    @discord.ui.button(label="🔬 Research", style=discord.ButtonStyle.secondary)
    async def research(self, interaction: discord.Interaction, button: discord.ui.Button):
        await mission_research(interaction, self)

    @discord.ui.button(label="📊 Status", style=discord.ButtonStyle.gray)
    async def status(self, interaction: discord.Interaction, button: discord.ui.Button):
        await mission_status(interaction)


# ======= Command to start a mission =======
@bot.command()
async def mission(ctx):
    """Start or view your Starship mission with UI buttons."""
    if ctx.author.id not in player_states or not player_states[ctx.author.id]["active"]:
        # Create new state
        player_states[ctx.author.id] = {
            "fuel": 50,
            "food": 50,
            "research": 0,
            "turns": 0,
            "active": True
        }
        embed = discord.Embed(
            title=f"🚀 Starship Mission Started for {ctx.author.display_name}",
            description="Manage your resources wisely using the buttons below.",
            color=discord.Color.blurple()
        )
    else:
        embed = discord.Embed(
            title=f"🚀 Starship Mission ({ctx.author.display_name})",
            description="Mission already active! Use the buttons below to continue.",
            color=discord.Color.blurple()
        )

    view = MissionView(ctx.author.id)
    await ctx.send(embed=embed, view=view)


# ======= Mission Action Handlers =======
async def mission_status(interaction):
    """Public status embed."""
    state = player_states.get(interaction.user.id)
    if not state:
        await interaction.response.send_message("⚠️ No active mission.", ephemeral=True)
        return

    # Simple bars
    def bar(value, max_val=100):
        filled = int(value / max_val * 10)
        return "█" * filled + "░" * (10 - filled)

    embed = discord.Embed(
        title=f"📊 Starship Status — {interaction.user.display_name}",
        description=(f"**Fuel:** {state['fuel']} {bar(state['fuel'])}\n"
                     f"**Food:** {state['food']} {bar(state['food'])}\n"
                     f"**Research:** {state['research']}\n"
                     f"**Turns:** {state['turns']}"),
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, ephemeral=False)


async def mission_launch(interaction, view: MissionView):
    state = player_states.get(interaction.user.id)
    if not state or not state["active"]:
        await interaction.response.send_message("💥 Mission already ended.", ephemeral=True)
        return

    fuel_cost = random.randint(5, 10)
    food_cost = random.randint(3, 8)
    state["fuel"] -= fuel_cost
    state["food"] -= food_cost
    state["turns"] += 1

    event_text = f"You launched forward, using **{fuel_cost} fuel** and **{food_cost} food**."
    if random.random() < 0.3:
        bonus = random.randint(5, 15)
        state["research"] += bonus
        event_text += f"\nDiscovered alien tech! **+{bonus} research points**."

    if state["fuel"] <= 0 or state["food"] <= 0:
        points = state["turns"] // 2
        total = add_score(interaction.user.id, points)  # ✅ integrated here
        state["active"] = False
        view.disable_all()
        await interaction.message.edit(view=view)

        embed = discord.Embed(
            title="💥 Mission Failed",
            description=f"You ran out of resources after {state['turns']} turns.\n"
                        f"You earned **{points} points**.\nTotal points: **{total}**",
            color=discord.Color.red()
        )
    else:
        embed = discord.Embed(title="🚀 Launch", description=event_text, color=discord.Color.blue())

    await interaction.response.send_message(embed=embed, ephemeral=True)


async def mission_refuel(interaction, view: MissionView):
    state = player_states.get(interaction.user.id)
    if not state or not state["active"]:
        await interaction.response.send_message("💥 Mission already ended.", ephemeral=True)
        return

    fuel_gain = random.randint(5, 15)
    food_gain = random.randint(5, 15)
    state["fuel"] += fuel_gain
    state["food"] += food_gain
    state["turns"] += 1

    embed = discord.Embed(
        title="⛽ Refuel Complete",
        description=f"+{fuel_gain} Fuel and +{food_gain} Food gained!",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def mission_research(interaction, view: MissionView):
    state = player_states.get(interaction.user.id)
    if not state or not state["active"]:
        await interaction.response.send_message("💥 Mission already ended.", ephemeral=True)
        return

    food_cost = random.randint(3, 8)
    state["food"] -= food_cost
    state["turns"] += 1
    gain = random.randint(5, 20)
    state["research"] += gain

    if state["fuel"] <= 0 or state["food"] <= 0:
        points = state["turns"] // 2
        total = add_score(interaction.user.id, points)  # ✅ integrated here
        state["active"] = False
        view.disable_all()
        await interaction.message.edit(view=view)

        embed = discord.Embed(
            title="💥 Mission Failed",
            description=f"You ran out of resources after {state['turns']} turns.\n"
                        f"You earned **{points} points**.\nTotal points: **{total}**",
            color=discord.Color.red()
        )
    else:
        embed = discord.Embed(
            title="🔬 Research Complete",
            description=f"Used **{food_cost} food** → gained **{gain} research points**",
            color=discord.Color.teal()
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)

rocket_design_states = {}

@bot.command(name="rocketdesign")
async def rocketdesign(ctx):
    """
    Chat-based Rocket Design Quiz (no UI).
    """
    await ctx.send(embed=discord.Embed(
        title="🚀 Rocket Design Quiz",
        description=("Welcome Commander!\n"
                     "We'll design your rocket step by step.\n"
                     "Reply to each question within 20 seconds."),
        color=discord.Color.orange()
    ))

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    # 1️⃣ Engine
    await ctx.send(embed=discord.Embed(
        title="Step 1: Choose Engine",
        description=("Options:\n"
                     "- `Raptor` (high thrust)\n"
                     "- `Merlin` (balanced)\n"
                     "- `Ion Drive` (efficient, low thrust)\n\n"
                     "Type your choice exactly."),
        color=discord.Color.blue()
    ))
    try:
        msg = await bot.wait_for('message', timeout=20.0, check=check)
        engine = msg.content.strip().title()
    except asyncio.TimeoutError:
        await ctx.send("⏰ Timeout. Rocket design cancelled.")
        return

    # 2️⃣ Tank
    await ctx.send(embed=discord.Embed(
        title="Step 2: Choose Tank Size",
        description=("Options:\n"
                     "- `Large` (more fuel)\n"
                     "- `Medium`\n"
                     "- `Small` (lighter)\n\n"
                     "Type your choice exactly."),
        color=discord.Color.blue()
    ))
    try:
        msg = await bot.wait_for('message', timeout=20.0, check=check)
        tank = msg.content.strip().title()
    except asyncio.TimeoutError:
        await ctx.send("⏰ Timeout. Rocket design cancelled.")
        return

    # 3️⃣ Payload
    await ctx.send(embed=discord.Embed(
        title="Step 3: Choose Payload",
        description=("Options:\n"
                     "- `Satellite`\n"
                     "- `Crew Capsule`\n"
                     "- `Heavy Cargo`\n\n"
                     "Type your choice exactly."),
        color=discord.Color.blue()
    ))
    try:
        msg = await bot.wait_for('message', timeout=20.0, check=check)
        payload = msg.content.strip().title()
    except asyncio.TimeoutError:
        await ctx.send("⏰ Timeout. Rocket design cancelled.")
        return

    # Compute success chance
    success_chance = 50

    # Engine effect
    if engine == "Raptor":
        success_chance += 15
    elif engine == "Ion Drive":
        success_chance -= 10

    # Tank effect
    if tank == "Large":
        success_chance += 10
    elif tank == "Small":
        success_chance -= 5

    # Payload effect
    if payload == "Heavy Cargo":
        success_chance -= 15
    elif payload == "Satellite":
        success_chance += 5

    # Launch result
    result = random.randint(1, 100)
    if result <= success_chance:
        points = 2
        add_score(ctx.author.id, points)
        total = scores.get(ctx.author.id, 0)
        embed = discord.Embed(
            title="✅ Launch Successful!",
            description=(f"Your rocket launched successfully!\n\n"
                         f"**Engine:** {engine}\n"
                         f"**Tank:** {tank}\n"
                         f"**Payload:** {payload}\n\n"
                         f"You earned **{points} points**.\nTotal points: **{total}**"),
            color=discord.Color.green()
        )
    else:
        embed = discord.Embed(
            title="💥 Launch Failed",
            description=(f"Your rocket failed to launch.\n\n"
                         f"**Engine:** {engine}\n"
                         f"**Tank:** {tank}\n"
                         f"**Payload:** {payload}\n\n"
                         f"Better luck next time!"),
            color=discord.Color.red()
        )

    await ctx.send(embed=embed)


# Booster Catch Game
class CatchGameView(discord.ui.View):
    def __init__(self, game_instance):
        super().__init__(timeout=120)  # 2 minute timeout
        self.game = game_instance
        self.update_button_states()

    def update_button_states(self):
        """Update button availability based on game state"""
        # Disable thrust if no fuel
        self.thrust_button.disabled = self.game.game_state['fuel'] <= 0

        # Disable catch if not ready
        self.catch_button.disabled = not self.game.game_state['catch_ready']

        # Disable arms if at boundaries
        self.left_button.disabled = self.game.game_state['arm_left'] <= 2
        self.right_button.disabled = self.game.game_state['arm_right'] >= 22

        # Disable all if game over
        if self.game.game_state['game_over']:
            for item in self.children:
                item.disabled = True

    @discord.ui.button(label='← Arms Left', style=discord.ButtonStyle.secondary, emoji='⬅️')
    async def left_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user == self.game.ctx.author:
            self.game.handle_action('left')
            self.update_button_states()
            await interaction.response.defer()

    @discord.ui.button(label='Arms Right →', style=discord.ButtonStyle.secondary, emoji='➡️')
    async def right_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user == self.game.ctx.author:
            self.game.handle_action('right')
            self.update_button_states()
            await interaction.response.defer()

    @discord.ui.button(label='🔥 THRUST', style=discord.ButtonStyle.danger, emoji='⬆️')
    async def thrust_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user == self.game.ctx.author:
            self.game.handle_action('thrust')
            self.update_button_states()
            await interaction.response.defer()

    @discord.ui.button(label='CATCH!', style=discord.ButtonStyle.success, emoji='🥢')
    async def catch_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user == self.game.ctx.author:
            self.game.handle_action('catch')
            self.update_button_states()
            await interaction.response.defer()


class EnhancedCatchGame:
    def __init__(self, ctx):
        self.ctx = ctx
        self.game_state = {
            'booster_x': 6,  # Center position (0-24 range)
            'booster_y': 0,  # Top of screen
            'booster_vel_x': random.uniform(-0.5, 0.5),
            'booster_vel_y': 0.05,
            'arm_left': 8,
            'arm_right': 16,
            'fuel': 100,
            'wind': random.uniform(-0.2, 0.2),
            'phase': 'falling',
            'catch_ready': False,
            'game_over': False,
            'success': False,
            'score': 0,
            'engine_light': False,
            'auto_engine_active': False,
            'landing_burn_active': False,
            'landing_burn_initiated': False,
            'optimal_burn_altitude': None,
            'thrust_particles': [],
            'animation_frame': 0,
            'altitude_warnings': 0,
            'atmospheric_effects': [],
            'debris_particles': [],
            'tower_lights': 0,
            'sonic_boom_frame': -1
        }

        self.timeline = ["🚀 **Mechzilla Mission Initiated**"]
        self.view = None

    def get_atmospheric_effects(self):
        """Generate atmospheric effects based on altitude and speed"""
        effects = []
        bx = int(self.game_state['booster_x'])
        by = int(self.game_state['booster_y'])

        # Sonic boom effect when falling fast
        if self.game_state['booster_vel_y'] > 0.8 and by < 8:
            self.game_state['sonic_boom_frame'] = self.game_state['animation_frame']

        # Add sonic boom visual
        if (self.game_state['animation_frame'] - self.game_state['sonic_boom_frame']) < 3:
            boom_radius = self.game_state['animation_frame'] - self.game_state['sonic_boom_frame'] + 1
            for offset in range(-boom_radius, boom_radius + 1):
                if 0 <= bx + offset < 25 and by - 1 >= 0:
                    effects.append((by - 1, bx + offset, '○'))

        # Entry plasma effects at high altitude
        if by < 4 and self.game_state['booster_vel_y'] > 0.5:
            if random.random() < 0.6:
                for i in range(-2, 3):
                    if 0 <= bx + i < 25 and by + 1 < 12:
                        effects.append((by + 1, bx + i, random.choice(['·', '°', '∘'])))

        # Atmospheric heating trail
        if by < 6 and self.game_state['booster_vel_y'] > 0.6:
            trail_length = min(4, int(self.game_state['booster_vel_y'] * 3))
            for i in range(1, trail_length):
                if by - i >= 0 and 0 <= bx < 25:
                    intensity = trail_length - i
                    if intensity == 3:
                        effects.append((by - i, bx, '▪'))
                    elif intensity == 2:
                        effects.append((by - i, bx, '·'))
                    else:
                        effects.append((by - i, bx, '˙'))

        return effects

    def get_booster_sprite(self):
        """Get enhanced animated booster sprite based on state"""
        frame = self.game_state['animation_frame'] % 8
        velocity = self.game_state['booster_vel_y']

        if self.game_state['landing_burn_active']:
            # More dramatic landing burn sprites with alternating intensity
            if frame < 2:
                return '🔥'
            elif frame < 4:
                return '💥'
            elif frame < 6:
                return '⚡'
            else:
                return '🌟'
        elif self.game_state['engine_light'] or self.game_state['auto_engine_active']:
            # Enhanced thrust sprites
            thrust_sprites = ['🚀', '🔥', '💨', '⚡', '🛸', '💥', '🌟', '✨']
            return thrust_sprites[frame]
        elif self.game_state['phase'] == 'catch_zone':
            # Rapid blinking in catch zone
            return '🚀' if frame < 4 else '📍'
        elif velocity > 0.8:  # High speed effects
            # Fast rotation sprites for high velocity
            speed_sprites = ['🚀', '🛸', '🌟', '💫', '🔥', '⚡', '✨', '💥']
            return speed_sprites[frame]
        else:
            # Normal falling with smoother rotation
            rotation_sprites = ['🚀', '🛸', '🚁', '🛰️', '🚀', '🛸', '🚁', '🛰️']
            return rotation_sprites[frame]

    def get_enhanced_particles(self):
        """Generate enhanced particle effects with more variety"""
        if not (self.game_state['engine_light'] or self.game_state['auto_engine_active'] or
                self.game_state['landing_burn_active']):
            return []

        particles = []
        bx = int(self.game_state['booster_x'])
        by = int(self.game_state['booster_y'])
        frame = self.game_state['animation_frame'] % 8

        if self.game_state['landing_burn_active']:
            # Multi-layer landing burn with pulsing effect
            intensity_multiplier = 1.5 if frame < 4 else 1.0

            # Main exhaust plume
            for i in range(1, int(6 * intensity_multiplier)):
                if by + i < 12 and 0 <= bx < 25:
                    distance = i / (6 * intensity_multiplier)
                    if distance < 0.3:
                        particles.append((by + i, bx, '🔥'))
                    elif distance < 0.5:
                        particles.append((by + i, bx, '💥'))
                    elif distance < 0.7:
                        particles.append((by + i, bx, '💨'))
                    else:
                        particles.append((by + i, bx, '·'))

            # Side exhaust plumes
            for side_offset in [-1, 1]:
                if 0 <= bx + side_offset < 25:
                    for i in range(1, 4):
                        if by + i < 12:
                            if i == 1:
                                particles.append((by + i, bx + side_offset, '💨'))
                            else:
                                particles.append((by + i, bx + side_offset, '·'))

            # Shock diamonds effect
            if frame < 3:
                for i in range(2, 6, 2):
                    if by + i < 12 and 0 <= bx < 25:
                        particles.append((by + i, bx, '◊'))

        else:
            # Enhanced normal thrust
            thrust_length = 4 if self.game_state['engine_light'] else 3

            for i in range(1, thrust_length + 1):
                if by + i < 12 and 0 <= bx < 25:
                    if i == 1:
                        particles.append((by + i, bx, '🔥'))
                    elif i == 2:
                        particles.append((by + i, bx, '💨'))
                    elif i == 3:
                        particles.append((by + i, bx, '·'))
                    else:
                        particles.append((by + i, bx, '˙'))

            # Alternating side vents
            if frame % 2 == 0:
                for side in [-1, 1]:
                    if 0 <= bx + side < 25 and by + 1 < 12:
                        particles.append((by + 1, bx + side, '°'))

        return particles

    def get_tower_animation(self):
        """Generate animated tower effects"""
        frame = self.game_state['animation_frame'] % 16

        # Tower status lights
        if self.game_state['catch_ready']:
            # Rapid blinking when catch zone is active
            light_state = '●' if frame < 8 else '○'
        elif self.game_state['booster_y'] > 6:
            # Slow pulsing when booster is approaching
            light_state = '●' if frame < 12 else '○'
        else:
            # Steady light during normal operation
            light_state = '●'

        return light_state

    def calculate_landing_burn(self):
        """Calculate optimal landing burn parameters"""
        current_altitude = 12 - self.game_state['booster_y']
        current_velocity = self.game_state['booster_vel_y']
        target_velocity = 0.4

        gravity = 0.025
        thrust_power = 0.25

        if current_velocity <= 0:
            return None

        velocity_reduction_needed = current_velocity - target_velocity
        burn_time_needed = velocity_reduction_needed / thrust_power

        distance_during_burn = (current_velocity * burn_time_needed +
                                0.5 * (gravity - thrust_power) * burn_time_needed ** 2)

        optimal_burn_altitude = current_altitude - distance_during_burn
        return max(1.5, optimal_burn_altitude)

    def landing_burn_system(self):
        """Automated landing burn system"""
        current_altitude = 12 - self.game_state['booster_y']

        if self.game_state['optimal_burn_altitude'] is None:
            self.game_state['optimal_burn_altitude'] = self.calculate_landing_burn()

        if (not self.game_state['landing_burn_initiated'] and
                self.game_state['optimal_burn_altitude'] and
                current_altitude <= self.game_state['optimal_burn_altitude'] and
                self.game_state['fuel'] > 10):
            self.game_state['landing_burn_initiated'] = True
            self.timeline.append("🔥 **LANDING BURN SEQUENCE INITIATED**")

        if (self.game_state['landing_burn_initiated'] and
                not self.game_state['landing_burn_active'] and
                self.game_state['fuel'] > 5 and
                self.game_state['booster_vel_y'] > 0.4):

            self.game_state['landing_burn_active'] = True
            self.game_state['booster_vel_y'] -= 0.3
            self.game_state['fuel'] -= 12

            if current_altitude <= 2.0:
                self.timeline.append("🌟 **FINAL LANDING BURN - MAXIMUM THRUST**")
            elif current_altitude <= 3.5:
                self.timeline.append("⚡ **LANDING BURN - TRAJECTORY CORRECTION**")

        elif (self.game_state['landing_burn_active'] and
              self.game_state['fuel'] > 0 and
              self.game_state['booster_vel_y'] > 0.35):

            velocity_error = self.game_state['booster_vel_y'] - 0.4
            if velocity_error > 0.1:
                thrust_adjustment = min(0.2, velocity_error * 0.8)
                self.game_state['booster_vel_y'] -= thrust_adjustment
                fuel_consumption = int(thrust_adjustment * 40)
                self.game_state['fuel'] -= fuel_consumption

        elif (self.game_state['landing_burn_active'] and
              (self.game_state['booster_vel_y'] <= 0.35 or self.game_state['fuel'] <= 5)):

            self.game_state['landing_burn_active'] = False
            if self.game_state['booster_vel_y'] <= 0.35:
                self.timeline.append("✅ **Landing burn complete - Optimal velocity achieved**")
            else:
                self.timeline.append("⚠️ **Landing burn terminated - Low fuel**")

    def auto_engine_logic(self):
        """Auto-engine stabilization system"""
        # Simple auto-stabilizer when not in landing burn
        if (self.game_state['booster_vel_y'] > 1.2 and
                self.game_state['fuel'] > 15 and
                not self.game_state['landing_burn_initiated']):

            self.game_state['auto_engine_active'] = True
            self.game_state['booster_vel_y'] -= 0.15
            self.game_state['fuel'] -= 8
        else:
            self.game_state['auto_engine_active'] = False

    def make_field(self):
        """Create enhanced ASCII game field with superior animations"""
        lines = []
        particles = self.get_enhanced_particles()
        atmospheric = self.get_atmospheric_effects()
        tower_light = self.get_tower_animation()

        # Enhanced sky with dynamic background
        for row in range(12):
            line = [' '] * 25

            # Dynamic star field that twinkles
            if row < 4 and random.random() < 0.03:
                pos = random.randint(0, 24)
                stars = ['·', '✦', '○', '◦', '∘', '°', '˙']
                line[pos] = random.choice(stars)

            # Enhanced wind visualization
            if row == 1:
                wind_strength = abs(self.game_state['wind'])
                if wind_strength > 0.15:
                    wind_char = '🌪️' if self.game_state['wind'] > 0 else '💨'
                    line[23] = wind_char
                elif wind_strength > 0.05:
                    wind_char = '~' if self.game_state['wind'] > 0 else '≈'
                    line[23] = wind_char

            # Atmospheric entry heating effects
            if row < 6:
                heat_intensity = (6 - row) * 0.1
                if random.random() < heat_intensity * 0.05:
                    pos = random.randint(5, 19)
                    line[pos] = random.choice(['°', '·', '˙'])

            # Draw booster with enhanced positioning
            booster_row = int(self.game_state['booster_y'])
            booster_col = max(0, min(24, int(self.game_state['booster_x'])))

            if row == booster_row:
                line[booster_col] = self.get_booster_sprite()

            # Enhanced particle system
            for p_row, p_col, p_char in particles + atmospheric:
                if p_row == row and 0 <= p_col < 25 and line[p_col] == ' ':
                    line[p_col] = p_char

            # Enhanced altitude markers with status
            if row in [2, 5, 8]:
                marker_char = '┤' if row == 2 else '├' if row == 8 else '│'
                line[0] = marker_char
                line[24] = marker_char

            # Add trajectory prediction line when catch zone is active
            if self.game_state['catch_ready'] and row == booster_row + 1:
                predicted_x = int(self.game_state['booster_x'] + self.game_state['booster_vel_x'] * 2)
                if 0 <= predicted_x < 25 and line[predicted_x] == ' ':
                    line[predicted_x] = '↓'

            lines.append(''.join(line))

        # Super enhanced tower with dynamic lighting
        tower = ['═'] * 25
        frame = self.game_state['animation_frame'] % 8

        # Animated tower base with energy field
        base_chars = ['█', '▓', '▒', '░', '▒', '▓']
        base_char = base_chars[frame % len(base_chars)]

        # Enhanced left arm with grip visualization
        left_pos = max(0, int(self.game_state['arm_left']))
        for i in range(left_pos, min(left_pos + 3, 25)):
            if i == left_pos:
                tower[i] = '╫' if self.game_state['catch_ready'] else '╪'
            elif i == left_pos + 1:
                tower[i] = '═'
            else:
                tower[i] = '─'

        # Enhanced right arm with grip visualization
        right_pos = min(24, int(self.game_state['arm_right']))
        for i in range(max(0, right_pos - 2), right_pos + 1):
            if i == right_pos:
                tower[i] = '╫' if self.game_state['catch_ready'] else '╪'
            elif i == right_pos - 1:
                tower[i] = '═'
            else:
                tower[i] = '─'

        # Enhanced tower supports with status lights
        tower[0] = '║'
        tower[1] = tower_light
        tower[24] = '║'
        tower[23] = tower_light

        # Dynamic catch zone indicator
        if self.game_state['catch_ready']:
            center = (self.game_state['arm_left'] + self.game_state['arm_right']) // 2
            if 3 <= center <= 21:
                if frame < 4:
                    tower[center] = '🎯'
                else:
                    tower[center] = '⭕'

        # Energy field effect when arms are moving
        if hasattr(self, '_last_arm_pos'):
            if (self._last_arm_pos != (self.game_state['arm_left'], self.game_state['arm_right'])):
                # Add energy effects
                for i in range(max(0, left_pos - 1), min(25, right_pos + 2)):
                    if tower[i] == '═' and random.random() < 0.3:
                        tower[i] = '⚡' if frame < 2 else '═'

        self._last_arm_pos = (self.game_state['arm_left'], self.game_state['arm_right'])

        lines.append(''.join(tower))

        # Enhanced ground with impact effects
        ground_line = ['█'] * 25
        if self.game_state['game_over'] and not self.game_state['success']:
            # Add impact crater effect
            impact_x = int(self.game_state['booster_x'])
            for i in range(max(0, impact_x - 2), min(25, impact_x + 3)):
                distance = abs(i - impact_x)
                if distance == 0:
                    ground_line[i] = '💥'
                elif distance == 1:
                    ground_line[i] = '▓'
                else:
                    ground_line[i] = '▒'

        lines.append(''.join(ground_line))
        return '\n'.join(lines)

    def update_game(self):
        """Enhanced physics and game logic"""
        self.game_state['animation_frame'] += 1

        # Enhanced wind with realistic gusts
        if random.random() < 0.15:
            gust_strength = random.uniform(-0.03, 0.03)
            self.game_state['wind'] += gust_strength
            self.game_state['wind'] = max(-0.25, min(0.25, self.game_state['wind']))

            # Wind decay
            self.game_state['wind'] *= 0.98

        # Apply wind with altitude effects (stronger at higher altitudes)
        altitude_factor = max(0.5, (12 - self.game_state['booster_y']) / 12)
        wind_effect = self.game_state['wind'] * altitude_factor
        self.game_state['booster_vel_x'] += wind_effect * 0.06

        # Enhanced gravity with atmospheric drag
        base_gravity = 0.025
        drag_factor = 1.0 - (self.game_state['booster_vel_y'] * 0.01)  # Atmospheric drag
        effective_gravity = base_gravity * drag_factor
        self.game_state['booster_vel_y'] += effective_gravity

        # Landing burn system
        self.landing_burn_system()

        # Auto-engine system
        if not self.game_state['landing_burn_active'] and not self.game_state['landing_burn_initiated']:
            self.auto_engine_logic()

        # Reset engine light
        if self.game_state['engine_light']:
            self.game_state['engine_light'] = False

        # Enhanced movement with realistic physics
        self.game_state['booster_x'] += self.game_state['booster_vel_x']
        self.game_state['booster_y'] += self.game_state['booster_vel_y']

        # Enhanced boundary collisions with realistic bounce
        if self.game_state['booster_x'] <= 0:
            self.game_state['booster_x'] = 0
            self.game_state['booster_vel_x'] = abs(self.game_state['booster_vel_x']) * 0.3
            self.timeline.append("💥 **Left wall collision - Trajectory altered!**")
        elif self.game_state['booster_x'] >= 24:
            self.game_state['booster_x'] = 24
            self.game_state['booster_vel_x'] = -abs(self.game_state['booster_vel_x']) * 0.3
            self.timeline.append("💥 **Right wall collision - Trajectory altered!**")

        # Progressive altitude warnings
        current_altitude = 12 - self.game_state['booster_y']
        if current_altitude <= 5 and self.game_state['altitude_warnings'] == 0:
            self.timeline.append("⚠️ **ALTITUDE WARNING - 5km remaining**")
            self.game_state['altitude_warnings'] = 1
        elif current_altitude <= 3 and self.game_state['altitude_warnings'] == 1:
            self.timeline.append("🚨 **CRITICAL ALTITUDE - 3km remaining**")
            self.game_state['altitude_warnings'] = 2
        elif current_altitude <= 1.5 and self.game_state['altitude_warnings'] == 2:
            self.timeline.append("🔴 **FINAL APPROACH - CATCH IMMEDIATELY!**")
            self.game_state['altitude_warnings'] = 3

        # Enhanced catch zone activation
        if self.game_state['booster_y'] >= 9.5 and not self.game_state['catch_ready']:
            self.game_state['catch_ready'] = True
            self.game_state['phase'] = 'catch_zone'
            self.timeline.append("🎯 **CATCH ZONE ACTIVE - WINDOW OPEN!**")

        # Enhanced crash detection with different outcomes
        if self.game_state['booster_y'] >= 11.5:
            self.game_state['game_over'] = True
            crash_speed = self.game_state['booster_vel_y']
            if crash_speed > 1.5:
                self.timeline.append("💥 **CATASTROPHIC IMPACT - Total loss!**")
            elif crash_speed > 1.0:
                self.timeline.append("💥 **Hard impact - Major damage sustained**")
            else:
                self.timeline.append("💥 **Rough landing - Minor damage reported**")

    def check_catch(self):
        """Enhanced catch detection with more nuanced results"""
        bx = self.game_state['booster_x']
        by = self.game_state['booster_y']
        left = self.game_state['arm_left'] + 1
        right = self.game_state['arm_right'] - 1

        # Enhanced catch conditions
        position_good = left <= bx <= right
        altitude_good = 10.5 <= by <= 11.2
        velocity_good = abs(self.game_state['booster_vel_y']) < 0.7
        lateral_good = abs(self.game_state['booster_vel_x']) < 0.5

        # Perfect catch - all conditions optimal
        if (position_good and altitude_good and
                abs(self.game_state['booster_vel_y']) < 0.5 and
                abs(self.game_state['booster_vel_x']) < 0.3):
            return 'perfect'
        # Good catch - most conditions met
        elif position_good and altitude_good and velocity_good:
            return 'good'
        # Rough catch - position good but challenging conditions
        elif position_good and altitude_good:
            return 'rough'
        # Near miss - close but not quite
        elif abs(bx - (left + right) / 2) < 3 and altitude_good:
            return 'near_miss'
        else:
            return 'miss'

    def handle_action(self, action):
        """Enhanced action handling"""
        if self.game_state['game_over']:
            return False

        if action == 'left' and self.game_state['arm_left'] > 2:
            self.game_state['arm_left'] -= 2
            self.game_state['arm_right'] -= 2
            self.timeline.append("⬅️ **Arms repositioned LEFT**")
            return True

        elif action == 'right' and self.game_state['arm_right'] < 22:
            self.game_state['arm_left'] += 2
            self.game_state['arm_right'] += 2
            self.timeline.append("➡️ **Arms repositioned RIGHT**")
            return True

        elif action == 'thrust' and self.game_state['fuel'] > 0:
            thrust_power = min(20, self.game_state['fuel'])
            self.game_state['booster_vel_y'] -= 0.25 * (thrust_power / 20)
            self.game_state['fuel'] -= thrust_power
            self.game_state['engine_light'] = True

            if thrust_power >= 15:
                self.timeline.append("🔥 **Full thrust burn executed!**")
            else:
                self.timeline.append("💨 **Low power thrust applied**")
            return True

        elif action == 'catch' and self.game_state['catch_ready']:
            catch_result = self.check_catch()

            if catch_result == 'perfect':
                self.game_state['success'] = True
                self.game_state['game_over'] = True
                self.game_state['score'] = 200  # Increased for perfect catch
                self.timeline.append("🌟 **PERFECT CATCH! FLAWLESS EXECUTION!**")
            elif catch_result == 'good':
                self.game_state['success'] = True
                self.game_state['game_over'] = True
                self.game_state['score'] = 150
                self.timeline.append("✅ **Excellent catch! Well executed!**")
            elif catch_result == 'rough':
                self.game_state['success'] = True
                self.game_state['game_over'] = True
                self.game_state['score'] = 100
                self.timeline.append("✅ **Rough but successful catch!**")
            elif catch_result == 'near_miss':
                self.timeline.append("⚠️ **Near miss! Adjust position and try again!**")
            else:
                self.timeline.append("❌ **Catch attempt failed - Booster missed!**")
            return True

        return False

    def make_embed(self, status=""):
        """Create enhanced Discord embed with improved visuals"""
        field = f"```ansi\n{self.make_field()}\n```"

        # Enhanced fuel bar with gradient colors
        fuel_pct = self.game_state['fuel'] / 100
        fuel_blocks = int(fuel_pct * 15)

        if fuel_pct > 0.7:
            fuel_bar = "🟢" * fuel_blocks + "⚫" * (15 - fuel_blocks)
        elif fuel_pct > 0.4:
            fuel_bar = "🟡" * fuel_blocks + "⚫" * (15 - fuel_blocks)
        elif fuel_pct > 0.2:
            fuel_bar = "🟠" * fuel_blocks + "⚫" * (15 - fuel_blocks)
        else:
            fuel_bar = "🔴" * fuel_blocks + "⚫" * (15 - fuel_blocks)

        # Enhanced wind indicator with strength visualization
        wind_strength = abs(self.game_state['wind'])
        if wind_strength < 0.05:
            wind_status = "🟢 Calm"
        elif wind_strength < 0.10:
            wind_status = f"🟡 {'←' if self.game_state['wind'] < 0 else '→'} Light Breeze"
        elif wind_strength < 0.20:
            wind_status = f"🟠 {'⬅️' if self.game_state['wind'] < 0 else '➡️'} Moderate Wind"
        else:
            wind_status = f"🔴 {'⬅️⬅️' if self.game_state['wind'] < 0 else '➡️➡️'} Strong Gust"

        # Enhanced phase descriptions
        phase_descriptions = {
            'falling': f'🛸 **Atmospheric Entry** (Alt: {12 - self.game_state["booster_y"]:.1f}km)',
            'catch_zone': '🎯 **🚨 CATCH ZONE ACTIVE 🚨**'
        }

        # Dynamic embed color based on game state
        if self.game_state['catch_ready']:
            embed_color = 0xFF0000  # Red for urgent catch zone
        elif self.game_state['booster_y'] > 8:
            embed_color = 0xFF6B00  # Orange for approach phase
        elif self.game_state['landing_burn_active']:
            embed_color = 0x00FF00  # Green for landing burn
        else:
            embed_color = 0x0099FF  # Blue for normal flight

        embed = discord.Embed(
            title="Catch Booster16",
            description=field,
            color=embed_color
        )

        # Enhanced mission status with more details
        auto_system_status = ""
        if self.game_state['landing_burn_active']:
            auto_system_status = "🔥 Landing Burn ACTIVE"
        elif self.game_state['auto_engine_active']:
            auto_system_status = "🤖 Auto-Stabilizer ON"
        elif self.game_state['landing_burn_initiated']:
            auto_system_status = "⏳ Landing Burn READY"
        else:
            auto_system_status = "⚫ Manual Control"

        embed.add_field(
            name="📊 Mission Control",
            value=(f"**Fuel:** {fuel_bar} {self.game_state['fuel']}%\n"
                   f"**Wind:** {wind_status}\n"
                   f"**Phase:** {phase_descriptions.get(self.game_state['phase'], self.game_state['phase'].upper())}\n"
                   f"**Systems:** {auto_system_status}"),
            inline=True
        )

        # Enhanced telemetry with more precise data
        altitude = 12 - self.game_state['booster_y']
        v_speed = self.game_state['booster_vel_y']
        h_speed = self.game_state['booster_vel_x']

        # Add velocity indicators
        v_indicator = "↓" if v_speed > 0.5 else "→" if v_speed > 0 else "↑"
        h_indicator = "→" if h_speed > 0 else "←" if h_speed < 0 else "•"

        embed.add_field(
            name="📡 Flight Data",
            value=(f"**Altitude:** {altitude:.1f}km {v_indicator}\n"
                   f"**V-Speed:** {abs(v_speed):.2f}m/s\n"
                   f"**H-Speed:** {abs(h_speed):.2f}m/s {h_indicator}\n"
                   f"**Position:** {self.game_state['booster_x']:.1f}m\n"
                   f"**Arms Gap:** {self.game_state['arm_right'] - self.game_state['arm_left']:.0f}m"),
            inline=True
        )

        # Enhanced mission log with color coding
        if self.timeline:
            recent_events = self.timeline[-4:]  # Show more events
            embed.add_field(
                name="📺 Mission Log",
                value="\n".join(recent_events),
                inline=False
            )

        if status:
            embed.add_field(name="🚨 STATUS UPDATE", value=f"**{status}**", inline=False)

        # Enhanced footer with dynamic tips
        footer_texts = [
            "🎮 Use buttons to control • 🔥 Advanced Auto-Landing System",
            "💡 TIP: Position arms early for better catches!",
            "⚡ TIP: Save fuel for final approach corrections!",
            "🎯 TIP: Watch horizontal velocity in catch zone!"
        ]

        footer_text = footer_texts[self.game_state['animation_frame'] % len(footer_texts)]
        embed.set_footer(text=footer_text)

        return embed


@bot.command(name="catchbooster")
async def catchbooster(ctx):
    """Enhanced Mechzilla.io-style booster catching game with superior animations (fully integrated with scoring system)."""

    # Create the game and view
    game = EnhancedCatchGame(ctx)
    view = CatchGameView(game)
    game.view = view

    embed = game.make_embed("🚀 **Mission Control Online - Booster separation confirmed!**")
    msg = await ctx.send(embed=embed, view=view)

    await asyncio.sleep(2)
    start_time = time.time()

    update_counter = 0
    last_update_time = time.time()

    # === GAME LOOP ===
    while not game.game_state['game_over']:
        current_time = time.time()
        game.update_game()
        update_counter += 1

        if game.game_state['catch_ready']:
            update_interval = 0.4
        elif game.game_state['booster_y'] > 8:
            update_interval = 0.5
        else:
            update_interval = 0.6

        if current_time - last_update_time >= update_interval:
            altitude = 12 - game.game_state['booster_y']
            velocity = game.game_state['booster_vel_y']

            # Dynamic status messages
            if game.game_state['catch_ready']:
                status_msg = "🚨 **CATCH WINDOW OPEN - EXECUTE IMMEDIATELY!** 🚨"
            elif game.game_state['landing_burn_active']:
                status_msg = "🔥 **LANDING BURN ACTIVE - Automatic control engaged**"
            elif altitude <= 2:
                status_msg = "🔴 **FINAL APPROACH - Last chance for corrections!**"
            elif altitude <= 4:
                status_msg = "⚠️ **Critical altitude - Position arms NOW!**"
            elif velocity > 1.0:
                status_msg = "⚡ **High velocity detected - Consider thrust burn**"
            elif game.game_state['auto_engine_active']:
                status_msg = "🤖 **Auto-stabilizers maintaining safe trajectory**"
            elif altitude <= 8:
                status_msg = "🎯 **Approach phase - Monitor systems closely**"
            else:
                status_msg = "🚀 **Descent phase - All systems nominal**"

            view.update_button_states()

            try:
                await msg.edit(embed=game.make_embed(status_msg), view=view)
                last_update_time = current_time
            except discord.errors.NotFound:
                break
            except discord.errors.HTTPException:
                await asyncio.sleep(0.2)

        await asyncio.sleep(0.1)

    # Disable buttons on game end
    for item in view.children:
        item.disabled = True

    # === SCORING ===
    elapsed_time = time.time() - start_time
    user_id = ctx.author.id

    if game.game_state['success']:
        # Scoring breakdown
        base_score = game.game_state['score']
        time_bonus = max(0, int(100 - elapsed_time * 2))
        fuel_bonus = game.game_state['fuel'] // 2
        arm_center = (game.game_state['arm_left'] + game.game_state['arm_right']) / 2
        booster_pos = game.game_state['booster_x']
        precision_error = abs(arm_center - booster_pos)
        precision_bonus = max(0, int(50 - precision_error * 10))
        final_velocity = abs(game.game_state['booster_vel_y'])
        velocity_bonus = max(0, int(30 - final_velocity * 20))
        auto_penalty = 20 if hasattr(game, '_auto_engine_used') else 0

        total_score = base_score + time_bonus + fuel_bonus + precision_bonus + velocity_bonus - auto_penalty

        # === Add to persistent scoring ===
        add_score(user_id, total_score)
        user_total = scores.get(str(user_id), 0)

        final_embed = discord.Embed(
            title="🏆 MISSION SUCCESS! BOOSTER RECOVERED!",
            description=f"**{ctx.author.display_name}** has successfully caught the booster with Mechzilla!",
            color=0x00FF00
        )

        final_embed.add_field(
            name="📊 Detailed Scoring",
            value=(f"**Base Score:** {base_score} pts\n"
                   f"**Time Bonus:** +{time_bonus} pts\n"
                   f"**Fuel Bonus:** +{fuel_bonus} pts\n"
                   f"**Precision Bonus:** +{precision_bonus} pts\n"
                   f"**Velocity Bonus:** +{velocity_bonus} pts\n"
                   f"**Auto-Pilot Penalty:** -{auto_penalty} pts\n"
                   f"**MISSION TOTAL:** **{total_score} pts**"),
            inline=True
        )

        final_embed.add_field(
            name="⏱️ Mission Stats",
            value=(f"**Duration:** {elapsed_time:.1f}s\n"
                   f"**Fuel Remaining:** {game.game_state['fuel']}%\n"
                   f"**Final Velocity:** {final_velocity:.2f}m/s\n"
                   f"**Precision Error:** {precision_error:.1f}m"),
            inline=True
        )

        # Achievements
        achievements = []
        if base_score >= 200: achievements.append("🌟 Perfect Landing Master")
        if fuel_bonus >= 40: achievements.append("⛽ Fuel Conservation Expert")
        if time_bonus >= 60: achievements.append("⚡ Lightning Fast Pilot")
        if precision_bonus >= 40: achievements.append("🎯 Precision Specialist")
        if velocity_bonus >= 25: achievements.append("🪶 Feather Touch Landing")
        if auto_penalty == 0: achievements.append("🎮 Manual Flight Ace")
        if total_score >= 300: achievements.append("👨‍🚀 Elite Space Pilot")

        if achievements:
            final_embed.add_field(
                name="🏅 Achievements",
                value="\n".join(achievements),
                inline=False
            )

        final_embed.add_field(
            name="🏆 Career Statistics",
            value=f"**Total Career Points:** {user_total:,} pts\nCheck leaderboard for rank!",
            inline=False
        )

    else:
        # === FAILURE ===
        final_embed = discord.Embed(
            title="💥 MISSION FAILED - BOOSTER LOST",
            description="Mission analysis and recommendations for future attempts:",
            color=0xFF0000
        )

        impact_velocity = game.game_state['booster_vel_y']
        fuel_remaining = game.game_state['fuel']
        final_position = game.game_state['booster_x']

        final_embed.add_field(
            name="📋 Failure Analysis",
            value=(f"**Impact Velocity:** {impact_velocity:.2f}m/s\n"
                   f"**Final Position:** {final_position:.1f}m\n"
                   f"**Fuel Remaining:** {fuel_remaining}%\n"
                   f"**Mission Duration:** {elapsed_time:.1f}s\n"
                   f"**Catch Attempted:** {'Yes' if game.game_state.get('catch_attempted') else 'No'}"),
            inline=True
        )

        recommendations = []
        if impact_velocity > 1.5:
            recommendations.append("• Use thrust burns earlier to reduce descent speed")
        if fuel_remaining > 50:
            recommendations.append("• Use more fuel for control if needed")
        if abs(final_position - 12) > 5:
            recommendations.append("• Position arms earlier")
        if not game.game_state.get('catch_attempted'):
            recommendations.append("• Attempt catch when booster enters the catch zone")
        recommendations.append("• Monitor the auto-landing burn system")

        final_embed.add_field(
            name="💡 Recommendations",
            value="\n".join(recommendations),
            inline=True
        )

        final_embed.add_field(
            name="📺 Final Mission Event",
            value=game.timeline[-1] if game.timeline else "System malfunction detected",
            inline=False
        )

        # Consolation score
        consolation_score = 10
        add_score(user_id, consolation_score)
        user_total = scores.get(str(user_id), 0)

        final_embed.add_field(
            name="🎖️ Participation Award",
            value=f"+{consolation_score} pts for mission attempt\n**Career Total:** {user_total:,} pts",
            inline=False
        )

    final_embed.set_footer(
        text="🚀 Use 'catchbooster' again to attempt another mission! • Check leaderboards for rankings!")

    try:
        await msg.edit(embed=final_embed, view=view)
    except:
        await ctx.send(embed=final_embed)





SCORES_FILE = "scores.json"

def load_scores():
    """Load scores from a JSON file if it exists, otherwise return empty dict."""
    if os.path.exists(SCORES_FILE):
        with open(SCORES_FILE, "r") as f:
            return json.load(f)
    return {}

def save_scores():
    """Save current scores dict to JSON file."""
    with open(SCORES_FILE, "w") as f:
        json.dump(scores, f)

scores = load_scores()

def add_score(user_id, points=1):
    """Add points to a user and persist to JSON."""
    scores[str(user_id)] = scores.get(str(user_id), 0) + points
    save_scores()


@bot.command(name="games")
async def games(ctx):
    """Display a beautiful, comprehensive list of all available games."""

    # Create main embed with gradient-like color and attractive styling
    embed = discord.Embed(
        title="🎮 Space Gaming Hub — Complete Game Collection",
        description="**Welcome to the ultimate space-themed gaming experience!**\n\nChoose from our collection of mini-games, challenges, and simulations. Earn points, climb the leaderboard, and become the ultimate space commander!",
        color=0x5865F2,  # Discord's blurple
        timestamp=ctx.message.created_at
    )

    # Set thumbnail and author
    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    embed.set_author(name=f"Games requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)

    # Quick Play Games Section
    quick_games = (
        "🪨📄✂️ **Rock Paper Scissors** — `!rps`\n"
        "├ Classic RPS battle with the bot\n"
        "└ **Reward:** +1 point for victory\n\n"

        "🪙 **Coin Flip** — `!coinflip`\n"
        "├ Test your luck with a simple coin toss\n"
        "└ **Reward:** +1 point for correct guess\n\n"

        "🎲 **Dice Roll** — `!dice <guess> <sides>`\n"
        "├ Roll dice and predict the outcome\n"
        "└ **Reward:** +1 point for exact match\n\n"

        "🔢 **Number Guess** — `!guess`\n"
        "├ Guess a number between 1-10 in 15 seconds\n"
        "└ **Reward:** +1 point for correct answer"
    )

    embed.add_field(
        name="⚡ Quick Play Games",
        value=quick_games,
        inline=False
    )

    # Knowledge Games Section
    knowledge_games = (
        "🎓 **Space Trivia** — `!trivia`\n"
        "├ Test your knowledge of space, planets, and the universe\n"
        "├ Three difficulty levels: Easy (1pt) • Medium (2pts) • Hard (3pts)\n"
        "└ **Features:** Interactive buttons, timed questions, detailed explanations\n\n"

        "🔤 **Word Unscramble** — `!unscramble`\n"
        "├ Unscramble words of varying difficulty\n"
        "├ Categories: Simple words • Space terms • Technical vocabulary\n"
        "└ **Rewards:** Easy (+1pt) • Medium (+2pts) • Hard (+3pts)\n\n"

        "🧮 **Math Quiz** — `!mathquiz`\n"
        "├ Solve random mathematical problems\n"
        "└ **Reward:** +1 point for correct solution\n\n"

        "7️⃣ **Rocket Design Quiz** — `!rocketdesign`\n"
        "├ Choose engines, tank sizes, and staging\n"
        "├ Design your own custom rocket configuration\n"
        
        "└ **Rewards:** Success based on engineering choices"
    )

    embed.add_field(
        name="🧠 Knowledge & Puzzle Games",
        value=knowledge_games,
        inline=False
    )

    # Advanced Simulation Games Section
    simulation_games = (
        "🛰️ **Starship Mission** — `!mission`\n"
        "├ Manage resources: Fuel, Food, and Research\n"
        "├ Make strategic decisions to survive in space\n"
        "└ **Rewards:** Points scale with survival turns\n\n"

        "🪝 **Booster Catch Challenge** — `!catchbooster`\n"
        "├ Position mechanical arms like Mechazilla\n"
        "├ Time your catch with precision and accuracy\n"
        "└ **Rewards:** Points based on reaction time & precision\n\n"

        "🚀 **Starship Predictor** — `!starship`\n"
        "├ Simulate full Starship launch (Booster + Ship)\n"
        "├ Answer mission parameters and technical questions\n"
        "└ **Rewards:** Success probability affects point multiplier\n\n"

        "🚀 **Ship Simulation** — `!predict <shipname>`\n"
        "├ Predict success for specific Starship vehicles\n"
        "├ Choose ship name and mission parameters\n"
        "└ **Rewards:** Based on prediction accuracy"
    )

    embed.add_field(
        name="🚀 Advanced Simulations",
        value=simulation_games,
        inline=False
    )

    # Coming Soon Section
    coming_soon = (
        "🌌 **Galaxy Exploration** 🔜\n"
        "├ Explore procedurally generated star systems\n"
        "└ **Rewards:** Discover rare planets and phenomena\n\n"
    )

    embed.add_field(
        name="🔮 Coming Soon",
        value=coming_soon,
        inline=False
    )

    # Stats and Leaderboard Section
    stats_info = (
        "🏆 **Leaderboard** — `!leaderboard`\n"
        "├ View top 10 players in your server\n"
        "├ Automatic Leader role assignment\n"
        "└ Server-specific rankings with medals\n\n"

        "📊 **Your Stats** — `!stats` *(Coming Soon)*\n"
        "├ Personal gaming statistics\n"
        "├ Game completion rates and streaks\n"
        "└ Achievement progress tracking"
    )

    embed.add_field(
        name="📈 Statistics & Rankings",
        value=stats_info,
        inline=False
    )

    # Game Categories Overview
    embed.add_field(
        name="🎯 Difficulty & Rewards",
        value=(
            "**🟢 Easy Games:** +1 point • Quick and accessible\n"
            "**🟡 Medium Games:** +2 points • Moderate challenge\n"
            "**🔴 Hard Games:** +3 points • Expert level difficulty\n"
            "**⭐ Bonus Rewards:** Performance-based scaling"
        ),
        inline=True
    )

    embed.add_field(
        name="🎮 Game Categories",
        value=(
            "**⚡ Quick Play:** Instant fun games\n"
            "**🧠 Knowledge:** Test your brain power\n"
            "**🚀 Simulations:** Complex challenges\n"
            "**🏆 Competitive:** Leaderboard climbing"
        ),
        inline=True
    )

    embed.add_field(
        name="💡 Pro Tips",
        value=(
            "• Play daily to climb the leaderboard\n"
            "• Try different difficulties for variety\n"
            "• Challenge friends to beat your scores\n"
            "• Master hard games for maximum points"
        ),
        inline=True
    )

    # Add server info if available
    if ctx.guild:
        embed.add_field(
            name=f"🏠 Playing in {ctx.guild.name}",
            value=f"**{len(ctx.guild.members)}** members • **{len([m for m in ctx.guild.members if not m.bot])}** humans",
            inline=False
        )

    # Footer with additional info
    embed.set_footer(
        text="🌟 All progress saved automatically • Use !help for command details • New games added regularly!",
        icon_url=ctx.bot.user.display_avatar.url if ctx.bot.user else None
    )

    # Send the main embed
    await ctx.send(embed=embed)
#trolling


MASTER_ID = 814791086114865233  # make sure this is an int, no quotes

# Map of guild_id -> list of allowed user IDs (multiple users can access same server)
GUILD_USER_MAP = {
    1210475350119813120: [814791086114865233,827552324389175297],  # Multiple users for server 1
    1397218218535424090: [1085236492571529287, 948973975353057341, 1418946895816167475, 1343933090191376446, 1357772900916138219],  # Multiple users for server 2
    # You can add more servers with their allowed user lists
    # 1234567890123456789: [111111111111111111, 222222222222222222],  # Example server 3
}

ALLOWED_GUILDS = set(GUILD_USER_MAP.keys())


@bot.command(name="timeout")
async def timeout(ctx, member: discord.Member, hours: int = 24):
    # Must be used in a guild (not DM)
    if ctx.guild is None:
        return await ctx.send("❌ This command must be used in a server (not DMs).")

    author_id = int(ctx.author.id)
    member_id = int(member.id)
    guild_id = int(ctx.guild.id)

    # DEBUG: uncomment if you want to see values in console for troubleshooting
    # print(f"[timeout] author={author_id}, member={member_id}, guild={guild_id}, MASTER={MASTER_ID}")

    # 1) First check if server is allowed
    if guild_id not in ALLOWED_GUILDS:
        error_embed = discord.Embed(
            title="❌ Server Not Authorized",
            description="This command can only be used in designated servers.",
            color=0xff0000
        )
        return await ctx.send(embed=error_embed)

    # 2) Check if author is allowed in this guild (except master)
    allowed_users = GUILD_USER_MAP.get(guild_id, [])
    if author_id != MASTER_ID and author_id not in allowed_users:
        error_embed = discord.Embed(
            title="❌ Access Denied",
            description="You are not allowed to use this command in this server.",
            color=0xff0000
        )
        error_embed.set_thumbnail(url=ctx.author.display_avatar.url)
        return await ctx.send(embed=error_embed)

    # 3) Block attempts to timeout the master user
    if member_id == MASTER_ID:
        master_embed = discord.Embed(
            title="👑 Cannot Target Master",
            description="You can't timeout the master!",
            color=0xffd700  # Gold color
        )
        master_embed.set_thumbnail(url=member.display_avatar.url)
        return await ctx.send(embed=master_embed)

    # 4) Block master from timing out anyone (if you want this behavior)
    # Remove this section if you want the master to be able to use the command

    # 5) Perform timeout / remove timeout
    try:
        if hours <= 0:
            await member.timeout(None, reason=f"Timeout removed by {ctx.author}")

            # Create embed for timeout removal
            embed = discord.Embed(
                title="🔓 Timeout Removed",
                description=f"{member.mention} has been freed from timeout!",
                color=0x00ff00,  # Green color
                timestamp=ctx.message.created_at
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="User", value=f"{member.name}#{member.discriminator}", inline=True)
            embed.add_field(name="Moderator", value=f"{ctx.author.mention}", inline=True)
            embed.add_field(name="Server", value=f"{ctx.guild.name}", inline=False)
            embed.set_footer(text=f"User ID: {member.id}")

            await ctx.send(embed=embed)

        else:
            # Discord has a maximum timeout of 28 days
            max_hours = 28 * 24  # 28 days in hours
            original_hours = hours
            if hours > max_hours:
                hours = max_hours

            duration = timedelta(hours=hours)
            await member.timeout(duration, reason=f"Timed out by {ctx.author}")

            # Create embed for timeout
            embed = discord.Embed(
                title="🔇 User Timed Out",
                description=f"{member.mention} has been placed in timeout",
                color=0xff6b6b,  # Red color
                timestamp=ctx.message.created_at
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="User", value=f"{member.name}#{member.discriminator}", inline=True)
            embed.add_field(name="Duration", value=f"{hours} hours", inline=True)
            embed.add_field(name="Moderator", value=f"{ctx.author.mention}", inline=True)

            # Calculate when timeout ends
            end_time = ctx.message.created_at + duration
            embed.add_field(name="Ends At", value=f"<t:{int(end_time.timestamp())}:F>", inline=True)
            embed.add_field(name="Server", value=f"{ctx.guild.name}", inline=True)
            embed.add_field(name="​", value="​", inline=True)  # Empty field for spacing

            embed.set_footer(text=f"User ID: {member.id}")

            # Add warning if hours were capped
            if original_hours > max_hours:
                embed.add_field(
                    name="⚠️ Note",
                    value=f"Requested {original_hours} hours, but maximum is {max_hours} hours (28 days)",
                    inline=False
                )

            await ctx.send(embed=embed)

    except discord.Forbidden:
        error_embed = discord.Embed(
            title="❌ Permission Error",
            description="I don't have permission or my role is too low to timeout this member.",
            color=0xff0000
        )
        error_embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=error_embed)

    except discord.HTTPException as e:
        if e.status == 50013:  # Missing permissions
            error_embed = discord.Embed(
                title="❌ Permission Error",
                description="I don't have the required permissions to timeout this member.",
                color=0xff0000
            )
        else:
            error_embed = discord.Embed(
                title="❌ Discord API Error",
                description=f"Discord API error: {e}",
                color=0xff0000
            )
        error_embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=error_embed)

    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Unexpected Error",
            description=f"Could not update timeout for {member.mention}",
            color=0xff0000
        )
        error_embed.add_field(name="Error Details", value=str(e), inline=False)
        error_embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=error_embed)


# Optional: Add a command to check who can use timeout in current server
@bot.command(name="timeout_users")
async def timeout_users(ctx):
    """Show which users can use the timeout command in this server"""
    if ctx.guild is None:
        return await ctx.send("❌ This command must be used in a server (not DMs).")

    guild_id = int(ctx.guild.id)
    author_id = int(ctx.author.id)

    # Only allow master or authorized users to see this info
    allowed_users = GUILD_USER_MAP.get(guild_id, [])
    if author_id != MASTER_ID and author_id not in allowed_users:
        return await ctx.send("❌ You are not allowed to use this command in this server.")

    if guild_id not in ALLOWED_GUILDS:
        return await ctx.send("❌ This server is not configured for timeout commands.")

    user_mentions = []
    for user_id in allowed_users:
        try:
            user = await bot.fetch_user(user_id)
            user_mentions.append(f"• {user.mention} ({user.name})")
        except:
            user_mentions.append(f"• User ID: {user_id} (user not found)")

    if user_mentions:
        embed = discord.Embed(
            title="Authorized Timeout Users",
            description="\n".join(user_mentions),
            color=0x00ff00
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ No users are configured for this server.")


AUTOMOD_ENABLED_GUILDS = {
    1210475350119813120: True,  # Server 1 - automod enabled
    1397218218535424090: True,  # Server 2 - automod enabled
    # Add more servers here as needed
    # 1234567890123456789: False,  # Example: Server 3 - automod disabled
}

# Users exempt from auto-moderation (in addition to master)
AUTOMOD_EXEMPT_USERS = [
    1085236492571529287,
    814791086114865233,
    948973975353057341,
    1343933090191376446,
    1418946895816167475,
    1414168461172539454,
    827552324389175297,
    # Master user
    # Add other user IDs here who should be exempt
    # 123456789012345678,  # Example: Moderator 1
    # 987654321098765432,  # Example: Moderator 2
]


# Auto-moderation: N-word detection and timeout
@bot.event
async def on_message(message):
    # Don't moderate bots or DMs
    if message.author.bot or message.guild is None:
        return

    guild_id = int(message.guild.id)
    author_id = int(message.author.id)

    # Check if auto-moderation is enabled for this server
    if not AUTOMOD_ENABLED_GUILDS.get(guild_id, False):
        # Process commands and return if automod is disabled
        await bot.process_commands(message)
        return

    # Don't timeout exempt users (master + any others you specify)
    if author_id in AUTOMOD_EXEMPT_USERS:
        # Process commands and return if user is exempt
        await bot.process_commands(message)
        return

    # List of N-word variations to detect (case insensitive)
    n_word_variations = [
        'nigger', 'nigga', 'n1gger', 'n1gga', 'nig ger', 'nig ga',
        'n-word', 'nword', 'n word', 'nigg3r', 'nigg4', 'n!gger',
        'n!gga', 'niqqer', 'niqqa', 'niggеr', 'niggа'  # Some with special characters
    ]

    # Check if message contains any variation
    message_content = message.content.lower().replace(' ', '').replace('-', '').replace('_', '')

    detected_word = None
    for word in n_word_variations:
        clean_word = word.lower().replace(' ', '').replace('-', '').replace('_', '')
        if clean_word in message_content:
            detected_word = word
            break

    if detected_word:
        try:
            # Delete the message first
            await message.delete()

            # Timeout the user for 24 hours
            duration = timedelta(hours=24)
            await message.author.timeout(duration, reason="Auto-moderation: Inappropriate language detected")

            # Create embed for auto-timeout
            embed = discord.Embed(
                title="🚫 Auto-Moderation Activated",
                description=f"{message.author.mention} has been automatically sanctioned",
                color=0xff2b2b,  # Dark red for auto-moderation
                timestamp=message.created_at
            )
            embed.set_thumbnail(url=message.author.display_avatar.url)
            embed.add_field(name="👤 User", value=f"{message.author.name}#{message.author.discriminator}", inline=True)
            embed.add_field(name="⏰ Duration", value="24 hours", inline=True)
            embed.add_field(name="📝 Violation", value="Inappropriate language", inline=True)

            # Calculate when timeout ends
            end_time = message.created_at + duration
            embed.add_field(name="🔚 Ends At", value=f"<t:{int(end_time.timestamp())}:F>", inline=True)
            embed.add_field(name="📍 Channel", value=f"{message.channel.mention}", inline=True)
            embed.add_field(name="🤖 System", value="Auto-Moderation", inline=True)

            embed.set_footer(text=f"User ID: {message.author.id} | Message auto-deleted")

            # Send the embed to the channel where the violation occurred
            await message.channel.send(embed=embed)

            print(
                f"[AUTO-MOD] User {message.author.name}#{message.author.discriminator} ({message.author.id}) timed out in {message.guild.name} for inappropriate language")

        except discord.Forbidden:
            # If bot can't timeout, just delete the message and send a warning
            warning_embed = discord.Embed(
                title="⚠️ Auto-Moderation Alert",
                description=f"{message.author.mention} used inappropriate language, but I lack timeout permissions.",
                color=0xff9900,
                timestamp=message.created_at
            )
            warning_embed.set_thumbnail(url=message.author.display_avatar.url)
            warning_embed.add_field(name="⚡ Action Needed", value="Manual moderation required", inline=False)
            warning_embed.add_field(name="🔍 Detected", value="Inappropriate language", inline=True)
            warning_embed.add_field(name="📍 Channel", value=f"{message.channel.mention}", inline=True)
            await message.channel.send(embed=warning_embed)

        except Exception as e:
            print(f"[AUTO-MOD ERROR] Failed to moderate {message.author.name}: {e}")
            # Still delete the message even if timeout fails
            try:
                if not message.flags.ephemeral:  # Only delete if message still exists
                    await message.delete()
            except:
                pass

    # Always process commands after checking the message
    await bot.process_commands(message)


# Command to manage auto-moderation settings
@bot.command(name="automod")
async def manage_automod(ctx, action: str = None, server_id: int = None):
    """Manage auto-moderation settings. Usage: !automod [status/enable/disable] [server_id]"""
    if ctx.guild is None:
        return await ctx.send("❌ This command must be used in a server (not DMs).")

    author_id = int(ctx.author.id)
    current_guild_id = int(ctx.guild.id)

    # Only master can manage automod settings
    if author_id != MASTER_ID:
        error_embed = discord.Embed(
            title="❌ Access Denied",
            description="Only the master user can manage auto-moderation settings.",
            color=0xff0000
        )
        error_embed.set_thumbnail(url=ctx.author.display_avatar.url)
        return await ctx.send(embed=error_embed)

    # If no action specified, show current status
    if action is None or action.lower() == "status":
        target_guild = server_id if server_id else current_guild_id
        is_enabled = AUTOMOD_ENABLED_GUILDS.get(target_guild, False)

        status_embed = discord.Embed(
            title="🤖 Auto-Moderation Status",
            color=0x00ff00 if is_enabled else 0xff6b6b
        )

        # Show status for current server or specified server
        if server_id:
            try:
                guild_name = bot.get_guild(server_id).name if bot.get_guild(server_id) else f"Server ID: {server_id}"
                status_embed.add_field(name="🏠 Server", value=guild_name, inline=False)
            except:
                status_embed.add_field(name="🏠 Server", value=f"Server ID: {server_id}", inline=False)
        else:
            status_embed.add_field(name="🏠 Current Server", value=ctx.guild.name, inline=False)

        status_embed.add_field(name="📊 Status", value="🟢 **ENABLED**" if is_enabled else "🔴 **DISABLED**", inline=True)
        status_embed.add_field(name="⏰ Timeout Duration", value="24 hours", inline=True)
        status_embed.add_field(name="🛡️ Protected Users", value=f"{len(AUTOMOD_EXEMPT_USERS)} exempt", inline=True)

        # Show all configured servers
        enabled_servers = [guild_id for guild_id, enabled in AUTOMOD_ENABLED_GUILDS.items() if enabled]
        disabled_servers = [guild_id for guild_id, enabled in AUTOMOD_ENABLED_GUILDS.items() if not enabled]

        if enabled_servers:
            status_embed.add_field(name="🟢 Enabled Servers", value=f"{len(enabled_servers)} servers", inline=True)
        if disabled_servers:
            status_embed.add_field(name="🔴 Disabled Servers", value=f"{len(disabled_servers)} servers", inline=True)

        status_embed.set_footer(text="Use !automod enable/disable [server_id] to change settings")
        return await ctx.send(embed=status_embed)

    # Enable or disable automod
    target_guild = server_id if server_id else current_guild_id

    if action.lower() == "enable":
        AUTOMOD_ENABLED_GUILDS[target_guild] = True
        action_embed = discord.Embed(
            title="✅ Auto-Moderation Enabled",
            description=f"Auto-moderation has been **enabled** for server ID: {target_guild}",
            color=0x00ff00,
            timestamp=ctx.message.created_at
        )
        action_embed.add_field(name="⚡ Takes Effect", value="Immediately", inline=True)
        action_embed.add_field(name="🎯 Target", value="Inappropriate language", inline=True)
        action_embed.add_field(name="⏰ Punishment", value="24-hour timeout", inline=True)

    elif action.lower() == "disable":
        AUTOMOD_ENABLED_GUILDS[target_guild] = False
        action_embed = discord.Embed(
            title="🔴 Auto-Moderation Disabled",
            description=f"Auto-moderation has been **disabled** for server ID: {target_guild}",
            color=0xff6b6b,
            timestamp=ctx.message.created_at
        )
        action_embed.add_field(name="⚡ Takes Effect", value="Immediately", inline=True)
        action_embed.add_field(name="📝 Note", value="Manual moderation only", inline=True)
        action_embed.add_field(name="🔄 Re-enable", value="Use !automod enable", inline=True)

    else:
        help_embed = discord.Embed(
            title="❓ Auto-Mod Command Help",
            description="**Usage:** `!automod [action] [server_id]`",
            color=0x3498db
        )
        help_embed.add_field(name="📊 Check Status", value="`!automod status`", inline=False)
        help_embed.add_field(name="🟢 Enable", value="`!automod enable [server_id]`", inline=True)
        help_embed.add_field(name="🔴 Disable", value="`!automod disable [server_id]`", inline=True)
        help_embed.add_field(name="💡 Examples", value="`!automod enable 123456789`\n`!automod status`", inline=False)
        return await ctx.send(embed=help_embed)

    action_embed.set_footer(text=f"Changed by {ctx.author.name}")
    await ctx.send(embed=action_embed)


# Command to manage exempt users
@bot.command(name="automod_exempt")
async def manage_exempt_users(ctx, action: str = None, user_id: int = None):
    """Manage users exempt from auto-moderation. Usage: !automod_exempt [add/remove/list] [user_id]"""
    author_id = int(ctx.author.id)

    # Only master can manage exempt users
    if author_id != MASTER_ID:
        error_embed = discord.Embed(
            title="❌ Access Denied",
            description="Only the master user can manage auto-moderation exemptions.",
            color=0xff0000
        )
        return await ctx.send(embed=error_embed)

    if action is None or action.lower() == "list":
        exempt_embed = discord.Embed(
            title="🛡️ Auto-Moderation Exempt Users",
            color=0x3498db
        )

        exempt_list = []
        for user_id in AUTOMOD_EXEMPT_USERS:
            try:
                user = await bot.fetch_user(user_id)
                if user_id == MASTER_ID:
                    exempt_list.append(f"👑 {user.mention} ({user.name}) - **Master**")
                else:
                    exempt_list.append(f"🛡️ {user.mention} ({user.name})")
            except:
                exempt_list.append(f"❓ User ID: {user_id} (user not found)")

        if exempt_list:
            exempt_embed.description = "\n".join(exempt_list)
        else:
            exempt_embed.description = "No exempt users configured"

        exempt_embed.set_footer(text="Use !automod_exempt add/remove [user_id] to modify")
        return await ctx.send(embed=exempt_embed)

    if user_id is None:
        return await ctx.send("❌ Please provide a user ID. Usage: `!automod_exempt [add/remove] [user_id]`")

    if action.lower() == "add":
        if user_id not in AUTOMOD_EXEMPT_USERS:
            AUTOMOD_EXEMPT_USERS.append(user_id)
            try:
                user = await bot.fetch_user(user_id)
                user_display = f"{user.name}#{user.discriminator}"
            except:
                user_display = f"User ID: {user_id}"

            add_embed = discord.Embed(
                title="✅ User Added to Exemption List",
                description=f"**{user_display}** is now exempt from auto-moderation",
                color=0x00ff00
            )
            await ctx.send(embed=add_embed)
        else:
            await ctx.send("❌ User is already exempt from auto-moderation.")

    elif action.lower() == "remove":
        if user_id == MASTER_ID:
            return await ctx.send("❌ Cannot remove the master user from exemption list.")

        if user_id in AUTOMOD_EXEMPT_USERS:
            AUTOMOD_EXEMPT_USERS.remove(user_id)
            try:
                user = await bot.fetch_user(user_id)
                user_display = f"{user.name}#{user.discriminator}"
            except:
                user_display = f"User ID: {user_id}"

            remove_embed = discord.Embed(
                title="🔴 User Removed from Exemption List",
                description=f"**{user_display}** is no longer exempt from auto-moderation",
                color=0xff6b6b
            )
            await ctx.send(embed=remove_embed)
        else:
            await ctx.send("❌ User is not in the exemption list.")

    else:
        await ctx.send("❌ Invalid action. Use `add`, `remove`, or `list`.")

@bot.command(name="bigboom")
async def gif(ctx):
    """Send an embed with a GIF."""
    embed = discord.Embed(
        title="**Big BOOM**",
        description="Here is your Big Boom!",
        color=discord.Color.blurple()
    )
    embed.set_image(url="https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExb2s4enRlejRsMjRqOHgxcXVpYXlsbGxpMDNiMG5mMXhkdWo1NmdrMyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/Ctv4yNLNfSpPd704nO/giphy.gif")
    # Replace with any GIF URL

    await ctx.send(embed=embed)



bot.run(TOKEN, log_handler=handler, log_level=logging.DEBUG)
from keep_alive import keep_alive, get_guild_commands, get_automod_words, get_allowed_users_list
keep_alive()
import discord
from discord import ui, ButtonStyle, Interaction, Embed
from galaxy_keeper import setup_galaxy, daily_galaxy_backup
from booster_catch import setup_booster_catch
from discord.ext import commands,tasks
import shutil
import logging
from dotenv import load_dotenv
from datetime import timedelta
import os
import time
import random
import json
import asyncio
import glob
import math
from typing import Dict, Any, List, Optional
import requests
import base64

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = os.getenv("GUILD_ID")

GUILD = discord.Object(id=int(GUILD_ID)) if GUILD_ID else None

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content=True
intents.voice_states=True
intents.members=True

bot=commands.Bot(command_prefix='!',intents=intents)



from keep_alive import (
    get_guild_commands,
    get_automod_words,
    get_automod_enabled_status,
    get_allowed_users_list,
    get_welcome_channel_id,
    set_bot_instance
)


# ============================================
# FIXED WELCOME MESSAGE EVENT HANDLER
# ============================================

@bot.event
async def on_member_join(member: discord.Member):
    """Send an embed welcome message with profile pic to the correct channel per server."""

    guild_id = member.guild.id

    # Get welcome channel from API
    channel_id = get_welcome_channel_id(guild_id)

    if channel_id:
        # Try to get the configured channel
        channel = member.guild.get_channel(channel_id)

        if not channel:
            # Channel was deleted or bot doesn't have access
            print(f"⚠️ Configured welcome channel {channel_id} not found in {member.guild.name}")
            return
    else:
        # No welcome channel configured - DO NOT send message
        print(f"ℹ️ No welcome channel configured for {member.guild.name} - skipping welcome message")
        return

    # Make the embed
    embed = discord.Embed(
        title=f"🎉 Welcome to {member.guild.name}!",
        description=(
            f"Hey {member.mention}, welcome aboard! We're excited to have you here.\n\n"
            f"Take a look at the rules, introduce yourself, and enjoy your stay 🚀"
        ),
        color=discord.Color.blurple()
    )
    embed.set_thumbnail(url=member.display_avatar.url)  # user's profile picture
    embed.set_footer(text=f"You're member #{len(member.guild.members)} in {member.guild.name}!")

    try:
        await channel.send(embed=embed)
        print(f"✅ Sent welcome message for {member.name} in {member.guild.name} to #{channel.name}")
    except discord.Forbidden:
        print(f"⚠️ Cannot send welcome message in {channel.name} - missing permissions")
    except Exception as e:
        print(f"❌ Error sending welcome message: {e}")


# ============================================
# UPDATED WELCOME INFO COMMAND
# ============================================

@bot.command(name='welcomeinfo')
async def welcome_info(ctx):
    """
    Show current welcome channel configuration
    Usage: !welcomeinfo
    """
    guild_id = ctx.guild.id
    channel_id = get_welcome_channel_id(guild_id)

    embed = discord.Embed(
        title="👋 Welcome Channel Info",
        description=f"Welcome message configuration for **{ctx.guild.name}**",
        color=discord.Color.blue()
    )

    if channel_id:
        channel = ctx.guild.get_channel(channel_id)
        if channel:
            embed.add_field(
                name="📍 Current Channel",
                value=f"{channel.mention}\n**Name:** #{channel.name}\n**ID:** `{channel_id}`",
                inline=False
            )
            embed.add_field(
                name="✅ Status",
                value="Welcome messages are **ACTIVE** for this server",
                inline=False
            )
            embed.color = discord.Color.green()
        else:
            embed.add_field(
                name="⚠️ Channel Not Found",
                value=f"Configured channel ID `{channel_id}` no longer exists.\n**Welcome messages are DISABLED until you set a new channel.**",
                inline=False
            )
            embed.add_field(
                name="🔧 Fix This",
                value="Use `!setwelcome #channel-name` to set a new welcome channel",
                inline=False
            )
            embed.color = discord.Color.orange()
    else:
        embed.add_field(
            name="❌ Not Configured",
            value="No welcome channel is set for this server.\n**Welcome messages are currently DISABLED.**",
            inline=False
        )
        embed.add_field(
            name="🔧 Setup Instructions",
            value="Use `!setwelcome #channel-name` to enable welcome messages.\n\nExample: `!setwelcome #general`",
            inline=False
        )
        embed.color = discord.Color.red()

    embed.add_field(
        name="🔧 Admin Commands",
        value=(
            "`!setwelcome #channel` - Set welcome channel\n"
            "`!testwelcome` - Test welcome message\n"
            "`!welcomeinfo` - Show this info"
        ),
        inline=False
    )

    embed.set_footer(text="Powered by OLIT API")

    await ctx.send(embed=embed)


# ============================================
# UPDATED BOT READY EVENT
# ============================================


# ============================================
# ADMIN COMMANDS FOR WELCOME MANAGEMENT
# ============================================

@bot.command(name='setwelcome')
@commands.has_permissions(administrator=True)
async def set_welcome_channel(ctx, channel: discord.TextChannel):
    """
    Set the welcome channel for this server
    Usage: !setwelcome #channel-name
    """
    import requests

    guild_id = ctx.guild.id
    channel_id = channel.id

    # Update via API
    try:
        API_BASE_URL = os.getenv('API_BASE_URL')
        API_KEY = os.getenv('API_KEY')

        response = requests.post(
            f"{API_BASE_URL}/api/welcome_channel",
            headers={
                'Content-Type': 'application/json',
                'X-API-Key': API_KEY
            },
            json={
                'guild_id': str(guild_id),
                'channel_id': str(channel_id)
            },
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()

            if data.get('success'):
                embed = discord.Embed(
                    title="✅ Welcome Channel Updated",
                    description=f"Welcome messages will now be sent to {channel.mention}",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="📍 Channel Info",
                    value=f"**Name:** #{channel.name}\n**ID:** `{channel_id}`",
                    inline=False
                )
                embed.set_footer(text="Changes take effect immediately")

                await ctx.send(embed=embed)
            else:
                await ctx.send(f"❌ API Error: {data.get('error', 'Unknown error')}")
        else:
            await ctx.send(f"❌ API request failed with status {response.status_code}")

    except requests.exceptions.RequestException as e:
        await ctx.send(f"❌ Connection error: {str(e)}")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")


@bot.command(name='testwelcome')
@commands.has_permissions(administrator=True)
async def test_welcome(ctx):
    """
    Test the welcome message (simulates a new member joining)
    Usage: !testwelcome
    """
    guild_id = ctx.guild.id
    channel_id = get_welcome_channel_id(guild_id)

    if channel_id:
        channel = ctx.guild.get_channel(channel_id)
    else:
        channel = ctx.guild.system_channel

    if not channel:
        await ctx.send("❌ No welcome channel configured and no system channel available!")
        return

    # Create test embed
    embed = discord.Embed(
        title=f"🎉 Welcome to {ctx.guild.name}!",
        description=(
            f"Hey {ctx.author.mention}, welcome aboard! We're excited to have you here.\n\n"
            f"Take a look at the rules, introduce yourself, and enjoy your stay 🚀"
        ),
        color=discord.Color.blurple()
    )
    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    embed.set_footer(text=f"You're member #{len(ctx.guild.members)} in {ctx.guild.name}!")

    try:
        test_msg = await channel.send(embed=embed)

        await ctx.send(
            f"✅ Test welcome message sent to {channel.mention}!\n"
            f"**Message ID:** {test_msg.id}"
        )
    except discord.Forbidden:
        await ctx.send(f"❌ I don't have permission to send messages in {channel.mention}")
    except Exception as e:
        await ctx.send(f"❌ Error sending test message: {str(e)}")

# ============================================
# ERROR HANDLER
# ============================================

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command!")
    elif isinstance(error, commands.ChannelNotFound):
        await ctx.send("❌ Channel not found! Please mention a valid channel.")
    elif isinstance(error, commands.CommandNotFound):
        pass  # Ignore - might be custom command
    else:
        print(f"Error: {error}")
        await ctx.send(f"❌ An error occurred: {str(error)}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if "scrub" in message.content.lower():
        await message.delete()

    await bot.process_commands(message)


server_emojis = {
    1411425019434766499: {  # Replace with your actual server ID
        "bash_emojis": [1414192630165667872, 1414188725163790336, 1414192628010061824],
        "eq_emoji": 1414188725163790336,
        "aa_emoji": 1414192630165667872,
        "sheriff_emoji": 1414192628010061824
    }
    # Add more servers here if needed
}


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Don't respond to DMs
    if not message.guild:
        return

    content = message.content.lower()
    server_id = message.guild.id

    # Check for command triggers
    if "appbcbash" in content:
        await handle_bash_command(message, server_emojis.get(server_id))
    elif "appbceq" in content:
        await handle_eq_command(message, server_emojis.get(server_id))
    elif "appbaa" in content:
        await handle_aa_command(message, server_emojis.get(server_id))
    elif "appsheriff" in content:
        await handle_sheriff_command(message, server_emojis.get(server_id))

    # Process other commands if you have them
    await bot.process_commands(message)


async def handle_bash_command(message, server_config):
    """Handle the bash command"""
    if server_config and "bash_emojis" in server_config:
        # Try custom emojis
        success = False
        for emoji_id in server_config["bash_emojis"]:
            emoji = await get_emoji_safely(message.guild, emoji_id)
            if emoji:
                try:
                    await message.add_reaction(emoji)
                    success = True
                except Exception as e:
                    print(f"Failed to add custom emoji {emoji_id}: {e}")

        if not success:
            await message.add_reaction("✅")
    else:
        # Default emojis for servers without custom setup
        default_emojis = ["✅", "👍", "⭐"]
        for emoji in default_emojis:
            try:
                await message.add_reaction(emoji)
            except Exception as e:
                print(f"Failed to add default emoji {emoji}: {e}")


async def handle_eq_command(message, server_config):
    """Handle the eq command"""
    if server_config and "eq_emoji" in server_config:
        emoji = await get_emoji_safely(message.guild, server_config["eq_emoji"])
        if emoji:
            try:
                await message.add_reaction(emoji)
                return
            except Exception as e:
                print(f"Failed to add custom emoji: {e}")

    # Fallback to default
    try:
        await message.add_reaction("✅")
    except Exception as e:
        print(f"Failed to add fallback emoji: {e}")


async def handle_aa_command(message, server_config):
    """Handle the aa command"""
    if server_config and "aa_emoji" in server_config:
        emoji = await get_emoji_safely(message.guild, server_config["aa_emoji"])
        if emoji:
            try:
                await message.add_reaction(emoji)
                return
            except Exception as e:
                print(f"Failed to add custom emoji: {e}")

    # Fallback to default
    try:
        await message.add_reaction("👍")
    except Exception as e:
        print(f"Failed to add fallback emoji: {e}")


async def handle_sheriff_command(message, server_config):
    """Handle the sheriff command"""
    if server_config and "sheriff_emoji" in server_config:
        emoji = await get_emoji_safely(message.guild, server_config["sheriff_emoji"])
        if emoji:
            try:
                await message.add_reaction(emoji)
                return
            except Exception as e:
                print(f"Failed to add custom emoji: {e}")

    # Fallback to default
    try:
        await message.add_reaction("⭐")
    except Exception as e:
        print(f"Failed to add fallback emoji: {e}")


async def get_emoji_safely(guild, emoji_id):
    """Safely get an emoji, trying multiple methods"""
    try:
        # First try to find it in the current guild
        for emoji in guild.emojis:
            if emoji.id == emoji_id:
                return emoji

        # Then try bot.get_emoji (for emojis from other guilds the bot is in)
        emoji = bot.get_emoji(emoji_id)
        if emoji:
            return emoji

    except Exception as e:
        print(f"Error getting emoji {emoji_id}: {e}")

    return None


# Slash commands using bot.tree.command
@bot.tree.command(name="appbcbash", description="React with appbcbash emojis")
async def slash_appbcbash(interaction: discord.Interaction):
    """Slash command for bash emojis"""
    try:
        # Get the message the interaction was on (if it's a context menu command)
        # For regular slash commands, we'll react to the last message in the channel
        messages = [msg async for msg in interaction.channel.history(limit=1)]
        if messages:
            target_message = messages[0]
        else:
            await interaction.response.send_message("No message found to react to!", ephemeral=True)
            return

        server_config = server_emojis.get(interaction.guild.id) if interaction.guild else None
        await handle_bash_command(target_message, server_config)
        await interaction.response.send_message("Added appbcbash emojis!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Error: {e}", ephemeral=True)


@bot.tree.command(name="appbceq", description="React with appbceq emoji")
async def slash_appbceq(interaction: discord.Interaction):
    """Slash command for eq emoji"""
    try:
        messages = [msg async for msg in interaction.channel.history(limit=1)]
        if messages:
            target_message = messages[0]
        else:
            await interaction.response.send_message("No message found to react to!", ephemeral=True)
            return

        server_config = server_emojis.get(interaction.guild.id) if interaction.guild else None
        await handle_eq_command(target_message, server_config)
        await interaction.response.send_message("Added appbceq emoji!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Error: {e}", ephemeral=True)


@bot.tree.command(name="appbaa", description="React with appbaa emoji")
async def slash_appbaa(interaction: discord.Interaction):
    """Slash command for aa emoji"""
    try:
        messages = [msg async for msg in interaction.channel.history(limit=1)]
        if messages:
            target_message = messages[0]
        else:
            await interaction.response.send_message("No message found to react to!", ephemeral=True)
            return

        server_config = server_emojis.get(interaction.guild.id) if interaction.guild else None
        await handle_aa_command(target_message, server_config)
        await interaction.response.send_message("Added appbaa emoji!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Error: {e}", ephemeral=True)


@bot.tree.command(name="appsheriff", description="React with sheriff emoji")
async def slash_appsheriff(interaction: discord.Interaction):
    """Slash command for sheriff emoji"""
    try:
        messages = [msg async for msg in interaction.channel.history(limit=1)]
        if messages:
            target_message = messages[0]
        else:
            await interaction.response.send_message("No message found to react to!", ephemeral=True)
            return

        server_config = server_emojis.get(interaction.guild.id) if interaction.guild else None
        await handle_sheriff_command(target_message, server_config)
        await interaction.response.send_message("Added sheriff emoji!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Error: {e}", ephemeral=True)


# Don't forget to sync the commands when the bot starts up

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
async def behero(ctx):
    await ctx.send(f"Wanna be a hero try catching water tower which is 69m in height falling at insane speeds")


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
@bot.command(name="rolemapping")
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
    """Display a comprehensive, organized list of all available games with dynamic stats."""

    # Get current server stats
    guild_member_ids = [member.id for member in ctx.guild.members] if ctx.guild else []
    guild_scores = {uid: pts for uid, pts in scores.items() if int(uid) in guild_member_ids}
    total_players = len(guild_scores)
    total_galaxy_players = len(galaxy_user_data) if 'galaxy_user_data' in globals() else 0

    # Create main embed
    embed = discord.Embed(
        title="🎮 Launch Tower Gaming Hub — Complete Collection",
        description=f"**Welcome to the ultimate space gaming experience!**\n\n"
                    f"🏠 **{ctx.guild.name if ctx.guild else 'Server'}:** {total_players} active players\n"
                    f"🌌 **Galaxy Explorers:** {total_galaxy_players} commanders\n"
                    f"🏆 **Total Games:** 15+ unique experiences\n\n"
                    f"Earn points, climb leaderboards, and become the ultimate space commander!",
        color=0x5865F2,
        timestamp=ctx.message.created_at
    )

    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    embed.set_author(
        name=f"Gaming Hub requested by {ctx.author.display_name}",
        icon_url=ctx.author.display_avatar.url
    )

    # ⚡ QUICK PLAY GAMES
    quick_games = (
        "🪨📄✂️ **Rock Paper Scissors** — `!rps`\n"
        "├ Interactive button-based RPS battle\n"
        "└ **Reward:** +1 point for victory\n\n"

        "🪙 **Coin Flip** — `!coinflip`\n"
        "├ Heads or tails prediction game\n"
        "└ **Reward:** +1 point for correct guess\n\n"

        "🎲 **Dice Roll** — `!dice [guess] [sides]`\n"
        "├ Predict dice outcomes with custom sides\n"
        "└ **Reward:** +1 point for exact match\n\n"

        "🔢 **Number Guess** — `!guess`\n"
        "├ Guess numbers 1-10 within time limit\n"
        "└ **Reward:** +1 point for correct answer"
    )

    embed.add_field(
        name="⚡ Quick Play Games (1 Point Each)",
        value=quick_games,
        inline=False
    )

    # 🧠 KNOWLEDGE & PUZZLE GAMES
    knowledge_games = (
        "🎓 **Space Trivia Challenge** — `!trivia`\n"
        "├ 60+ questions across 3 difficulty levels\n"
        "├ Topics: Planets, space exploration, astrophysics\n"
        "└ **Rewards:** Easy (+1) • Medium (+2) • Hard (+3)\n\n"

        "🔤 **Word Unscramble** — `!unscramble`\n"
        "├ Unscramble words from simple to space-technical\n"
        "├ Three categories with increasing difficulty\n"
        "└ **Rewards:** Easy (+1) • Medium (+2) • Hard (+3)\n\n"

        "🧮 **Math Quiz** — `!mathquiz`\n"
        "├ Solve random mathematical equations\n"
        "├ Modal input system with validation\n"
        "└ **Reward:** +1 point for correct solution"
    )

    embed.add_field(
        name="🧠 Knowledge & Puzzle Games",
        value=knowledge_games,
        inline=False
    )

    # 🚀 SPACE SIMULATION GAMES
    simulation_games = (
        "🌌 **Galaxy Explorer** — `!galaxy` `!explore` `!space`\n"
        "├ **NEW:** Explore procedurally generated star systems\n"
        "├ Features: Ship upgrades, resource mining, storyline\n"
        "├ Persistent progress with JSON data storage\n"
        "└ **Rewards:** Variable points based on discoveries\n\n"

        "🛰️ **Starship Mission Control** — `!mission`\n"
        "├ Manage fuel, food, and research resources\n"
        "├ Interactive button-based decision making\n"
        "└ **Rewards:** Points scale with survival duration\n\n"

        "🪝 **Booster Catch Challenge** — `!catchbooster`\n"
        "├ **FEATURED:** Advanced Mechzilla-style catching game\n"
        "├ Real-time physics, atmospheric effects, auto-landing\n"
        "├ Multiple difficulty levels and precision scoring\n"
        "└ **Rewards:** Up to 300+ points for perfect catches"
    )

    embed.add_field(
        name="🚀 Advanced Space Simulations",
        value=simulation_games,
        inline=False
    )

    # 🎯 PREDICTION & STRATEGY GAMES
    prediction_games = (
        "🚀 **Starship Launch Predictor** — `!starship`\n"
        "├ Answer mission parameters via dropdowns\n"
        "├ Weather, vehicle condition, payload analysis\n"
        "└ **Rewards:** Based on prediction accuracy\n\n"

        "🔮 **Mission Predictor** — `!predict [ship_name]`\n"
        "├ Chat-based test sequence simulation\n"
        "├ 5 different spacecraft system tests\n"
        "└ **Rewards:** Mission success probability scoring\n\n"

        "🛠️ **Rocket Design Quiz** — `!rocketdesign`\n"
        "├ Choose engines, fuel tanks, and payloads\n"
        "├ Engineering decision impact simulation\n"
        "└ **Rewards:** +2 points for successful launches"
    )

    embed.add_field(
        name="🎯 Prediction & Strategy Games",
        value=prediction_games,
        inline=False
    )

    # 🏆 LEADERBOARD & STATISTICS
    leaderboard_info = (
        "🏆 **Server Leaderboard** — `!leaderboard`\n"
        "├ Top 10 players with medals and rankings\n"
        "├ Automatic Leader role assignment system\n"
        "├ Server-specific statistics and totals\n"
        "└ **Features:** Real-time role management\n\n"

        "🌌 **Galaxy Leaderboard** — `!galacticleaderboard` `!gtop`\n"
        "├ Exploration-specific rankings\n"
        "├ Systems discovered and rare phenomena found\n"
        "└ **Categories:** Most explored • Rare discoveries\n\n"

        "📊 **Personal Stats** — `!galaxystats` `!gstats`\n"
        "├ Comprehensive exploration statistics\n"
        "├ Ship status, resources, achievements\n"
        "└ **Features:** Career progress tracking\n\n"

        "📊 **Your Stats** — `!stats`\n"
        "├ Personal gaming statistics\n"
        "├ Game completion rates and streaks\n"
        "└ Achievement progress tracking"
    )

    embed.add_field(
        name="🏆 Statistics & Rankings",
        value=leaderboard_info,
        inline=False
    )

    # 🛠️ UTILITY & SPECIAL COMMANDS
    utility_commands = (
        "🔧 **Ship Upgrade System** — `!shipyard` `!upgrade`\n"
        "├ Interactive upgrade browser with buttons\n"
        "├ 5 upgrade categories: Fuel, scanners, shields, cargo\n"
        "└ **Currency:** Credits earned from exploration\n\n"

        "🔭 **System Scanner** — `!scan` `!system` `!probe`\n"
        "├ Detailed analysis of current star system\n"
        "├ Planet composition, phenomena, hazards\n"
        "└ **Features:** Exploration mission planning\n\n"

        "🎮 **Game Info** — `!games` (this command)\n"
        "└ Complete overview of all available games"
    )

    embed.add_field(
        name="🛠️ Utility & Special Features",
        value=utility_commands,
        inline=False
    )

    # 📈 DIFFICULTY & REWARDS BREAKDOWN
    embed.add_field(
        name="📈 Scoring System",
        value=(
            "**🟢 Basic Games:** 1-2 points • Quick entertainment\n"
            "**🟡 Skill Games:** 2-5 points • Knowledge & strategy\n"
            "**🔴 Simulation Games:** 5-300+ points • Complex challenges\n"
            "**⭐ Galaxy Exploration:** Variable • Discovery-based rewards\n"
            "**🏆 Bonus Multipliers:** Performance & difficulty scaling"
        ),
        inline=True
    )

    embed.add_field(
        name="🎮 Game Categories",
        value=(
            "**⚡ Quick Play:** Instant fun, 1-2 minutes\n"
            "**🧠 Knowledge:** Trivia, puzzles, education\n"
            "**🚀 Simulations:** Complex, persistent progress\n"
            "**🎯 Strategy:** Prediction, planning, analysis\n"
            "**🌌 Exploration:** Open-world, RPG elements"
        ),
        inline=True
    )

    # 🌟 FEATURED GAME HIGHLIGHT
    featured_text = (
        "**🌟 Galaxy Explorer — NEW PERSISTENT WORLD**\n"
        f"└ {total_galaxy_players} active commanders exploring the galaxy\n\n"
        "**🪝 Booster Catch — MOST ADVANCED GAME**\n"
        "└ Real-time physics simulation with 300+ point potential\n\n"
        "**🎓 Space Trivia — EDUCATIONAL FAVORITE**\n"
        "└ 60+ questions across beginner to expert levels"
    )

    embed.add_field(
        name="🌟 Featured Experiences",
        value=featured_text,
        inline=False
    )

    # Server-specific information
    if ctx.guild:
        # Calculate some basic stats
        top_scorer = max(guild_scores.items(), key=lambda x: x[1]) if guild_scores else None

        server_info = f"**{len(ctx.guild.members)}** total members • **{total_players}** active gamers"
        if top_scorer:
            try:
                top_user = ctx.guild.get_member(int(top_scorer[0]))
                server_info += f"\n🏆 **Leader:** {top_user.display_name if top_user else 'Unknown'} ({top_scorer[1]:,} pts)"
            except:
                pass

        embed.add_field(
            name=f"🏠 {ctx.guild.name} Server Stats",
            value=server_info,
            inline=False
        )

    # Footer with tips and updates
    embed.set_footer(
        text="🚀 All progress auto-saved • New games added regularly • Use !help [game] for detailed instructions",
        icon_url=ctx.bot.user.display_avatar.url if ctx.bot.user else None
    )

    await ctx.send(embed=embed)


@bot.command(name="stats")
async def personal_stats(ctx):
    """Display comprehensive personal gaming statistics and achievements."""
    user_id = str(ctx.author.id)

    # Get user's total score
    total_score = scores.get(user_id, 0)

    # Get galaxy exploration data if available
    galaxy_data = None
    if 'galaxy_user_data' in globals() and user_id in galaxy_user_data:
        galaxy_data = galaxy_user_data[user_id]

    # Create main stats embed
    embed = discord.Embed(
        title=f"📊 Personal Gaming Statistics",
        description=f"**{ctx.author.display_name}'s Complete Performance Report**",
        color=0x9932cc,
        timestamp=ctx.message.created_at
    )

    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    embed.set_author(
        name=f"Statistics for {ctx.author.display_name}",
        icon_url=ctx.author.display_avatar.url
    )

    # Overall Performance
    if ctx.guild:
        guild_member_ids = [member.id for member in ctx.guild.members]
        guild_scores = {uid: pts for uid, pts in scores.items() if int(uid) in guild_member_ids}

        if guild_scores:
            sorted_scores = sorted(guild_scores.items(), key=lambda x: x[1], reverse=True)
            user_rank = next((i + 1 for i, (uid, _) in enumerate(sorted_scores) if uid == user_id),
                             len(sorted_scores) + 1)
            total_players = len(guild_scores)

            percentile = max(1, int(((total_players - user_rank + 1) / total_players) * 100))
        else:
            user_rank = 1
            total_players = 1
            percentile = 100
    else:
        user_rank = 1
        total_players = 1
        percentile = 100

    embed.add_field(
        name="🏆 Overall Performance",
        value=(f"**Total Points:** {total_score:,}\n"
               f"**Server Rank:** #{user_rank} of {total_players}\n"
               f"**Percentile:** Top {100 - percentile + 1}%\n"
               f"**Status:** {'🥇 Champion' if user_rank == 1 else '🥈 Elite' if user_rank <= 3 else '🥉 Expert' if user_rank <= 10 else '⭐ Player'}"),
        inline=False
    )

    # Game Category Performance (estimated based on typical point values)
    quick_games_estimated = min(total_score, max(0, total_score // 10))  # Assume some points from quick games
    knowledge_games_estimated = min(total_score, max(0, (total_score - quick_games_estimated) // 3))
    simulation_games_estimated = total_score - quick_games_estimated - knowledge_games_estimated

    embed.add_field(
        name="🎮 Game Category Breakdown",
        value=(f"**⚡ Quick Play Games:** ~{quick_games_estimated:,} pts\n"
               f"**🧠 Knowledge Games:** ~{knowledge_games_estimated:,} pts\n"
               f"**🚀 Simulations:** ~{simulation_games_estimated:,} pts\n"
               f"**📈 Estimated Games Played:** {(total_score // 5) + 1:,}"),
        inline=True
    )

    # Achievement System
    achievements = []

    # Point-based achievements
    if total_score >= 1000:
        achievements.append("🏆 Point Master (1,000+ points)")
    elif total_score >= 500:
        achievements.append("⭐ High Scorer (500+ points)")
    elif total_score >= 100:
        achievements.append("🎯 Dedicated Player (100+ points)")
    elif total_score >= 25:
        achievements.append("🎮 Active Gamer (25+ points)")
    elif total_score >= 1:
        achievements.append("🌟 First Steps (1+ points)")

    # Rank-based achievements
    if user_rank == 1:
        achievements.append("👑 Server Champion")
    elif user_rank <= 3:
        achievements.append("🥈 Top 3 Player")
    elif user_rank <= 10:
        achievements.append("🥉 Top 10 Player")

    # Galaxy-specific achievements
    if galaxy_data:
        systems_explored = len(galaxy_data.get('discovered_systems', set()))
        rare_discoveries = len(galaxy_data.get('rare_discoveries', []))

        if systems_explored >= 50:
            achievements.append("🌌 Galaxy Master (50+ systems)")
        elif systems_explored >= 20:
            achievements.append("🚀 Space Explorer (20+ systems)")
        elif systems_explored >= 5:
            achievements.append("🛸 Pilot (5+ systems)")

        if rare_discoveries >= 10:
            achievements.append("💎 Phenomenon Hunter")
        elif rare_discoveries >= 3:
            achievements.append("✨ Discovery Specialist")

    # Consistency achievements (estimated)
    if total_score >= 200:
        achievements.append("🔥 Consistent Performer")

    if achievements:
        embed.add_field(
            name="🏅 Achievements Unlocked",
            value="\n".join(achievements),
            inline=True
        )
    else:
        embed.add_field(
            name="🏅 Achievements",
            value="Play games to unlock achievements!",
            inline=True
        )

    # Galaxy Exploration Stats (if available)
    if galaxy_data:
        systems_explored = len(galaxy_data.get('discovered_systems', set()))
        exploration_rank = galaxy_data.get('exploration_rank', 'Cadet')
        credits = galaxy_data.get('credits', 0)
        fuel = galaxy_data.get('fuel', 0)
        max_fuel = galaxy_data.get('max_fuel', 100)

        # Resources
        resources = galaxy_data.get('resources', {'crystals': 0, 'metals': 0, 'energy': 0})
        total_resources = sum(resources.values())

        embed.add_field(
            name="🌌 Galaxy Exploration Profile",
            value=(f"**Rank:** {exploration_rank}\n"
                   f"**Systems Explored:** {systems_explored}\n"
                   f"**Credits:** {credits:,}\n"
                   f"**Fuel:** {fuel}/{max_fuel}\n"
                   f"**Resources:** {total_resources:,} total"),
            inline=False
        )

        # Ship upgrades
        ship_upgrades_data = galaxy_data.get('ship_upgrades', {})
        upgrade_levels = sum(ship_upgrades_data.values())

        if upgrade_levels > 0:
            upgrades_text = []
            for upgrade, level in ship_upgrades_data.items():
                if level > 0:
                    upgrade_name = upgrade.replace('_', ' ').title()
                    upgrades_text.append(f"• {upgrade_name}: Lv.{level}")

            embed.add_field(
                name="⚡ Ship Upgrades",
                value="\n".join(upgrades_text) if upgrades_text else "No upgrades purchased",
                inline=True
            )

    # Progress Tracking & Goals
    next_milestone = 0
    milestone_name = ""

    if total_score < 25:
        next_milestone = 25
        milestone_name = "Active Gamer"
    elif total_score < 100:
        next_milestone = 100
        milestone_name = "Dedicated Player"
    elif total_score < 500:
        next_milestone = 500
        milestone_name = "High Scorer"
    elif total_score < 1000:
        next_milestone = 1000
        milestone_name = "Point Master"
    else:
        next_milestone = ((total_score // 1000) + 1) * 1000
        milestone_name = f"Elite {next_milestone // 1000}K"

    progress_to_next = next_milestone - total_score
    progress_percentage = (total_score / next_milestone) * 100 if next_milestone > 0 else 100

    embed.add_field(
        name="🎯 Next Milestone",
        value=(f"**Goal:** {milestone_name} ({next_milestone:,} points)\n"
               f"**Progress:** {progress_percentage:.1f}%\n"
               f"**Points Needed:** {progress_to_next:,}"),
        inline=True
    )

    # Game Recommendations
    recommendations = []

    if total_score < 10:
        recommendations.append("🎮 Try `!trivia` for easy points")
        recommendations.append("⚡ Play `!rps` for quick games")
    elif total_score < 50:
        recommendations.append("🚀 Challenge `!catchbooster` for big points")
        recommendations.append("🌌 Explore `!galaxy` for adventure")
    elif total_score < 200:
        recommendations.append("🔥 Master hard trivia questions")
        recommendations.append("🛸 Build your galaxy empire")
    else:
        recommendations.append("👑 Help others discover games")
        recommendations.append("🏆 Compete for server champion")

    if recommendations:
        embed.add_field(
            name="💡 Recommended Next Steps",
            value="\n".join(recommendations),
            inline=True
        )

    # Recent Activity Summary (estimated)
    if total_score > 0:
        activity_level = "🔥 Very Active" if total_score >= 100 else "⚡ Active" if total_score >= 25 else "🌟 Getting Started"

        embed.add_field(
            name="📈 Activity Summary",
            value=(f"**Activity Level:** {activity_level}\n"
                   f"**Games Available:** 15+ experiences\n"
                   f"**Favorite Category:** {'🚀 Simulations' if simulation_games_estimated > knowledge_games_estimated else '🧠 Knowledge Games'}\n"
                   f"**Play Style:** {'Completionist' if total_score >= 500 else 'Explorer' if total_score >= 100 else 'Casual'}"),
            inline=False
        )

    # Footer with tips
    embed.set_footer(
        text="🚀 Stats update in real-time • Use !games to see all available experiences • Keep playing to unlock more achievements!"
    )

    await ctx.send(embed=embed)
#trolling

import os
import asyncio
import traceback
from datetime import datetime, timedelta, timezone
import discord
from discord.ext import commands

# ---------- Timezone helper (tries pytz, falls back to fixed UTC+5:30) ----------
try:
    import pytz
    IST = pytz.timezone("Asia/Kolkata")
    def now_in_ist():
        return datetime.now(IST)
except Exception:
    IST = timezone(timedelta(hours=5, minutes=30))
    def now_in_ist():
        return datetime.now(IST)

# ---------- Configuration ----------
TIMEZONE_NAME = "Asia/Kolkata"
ACTIVE_MONTH = 12
ACTIVE_START_DAY = 1
ACTIVE_END_DAY = 25

FESTIVE_IMAGE = "https://img.freepik.com/free-vector/flat-christmas-season-celebration-background_23-2149872289.jpg?semt=ais_hybrid&w=740&q=80"
COMMAND_NAME = "merrychristmas"


# track active games per channel to avoid overlapping games
active_games = {}  # channel_id -> True while a game is running

def is_christmas_active() -> bool:
    now = now_in_ist()
    return (now.month == ACTIVE_MONTH) and (ACTIVE_START_DAY <= now.day <= ACTIVE_END_DAY)

# ---------- Embeds ----------
def make_game_embed(animation_line: str = ""):
    embed = discord.Embed(
        title="🎄 Merry Christmas!",
        description=(
            "The Grinch is trying to steal the presents! 🎁\n\n"
            "Click **Stop the Grinch!** within **5 seconds** to save Christmas!\n\n"
            f"{animation_line}"
        ),
        color=0xE63946
    )
    embed.set_image(url=FESTIVE_IMAGE)
    embed.set_footer(text=f"Grinch Sim • 5 second challenge • Timezone: {TIMEZONE_NAME}")
    return embed

def make_result_embed(*, winner: str):
    if winner == "you":
        title = "🎉 You saved Christmas!"
        desc = "You stopped the Grinch — all presents are safe. Merry Christmas! 🎅🤍"
        color = 0x2ECC71
    else:
        title = "😈 The Grinch got away..."
        desc = "The Grinch stole the presents this time — better luck next year. 🎁💨"
        color = 0x6C757D

    embed = discord.Embed(title=title, description=desc, color=color)
    embed.set_image(url=FESTIVE_IMAGE)
    embed.set_footer(text="Grinch Sim result")
    return embed

# ---------- Minigame view ----------
class GrinchView(discord.ui.View):
    def __init__(self, timeout: float = 5.0):
        super().__init__(timeout=timeout)
        self.result = None
        self._message = None
        self.winner_user = None  # store who clicked

    @discord.ui.button(label="Stop the Grinch!", style=discord.ButtonStyle.primary)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.result is not None:
            await interaction.response.send_message("The game already finished.", ephemeral=True)
            return

        # first click wins — record the user
        self.result = "stopped"
        self.winner_user = interaction.user
        button.disabled = True
        try:
            await interaction.response.edit_message(embed=make_result_embed(winner="you"), view=self)
        except Exception:
            await interaction.response.send_message("You stopped the Grinch! 🎉", ephemeral=True)
        self.stop()

    async def on_timeout(self):
        if self.result is None:
            self.result = "grinch_won"
            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True
            try:
                if self._message:
                    await self._message.edit(embed=make_result_embed(winner="grinch"), view=self)
            except Exception:
                pass

# ---------- Animation helper ----------
async def run_presents_animation(message: discord.Message, view: GrinchView, interval: float = 0.6):
    frames = [
        "🙂",
        "🙂 🎁",
        "🙂 🎁🎁",
        "🙂 🎁🎁🎁",
        "🙂 🎁🎁🎁🎉",
    ]
    idx = 0
    try:
        while True:
            if view.result is not None:
                return
            animation_line = f"**Presents:** {frames[idx % len(frames)]}"
            new_embed = make_game_embed(animation_line=animation_line)
            try:
                await message.edit(embed=new_embed, view=view)
            except Exception:
                return
            idx += 1
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        return

# ---------- Central runner ----------
async def start_grinch_sim_in_channel(channel: discord.abc.Messageable, invoked_by: discord.Member | None = None):
    channel_id = getattr(channel, "id", None)
    if channel_id is None:
        print("[GrinchSim] channel has no id; aborting.")
        return

    if active_games.get(channel_id):
        print(f"[GrinchSim] Game already active in channel {channel_id}; skipping.")
        return

    active_games[channel_id] = True
    print(f"[GrinchSim] Starting game in channel {channel_id} (invoked_by={getattr(invoked_by,'id',None)})")
    try:
        view = GrinchView(timeout=5.0)
        initial_embed = make_game_embed(animation_line="**Presents:** 🙂")
        message = await channel.send(embed=initial_embed, view=view)
        view._message = message

        animation_task = asyncio.create_task(run_presents_animation(message, view, interval=0.6))
        await view.wait()

        if not animation_task.done():
            animation_task.cancel()
            try:
                await animation_task
            except asyncio.CancelledError:
                pass

        # Announce who won (if known)
        if view.result == "stopped" and getattr(view, "winner_user", None):
            try:
                await channel.send(f"🎉 {view.winner_user.mention} stopped the Grinch and saved Christmas!")
            except Exception:
                pass
        else:
            try:
                await channel.send("The Grinch escaped... better luck next time. 😈")
            except Exception:
                pass

    except Exception as e:
        print("[GrinchSim] Exception in start_grinch_sim_in_channel:")
        traceback.print_exc()
    finally:
        # short cooldown to avoid immediate retriggers if needed (optional)
        active_games[channel_id] = False
        # Small sleep avoids instant re-trigger if many messages arrive
        await asyncio.sleep(0.1)

# ---------- on_message with debug prints ----------
@bot.event
async def on_message(message: discord.Message):
    try:
        print(f"[on_message] {message.author} in {getattr(message.channel,'name',message.channel)}: {message.content!r}")

        # ignore bot messages
        if message.author.bot:
            print("[on_message] message from bot — ignoring")
            return

        # allow commands still
        if message.content.startswith(BOT_PREFIX):
            print("[on_message] detected command prefix — letting command handler process it")
            await bot.process_commands(message)
            return

        # only in guilds (if you want DM triggering remove this)
        if message.guild is None:
            print("[on_message] DM message — ignoring for auto-trigger")
            await bot.process_commands(message)
            return

        # Check active window
        if not is_christmas_active():
            print("[on_message] not in active Christmas window — skipping auto-trigger")
            await bot.process_commands(message)
            return

        # Check bot permissions to send messages in channel (best-effort)
        try:
            me = message.guild.me or await message.guild.fetch_member(bot.user.id)
            perms = message.channel.permissions_for(me)
            if not perms.send_messages:
                print("[on_message] bot lacks send_messages permission in this channel — aborting auto-trigger")
                await bot.process_commands(message)
                return
        except Exception:
            # If fetching member/perms fails, keep going — will show error in start
            pass

        # Start game in background so we don't block the event loop
        # This returns immediately; start_grinch_sim_in_channel will handle active_games checks
        asyncio.create_task(start_grinch_sim_in_channel(message.channel, invoked_by=message.author))

    except Exception:
        print("[on_message] Unexpected error:")
        traceback.print_exc()
    finally:
        # Always let the command processor run (so commands still work)
        try:
            await bot.process_commands(message)
        except Exception:
            pass

# ---------- Command fallback ----------
@bot.command(name=COMMAND_NAME)
async def merrychristmas(ctx: commands.Context):
    try:
        if not is_christmas_active():
            now = now_in_ist()
            formatted = now.strftime("%Y-%m-%d %H:%M %Z") if hasattr(now, "tzname") else now.strftime("%Y-%m-%d %H:%M")
            return await ctx.reply(
                f"Sorry — the **{COMMAND_NAME}** command is available from "
                f"Dec {ACTIVE_START_DAY} through Dec {ACTIVE_END_DAY} (IST). "
                f"Current date/time ({TIMEZONE_NAME}): {formatted}."
            )
        await start_grinch_sim_in_channel(ctx.channel, invoked_by=ctx.author)
    except Exception as e:
        await ctx.reply(f"An unexpected error occurred: `{e}`")

@bot.command(name="christmashelp")
async def christmas_help(ctx: commands.Context):
    text = (
        "🎄 **merrychristmas** command\n"
        f"Use `{BOT_PREFIX}{COMMAND_NAME}` to start the 5-second Grinch Sim (Dec 1–25 IST).\n"
        "The bot also automatically starts the Grinch Sim when someone chats in a channel (first person to click the button wins).\n"
    )
    await ctx.send(text)





MASTER_ID = 814791086114865233  # make sure this is an int, no quotes

# ============================================
# FIXED AUTOMOD CONFIGURATION
# ============================================

# Static configuration (hardcoded for specific guilds)
# Add your guild ID here if you want automod always enabled
AUTOMOD_ENABLED_GUILDS = {
    1210475350119813120: True,
    1397218218535424090: True,
    1411425019434766499: True,
    1341485158129205278: True,
    # Add your guild ID below:
    # YOUR_GUILD_ID: True,
}

# Users exempt from auto-moderation
AUTOMOD_EXEMPT_USERS = [
    814791086114865233,
    1085236492571529287,
    948973975353057341,
    1343933090191376446,
    1418946895816167475,
    1414168461172539454,
    827552324389175297,
    1187981682280775733,
]

# Built-in N-word variations (always active when automod is enabled)
BUILTIN_NWORD_VARIATIONS = [
    'nigger', 'nigga', 'n1gger', 'n1gga', 'nig ger', 'nig ga',
    'n-word', 'nword', 'n word', 'nigg3r', 'nigg4', 'n!gger',
    '!gga', 'niqqer', 'niqqa', 'niggеr', 'niggа'
]


def get_combined_automod_enabled(guild_id):
    """
    Check if automod is enabled for a guild
    Priority: API > Hardcoded config
    """
    guild_id_int = int(guild_id)

    # Check API first (priority)
    api_enabled = get_automod_enabled_status(guild_id_int)

    # Check hardcoded config
    hardcoded_enabled = AUTOMOD_ENABLED_GUILDS.get(guild_id_int, False)

    # Return True if EITHER is enabled (OR logic)
    return api_enabled or hardcoded_enabled


def get_combined_exempt_users(guild_id):
    """
    Get all exempt users for a guild
    Combines hardcoded + API exempt users
    """
    # Get API allowed users
    api_exempt = get_allowed_users_list(str(guild_id))
    api_exempt_ids = [int(user_id) for user_id in api_exempt]

    # Merge with hardcoded (no duplicates)
    combined = list(set(AUTOMOD_EXEMPT_USERS + api_exempt_ids))
    return combined


def is_user_moderator(user_id, guild_id):
    """
    Check if a user is a moderator (exempt user or has permissions)
    """
    # Check if user is in exempt list
    exempt_users = get_combined_exempt_users(guild_id)
    return int(user_id) in exempt_users or int(user_id) == MASTER_ID


# ============================================
# FIXED AUTO-MODERATION EVENT HANDLER
# ============================================

@bot.event
async def on_message(message):
    """Enhanced message handler with API-integrated automod"""

    # Don't moderate bots or DMs
    if message.author.bot or message.guild is None:
        await bot.process_commands(message)
        return

    guild_id = int(message.guild.id)
    author_id = int(message.author.id)

    # ===== CHECK IF AUTOMOD IS ENABLED (API + Hardcoded) =====
    automod_enabled = get_combined_automod_enabled(guild_id)

    if not automod_enabled:
        await bot.process_commands(message)
        return

    # ===== GET COMBINED EXEMPT USERS (API + Hardcoded) =====
    all_exempt_users = get_combined_exempt_users(guild_id)

    # Don't timeout exempt users
    if author_id in all_exempt_users:
        await bot.process_commands(message)
        return

    # ===== COMBINED AUTOMOD CHECK (Built-in + API) =====
    # Get API-configured banned words for this guild
    api_banned_words = get_automod_words(str(guild_id))

    # Combine built-in N-word variations with API words
    all_banned_words = BUILTIN_NWORD_VARIATIONS + api_banned_words

    # Prepare message content for checking
    message_content_lower = message.content.lower()

    # Remove common separators for evasion detection
    message_content_clean = message_content_lower.replace(' ', '').replace('-', '').replace('_', '').replace('.',
                                                                                                             '').replace(
        '*', '')

    detected_word = None
    is_nword = False
    is_custom = False

    # Check for violations
    for word in all_banned_words:
        word_lower = word.lower()
        clean_word = word_lower.replace(' ', '').replace('-', '').replace('_', '').replace('.', '').replace('*', '')

        # Check both original and cleaned versions
        if word_lower in message_content_lower or clean_word in message_content_clean:
            detected_word = word
            is_nword = word in BUILTIN_NWORD_VARIATIONS
            is_custom = word in api_banned_words
            break

    if detected_word:
        try:
            # Delete the message first
            await message.delete()
            print(f"[AUTO-MOD] Deleted message from {message.author.name} containing: {detected_word}")

            # Timeout the user for 24 hours
            duration = timedelta(hours=24)
            await message.author.timeout(duration,
                                         reason=f"Auto-moderation: {'Built-in filter' if is_nword else 'Custom API filter'}")

            # Create embed for auto-timeout
            embed = discord.Embed(
                title="🚫 Auto-Moderation Activated",
                description=f"{message.author.mention} has been automatically sanctioned",
                color=0xff2b2b,
                timestamp=datetime.now()
            )
            embed.set_thumbnail(url=message.author.display_avatar.url)
            embed.add_field(name="👤 User", value=f"{message.author.name}", inline=True)
            embed.add_field(name="⏰ Duration", value="24 hours", inline=True)

            # Different violation type based on source
            if is_nword:
                embed.add_field(name="📝 Violation", value="Inappropriate language", inline=True)
                embed.add_field(name="🔍 Detection", value="Built-in N-word filter", inline=True)
            elif is_custom:
                embed.add_field(name="📝 Violation", value="Custom banned word", inline=True)
                embed.add_field(name="🔍 Detection", value="API Custom Filter", inline=True)
            else:
                embed.add_field(name="📝 Violation", value="Banned word usage", inline=True)
                embed.add_field(name="🔍 Detection", value="Auto-moderation", inline=True)

            # Calculate when timeout ends
            end_time = datetime.now() + duration
            embed.add_field(name="🔚 Ends At", value=f"<t:{int(end_time.timestamp())}:F>", inline=True)
            embed.add_field(name="📍 Channel", value=f"{message.channel.mention}", inline=True)
            embed.add_field(name="🤖 System", value="Auto-Moderation", inline=True)

            embed.set_footer(text=f"User ID: {message.author.id} | Message auto-deleted")

            # Send the embed
            await message.channel.send(embed=embed)

            filter_type = "N-word" if is_nword else ("Custom API" if is_custom else "Unknown")
            print(
                f"[AUTO-MOD] ✅ User {message.author.name} ({message.author.id}) timed out in {message.guild.name} - {filter_type}: {detected_word}")

        except discord.Forbidden:
            warning_embed = discord.Embed(
                title="⚠️ Auto-Moderation Alert",
                description=f"{message.author.mention} used prohibited content, but I lack timeout permissions.",
                color=0xff9900,
                timestamp=datetime.now()
            )
            warning_embed.set_thumbnail(url=message.author.display_avatar.url)
            warning_embed.add_field(name="⚡ Action Needed", value="Manual moderation required", inline=False)
            warning_embed.add_field(name="🔍 Detected",
                                    value=f"{'Built-in filter' if is_nword else 'Custom API filter'}", inline=True)
            warning_embed.add_field(name="📍 Channel", value=f"{message.channel.mention}", inline=True)
            await message.channel.send(embed=warning_embed)
            print(f"[AUTO-MOD] ⚠️ Missing permissions to timeout {message.author.name}")

        except Exception as e:
            print(f"[AUTO-MOD ERROR] Failed to moderate {message.author.name}: {e}")
            try:
                if not message.flags.ephemeral:
                    await message.delete()
            except:
                pass

        # Don't process commands if automod triggered
        return

    # ===== DYNAMIC COMMAND CHECK (from API) =====
    content = message.content.lower()

    if content.startswith('!'):
        command_name = content[1:].split()[0].lower()
        guild_commands = get_guild_commands(str(guild_id))

        if command_name in guild_commands:
            cmd_data = guild_commands[command_name]

            embed = discord.Embed(
                title=f"**{command_name.title()}**",
                description=cmd_data.get('description', f"Here is your {command_name}!"),
                color=discord.Color.blurple()
            )

            # Check if response is a URL (for image commands)
            response_text = cmd_data.get('response', '')
            if response_text.startswith('http'):
                embed.set_image(url=response_text)
            else:
                embed.add_field(name="Response", value=response_text, inline=False)

            embed.set_footer(text=f"Custom command • {message.guild.name}")

            await message.channel.send(embed=embed)
            return

    # Process normal commands
    await bot.process_commands(message)


# ============================================
# DEBUG COMMAND TO TEST AUTOMOD
# ============================================

@bot.command(name="testfilter")
async def test_filter(ctx, *, test_word: str = None):
    """
    Test if a word would trigger automod (Master only)
    Usage: !testfilter word
    """
    if ctx.author.id != MASTER_ID:
        return await ctx.send("❌ Master only command")

    if not test_word:
        return await ctx.send("❌ Please provide a word to test!\nUsage: `!testfilter word`")

    guild_id = ctx.guild.id

    # Check if automod is enabled
    automod_enabled = get_combined_automod_enabled(guild_id)

    # Get all banned words
    api_banned_words = get_automod_words(str(guild_id))
    all_banned_words = BUILTIN_NWORD_VARIATIONS + api_banned_words

    # Test the word
    test_word_lower = test_word.lower()
    test_word_clean = test_word_lower.replace(' ', '').replace('-', '').replace('_', '').replace('.', '').replace('*',
                                                                                                                  '')

    detected = False
    matched_word = None
    is_builtin = False
    is_api = False

    for word in all_banned_words:
        word_lower = word.lower()
        clean_word = word_lower.replace(' ', '').replace('-', '').replace('_', '').replace('.', '').replace('*', '')

        if word_lower in test_word_lower or clean_word in test_word_clean:
            detected = True
            matched_word = word
            is_builtin = word in BUILTIN_NWORD_VARIATIONS
            is_api = word in api_banned_words
            break

    # Create result embed
    embed = discord.Embed(
        title="🧪 Automod Filter Test",
        description=f"Testing word: `{test_word}`",
        color=0xff0000 if detected else 0x00ff00
    )

    embed.add_field(
        name="📊 Automod Status",
        value=f"{'🟢 Enabled' if automod_enabled else '🔴 Disabled'}",
        inline=True
    )

    embed.add_field(
        name="🔍 Detection Result",
        value=f"{'❌ WOULD TRIGGER' if detected else '✅ Safe'}",
        inline=True
    )

    if detected:
        filter_type = []
        if is_builtin:
            filter_type.append("Built-in N-word filter")
        if is_api:
            filter_type.append("Custom API filter")

        embed.add_field(
            name="⚠️ Matched Word",
            value=f"`{matched_word}`",
            inline=False
        )

        embed.add_field(
            name="🔍 Filter Type",
            value=" + ".join(filter_type),
            inline=False
        )

        if automod_enabled:
            embed.add_field(
                name="⚡ What Would Happen",
                value="• Message deleted immediately\n• User timed out for 24 hours\n• Notification sent to channel",
                inline=False
            )
        else:
            embed.add_field(
                name="ℹ️ Note",
                value="Automod is currently DISABLED, so this would not trigger any action.",
                inline=False
            )
    else:
        embed.add_field(
            name="✅ Result",
            value="This word would NOT trigger automod filters.",
            inline=False
        )

    # Show filter statistics
    embed.add_field(
        name="📊 Filter Statistics",
        value=f"**Built-in words:** {len(BUILTIN_NWORD_VARIATIONS)}\n**Custom API words:** {len(api_banned_words)}\n**Total filters:** {len(all_banned_words)}",
        inline=False
    )

    embed.set_footer(text="This is a safe test - no action will be taken")

    await ctx.send(embed=embed)


@bot.command(name="listfilters")
async def list_filters(ctx):
    """
    List all active automod filters (Master only)
    Usage: !listfilters
    """
    if ctx.author.id != MASTER_ID:
        return await ctx.send("❌ Master only command")

    guild_id = ctx.guild.id

    # Check if automod is enabled
    automod_enabled = get_combined_automod_enabled(guild_id)

    # Get filters
    api_words = get_automod_words(str(guild_id))
    builtin_count = len(BUILTIN_NWORD_VARIATIONS)

    embed = discord.Embed(
        title="🔍 Active Automod Filters",
        description=f"Configuration for **{ctx.guild.name}**",
        color=0x00ff00 if automod_enabled else 0xff6b6b
    )

    embed.add_field(
        name="📊 Status",
        value=f"{'🟢 ACTIVE' if automod_enabled else '🔴 DISABLED'}",
        inline=True
    )

    embed.add_field(
        name="🛡️ Built-in Filter",
        value=f"{builtin_count} N-word variations",
        inline=True
    )

    embed.add_field(
        name="🌐 Custom API Words",
        value=f"{len(api_words)} configured",
        inline=True
    )

    # Show built-in filter (don't list actual words)
    embed.add_field(
        name="🛡️ Built-in N-word Filter",
        value=f"✅ Active ({builtin_count} variations)\n*Words not shown for safety*",
        inline=False
    )

    # Show custom API words
    if api_words:
        words_preview = api_words[:10]
        words_text = "• " + "\n• ".join(f"`{word}`" for word in words_preview)
        if len(api_words) > 10:
            words_text += f"\n... and {len(api_words) - 10} more"

        embed.add_field(
            name="🌐 Custom API Words",
            value=words_text,
            inline=False
        )
    else:
        embed.add_field(
            name="🌐 Custom API Words",
            value="*No custom words configured*",
            inline=False
        )

    embed.add_field(
        name="💡 Commands",
        value="`!testfilter word` - Test a specific word\n`!enableautomod` - Enable automod\n`!automod status` - Full status",
        inline=False
    )

    embed.set_footer(text="Filters apply to all non-exempt users")

    await ctx.send(embed=embed)
# ============================================
# MODERATION COMMANDS (For Exempt Users)
# ============================================

@bot.command(name="timeout")
@commands.has_permissions(moderate_members=True)
async def timeout_user(ctx, member: discord.Member, duration: str, *, reason: str = "No reason provided"):
    """
    Timeout a user (Moderators/Exempt users only)
    Usage: !timeout @user 1h Reason
           !timeout @user 30m Spamming
           !timeout @user 1d Inappropriate behavior

    Duration formats: 1m, 30m, 1h, 12h, 1d, 7d
    """
    # Check if user is moderator/exempt
    if not is_user_moderator(ctx.author.id, ctx.guild.id):
        if not ctx.author.guild_permissions.moderate_members:
            return await ctx.send("❌ You don't have permission to use this command!")

    # Parse duration
    duration_mapping = {
        'm': 60,  # minutes
        'h': 3600,  # hours
        'd': 86400  # days
    }

    try:
        time_value = int(duration[:-1])
        time_unit = duration[-1].lower()

        if time_unit not in duration_mapping:
            return await ctx.send("❌ Invalid duration format! Use: 1m, 1h, or 1d")

        seconds = time_value * duration_mapping[time_unit]
        timeout_duration = timedelta(seconds=seconds)

        # Discord max timeout is 28 days
        if seconds > 2419200:  # 28 days in seconds
            return await ctx.send("❌ Maximum timeout duration is 28 days!")

    except (ValueError, IndexError):
        return await ctx.send("❌ Invalid duration format! Use: 1m, 30m, 1h, 12h, 1d, 7d")

    # Check if trying to timeout bot owner or moderators
    if member.id == ctx.guild.owner_id:
        return await ctx.send("❌ Cannot timeout the server owner!")

    if member.id == MASTER_ID:
        return await ctx.send("❌ Cannot timeout the bot master!")

    if is_user_moderator(member.id, ctx.guild.id):
        return await ctx.send("❌ Cannot timeout other moderators!")

    # Check hierarchy
    if member.top_role >= ctx.author.top_role:
        return await ctx.send("❌ You cannot timeout someone with equal or higher roles!")

    try:
        await member.timeout(timeout_duration, reason=f"{reason} (by {ctx.author.name})")

        # Create embed
        end_time = datetime.now() + timeout_duration
        embed = discord.Embed(
            title="⏰ User Timed Out",
            description=f"{member.mention} has been timed out",
            color=0xff9900,
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="👤 User", value=f"{member.name}#{member.discriminator}", inline=True)
        embed.add_field(name="⏱️ Duration", value=duration, inline=True)
        embed.add_field(name="👮 Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="📝 Reason", value=reason, inline=False)
        embed.add_field(name="🔚 Ends At", value=f"<t:{int(end_time.timestamp())}:F>", inline=False)
        embed.set_footer(text=f"User ID: {member.id}")

        await ctx.send(embed=embed)

        # Try to DM the user
        try:
            dm_embed = discord.Embed(
                title=f"⏰ You've been timed out in {ctx.guild.name}",
                description=f"**Duration:** {duration}\n**Reason:** {reason}",
                color=0xff9900
            )
            dm_embed.add_field(name="⏰ Timeout Ends", value=f"<t:{int(end_time.timestamp())}:R>", inline=False)
            dm_embed.set_footer(text="Please follow server rules to avoid future timeouts")
            await member.send(embed=dm_embed)
        except:
            pass  # User has DMs disabled

        print(f"[TIMEOUT] {member.name} timed out for {duration} by {ctx.author.name} in {ctx.guild.name}")

    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to timeout this user!")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")


@bot.command(name="untimeout")
@commands.has_permissions(moderate_members=True)
async def untimeout_user(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """
    Remove timeout from a user (Moderators/Exempt users only)
    Usage: !untimeout @user Reason
    """
    # Check if user is moderator/exempt
    if not is_user_moderator(ctx.author.id, ctx.guild.id):
        if not ctx.author.guild_permissions.moderate_members:
            return await ctx.send("❌ You don't have permission to use this command!")

    try:
        if not member.timed_out:
            return await ctx.send(f"❌ {member.mention} is not timed out!")

        await member.timeout(None, reason=f"{reason} (by {ctx.author.name})")

        embed = discord.Embed(
            title="✅ Timeout Removed",
            description=f"{member.mention}'s timeout has been removed",
            color=0x00ff00,
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="👤 User", value=f"{member.name}#{member.discriminator}", inline=True)
        embed.add_field(name="👮 Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="📝 Reason", value=reason, inline=False)
        embed.set_footer(text=f"User ID: {member.id}")

        await ctx.send(embed=embed)

        # Try to DM the user
        try:
            dm_embed = discord.Embed(
                title=f"✅ Your timeout has been removed in {ctx.guild.name}",
                description=f"**Reason:** {reason}",
                color=0x00ff00
            )
            dm_embed.set_footer(text="Remember to follow server rules")
            await member.send(embed=dm_embed)
        except:
            pass

        print(f"[UNTIMEOUT] {member.name} untimeouted by {ctx.author.name} in {ctx.guild.name}")

    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to remove timeout from this user!")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")


@bot.command(name="warn")
async def warn_user(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """
    Warn a user (Moderators/Exempt users only)
    Usage: !warn @user Reason
    """
    # Check if user is moderator/exempt
    if not is_user_moderator(ctx.author.id, ctx.guild.id):
        if not ctx.author.guild_permissions.moderate_members:
            return await ctx.send("❌ You don't have permission to use this command!")

    if member.id == MASTER_ID:
        return await ctx.send("❌ Cannot warn the bot master!")

    if member.id == ctx.guild.owner_id:
        return await ctx.send("❌ Cannot warn the server owner!")

    embed = discord.Embed(
        title="⚠️ User Warned",
        description=f"{member.mention} has been warned",
        color=0xffaa00,
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="👤 User", value=f"{member.name}#{member.discriminator}", inline=True)
    embed.add_field(name="👮 Moderator", value=ctx.author.mention, inline=True)
    embed.add_field(name="📝 Reason", value=reason, inline=False)
    embed.set_footer(text=f"User ID: {member.id}")

    await ctx.send(embed=embed)

    # Try to DM the user
    try:
        dm_embed = discord.Embed(
            title=f"⚠️ You've been warned in {ctx.guild.name}",
            description=f"**Reason:** {reason}",
            color=0xffaa00
        )
        dm_embed.set_footer(text="Please follow server rules to avoid further action")
        await member.send(embed=dm_embed)
        await ctx.send(f"✅ {member.mention} has been notified via DM")
    except:
        await ctx.send("⚠️ Could not DM user (DMs disabled)")

    print(f"[WARN] {member.name} warned by {ctx.author.name} in {ctx.guild.name}: {reason}")


@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick_user(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """
    Kick a user from the server (Moderators/Exempt users only)
    Usage: !kick @user Reason
    """
    # Check if user is moderator/exempt
    if not is_user_moderator(ctx.author.id, ctx.guild.id):
        if not ctx.author.guild_permissions.kick_members:
            return await ctx.send("❌ You don't have permission to use this command!")

    if member.id == ctx.guild.owner_id:
        return await ctx.send("❌ Cannot kick the server owner!")

    if member.id == MASTER_ID:
        return await ctx.send("❌ Cannot kick the bot master!")

    if is_user_moderator(member.id, ctx.guild.id):
        return await ctx.send("❌ Cannot kick other moderators!")

    if member.top_role >= ctx.author.top_role:
        return await ctx.send("❌ You cannot kick someone with equal or higher roles!")

    try:
        # Try to DM before kicking
        try:
            dm_embed = discord.Embed(
                title=f"👢 You've been kicked from {ctx.guild.name}",
                description=f"**Reason:** {reason}",
                color=0xff0000
            )
            dm_embed.set_footer(text="You can rejoin with a valid invite link")
            await member.send(embed=dm_embed)
        except:
            pass

        await member.kick(reason=f"{reason} (by {ctx.author.name})")

        embed = discord.Embed(
            title="👢 User Kicked",
            description=f"{member.mention} has been kicked from the server",
            color=0xff0000,
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="👤 User", value=f"{member.name}#{member.discriminator}", inline=True)
        embed.add_field(name="👮 Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="📝 Reason", value=reason, inline=False)
        embed.set_footer(text=f"User ID: {member.id}")

        await ctx.send(embed=embed)
        print(f"[KICK] {member.name} kicked by {ctx.author.name} in {ctx.guild.name}")

    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to kick this user!")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")


@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban_user(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """
    Ban a user from the server (Moderators/Exempt users only)
    Usage: !ban @user Reason
    """
    # Check if user is moderator/exempt
    if not is_user_moderator(ctx.author.id, ctx.guild.id):
        if not ctx.author.guild_permissions.ban_members:
            return await ctx.send("❌ You don't have permission to use this command!")

    if member.id == ctx.guild.owner_id:
        return await ctx.send("❌ Cannot ban the server owner!")

    if member.id == MASTER_ID:
        return await ctx.send("❌ Cannot ban the bot master!")

    if is_user_moderator(member.id, ctx.guild.id):
        return await ctx.send("❌ Cannot ban other moderators!")

    if member.top_role >= ctx.author.top_role:
        return await ctx.send("❌ You cannot ban someone with equal or higher roles!")

    try:
        # Try to DM before banning
        try:
            dm_embed = discord.Embed(
                title=f"🔨 You've been banned from {ctx.guild.name}",
                description=f"**Reason:** {reason}",
                color=0x000000
            )
            dm_embed.set_footer(text="Contact server moderators to appeal")
            await member.send(embed=dm_embed)
        except:
            pass

        await member.ban(reason=f"{reason} (by {ctx.author.name})", delete_message_days=1)

        embed = discord.Embed(
            title="🔨 User Banned",
            description=f"{member.mention} has been banned from the server",
            color=0x000000,
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="👤 User", value=f"{member.name}#{member.discriminator}", inline=True)
        embed.add_field(name="👮 Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="📝 Reason", value=reason, inline=False)
        embed.set_footer(text=f"User ID: {member.id}")

        await ctx.send(embed=embed)
        print(f"[BAN] {member.name} banned by {ctx.author.name} in {ctx.guild.name}")

    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to ban this user!")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")


@bot.command(name="purge")
@commands.has_permissions(manage_messages=True)
async def purge_messages(ctx, amount: int, member: discord.Member = None):
    """
    Delete messages (Moderators/Exempt users only)
    Usage: !purge 10 - Delete last 10 messages
           !purge 50 @user - Delete last 50 messages from specific user
    """
    # Check if user is moderator/exempt
    if not is_user_moderator(ctx.author.id, ctx.guild.id):
        if not ctx.author.guild_permissions.manage_messages:
            return await ctx.send("❌ You don't have permission to use this command!")

    if amount < 1:
        return await ctx.send("❌ Amount must be at least 1!")

    if amount > 100:
        return await ctx.send("❌ Cannot delete more than 100 messages at once!")

    try:
        # Delete command message first
        await ctx.message.delete()

        if member:
            # Delete messages from specific user
            deleted = await ctx.channel.purge(limit=amount, check=lambda m: m.author == member)
            msg = await ctx.send(f"✅ Deleted {len(deleted)} messages from {member.mention}")
        else:
            # Delete any messages
            deleted = await ctx.channel.purge(limit=amount)
            msg = await ctx.send(f"✅ Deleted {len(deleted)} messages")

        # Auto-delete confirmation after 5 seconds
        await asyncio.sleep(5)
        await msg.delete()

        print(f"[PURGE] {len(deleted)} messages deleted by {ctx.author.name} in {ctx.guild.name}")

    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to delete messages!")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")


@bot.command(name="slowmode")
@commands.has_permissions(manage_channels=True)
async def set_slowmode(ctx, seconds: int = 0):
    """
    Set slowmode for current channel (Moderators/Exempt users only)
    Usage: !slowmode 5 - Set 5 second slowmode
           !slowmode 0 - Disable slowmode
    """
    # Check if user is moderator/exempt
    if not is_user_moderator(ctx.author.id, ctx.guild.id):
        if not ctx.author.guild_permissions.manage_channels:
            return await ctx.send("❌ You don't have permission to use this command!")

    if seconds < 0:
        return await ctx.send("❌ Slowmode must be 0 or positive!")

    if seconds > 21600:  # Max 6 hours
        return await ctx.send("❌ Maximum slowmode is 21600 seconds (6 hours)!")

    try:
        await ctx.channel.edit(slowmode_delay=seconds)

        if seconds == 0:
            embed = discord.Embed(
                title="🚫 Slowmode Disabled",
                description=f"Slowmode has been disabled in {ctx.channel.mention}",
                color=0x00ff00
            )
        else:
            embed = discord.Embed(
                title="⏱️ Slowmode Enabled",
                description=f"Slowmode set to **{seconds} seconds** in {ctx.channel.mention}",
                color=0x3498db
            )

        embed.add_field(name="👮 Moderator", value=ctx.author.mention, inline=True)
        embed.set_footer(text=f"Channel ID: {ctx.channel.id}")

        await ctx.send(embed=embed)
        print(f"[SLOWMODE] Set to {seconds}s by {ctx.author.name} in {ctx.channel.name}")

    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to manage this channel!")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")


# ============================================
# MODERATION INFO COMMANDS
# ============================================

@bot.command(name="modhelp")
async def mod_help(ctx):
    """
    Show all moderation commands
    Usage: !modhelp
    """
    embed = discord.Embed(
        title="🛡️ Moderation Commands",
        description="Available commands for moderators and exempt users",
        color=0x3498db
    )

    embed.add_field(
        name="⏰ Timeout Management",
        value=(
            "`!timeout @user 1h reason` - Timeout user\n"
            "`!untimeout @user reason` - Remove timeout\n"
            "Duration formats: 1m, 30m, 1h, 12h, 1d, 7d"
        ),
        inline=False
    )

    embed.add_field(
        name="⚠️ Warnings & Actions",
        value=(
            "`!warn @user reason` - Warn a user\n"
            "`!kick @user reason` - Kick from server\n"
            "`!ban @user reason` - Ban from server"
        ),
        inline=False
    )

    embed.add_field(
        name="🧹 Channel Management",
        value=(
            "`!purge 10` - Delete 10 messages\n"
            "`!purge 50 @user` - Delete 50 from user\n"
            "`!slowmode 5` - Set 5s slowmode\n"
            "`!slowmode 0` - Disable slowmode"
        ),
        inline=False
    )

    embed.add_field(
        name="📊 Automod Commands",
        value=(
            "`!automod status` - View automod status\n"
            "`!enableautomod` - Enable automod\n"
            "`!automod_exempt list` - View exempt users"
        ),
        inline=False
    )

    embed.set_footer(text="Only moderators and exempt users can use these commands")

    await ctx.send(embed=embed)


# ============================================
# ENHANCED AUTOMOD STATUS COMMAND
# ============================================

@bot.command(name="automod")
async def manage_automod(ctx, action: str = None, server_id: int = None):
    """
    Manage auto-moderation settings
    Usage:
        !automod status - Show current status
        !automod enable - Enable for current server (adds to hardcoded config)
        !automod disable - Disable for current server
    """
    if ctx.guild is None:
        return await ctx.send("❌ This command must be used in a server.")

    author_id = int(ctx.author.id)
    current_guild_id = int(ctx.guild.id)

    # Only master can manage automod
    if author_id != MASTER_ID:
        error_embed = discord.Embed(
            title="❌ Access Denied",
            description="Only the master user can manage auto-moderation settings.",
            color=0xff0000
        )
        return await ctx.send(embed=error_embed)

    # Show current status
    if action is None or action.lower() == "status":
        target_guild = server_id if server_id else current_guild_id

        # Get status from both sources
        api_enabled = get_automod_enabled_status(target_guild)
        hardcoded_enabled = AUTOMOD_ENABLED_GUILDS.get(target_guild, False)
        combined_enabled = get_combined_automod_enabled(target_guild)

        # Get words and exempt users
        api_words = get_automod_words(str(target_guild))
        api_exempt = get_allowed_users_list(str(target_guild))
        all_exempt = get_combined_exempt_users(target_guild)

        status_embed = discord.Embed(
            title="🤖 Auto-Moderation Status",
            description=f"Configuration for **{ctx.guild.name}**",
            color=0x00ff00 if combined_enabled else 0xff6b6b
        )

        # Overall Status
        status_icon = "🟢" if combined_enabled else "🔴"
        status_text = "**ACTIVE**" if combined_enabled else "**DISABLED**"
        status_embed.add_field(
            name="📊 Overall Status",
            value=f"{status_icon} {status_text}",
            inline=False
        )

        # Configuration Sources
        sources = []
        if hardcoded_enabled:
            sources.append("✅ Hardcoded Config")
        else:
            sources.append("❌ Hardcoded Config")

        if api_enabled:
            sources.append("✅ API Enabled")
        else:
            sources.append("❌ API Enabled")

        status_embed.add_field(
            name="🔧 Configuration Sources",
            value="\n".join(sources),
            inline=True
        )

        status_embed.add_field(
            name="⏰ Timeout Duration",
            value="24 hours",
            inline=True
        )

        # Filter Details
        status_embed.add_field(
            name="🔍 Active Filters",
            value=(
                f"**Built-in N-word:** {len(BUILTIN_NWORD_VARIATIONS)} variations\n"
                f"**Custom API words:** {len(api_words)} configured\n"
                f"**Total:** {len(BUILTIN_NWORD_VARIATIONS) + len(api_words)} banned words"
            ),
            inline=False
        )

        # Exempt Users
        status_embed.add_field(
            name="🛡️ Protected Users",
            value=(
                f"**Hardcoded:** {len(AUTOMOD_EXEMPT_USERS)} users\n"
                f"**API:** {len(api_exempt)} users\n"
                f"**Total:** {len(all_exempt)} (no duplicates)"
            ),
            inline=False
        )

        # Show custom words preview if any
        if api_words:
            preview_words = api_words[:5]
            preview_text = "• " + "\n".join(f"`{word}`" for word in preview_words)
            if len(api_words) > 5:
                preview_text += f"\n... and {len(api_words) - 5} more"
            status_embed.add_field(
                name="📝 Custom API Words (Preview)",
                value=preview_text,
                inline=False
            )

        # Instructions
        if not combined_enabled:
            status_embed.add_field(
                name="🔧 How to Enable",
                value=(
                    "**Option 1 (Hardcoded):** Use `!automod enable` (instant)\n"
                    "**Option 2 (API):** Use the admin panel to enable automod\n"
                    "**Option 3 (API):** Add a custom word via API (auto-enables)\n\n"
                    f"**Your Guild ID:** `{target_guild}`"
                ),
                inline=False
            )

        status_embed.set_footer(text="API changes sync automatically • No restart needed")
        return await ctx.send(embed=status_embed)

    # Enable automod (adds to hardcoded config)
    elif action.lower() == "enable":
        AUTOMOD_ENABLED_GUILDS[current_guild_id] = True

        embed = discord.Embed(
            title="✅ Automod Enabled",
            description=f"Auto-moderation is now **ACTIVE** for {ctx.guild.name}",
            color=0x00ff00
        )
        embed.add_field(
            name="⚡ Changes Applied",
            value=(
                "• Added to hardcoded enabled guilds\n"
                "• Built-in N-word filter active\n"
                "• 24-hour timeout on violations\n"
                "• Takes effect immediately"
            ),
            inline=False
        )
        embed.add_field(
            name="📝 Note",
            value="This setting is stored in bot code. For persistent API-based config, use the admin panel.",
            inline=False
        )
        embed.set_footer(text=f"Guild ID: {current_guild_id}")

        print(f"[AUTOMOD] Enabled for guild {current_guild_id} ({ctx.guild.name})")
        return await ctx.send(embed=embed)

    # Disable automod
    elif action.lower() == "disable":
        if current_guild_id in AUTOMOD_ENABLED_GUILDS:
            del AUTOMOD_ENABLED_GUILDS[current_guild_id]

        # Note: This only disables hardcoded. If API is enabled, it will still be active
        api_enabled = get_automod_enabled_status(current_guild_id)

        embed = discord.Embed(
            title="⚠️ Automod Disabled (Hardcoded)",
            description=f"Hardcoded automod setting removed for {ctx.guild.name}",
            color=0xff9900
        )

        if api_enabled:
            embed.add_field(
                name="⚠️ Important",
                value="**API automod is still ENABLED** for this server.\nAutomod will remain active until you disable it via API.",
                inline=False
            )
        else:
            embed.add_field(
                name="✅ Status",
                value="Auto-moderation is now **DISABLED** for this server.",
                inline=False
            )

        embed.set_footer(text=f"Guild ID: {current_guild_id}")
        return await ctx.send(embed=embed)

    else:
        return await ctx.send(f"❌ Invalid action. Use: `!automod status`, `!automod enable`, or `!automod disable`")


@bot.command(name="enableautomod")
async def quick_enable_automod(ctx):
    """
    Quick command to enable automod for current server
    Usage: !enableautomod
    """
    if ctx.author.id != MASTER_ID:
        return await ctx.send("❌ Master only command")

    if not ctx.guild:
        return await ctx.send("❌ Use this command in a server")

    guild_id = ctx.guild.id
    AUTOMOD_ENABLED_GUILDS[guild_id] = True

    embed = discord.Embed(
        title="✅ Automod Enabled!",
        description=f"Auto-moderation is now active for **{ctx.guild.name}**",
        color=0x00ff00
    )
    embed.add_field(
        name="🔍 Active Filters",
        value=f"• Built-in N-word filter ({len(BUILTIN_NWORD_VARIATIONS)} variations)\n• 24-hour timeout\n• Instant activation",
        inline=False
    )
    embed.add_field(
        name="💡 Tip",
        value="Use `!automod status` to see detailed configuration",
        inline=False
    )

    await ctx.send(embed=embed)
    print(f"[AUTOMOD] Quick-enabled for {ctx.guild.name} ({guild_id})")


@bot.command(name="guildid")
async def get_guild_id(ctx):
    """
    Get the current guild ID (for configuration)
    Usage: !guildid
    """
    if not ctx.guild:
        return await ctx.send("❌ This command must be used in a server")

    embed = discord.Embed(
        title="🏠 Server Information",
        description=f"**{ctx.guild.name}**",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="🆔 Guild ID",
        value=f"`{ctx.guild.id}`",
        inline=False
    )
    embed.add_field(
        name="💡 Usage",
        value="Copy this ID to enable automod:\n```python\nAUTOMOD_ENABLED_GUILDS = {\n    " + str(
            ctx.guild.id) + ": True,\n}\n```",
        inline=False
    )

    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)

    await ctx.send(embed=embed)


# ============================================
# BOT READY EVENT - SET BOT INSTANCE IN API
# ============================================







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



@bot.command(name="smallboom")
async def gif(ctx):
    """Send an embed with a GIF."""
    embed = discord.Embed(
        title="**Small BOOM**",
        description="Here is your Small Boom!",
        color=discord.Color.blurple()
    )
    embed.set_image(url="https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExcHB2czYwcjYyYzhsMHZhN3R2aWpkb3pqZ2ltYnNyaXFsM2Z6Z2Y1cyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/5Ckdv9YS6XUH7A3Vya/giphy.gif")
    # Replace with any GIF URL

    await ctx.send(embed=embed)

@bot.command(name="wish")
async def gif(ctx):
    """Send an embed with a GIF."""
    embed = discord.Embed(
        title="**Shooting Stars**",
        description="Wish whatever you want!",
        color=discord.Color.blurple()
    )
    embed.set_image(url="https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExZ29tNmVkMHA5NXc3dzh5NHVzejYzbjB4Z3M0NWx5Y2YzOHNwMzZjcCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/afhd72IpCFMiqGKReK/giphy.gif")
    # Replace with any GIF URL

    await ctx.send(embed=embed)

@bot.command(name="mediumboom")
async def gif(ctx):
    """Send an embed with a GIF."""
    embed = discord.Embed(
        title="**Medium BOOM**",
        description="Here is your Medium Boom!",
        color=discord.Color.blurple()
    )
    embed.set_image(url="https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExcWx4eHNnNWUxMjZwNWVkNndxZHdtaHlpd2xkcG9oOThxOHVhaDRkcSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/UJUDgMjE92ZLA7768U/giphy.gif")
    # Replace with any GIF URL

    await ctx.send(embed=embed)

@bot.command(name="lightsaber")
async def gif(ctx):
    """Send an embed with a GIF."""
    embed = discord.Embed(
        title="**Light Saber**",
        description="Here comes your Light Saber its upside down but I think since I can you can manage it!",
        color=discord.Color.red()
    )
    embed.set_image(url="https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExdXprdG16ZXhpbzhqZnVnMHlhOTZ5eHFmYWNrNzVvb29sZmFxbDB0dyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/4mm9vEickH766HCp7u/giphy.gif")
    # Replace with any GIF URL

    await ctx.send(embed=embed)

@bot.command(name="lonely")
async def gif(ctx):
    """Send an embed with a GIF."""
    embed = discord.Embed(
        title="**Feeling lonely**",
        description="This dude is chilling in space kilometers away in some random dudes car!",
        color=discord.Color.yellow()
    )
    embed.set_image(url="https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExejM2OTh2dHB0bHQ4aDN3eW5qMTRsOGFmaGI5ZHZ1bGdjYmdiNDZjYyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/obLAwiCqhKD3rMKq31/giphy.gif")
    # Replace with any GIF URL

    await ctx.send(embed=embed)

@bot.command(name="rafshocked")
async def gif(ctx):
    """Send an embed with a GIF."""
    embed = discord.Embed(
        title="**RAF Shocked**",
        description="You shocked a Protogen!",
        color=discord.Color.from_rgb(128, 0, 0)
    )
    embed.set_image(url="https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExZnpmam1qOXdmb2Y0eDFja2wwaWt0cGRpNXV0NjRtbWppMWljZnRiaiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/CKu1S2EgBdNNLxD6hu/giphy.gif")
    # Replace with any GIF URL

    await ctx.send(embed=embed)
@bot.command(name="destructivecryo")
async def gif(ctx):
    """Send an embed with a GIF."""
    embed = discord.Embed(
        title="**Destructive Cryo**",
        description="Your vehicle didn't hold up to your expectations!",
        color=discord.Color.from_rgb(255, 255, 255)
    )
    embed.set_image(url="https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExbWxnODUybmFzNzUzaWxpaHo0Znc5dWF4a3lqOGlrMTAzZThsbHZ1NCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/23OBfFWEyJSYj6fvhY/giphy.gif")
    # Replace with any GIF URL

    await ctx.send(embed=embed)

# Replace with your developer's Discord user ID
DEV_USER_ID = 814791086114865233  # 🟩 put the actual ID here

class DevView(discord.ui.View):
    def __init__(self, dev_user):
        super().__init__(timeout=None)
        self.dev_user = dev_user

        # Button to open profile
        self.add_item(discord.ui.Button(
            label="🔗 View Profile",
            url=f"https://discord.com/users/{dev_user.id}"
        ))

        # Only one button for DM
        self.add_item(MessageDevButton(dev_user))

class MessageDevButton(discord.ui.Button):
    def __init__(self, dev_user):
        super().__init__(label="✉️ Message Dev", style=discord.ButtonStyle.primary)
        self.dev_user = dev_user

    async def callback(self, interaction: discord.Interaction):
        try:
            await self.dev_user.send(
                f"📩 **{interaction.user}** from **{interaction.guild.name}** wants to chat with you!"
            )
            await interaction.response.send_message(
                "✅ Message sent to the developer!", ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "⚠️ Could not DM the developer.", ephemeral=True
            )

@bot.command(name="dev")
async def dev(ctx):
    """
    Mention the developer with a super beautiful embed.
    Usage: !dev
    """
    # Get dev user
    dev_user = ctx.guild.get_member(DEV_USER_ID) or await bot.fetch_user(DEV_USER_ID)
    if dev_user is None:
        await ctx.send("⚠️ Developer not found.")
        return

    # 🎨 Build the embed
    embed = discord.Embed(
        title=f"✨ Meet Our Developer — {dev_user.display_name} ✨",
        description=f"👋 Say hi to our amazing developer: {dev_user.mention}",
        color=discord.Color.purple()
    )

    embed.set_image(url=dev_user.display_avatar.url)  # Big banner
    embed.set_thumbnail(url=dev_user.display_avatar.url)  # Thumbnail

    embed.set_author(
        name=f"{dev_user.display_name}",
        icon_url=dev_user.display_avatar.url,
        url=f"https://discord.com/users/{dev_user.id}"
    )

    embed.add_field(
        name="👨‍💻 About",
        value="💡 Creator of this awesome bot.\n🚀 Building cool features for you.",
        inline=False
    )
    embed.add_field(
        name="🎯 Contact",
        value="Use the buttons below to **view profile** or **message** the dev!",
        inline=False
    )

    embed.set_footer(
        text=f"Requested by {ctx.author.display_name}",
        icon_url=ctx.author.display_avatar.url
    )

    view = DevView(dev_user)
    await ctx.send(embed=embed, view=view)


class HelpView(discord.ui.View):
    """Interactive view for the help command with category buttons"""

    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot

    @discord.ui.button(label="🎮 Games", style=discord.ButtonStyle.primary, emoji="🎮")
    async def games_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.create_games_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🛠️ Utility", style=discord.ButtonStyle.secondary, emoji="🛠️")
    async def utility_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.create_utility_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🎭 Fun", style=discord.ButtonStyle.success, emoji="🎭")
    async def fun_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.create_fun_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="👑 Admin", style=discord.ButtonStyle.danger, emoji="👑")
    async def admin_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.create_admin_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🏠 Home", style=discord.ButtonStyle.gray, emoji="🏠")
    async def home_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    def create_main_embed(self):
        """Create the main help embed with comprehensive overview"""
        embed = discord.Embed(
            title="🚀 OLIT Bot - Mission Control Center",
            description=(
                "**Welcome to your comprehensive space-themed Discord bot!**\n\n"
                "I'm Launch Tower, your ultimate mission control companion. "
                "From epic space games to advanced server management, I've got everything covered!\n\n"
                "📊 **Bot Statistics:**\n"
                f"• Servers: {len(self.bot.guilds)}\n"
                f"• Users: {len(set(self.bot.get_all_members()))}\n"
                f"• Commands: 35+\n"
                f"• Games: 15+ Interactive experiences\n\n"
                "🎯 **Quick Start Guide:**\n"
                "Click the category buttons below to explore all features!"
            ),
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="🎮 Games & Entertainment",
            value=(
                "**15+ Interactive Games with Scoring!**\n"
                "• Space Trivia (3 difficulties)\n"
                "• Mechzilla Booster Catch Game\n"
                "• Rock Paper Scissors • Coin Flip\n"
                "• Word Unscramble • Math Quiz\n"
                "• Starship Mission Simulator\n"
                "• Rocket Design Challenge\n"
                "• Galaxy Exploration RPG"
            ),
            inline=True
        )

        embed.add_field(
            name="🛠️ Utility & Management",
            value=(
                "**Advanced Server Tools**\n"
                "• Performance Monitoring\n"
                "• Auto-Moderation System\n"
                "• Welcome Message System\n"
                "• Leader Role Assignment\n"
                "• Timeout Management\n"
                "• Global Leaderboards"
            ),
            inline=True
        )

        embed.add_field(
            name="🎭 Fun & Entertainment",
            value=(
                "**Space-Themed Content**\n"
                "• Animated GIFs Collection\n"
                "• Custom Emoji Reactions\n"
                "• Space Catchphrases\n"
                "• Mission Control Roleplay\n"
                "• Interactive UI Elements\n"
                "• Dynamic Visual Effects"
            ),
            inline=True
        )

        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(
            text="🌟 Over 35 commands | Made for space enthusiasts | Click buttons to explore!",
            icon_url=self.bot.user.display_avatar.url
        )

        return embed

    def create_games_embed(self):
        """Create comprehensive games category embed with ALL games"""
        embed = discord.Embed(
            title="🎮 Complete Games Collection - 15+ Interactive Experiences",
            description="**Master the cosmos with our comprehensive game suite! All games award points and contribute to server leaderboards.**",
            color=discord.Color.green()
        )

        embed.add_field(
            name="🎓 **Knowledge & Quiz Games**",
            value=(
                "`/trivia` or `!trivia`\n"
                "🌟 **Space Trivia Challenge** - Test your cosmic knowledge!\n"
                "• 🟩 Easy (1pt) • 🟨 Medium (2pts) • 🟥 Hard (3pts)\n"
                "• 60+ Questions across all difficulties\n"
                "• 30-second time limit per question\n\n"

                "`!mathquiz`\n"
                "🧮 **Mathematical Challenge** - Solve random equations!\n"
                "• Addition, subtraction, multiplication, division\n"
                "• Random number generation • 1 point per correct answer\n\n"

                "`!unscramble`\n"
                "🔤 **Word Unscramble Game** - Decode scrambled words!\n"
                "• Multiple difficulty levels • Space-themed vocabulary\n"
                "• 60-second time limit • Interactive UI buttons"
            ),
            inline=False
        )

        embed.add_field(
            name="🚀 **Space Mission Simulators**",
            value=(
                "`!starship`\n"
                "🚀 **Interactive Starship Predictor** - Mission success calculator!\n"
                "• Multiple choice mission parameters\n"
                "• Weather, vehicle condition, payload factors\n"
                "• Dynamic success probability with explanations\n\n"

                "`!predict [ship_name]`\n"
                "🎯 **Chat-Based Mission Simulation** - Complete testing sequence!\n"
                "• 6 different test scenarios • 20-second response time\n"
                "• Success/Partial/Failure options • Detailed scoring system\n\n"

                "`!mission`\n"
                "⚡ **Resource Management Game** - Manage fuel, food & research!\n"
                "• Launch, Refuel, Research actions • Interactive UI buttons\n"
                "• Survival mechanics • Progressive difficulty\n\n"

                "`!rocketdesign`\n"
                "🔧 **Rocket Design Challenge** - Build your perfect rocket!\n"
                "• Engine selection (Raptor/Merlin/Ion Drive)\n"
                "• Tank sizing • Payload configuration • Launch simulation"
            ),
            inline=False
        )

        embed.add_field(
            name="🎯 **Classic & Arcade Games**",
            value=(
                "`!rps`\n"
                "✂️ **Rock Paper Scissors** - Classic game with interactive buttons!\n"
                "• Beautiful UI • Instant results • Score tracking\n\n"

                "`!coinflip`\n"
                "🪙 **Coin Flip Challenge** - Heads or tails prediction!\n"
                "• Interactive button selection • 50/50 odds\n\n"

                "`!dice [guess] [sides]`\n"
                "🎲 **Dice Rolling Game** - Predict the roll!\n"
                "• Customizable dice sides • Optional guessing • Score points\n\n"

                "`!guess`\n"
                "🔢 **Number Guessing Game** - Predict numbers 1-10!\n"
                "• Modal input system • 15-second time limit\n\n"

                "`!catchbooster`\n"
                "🦾 **ULTIMATE: Mechzilla Booster Catch Game**\n"
                "• Advanced physics simulation • Real-time controls\n"
                "• Fuel management • Precision landing mechanics\n"
                "• Multiple scoring factors • Achievement system!"
            ),
            inline=False
        )

        embed.add_field(
            name="🌌 **Advanced RPG Systems**",
            value=(
                "`!galaxy` or `!explore`\n"
                "🌟 **Galaxy Exploration RPG** - Discover the universe!\n"
                "• 11x11 interactive galaxy map • Resource collection\n"
                "• Ship upgrades • Achievement system • Rare discoveries\n"
                "• Danger encounters • Credit economy • Exploration ranks\n\n"

                "**📊 Scoring & Progression:**\n"
                "All games contribute to your server leaderboard ranking!\n"
                "Top players automatically receive Leader roles!\n"
                "`!leaderboard` - View your server's top players"
            ),
            inline=False
        )

        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1234567890123456789.png")  # Replace with game icon
        embed.set_footer(
            text="🏆 Pro tip: Master all games to dominate the leaderboard! Points persist across sessions.")

        return embed

    def create_utility_embed(self):
        """Create the utility category embed with all management features"""
        embed = discord.Embed(
            title="🛠️ Advanced Utility & Server Management",
            description="**Professional-grade tools for server administration and performance monitoring**",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="📡 **Performance & Monitoring**",
            value=(
                "`/ping` or `!ping`\n"
                "🎯 **Advanced Latency Checker** - Multi-metric performance analysis\n"
                "• WebSocket latency • API response time • Processing latency\n"
                "• Beautiful embed display • Real-time timestamp\n"
                "• Both slash and prefix command support"
            ),
            inline=False
        )

        embed.add_field(
            name="📊 **Scoring & Leadership System**",
            value=(
                "`!leaderboard`\n"
                "🏆 **Interactive Leaderboard** - Server rankings with auto-roles!\n"
                "• Game score tracking • Server-specific statistics\n"
                "• Automatic Leader role assignment to top players\n"
                "• Player count and total points display\n"
                "• User avatar integration • Beautiful formatting\n\n"

                "`!role_mapping [list/add/remove] [server_id] [role_id]` *(Master only)*\n"
                "👑 **Leader Role Configuration** - Customize rewards per server\n"
                "• Server-specific role mappings • Automatic role updates\n"
                "• Permission validation • Status verification"
            ),
            inline=False
        )

        embed.add_field(
            name="🎉 **Welcome & Social Systems**",
            value=(
                "**🤖 Automatic Welcome Messages**\n"
                "• Beautiful embed welcomes with user avatars\n"
                "• Server member count tracking • Custom welcome channels\n"
                "• Automatic server detection • Personalized greetings\n"
                "*Configured per server - works automatically!*\n\n"

                "**🗑️ Content Filtering**\n"
                "• Automatic 'scrub' message deletion\n"
                "• Clean server maintenance • No configuration needed"
            ),
            inline=False
        )

        embed.add_field(
            name="🛡️ **Advanced Auto-Moderation**",
            value=(
                "`!automod [status/enable/disable] [server_id]` *(Master only)*\n"
                "🚨 **Intelligent Content Moderation** - Advanced protection system\n"
                "• Automatic inappropriate content detection\n"
                "• 24-hour timeout enforcement • Message deletion\n"
                "• Server-specific configuration • Multi-variation detection\n\n"

                "`!automod_exempt [add/remove/list] [user_id]` *(Master only)*\n"
                "⚪ **User Exemption Management** - Whitelist trusted users\n"
                "• Master user protection • Flexible exemption system\n"
                "• Easy user management • Status verification"
            ),
            inline=False
        )

        embed.add_field(
            name="⏰ **Advanced Timeout System**",
            value=(
                "`!timeout_users`\n"
                "👥 **Authorization Checker** - View timeout permissions per server\n"
                "• Server-specific user lists • Permission validation\n"
                "• User mention formatting • Access control verification"
            ),
            inline=False
        )

        embed.set_thumbnail(
            url="https://cdn.discordapp.com/emojis/1234567890123456789.png")  # Replace with utility icon
        embed.set_footer(text="⚙️ These tools ensure smooth server operation and enhanced user experience")

        return embed

    def create_fun_embed(self):
        """Create the fun category embed with all entertainment features"""
        embed = discord.Embed(
            title="🎭 Fun & Entertainment - Space-Themed Content",
            description="**Immersive space entertainment and social interaction features!**",
            color=discord.Color.gold()
        )

        embed.add_field(
            name="🚀 **Space Mission Control Roleplay**",
            value=(
                "`!hello` - 👋 Greet your Launch Tower companion\n"
                "`!catch` - 🛸 Learn about Booster 16's perfect recovery\n"
                "`!vent` - 💨 Experience Launch Tower venting sequence\n"
                "`!behero` - 🦸 Water tower catching challenge description\n"
                "*Perfect for space enthusiasts and SpaceX fans!*"
            ),
            inline=False
        )

        embed.add_field(
            name="💥 **Animated GIF Collection**",
            value=(
                "`!bigboom` - 🔥 **Epic explosion GIF** for dramatic moments\n"
                "`!mediumboom` - 💥 **Medium explosion** for regular celebrations\n"
                "`!smallboom` - ✨ **Small explosion** for minor events\n"
                "`!lonely` - 🚗 **Space car vibes** - Starman chilling in space\n"
                "`!wish` - 🌠 **Shooting stars** - Make a wish on cosmic beauty\n"
                "*Add visual flair to any conversation!*"
            ),
            inline=False
        )

        embed.add_field(
            name="😀 **Interactive Emoji Reaction System**",
            value=(
                "**🎯 Text Triggers** *(type these in chat)*:\n"
                "• `appbcbash` - 💥 Multiple bash emoji reactions\n"
                "• `appbceq` - ⚖️ EQ emoji reaction\n"
                "• `appbaa` - 📊 AA emoji reaction\n"
                "• `appsheriff` - 🤠 Sheriff emoji reaction\n\n"

                "**⚡ Slash Commands** *(react to last message)*:\n"
                "`/appbcbash` `/appbceq` `/appbaa` `/appsheriff`\n"
                "• Custom server emoji support • Fallback to default emojis\n"
                "• Multi-server configuration • Safe emoji handling\n"
                "*Automatic reactions make conversations more engaging!*"
            ),
            inline=False
        )

        embed.add_field(
            name="🎮 **Interactive Entertainment Features**",
            value=(
                "**🎪 Dynamic UI Elements:**\n"
                "• Interactive buttons for all games\n"
                "• Modal input systems for precise control\n"
                "• Dropdown menus for complex selections\n"
                "• Real-time status updates • Progress bars\n\n"

                "**🌟 Visual Effects:**\n"
                "• Animated embed colors • Dynamic status messages\n"
                "• Progress indicators • Achievement notifications\n"
                "• Particle effects in games • Atmospheric simulations"
            ),
            inline=False
        )

        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1234567890123456789.png")  # Replace with fun icon
        embed.set_footer(text="🎉 Bring the excitement of space exploration to your Discord server!")

        return embed

    def create_admin_embed(self):
        """Create the admin category embed with all master commands"""
        embed = discord.Embed(
            title="👑 Admin & Master Commands - Advanced Management",
            description="**Powerful administrative tools for bot management and advanced server control**",
            color=discord.Color.red()
        )

        embed.add_field(
            name="🛡️ **Auto-Moderation Control**",
            value=(
                "`!automod [status/enable/disable] [server_id]`\n"
                "🎛️ **Master Moderation System** - Server-wide content control\n"
                "• Enable/disable per server • Status checking\n"
                "• Automatic timeout enforcement • Multi-server support\n"
                "• Intelligent content detection • 24-hour timeout duration\n\n"

                "`!automod_exempt [add/remove/list] [user_id]`\n"
                "⚪ **User Exemption Management** - Whitelist system\n"
                "• Add/remove trusted users • List current exemptions\n"
                "• Master user protection • User display formatting\n"
                "• Safe user management • Permission validation"
            ),
            inline=False
        )

        embed.add_field(
            name="👑 **Role & Permission Management**",
            value=(
                "`!rolemapping [list/add/remove] [server_id] [role_id]`\n"
                "🎭 **Leader Role Configuration** - Reward system management\n"
                "• Configure Leader roles per server • Automatic role assignment\n"
                "• Top player recognition • Permission validation\n"
                "• Server information display • Role status verification\n\n"

                "`!timeout_users`\n"
                "👥 **Authorization Management** - View timeout permissions\n"
                "• Server-specific user lists • Permission checking\n"
                "• User mention formatting • Access control verification"
            ),
            inline=False
        )

        embed.add_field(
            name="🌌 **Galaxy System Administration** *(Master only)*",
            value=(
                "`!teleport [location/coords] [@user]`\n"
                "🚀 **Advanced Teleportation System** - Master galaxy control\n"
                "• **Preset Locations:** puzzle1, puzzle2, puzzle3, puzzle4, boss, home\n"
                "• **Custom Coordinates:** `!teleport coords X Y [@user]`\n"
                "• **User Teleportation:** Move any user to any location\n"
                "• **Self Teleportation:** Navigate the galaxy instantly\n"
                "*Master the entire galaxy exploration system!*"
            ),
            inline=False
        )

        embed.add_field(
            name="📊 **System Monitoring & Analytics**",
            value=(
                "**🔍 Server Statistics:**\n"
                "• Multi-server configuration tracking\n"
                "• User permission monitoring • Role assignment analytics\n"
                "• Auto-moderation status reporting • Exemption list management\n\n"

                "**⚙️ Bot Management:**\n"
                "• Guild-specific settings • Error handling & logging\n"
                "• Performance monitoring • Command usage tracking\n"
                "• Cross-server data synchronization"
            ),
            inline=False
        )

        embed.add_field(
            name="⚠️ **Security & Access Control**",
            value=(
                "🔐 **Master ID Required** for all admin commands\n"
                "🏠 **Server-Specific** configurations and exemptions\n"
                "👥 **Granular Permissions** for different user groups\n"
                "🛡️ **Protected Systems** prevent unauthorized access\n"
                "⚡ **Real-Time Validation** ensures command safety\n"
                "*Maximum security with flexible control options*"
            ),
            inline=False
        )

        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1234567890123456789.png")  # Replace with admin icon
        embed.set_footer(text="⚠️ Master commands require proper authorization | Use responsibly")

        return embed


# Add the slash command to your bot
@bot.tree.command(name="help", description="Show all available bot commands and features")
async def help_slash(interaction: discord.Interaction, category: Optional[str] = None):
    """Beautiful interactive help command with all games and features"""

    view = HelpView(bot)

    if category:
        category = category.lower()
        if category in ['games', 'game', 'gaming', 'play']:
            embed = view.create_games_embed()
        elif category in ['utility', 'util', 'tools', 'management']:
            embed = view.create_utility_embed()
        elif category in ['fun', 'entertainment', 'social', 'meme']:
            embed = view.create_fun_embed()
        elif category in ['admin', 'administration', 'master', 'mod']:
            embed = view.create_admin_embed()
        else:
            embed = view.create_main_embed()
    else:
        embed = view.create_main_embed()

    await interaction.response.send_message(embed=embed, view=view, ephemeral=False)


# Also add a traditional prefix command version
@bot.command(name="olithelp")
async def help_prefix(ctx, category: str = None):
    """Traditional prefix help command with all features"""

    view = HelpView(bot)

    if category:
        category = category.lower()
        if category in ['games', 'game', 'gaming', 'play']:
            embed = view.create_games_embed()
        elif category in ['utility', 'util', 'tools', 'management']:
            embed = view.create_utility_embed()
        elif category in ['fun', 'entertainment', 'social', 'meme']:
            embed = view.create_fun_embed()
        elif category in ['admin', 'administration', 'master', 'mod']:
            embed = view.create_admin_embed()
        else:
            embed = view.create_main_embed()
    else:
        embed = view.create_main_embed()

    await ctx.send(embed=embed, view=view)


# Enhanced about command with complete feature list
@bot.tree.command(name="about", description="Learn more about Launch Tower Bot's comprehensive features")
async def about_command(interaction: discord.Interaction):
    """Comprehensive bot information command"""

    embed = discord.Embed(
        title="🚀 About Launch Tower Bot - Complete Feature Overview",
        description=(
            "**The ultimate space-themed Discord bot for gaming and server management**\n\n"
            "Launch Tower is your comprehensive mission control companion, bringing "
            "the excitement of space exploration with professional server management tools!\n\n"
            "🎮 **Gaming Features:**\n"
            "• 15+ Interactive games with scoring system\n"
            "• Space trivia with 60+ questions (3 difficulties)\n"
            "• Advanced Mechzilla booster catch game\n"
            "• Galaxy exploration RPG system\n"
            "• Mission simulators and rocket design\n"
            "• Classic games with modern UI\n\n"

            "🛠️ **Management Features:**\n"
            "• Advanced auto-moderation with exemptions\n"
            "• Welcome message system with avatars\n"
            "• Automatic leader role assignment\n"
            "• Multi-server configuration support\n"
            "• Performance monitoring tools\n"
            "• Comprehensive admin controls\n\n"

            "🎭 **Entertainment Features:**\n"
            "• Animated GIF collection\n"
            "• Interactive emoji reaction system\n"
            "• Space-themed roleplay commands\n"
            "• Dynamic visual effects\n"
            "• Modal and button interactions"
        ),
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="📊 Complete Bot Statistics",
        value=(
            f"**Servers:** {len(bot.guilds)}\n"
            f"**Users:** {len(set(bot.get_all_members()))}\n"
            f"**Commands:** 35+\n"
            f"**Games:** 15+\n"
            f"**Admin Tools:** 10+\n"
            f"**Fun Commands:** 12+"
        ),
        inline=True
    )

    embed.add_field(
        name="🌟 Key Highlights",
        value=(
            "**Advanced Gaming:** Comprehensive scoring system\n"
            "**Smart Moderation:** Multi-server auto-mod\n"
            "**Role Automation:** Leader role rewards\n"
            "**Space Theme:** SpaceX-inspired content\n"
            "**Interactive UI:** Buttons, modals, dropdowns\n"
            "**Professional:** Enterprise-grade features"
        ),
        inline=True
    )

    embed.add_field(
        name="🚀 Getting Started",
        value=(
            "**Essential Commands:**\n"
            "`/help` - Complete command guide\n"
            "`/trivia` - Start with space trivia\n"
            "`!catchbooster` - Try the ultimate game\n"
            "`!leaderboard` - View server rankings\n"
            "`/ping` - Check bot performance\n"
            "`!galaxy` - Explore the universe"
        ),
        inline=True
    )

    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(
        text="🌌 OLIT Bot v4.0 | Comprehensive Space-Themed Discord Experience",
        icon_url=bot.user.display_avatar.url
    )

    await interaction.response.send_message(embed=embed, ephemeral=False)


# Command shortcuts for quick access to specific categories


@bot.tree.command(name="commands", description="List all bot commands by category")
async def commands_command(interaction: discord.Interaction):
    """Quick command overview"""
    embed = discord.Embed(
        title="📋 Quick Command Reference",
        description="**Essential commands organized by category**",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="🎮 Popular Games",
        value=(
            "`/trivia` - Space trivia quiz\n"
            "`!catchbooster` - Mechzilla game\n"
            "`!galaxy` - Space exploration\n"
            "`!rps` - Rock paper scissors\n"
            "`!starship` - Mission predictor"
        ),
        inline=True
    )

    embed.add_field(
        name="🛠️ Utilities",
        value=(
            "`/ping` - Bot performance\n"
            "`!leaderboard` - Server rankings\n"
            "`/help` - Complete help system\n"
            "`/about` - Bot information\n"
            "`!timeout_users` - Permission check"
        ),
        inline=True
    )

    embed.add_field(
        name="🎭 Fun Commands",
        value=(
            "`!bigboom` - Explosion GIF\n"
            "`!hello` - Greet Launch Tower\n"
            "`!wish` - Shooting stars\n"
            "`/appbcbash` - Emoji reactions\n"
            "`!vent` - Tower venting"
        ),
        inline=True
    )

    embed.set_footer(text="Use /help for detailed information about all commands")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# Don't forget to remove the default help command
bot.remove_command('help')

print("✅ Complete help command system loaded successfully!")
print("📊 Features: 35+ commands, 15+ games, comprehensive management tools")
print("🚀 Ready for launch!")

import discord
from discord.ext import commands
from discord import ui
import asyncio
from datetime import datetime, timedelta, UTC
import json
import os
from typing import Optional
import traceback

# ========================
# DISCORD ELECTION SYSTEM
# ========================

# ========================
# ROLE MAPPING FOR MULTI-SERVER SUPPORT
# ========================
ROLE_MAPPING = {
    # Format: guild_id: election_official_role_id
    # Add your server configurations here
    1210475350119813120: 1418639851586191572,  # Server 1
    1411425019434766499: 1424409812070039562,  # Server 2
    # Add more servers as needed
    # 987654321: ELECTION_OFFICIAL_ROLE_ID,
}

# Common logo URL for BAA and HS elections
ELECTION_LOGO_URL = "https://media.discordapp.net/attachments/1421476807189991444/1426195894814117918/92ecea0f-2a16-4c0b-9b03-e3662cbd16d7.png?ex=68ea57ee&is=68e9066e&hm=378057ab1ccc76bc9347189960514911729d2510500065717b273c5584ad1a3e&=&format=webp&quality=lossless&width=960&height=960"

# File paths for data persistence
ELECTIONS_FILE = "active_elections.json"
HISTORY_FILE = "election_history.json"

# Store active elections
active_elections = {}
election_tasks = {}


# ========================
# DATA PERSISTENCE FUNCTIONS
# ========================
def load_election_history():
    """Load election history from JSON file"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading history: {e}")
    return {}


def save_election_history(history):
    """Save election history to JSON file"""
    try:
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=4)
    except Exception as e:
        print(f"Error saving history: {e}")


def load_active_elections():
    """Load active elections from JSON file"""
    global active_elections
    if os.path.exists(ELECTIONS_FILE):
        try:
            with open(ELECTIONS_FILE, 'r') as f:
                data = json.load(f)
                # Convert string keys back to integers and reconstruct datetime objects
                for key, election in data.items():
                    election['end_time'] = datetime.fromisoformat(election['end_time'])
                    election['options'] = {opt: voters for opt, voters in election['options'].items()}
                    active_elections[int(key)] = election
            print(f"Loaded {len(active_elections)} active elections")
        except Exception as e:
            print(f"Error loading elections: {e}")


def save_active_elections():
    """Save active elections to JSON file"""
    try:
        data = {}
        for key, election in active_elections.items():
            election_copy = election.copy()
            election_copy['end_time'] = election['end_time'].isoformat()
            data[str(key)] = election_copy

        with open(ELECTIONS_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving elections: {e}")


def get_consecutive_wins(guild_id: int, user_id: int, election_type: str) -> int:
    """Get number of consecutive wins for a user in a specific election type"""
    history = load_election_history()
    guild_key = str(guild_id)

    if guild_key not in history:
        return 0

    if election_type not in history[guild_key]:
        return 0

    elections = history[guild_key][election_type]
    if not elections:
        return 0

    # Sort by timestamp (most recent first)
    sorted_elections = sorted(elections, key=lambda x: x['timestamp'], reverse=True)

    consecutive = 0
    for election in sorted_elections:
        if election['winner_id'] == user_id:
            consecutive += 1
        else:
            break

    return consecutive


def record_election_result(guild_id: int, election_type: str, winner_id: int, winner_name: str, total_votes: int):
    """Record election result in history"""
    history = load_election_history()
    guild_key = str(guild_id)

    if guild_key not in history:
        history[guild_key] = {}

    if election_type not in history[guild_key]:
        history[guild_key][election_type] = []

    history[guild_key][election_type].append({
        'winner_id': winner_id,
        'winner_name': winner_name,
        'total_votes': total_votes,
        'timestamp': datetime.now(UTC).isoformat()
    })

    save_election_history(history)


def get_election_official_role(guild_id: int) -> Optional[int]:
    """Get election official role ID for a guild"""
    return ROLE_MAPPING.get(guild_id)


# ========================
# HELPER FUNCTIONS
# ========================
def clean_button_label(label: str, guild=None) -> str:
    """Convert long labels to button-friendly format"""
    if label.startswith("<@") and label.endswith(">"):
        user_id = label[2:-1].replace("!", "")
        try:
            user_id_int = int(user_id)
            if guild:
                member = guild.get_member(user_id_int)
                if member:
                    return member.nick if member.nick else (member.display_name if member.display_name else member.name)

            user = bot.get_user(user_id_int)
            if user:
                if hasattr(user, 'display_name') and user.display_name:
                    return user.display_name
                elif hasattr(user, 'global_name') and user.global_name:
                    return user.global_name
                else:
                    return user.name
            return f"User {user_id[:4]}"
        except:
            return f"User {user_id[:4]}"
    if len(label) > 80:
        return label[:77] + "..."
    return label


def extract_user_id(mention: str) -> Optional[int]:
    """Extract user ID from mention string"""
    if mention.startswith("<@") and mention.endswith(">"):
        try:
            return int(mention[2:-1].replace("!", ""))
        except ValueError:
            return None
    return None


# ========================
# Voting Button System
# ========================
class ElectionVoteView(ui.View):
    def __init__(self, election_id, options):
        super().__init__(timeout=None)
        self.election_id = election_id

        for i, option in enumerate(options):
            button = ElectionVoteButton(election_id, option, i)
            self.add_item(button)


class ElectionVoteButton(ui.Button):
    def __init__(self, election_id, option, option_index, display_label=None):
        button_label = f"Option {option_index + 1}"
        super().__init__(
            label=button_label,
            style=discord.ButtonStyle.primary,
            custom_id=f"vote:{election_id}:{option_index}"
        )
        self.election_id = election_id
        self.option = option
        self.option_index = option_index

    async def callback(self, interaction: discord.Interaction):
        election = active_elections.get(self.election_id)

        if not election:
            embed = discord.Embed(
                title="⚠️ Election Unavailable",
                description="This election has ended or is no longer available.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Please check for active elections")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Check if user is a contestant (prevent self-voting) - ONLY for BAA elections
        if election["title"] == "BAA Administrator":
            contestant_id = election["contestants"].get(self.option)
            if contestant_id and int(contestant_id) == interaction.user.id:
                embed = discord.Embed(
                    title="❌ Self-Voting Not Allowed",
                    description="You cannot vote for yourself in BAA Administrator elections!\n\n*Please vote for another candidate.*",
                    color=discord.Color.red()
                )
                embed.set_footer(text=f"Election: {election['title']}")
                return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Check if user has already voted
        user_voted_for = None
        for option_name, voters in election["options"].items():
            if interaction.user.id in voters:
                user_voted_for = option_name
                break

        # If already voted for this option, don't allow duplicate
        if user_voted_for == self.option:
            embed = discord.Embed(
                title="✅ Already Voted",
                description=f"You have already cast your vote for:\n\n**{clean_button_label(self.option, interaction.guild)}**",
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Election: {election['title']} • You can change your vote anytime")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Remove user from previous vote
        if user_voted_for:
            election["options"][user_voted_for].remove(interaction.user.id)
            embed = discord.Embed(
                title="🔄 Vote Changed Successfully!",
                description=f"**Previous Vote:** {clean_button_label(user_voted_for, interaction.guild)}\n**New Vote:** {clean_button_label(self.option, interaction.guild)}",
                color=discord.Color.gold()
            )
            embed.add_field(
                name="📊 Your Vote Status",
                value="Your vote has been updated and recorded.",
                inline=False
            )
        else:
            embed = discord.Embed(
                title="✅ Vote Recorded Successfully!",
                description=f"You have voted for:\n\n**{clean_button_label(self.option, interaction.guild)}**",
                color=discord.Color.green()
            )
            embed.add_field(
                name="📊 Your Vote Status",
                value="Your vote has been recorded. You can change it anytime before the election ends.",
                inline=False
            )

        # Add new vote
        if self.option in election["options"]:
            election["options"][self.option].append(interaction.user.id)
        else:
            embed = discord.Embed(
                title="❌ Invalid Option",
                description="The selected option is not valid for this election.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Please try again or contact an administrator")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Save updated elections
        save_active_elections()

        embed.set_footer(text=f"Election: {election['title']} • Thank you for voting!")
        if election.get("logo"):
            embed.set_thumbnail(url=election["logo"])

        await interaction.response.send_message(embed=embed, ephemeral=True)


# ========================
# Helper Function to End Election
# ========================
async def end_election_process(election_id):
    """End an election and display results"""
    election = active_elections.get(election_id)
    if not election:
        return

    print(f"Ending election {election_id} - {election['title']}")
    active_elections.pop(election_id, None)
    election_tasks.pop(election_id, None)
    save_active_elections()

    try:
        channel = bot.get_channel(election["channel_id"])
        if not channel:
            return

        guild = bot.get_guild(election.get("guild_id"))
        msg = await channel.fetch_message(election["message_id"])

        # Calculate results
        results = {opt: len(voters) for opt, voters in election["options"].items()}

        if not results or all(count == 0 for count in results.values()):
            result_embed = discord.Embed(
                title="🏁 Election Concluded",
                description=f"**{election['title']}**\n\n⚠️ **No votes were cast during this election.**",
                color=discord.Color.orange()
            )
            result_embed.add_field(
                name="📊 Final Status",
                value="The election period has ended without any votes.",
                inline=False
            )
        else:
            max_votes = max(results.values())
            potential_winners = [opt for opt, count in results.items() if count == max_votes]

            # Check for consecutive wins and disqualify if necessary
            final_winners = []
            disqualified = []

            for winner in potential_winners:
                winner_id = extract_user_id(winner)
                if winner_id:
                    election_type = None
                    if election["title"] == "BAA Administrator":
                        election_type = "baa_admin"
                    elif election["title"] == "Head Sheriff":
                        election_type = "head_sheriff"

                    if election_type:
                        consecutive = get_consecutive_wins(guild.id, winner_id, election_type)
                        if consecutive >= 2:
                            disqualified.append((winner, consecutive))
                            continue

                final_winners.append(winner)

            # If all winners are disqualified, pick next best
            if not final_winners and len(results) > len(potential_winners):
                sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)
                for opt, count in sorted_results:
                    if opt not in potential_winners:
                        winner_id = extract_user_id(opt)
                        if winner_id:
                            election_type = None
                            if election["title"] == "BAA Administrator":
                                election_type = "baa_admin"
                            elif election["title"] == "Head Sheriff":
                                election_type = "head_sheriff"

                            if election_type:
                                consecutive = get_consecutive_wins(guild.id, winner_id, election_type)
                                if consecutive < 2:
                                    final_winners.append(opt)
                                    break

            # Create result embed
            if not final_winners:
                result_embed = discord.Embed(
                    title="🏁 Election Concluded",
                    description=f"**{election['title']}**\n\n⚠️ **No eligible winner (all candidates won 2+ consecutive times)**",
                    color=discord.Color.orange()
                )
            elif len(final_winners) > 1:
                winner_text = f"🤝 **Tie Between:**\n" + "\n".join(
                    [f"• {clean_button_label(w, guild)}" for w in final_winners])
                winner_color = discord.Color.blue()
                result_embed = discord.Embed(
                    title="🏁 Election Results",
                    description=f"**{election['title']}**\n\n{winner_text}",
                    color=winner_color
                )
            else:
                winner = final_winners[0]
                winner_text = f"🏆 **Winner:**\n**{clean_button_label(winner, guild)}**"
                winner_color = discord.Color.gold()
                result_embed = discord.Embed(
                    title="🏁 Election Results",
                    description=f"**{election['title']}**\n\n{winner_text}",
                    color=winner_color
                )

                # Record the win
                winner_id = extract_user_id(winner)
                if winner_id:
                    election_type = None

                    if election["title"] == "BAA Administrator":
                        election_type = "baa_admin"
                    elif election["title"] == "Head Sheriff":
                        election_type = "head_sheriff"

                    if election_type:
                        record_election_result(
                            guild.id,
                            election_type,
                            winner_id,
                            clean_button_label(winner, guild),
                            sum(results.values())
                        )

            # Add disqualification notice
            if disqualified:
                disq_text = "\n".join([f"• {clean_button_label(w, guild)} ({c} consecutive wins)"
                                       for w, c in disqualified])
                result_embed.add_field(
                    name="⚠️ Disqualified (2+ Consecutive Wins)",
                    value=disq_text,
                    inline=False
                )

            # Vote breakdown
            vote_lines = []
            total_votes = sum(results.values())
            for opt, count in sorted(results.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / total_votes * 100) if total_votes > 0 else 0
                bar_length = int(percentage / 10)
                bar = "█" * bar_length + "░" * (10 - bar_length)
                status = " ⚠️ Disqualified" if any(opt == d[0] for d in disqualified) else ""
                vote_lines.append(
                    f"**{clean_button_label(opt, guild)}**{status}\n{bar} {count} vote{'s' if count != 1 else ''} ({percentage:.1f}%)")

            result_embed.add_field(
                name="📊 Vote Breakdown",
                value="\n\n".join(vote_lines),
                inline=False
            )

            result_embed.add_field(
                name="📈 Total Participation",
                value=f"**{total_votes}** total vote{'s' if total_votes != 1 else ''} cast",
                inline=False
            )

        if election.get("logo"):
            result_embed.set_thumbnail(url=election["logo"])

        result_embed.set_footer(text=f"Election ended • {datetime.now(UTC).strftime('%B %d, %Y at %H:%M UTC')}")

        await msg.edit(embed=result_embed, view=None)

        if results and not all(count == 0 for count in results.values()):
            announce_embed = discord.Embed(
                title="🎉 Election Complete!",
                description=f"The **{election['title']}** election has officially concluded!\n\nCheck the results above.",
                color=discord.Color.gold()
            )
            if election.get("logo"):
                announce_embed.set_thumbnail(url=election["logo"])
            announce_embed.set_footer(text="Thank you to everyone who participated!")
            await channel.send(embed=announce_embed)

    except Exception as e:
        print(f"ERROR ending election {election_id}: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


async def start_election_timeout(election_id, hours):
    """Wait for election to end, then process results"""
    await asyncio.sleep(hours * 3600)
    await end_election_process(election_id)


# ========================
# BAA Administrator Election Command
# ========================
@bot.command(name="BAAelections")
async def baa_election(ctx, hours: int = 24, *candidates: str):
    try:
        official_role = get_election_official_role(ctx.guild.id)
        if not official_role or not any(role.id == official_role for role in ctx.author.roles):
            embed = discord.Embed(
                title="🚫 Access Denied",
                description="You don't have permission to start elections.\n\nOnly Election Officials can use this command.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Contact an administrator if you believe this is an error")
            return await ctx.send(embed=embed)

        if hours <= 0:
            embed = discord.Embed(
                title="❌ Invalid Duration",
                description="Election duration must be greater than 0 hours.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        if len(candidates) < 2:
            candidates = ["Candidate A", "Candidate B", "Candidate C"]

        title = "BAA Administrator"
        end_time = datetime.now(UTC) + timedelta(hours=hours)
        options = {c: [] for c in candidates}

        # Parse contestant IDs
        contestant_ids = {}
        for c in candidates:
            user_id = extract_user_id(c)
            contestant_ids[c] = user_id

        embed = discord.Embed(
            title=f"🗳️ {title} Election",
            description="**Vote for your preferred candidate!**\n\nClick the buttons below to cast your vote. You can change your vote anytime before the election ends.\n\n⚠️ *Candidates cannot vote for themselves.*\n⚠️ *Candidates with 2 consecutive wins are ineligible.*",
            color=0x5865F2
        )
        embed.set_thumbnail(url=ELECTION_LOGO_URL)

        candidates_text = []
        for i, c in enumerate(candidates, 1):
            display_name = clean_button_label(c, ctx.guild)
            user_id = extract_user_id(c)
            consecutive = get_consecutive_wins(ctx.guild.id, user_id, "baa_admin") if user_id else 0
            status = f" ⚠️ ({consecutive}/2 wins)" if consecutive > 0 else ""
            candidates_text.append(f"**Option {i}:** {display_name}{status}")

        embed.add_field(name="📋 Candidates", value="\n".join(candidates_text), inline=False)
        embed.add_field(name="⏱️ Duration", value=f"`{hours} hour{'s' if hours != 1 else ''}`", inline=True)
        embed.add_field(name="🏁 Ends", value=f"<t:{int(end_time.timestamp())}:R>", inline=True)
        embed.add_field(name="📊 Status", value="🟢 **Active**", inline=True)

        embed.set_footer(text=f"Started by {ctx.author.name} • Click buttons below to vote",
                         icon_url=ctx.author.avatar.url if ctx.author.avatar else None)

        msg = await ctx.send(embed=embed)

        active_elections[msg.id] = {
            "title": title,
            "options": options,
            "contestants": contestant_ids,
            "end_time": end_time,
            "message_id": msg.id,
            "channel_id": ctx.channel.id,
            "guild_id": ctx.guild.id,
            "logo": ELECTION_LOGO_URL
        }

        save_active_elections()

        view = ElectionVoteView(msg.id, candidates)
        await msg.edit(view=view)

        task = asyncio.create_task(start_election_timeout(msg.id, hours))
        election_tasks[msg.id] = task

        confirm_embed = discord.Embed(
            title="✅ Election Started Successfully!",
            description=f"**{title}** election is now live and accepting votes!",
            color=discord.Color.green()
        )
        confirm_embed.add_field(name="Duration", value=f"{hours} hour{'s' if hours != 1 else ''}", inline=True)
        confirm_embed.add_field(name="Candidates", value=f"{len(candidates)}", inline=True)
        await ctx.send(embed=confirm_embed, delete_after=10)

    except Exception as e:
        print(f"ERROR in BAAelections: {e}")
        import traceback
        traceback.print_exc()


# ========================
# Head Sheriff Election Command
# ========================
@bot.command(name="HSelections")
async def hs_election(ctx, hours: int = 24, *candidates: str):
    try:
        official_role = get_election_official_role(ctx.guild.id)
        if not official_role or not any(role.id == official_role for role in ctx.author.roles):
            embed = discord.Embed(
                title="🚫 Access Denied",
                description="You don't have permission to start elections.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        if hours <= 0:
            embed = discord.Embed(
                title="❌ Invalid Duration",
                description="Election duration must be greater than 0 hours.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        if len(candidates) < 2:
            candidates = ["Candidate A", "Candidate B", "Candidate C"]

        title = "Head Sheriff"
        end_time = datetime.now(UTC) + timedelta(hours=hours)
        options = {c: [] for c in candidates}

        contestant_ids = {}
        for c in candidates:
            user_id = extract_user_id(c)
            contestant_ids[c] = user_id

        embed = discord.Embed(
            title=f"🗳️ {title} Election",
            description="**Vote for your preferred candidate!**\n\nClick the buttons below to cast your vote. You can change your vote anytime before the election ends.\n\n⚠️ *Candidates with 2 consecutive wins are ineligible.*",
            color=0xED4245
        )
        embed.set_thumbnail(url=ELECTION_LOGO_URL)

        candidates_text = []
        for i, c in enumerate(candidates, 1):
            display_name = clean_button_label(c, ctx.guild)
            user_id = extract_user_id(c)
            consecutive = get_consecutive_wins(ctx.guild.id, user_id, "head_sheriff") if user_id else 0
            status = f" ⚠️ ({consecutive}/2 wins)" if consecutive > 0 else ""
            candidates_text.append(f"**Option {i}:** {display_name}{status}")

        embed.add_field(name="📋 Candidates", value="\n".join(candidates_text), inline=False)
        embed.add_field(name="⏱️ Duration", value=f"`{hours} hour{'s' if hours != 1 else ''}`", inline=True)
        embed.add_field(name="🏁 Ends", value=f"<t:{int(end_time.timestamp())}:R>", inline=True)
        embed.add_field(name="📊 Status", value="🟢 **Active**", inline=True)

        embed.set_footer(text=f"Started by {ctx.author.name} • Click buttons below to vote",
                         icon_url=ctx.author.avatar.url if ctx.author.avatar else None)

        msg = await ctx.send(embed=embed)

        active_elections[msg.id] = {
            "title": title,
            "options": options,
            "contestants": contestant_ids,
            "end_time": end_time,
            "message_id": msg.id,
            "channel_id": ctx.channel.id,
            "guild_id": ctx.guild.id,
            "logo": ELECTION_LOGO_URL
        }

        save_active_elections()

        view = ElectionVoteView(msg.id, candidates)
        await msg.edit(view=view)

        task = asyncio.create_task(start_election_timeout(msg.id, hours))
        election_tasks[msg.id] = task

        confirm_embed = discord.Embed(
            title="✅ Election Started Successfully!",
            description=f"**{title}** election is now live and accepting votes!",
            color=discord.Color.green()
        )
        await ctx.send(embed=confirm_embed, delete_after=10)

    except Exception as e:
        print(f"ERROR in HSelection: {e}")
        import traceback
        traceback.print_exc()


# ========================
# Clear Win History Command
# ========================
@bot.command(name="clearwins")
async def clear_wins(ctx, user: discord.Member, election_type: str):
    """Clear win history for a user. Types: baa_admin, head_sheriff, all"""
    official_role = get_election_official_role(ctx.guild.id)
    if not official_role or not any(role.id == official_role for role in ctx.author.roles):
        return await ctx.send("❌ You don't have permission to use this command.")

    if election_type not in ["baa_admin", "head_sheriff", "all"]:
        return await ctx.send("❌ Invalid type. Use: baa_admin, head_sheriff, or all")

    history = load_election_history()
    guild_key = str(ctx.guild.id)

    if guild_key not in history:
        return await ctx.send("✅ No history found for this server.")

    cleared_types = []

    if election_type == "all":
        types_to_clear = ["baa_admin", "head_sheriff"]
    else:
        types_to_clear = [election_type]

    for etype in types_to_clear:
        if etype in history[guild_key]:
            original_length = len(history[guild_key][etype])
            history[guild_key][etype] = [
                e for e in history[guild_key][etype]
                if e['winner_id'] != user.id
            ]
            removed = original_length - len(history[guild_key][etype])
            if removed > 0:
                cleared_types.append(f"{etype}: {removed} win(s)")

    save_election_history(history)

    if cleared_types:
        embed = discord.Embed(
            title="✅ Win History Cleared",
            description=f"Cleared win history for {user.mention}:\n" + "\n".join(f"• {t}" for t in cleared_types),
            color=discord.Color.green()
        )
    else:
        embed = discord.Embed(
            title="ℹ️ No History Found",
            description=f"No win history found for {user.mention} in the specified election type(s).",
            color=discord.Color.blue()
        )

    await ctx.send(embed=embed)


# ========================
# View Win History Command
# ========================
@bot.command(name="winhistory")
async def win_history(ctx, user: discord.Member = None):
    """View win history for a user or all users"""
    history = load_election_history()
    guild_key = str(ctx.guild.id)

    if guild_key not in history or not any(history[guild_key].values()):
        embed = discord.Embed(
            title="📊 Win History",
            description="No election history found for this server.",
            color=discord.Color.blue()
        )
        return await ctx.send(embed=embed)

    if user:
        # Show history for specific user
        embed = discord.Embed(
            title=f"📊 Win History - {user.display_name}",
            color=discord.Color.blue()
        )

        found_any = False
        for election_type, elections in history[guild_key].items():
            user_wins = [e for e in elections if e['winner_id'] == user.id]
            if user_wins:
                found_any = True
                consecutive = get_consecutive_wins(ctx.guild.id, user.id, election_type)

                wins_text = f"**Total Wins:** {len(user_wins)}\n"
                wins_text += f"**Consecutive Wins:** {consecutive}\n"
                wins_text += f"**Eligible:** {'❌ No' if consecutive >= 2 else '✅ Yes'}\n\n"
                wins_text += "**Recent Wins:**\n"

                for i, win in enumerate(sorted(user_wins, key=lambda x: x['timestamp'], reverse=True)[:3], 1):
                    timestamp = datetime.fromisoformat(win['timestamp'])
                    wins_text += f"{i}. <t:{int(timestamp.timestamp())}:R> ({win['total_votes']} votes)\n"

                embed.add_field(
                    name=f"🏆 {election_type.replace('_', ' ').title()}",
                    value=wins_text,
                    inline=False
                )

        if not found_any:
            embed.description = f"No win history found for {user.mention}"
    else:
        # Show overall statistics
        embed = discord.Embed(
            title="📊 Server Election History",
            color=discord.Color.blue()
        )

        for election_type, elections in history[guild_key].items():
            if elections:
                total_elections = len(elections)
                unique_winners = len(set(e['winner_id'] for e in elections))

                # Get top winners
                winner_counts = {}
                for e in elections:
                    winner_counts[e['winner_id']] = winner_counts.get(e['winner_id'], 0) + 1

                top_winners = sorted(winner_counts.items(), key=lambda x: x[1], reverse=True)[:3]

                stats_text = f"**Total Elections:** {total_elections}\n"
                stats_text += f"**Unique Winners:** {unique_winners}\n\n"
                stats_text += "**Top Winners:**\n"

                for i, (winner_id, wins) in enumerate(top_winners, 1):
                    member = ctx.guild.get_member(winner_id)
                    name = member.display_name if member else f"User {winner_id}"
                    consecutive = get_consecutive_wins(ctx.guild.id, winner_id, election_type)
                    status = " ⚠️" if consecutive >= 2 else ""
                    stats_text += f"{i}. {name}: {wins} win(s){status}\n"

                embed.add_field(
                    name=f"🏆 {election_type.replace('_', ' ').title()}",
                    value=stats_text,
                    inline=False
                )

    embed.set_footer(text="Use !clearwins @user <type> to clear history")
    await ctx.send(embed=embed)


# ========================
# General Election Command
# ========================
@bot.command(name="elections")
async def election_command(ctx, hours: int, title: str, logo_url: str = None, *candidates_str: str):
    official_role = get_election_official_role(ctx.guild.id)
    if not official_role or not any(role.id == official_role for role in ctx.author.roles):
        embed = discord.Embed(
            title="🚫 Access Denied",
            description="You don't have permission to start elections.",
            color=discord.Color.red()
        )
        return await ctx.send(embed=embed)

    if len(candidates_str) < 2:
        embed = discord.Embed(
            title="❌ Not Enough Candidates",
            description="You must provide at least 2 candidates for the election.",
            color=discord.Color.red()
        )
        return await ctx.send(embed=embed)

    if hours <= 0:
        embed = discord.Embed(
            title="❌ Invalid Duration",
            description="Election duration must be greater than 0 hours.",
            color=discord.Color.red()
        )
        return await ctx.send(embed=embed)

    candidates = list(candidates_str)
    contestant_ids = {}

    for candidate in candidates:
        user_id = extract_user_id(candidate)
        contestant_ids[candidate] = user_id

    end_time = datetime.now(UTC) + timedelta(hours=hours)
    options = {c: [] for c in candidates}

    embed = discord.Embed(
        title=f"🗳️ {title}",
        description="**Vote for your preferred candidate!**\n\nClick the buttons below to cast your vote. You can change your vote anytime before the election ends.",
        color=0x57F287
    )

    if logo_url and logo_url.startswith("http"):
        embed.set_thumbnail(url=logo_url)

    candidates_text = []
    for i, c in enumerate(candidates, 1):
        display_name = clean_button_label(c, ctx.guild)
        candidates_text.append(f"**Option {i}:** {display_name}")

    embed.add_field(name="📋 Candidates", value="\n".join(candidates_text), inline=False)
    embed.add_field(name="⏱️ Duration", value=f"`{hours} hour{'s' if hours != 1 else ''}`", inline=True)
    embed.add_field(name="🏁 Ends", value=f"<t:{int(end_time.timestamp())}:R>", inline=True)
    embed.add_field(name="📊 Status", value="🟢 **Active**", inline=True)

    embed.set_footer(text=f"Started by {ctx.author.name} • Click buttons below to vote",
                     icon_url=ctx.author.avatar.url if ctx.author.avatar else None)

    msg = await ctx.send(embed=embed)

    active_elections[msg.id] = {
        "title": title,
        "options": options,
        "contestants": contestant_ids,
        "end_time": end_time,
        "message_id": msg.id,
        "channel_id": ctx.channel.id,
        "guild_id": ctx.guild.id,
        "logo": logo_url if logo_url and logo_url.startswith("http") else None
    }

    save_active_elections()

    view = ElectionVoteView(msg.id, candidates)
    await msg.edit(view=view)

    task = asyncio.create_task(start_election_timeout(msg.id, hours))
    election_tasks[msg.id] = task

    confirm_embed = discord.Embed(
        title="✅ Election Started Successfully!",
        description=f"**{title}** election is now live and accepting votes!",
        color=discord.Color.green()
    )
    confirm_embed.add_field(name="Duration", value=f"{hours} hour{'s' if hours != 1 else ''}", inline=True)
    confirm_embed.add_field(name="Candidates", value=f"{len(candidates)}", inline=True)
    await ctx.send(embed=confirm_embed, delete_after=10)


# ========================
# Admin Command to End Election Early
# ========================
@bot.command(name="endelections")
async def end_election_early(ctx, message_id: int):
    official_role = get_election_official_role(ctx.guild.id)
    if not official_role or not any(role.id == official_role for role in ctx.author.roles):
        embed = discord.Embed(
            title="🚫 Access Denied",
            description="You don't have permission to end elections.",
            color=discord.Color.red()
        )
        return await ctx.send(embed=embed)

    election = active_elections.get(message_id)
    if not election:
        embed = discord.Embed(
            title="❌ Election Not Found",
            description="The election doesn't exist or has already ended.",
            color=discord.Color.red()
        )
        return await ctx.send(embed=embed)

    task = election_tasks.get(message_id)
    if task and not task.done():
        task.cancel()

    await end_election_process(message_id)

    confirm_embed = discord.Embed(
        title="✅ Election Ended",
        description=f"Successfully ended election:\n**{election['title']}**",
        color=discord.Color.green()
    )
    await ctx.send(embed=confirm_embed)


# ========================
# List Active Elections
# ========================
@bot.command(name="listelections")
async def list_elections(ctx):
    if not active_elections:
        embed = discord.Embed(
            title="📋 Active Elections",
            description="There are currently no active elections running.",
            color=discord.Color.blue()
        )
        return await ctx.send(embed=embed)

    embed = discord.Embed(
        title="📋 Active Elections",
        description=f"Currently running **{len(active_elections)}** election{'s' if len(active_elections) != 1 else ''}:",
        color=discord.Color.blue()
    )

    for i, (eid, election) in enumerate(active_elections.items(), 1):
        total_votes = sum(len(voters) for voters in election['options'].values())
        embed.add_field(
            name=f"{i}. {election['title']}",
            value=f"**ID:** `{eid}`\n**Votes:** {total_votes}\n**Ends:** <t:{int(election['end_time'].timestamp())}:R>",
            inline=False
        )

    embed.set_footer(text="Use !endelections <message_id> to end an election early")
    await ctx.send(embed=embed)


# ========================
# Help Command
# ========================
@bot.command(name="electionhelp")
async def election_help(ctx):
    embed = discord.Embed(
        title="📖 Election Bot Commands",
        description="Complete guide to using the election system",
        color=0x5865F2
    )

    embed.add_field(
        name="🗳️ Starting Elections",
        value=(
            "**!BAAelections <hours> @candidate1 @candidate2 ...**\n"
            "Start a BAA Administrator election\n\n"
            "**!HSelections <hours> @candidate1 @candidate2 ...**\n"
            "Start a Head Sheriff election\n\n"
            "**!elections <hours> \"Title\" [logo_url] candidate1 candidate2 ...**\n"
            "Start a custom election"
        ),
        inline=False
    )

    embed.add_field(
        name="📊 Managing Elections",
        value=(
            "**!listelections** - View all active elections\n"
            "**!endelections <message_id>** - End an election early\n"
            "**!winhistory [@user]** - View win history\n"
            "**!clearwins @user <type>** - Clear win history\n"
            "  Types: `baa_admin`, `head_sheriff`, `all`"
        ),
        inline=False
    )

    embed.add_field(
        name="⚙️ Features",
        value=(
            "✅ Vote tracking with button interface\n"
            "✅ Vote changing allowed anytime\n"
            "✅ Self-voting prevention (BAA only)\n"
            "✅ 2-consecutive-win rule enforcement\n"
            "✅ Multi-server support\n"
            "✅ Persistent data storage"
        ),
        inline=False
    )

    embed.add_field(
        name="🏆 Consecutive Win Rule",
        value=(
            "Candidates who have won **2 consecutive elections** of the same type "
            "are automatically disqualified. If disqualified candidates have the most votes, "
            "the next eligible candidate wins."
        ),
        inline=False
    )

    embed.set_footer(text="Only Election Officials can start and manage elections")
    await ctx.send(embed=embed)


# ========================
# Bot Events - FIXED VERSION
# ========================



# Add these imports at the top of your main.py file
import requests
import json
from typing import Dict, Optional
from datetime import datetime, timedelta

# ============================================
# API INTEGRATION CONFIGURATION
# ============================================

# Configuration for API integration
API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:8080')
API_KEY = os.getenv('API_KEY')  # Only needed for authenticated endpoints

# Cache for commands to avoid excessive API calls
command_cache = {}
cache_expiry = {}
CACHE_DURATION = timedelta(minutes=5)


# ============================================
# API HELPER FUNCTIONS
# ============================================

def fetch_guild_commands(guild_id: str) -> Dict:
    """Fetch commands from API for a specific guild"""
    try:
        url = f"{API_BASE_URL}/api/commands/{guild_id}"
        response = requests.get(url, timeout=3)

        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"✅ Loaded {len(data.get('commands', {}))} commands for guild {guild_id}")
                return data.get('commands', {})
        else:
            print(f"⚠️ API returned status {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Failed to fetch commands from API: {e}")
    except Exception as e:
        print(f"⚠️ Error fetching commands: {e}")

    # Fallback to local file if API fails
    return load_commands_from_file(guild_id)


def load_commands_from_file(guild_id: str) -> Dict:
    """Fallback: Load commands from local JSON file"""
    try:
        with open('config/guild_commands.json', 'r') as f:
            all_commands = json.load(f)
            return all_commands.get(str(guild_id), {})
    except FileNotFoundError:
        print(f"⚠️ Config file not found, no commands loaded for guild {guild_id}")
        return {}
    except Exception as e:
        print(f"⚠️ Error loading commands from file: {e}")
        return {}


def get_cached_commands(guild_id: str) -> Dict:
    """Get commands with caching to reduce API calls"""
    now = datetime.now()
    guild_id_str = str(guild_id)

    # Check if cache is valid
    if (guild_id_str in command_cache and
            guild_id_str in cache_expiry and
            cache_expiry[guild_id_str] > now):
        return command_cache[guild_id_str]

    # Reload from API
    commands = fetch_guild_commands(guild_id_str)
    command_cache[guild_id_str] = commands
    cache_expiry[guild_id_str] = now + CACHE_DURATION

    return commands


def fetch_automod_words(guild_id: str) -> list:
    """Fetch automod words from API"""
    try:
        url = f"{API_BASE_URL}/api/automod/{guild_id}"
        response = requests.get(url, timeout=3)

        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                return data.get('words', [])
    except Exception as e:
        print(f"⚠️ Failed to fetch automod words: {e}")

    return []


def fetch_allowed_users(guild_id: str) -> list:
    """Fetch allowed users from API"""
    try:
        url = f"{API_BASE_URL}/api/allowed_users/{guild_id}"
        response = requests.get(url, timeout=3)

        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                return data.get('users', [])
    except Exception as e:
        print(f"⚠️ Failed to fetch allowed users: {e}")

    return []


def clear_command_cache(guild_id: str = None):
    """Clear command cache for a guild or all guilds"""
    if guild_id:
        guild_id_str = str(guild_id)
        if guild_id_str in command_cache:
            del command_cache[guild_id_str]
        if guild_id_str in cache_expiry:
            del cache_expiry[guild_id_str]
    else:
        command_cache.clear()
        cache_expiry.clear()


# ============================================
# BOT EVENT HANDLERS
# ============================================

@bot.event
async def on_message(message):
    """Handle incoming messages and process custom commands"""
    # Ignore bot messages
    if message.author.bot:
        return

    # Check if message starts with ! (custom command prefix)
    if message.content.startswith('!'):
        # Extract command name
        parts = message.content[1:].split()
        if not parts:
            await bot.process_commands(message)
            return

        command_name = parts[0].lower()

        # Only check for custom commands in guilds
        if message.guild:
            guild_id = str(message.guild.id)

            # Fetch commands from API (with caching)
            commands = get_cached_commands(guild_id)

            # Check if this command exists
            if command_name in commands:
                command_data = commands[command_name]
                response_text = command_data.get('response', '')

                if response_text:
                    await message.channel.send(response_text)
                    print(f"✅ Executed custom command: !{command_name} in guild {guild_id}")
                    return  # Don't process as regular command

    # Process regular bot commands
    await bot.process_commands(message)





# ============================================
# ADMIN COMMANDS
# ============================================

@bot.command(name='testcommand')
@commands.has_permissions(administrator=True)
async def test_command(ctx, command_name: str = None):
    """Test if a custom command is loaded

    Usage:
        !testcommand - List all custom commands
        !testcommand <name> - Check specific command
    """
    guild_id = str(ctx.guild.id)
    commands = get_cached_commands(guild_id)

    if not command_name:
        # List all commands
        if not commands:
            await ctx.send("❌ No custom commands configured for this server.")
            return

        command_list = "\n".join([f"• `!{cmd}` - {data.get('description', 'No description')}"
                                  for cmd, data in commands.items()])

        embed = discord.Embed(
            title="📋 Custom Commands",
            description=f"**Total Commands:** {len(commands)}\n\n{command_list}",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)
    else:
        # Check specific command
        command_name = command_name.lower()
        if command_name in commands:
            cmd_data = commands[command_name]
            embed = discord.Embed(
                title=f"✅ Command: !{command_name}",
                color=discord.Color.green()
            )
            embed.add_field(name="Response", value=cmd_data.get('response', 'N/A'), inline=False)
            embed.add_field(name="Description", value=cmd_data.get('description', 'No description'), inline=False)
            embed.add_field(name="Added At", value=cmd_data.get('added_at', 'Unknown'), inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ Command `!{command_name}` not found.")


@bot.command(name='reloadcommands')
@commands.has_permissions(administrator=True)
async def reload_commands(ctx):
    """Reload custom commands from API

    Usage: !reloadcommands
    """
    guild_id = str(ctx.guild.id)

    # Clear cache
    clear_command_cache(guild_id)

    # Reload
    commands = get_cached_commands(guild_id)

    embed = discord.Embed(
        title="🔄 Commands Reloaded",
        description=f"Successfully reloaded **{len(commands)}** custom commands!",
        color=discord.Color.green()
    )

    if commands:
        command_list = ", ".join([f"`!{cmd}`" for cmd in commands.keys()])
        embed.add_field(name="Available Commands", value=command_list, inline=False)

    await ctx.send(embed=embed)


@bot.command(name='listcommands')
async def list_commands(ctx):
    """List all custom commands (public command)

    Usage: !listcommands
    """
    guild_id = str(ctx.guild.id)
    commands = get_cached_commands(guild_id)

    if not commands:
        await ctx.send("❌ No custom commands available for this server.")
        return

    embed = discord.Embed(
        title="📋 Available Custom Commands",
        description=f"Use `!<command>` to execute",
        color=discord.Color.blue()
    )

    for cmd, data in commands.items():
        description = data.get('description', 'No description')
        embed.add_field(
            name=f"!{cmd}",
            value=description,
            inline=False
        )

    embed.set_footer(text=f"Total: {len(commands)} commands")
    await ctx.send(embed=embed)


@bot.command(name='apistatus')
@commands.has_permissions(administrator=True)
async def api_status(ctx):
    """Check API connection status

    Usage: !apistatus
    """
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=3)

        if response.status_code == 200:
            data = response.json()
            embed = discord.Embed(
                title="✅ API Status: Online",
                color=discord.Color.green()
            )
            embed.add_field(name="Status", value=data.get('status', 'Unknown'), inline=True)
            embed.add_field(name="Timestamp", value=data.get('timestamp', 'Unknown'), inline=True)
            embed.add_field(name="API URL", value=API_BASE_URL, inline=False)
        else:
            embed = discord.Embed(
                title="⚠️ API Status: Error",
                description=f"Status Code: {response.status_code}",
                color=discord.Color.orange()
            )
    except Exception as e:
        embed = discord.Embed(
            title="❌ API Status: Offline",
            description=f"Error: {str(e)}",
            color=discord.Color.red()
        )

    await ctx.send(embed=embed)


# ============================================
# ERROR HANDLER
# ============================================

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command!")
    elif isinstance(error, commands.CommandNotFound):
        # Check if it might be a custom command that wasn't handled
        pass  # Already handled in on_message
    else:
        print(f"Error: {error}")
        await ctx.send(f"❌ An error occurred: {str(error)}")


# ============================================
# TESTING FUNCTION
# ============================================

async def test_api_connection():
    """Test API connection on startup"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ API connection successful!")
            return True
        else:
            print(f"⚠️ API returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Failed to connect to API: {e}")
        return False


# Add this to your bot startup section:
# asyncio.run(test_api_connection())  # Test API on startup
# ============================================
# API MANAGEMENT COMMANDS (Master Only)
# ============================================

@bot.command(name='api_reload')
async def reload_api_data(ctx):
    """Reload API configuration from files (Master only)"""

    if ctx.author.id != MASTER_ID:
        embed = discord.Embed(
            title="🚫 Access Denied",
            description="Only the master user can reload API data.",
            color=discord.Color.red()
        )
        return await ctx.send(embed=embed)

    try:
        # Import load function from keep_alive
        from keep_alive import load_all_data

        load_all_data()

        embed = discord.Embed(
            title="✅ API Data Reloaded",
            description="All configuration data has been reloaded from JSON files.",
            color=discord.Color.green()
        )

        # Show current stats
        from keep_alive import guild_commands, automod_config, allowed_users

        embed.add_field(
            name="📊 Loaded Data",
            value=f"**Guilds with commands:** {len(guild_commands)}\n"
                  f"**Guilds with automod:** {len(automod_config)}\n"
                  f"**Guilds with allowed users:** {len(allowed_users)}",
            inline=False
        )

        await ctx.send(embed=embed)

    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Reload Failed",
            description=f"Error reloading API data: {str(e)}",
            color=discord.Color.red()
        )
        await ctx.send(embed=error_embed)


@bot.command(name='api_status')
async def api_status(ctx):
    """Show API server status and statistics"""

    try:
        from keep_alive import guild_commands, automod_config, allowed_users, api_logs

        embed = discord.Embed(
            title="🌐 API Server Status",
            description="Current status of the OLIT API server",
            color=discord.Color.blue()
        )

        # Calculate totals
        total_guilds = len(set(
            list(guild_commands.keys()) +
            list(automod_config.keys()) +
            list(allowed_users.keys())
        ))

        total_commands = sum(len(cmds) for cmds in guild_commands.values())
        total_automod = sum(len(words) for words in automod_config.values())
        total_users = sum(len(users) for users in allowed_users.values())

        embed.add_field(
            name="📊 Configuration Stats",
            value=f"**Total Guilds:** {total_guilds}\n"
                  f"**Custom Commands:** {total_commands}\n"
                  f"**Automod Words:** {total_automod}\n"
                  f"**Allowed Users:** {total_users}",
            inline=True
        )

        embed.add_field(
            name="📝 API Activity",
            value=f"**Requests Logged:** {len(api_logs)}\n"
                  f"**Server Status:** 🟢 Online\n"
                  f"**Port:** 8080",
            inline=True
        )

        # Show guild-specific data if in a guild
        if ctx.guild:
            guild_id = str(ctx.guild.id)

            guild_cmd_count = len(guild_commands.get(guild_id, {}))
            guild_automod_count = len(automod_config.get(guild_id, []))
            guild_users_count = len(allowed_users.get(guild_id, []))

            embed.add_field(
                name=f"🏠 This Server ({ctx.guild.name})",
                value=f"**Commands:** {guild_cmd_count}\n"
                      f"**Automod Words:** {guild_automod_count}\n"
                      f"**Allowed Users:** {guild_users_count}",
                inline=False
            )

        embed.set_footer(text="Use !api_reload to refresh data from files")

        await ctx.send(embed=embed)

    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Status Check Failed",
            description=f"Error checking API status: {str(e)}",
            color=discord.Color.red()
        )
        await ctx.send(embed=error_embed)


@bot.command(name='api_commands')
async def show_api_commands(ctx):
    """Show all custom commands for this server"""

    if not ctx.guild:
        await ctx.send("This command can only be used in a server.")
        return

    guild_id = str(ctx.guild.id)
    guild_cmds = get_guild_commands(guild_id)

    if not guild_cmds:
        embed = discord.Embed(
            title="📋 Custom Commands",
            description="No custom commands configured for this server yet.\n\nUse the admin panel to add commands!",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)
        return

    embed = discord.Embed(
        title=f"📋 Custom Commands - {ctx.guild.name}",
        description=f"**{len(guild_cmds)}** custom command{'s' if len(guild_cmds) != 1 else ''} available",
        color=discord.Color.green()
    )

    # Group commands (max 25 fields)
    commands_text = []
    for i, (cmd, data) in enumerate(guild_cmds.items(), 1):
        description = data.get('description', 'No description')
        commands_text.append(f"**{i}.** `!{cmd}` - {description}")

    # Split into chunks if too many
    chunk_size = 10
    for i in range(0, len(commands_text), chunk_size):
        chunk = commands_text[i:i + chunk_size]
        embed.add_field(
            name=f"Commands {i + 1}-{min(i + chunk_size, len(commands_text))}",
            value="\n".join(chunk),
            inline=False
        )

    embed.set_footer(text="Use the admin panel to manage commands • API-powered")

    await ctx.send(embed=embed)


# ============================================
# OPTIONAL: ALLOWED USERS CHECK FOR COMMANDS
# ============================================

def check_allowed_user(ctx):
    """Check if user is in allowed users list for this guild"""

    # Master is always allowed
    if ctx.author.id == MASTER_ID:
        return True

    # Get allowed users for this guild
    guild_id = str(ctx.guild.id) if ctx.guild else None
    if not guild_id:
        return False

    allowed = get_allowed_users_list(guild_id)

    # If no restrictions set, allow everyone
    if not allowed:
        return True

    # Check if user is in allowed list
    return str(ctx.author.id) in allowed


# Example of using allowed users check:
@bot.command(name='restricted_command')
async def restricted_command(ctx):
    """Example command that requires allowed user status"""

    if not check_allowed_user(ctx):
        embed = discord.Embed(
            title="🚫 Access Denied",
            description="You don't have permission to use this command.",
            color=discord.Color.red()
        )
        embed.set_footer(text="Contact server administrators for access")
        return await ctx.send(embed=embed)

    # Command logic here
    await ctx.send("✅ You have access to this restricted command!")


# ============================================
# STARTUP LOG
# ============================================




# ============================================
# HELPER FUNCTION: GET COMMAND INFO
# ============================================

def get_command_info(guild_id: int, command_name: str):
    """Get information about a specific command"""
    guild_cmds = get_guild_commands(str(guild_id))
    return guild_cmds.get(command_name.lower())


def is_word_banned(guild_id: int, word: str):
    """Check if a word is banned in automod"""
    banned_words = get_automod_words(str(guild_id))
    return word.lower() in [w.lower() for w in banned_words]


# ============================================
# EXAMPLE: COMMAND USAGE STATISTICS
# ============================================

command_usage = {}  # {guild_id: {command: count}}


@bot.event
async def on_command(ctx):
    """Track command usage (optional)"""

    if ctx.guild:
        guild_id = str(ctx.guild.id)
        command = ctx.command.name

        if guild_id not in command_usage:
            command_usage[guild_id] = {}

        command_usage[guild_id][command] = command_usage[guild_id].get(command, 0) + 1


@bot.command(name='command_stats')
async def command_stats(ctx):
    """Show command usage statistics for this server"""

    if not ctx.guild:
        return

    guild_id = str(ctx.guild.id)
    usage = command_usage.get(guild_id, {})

    if not usage:
        await ctx.send("No command usage data available yet.")
        return

    embed = discord.Embed(
        title=f"📊 Command Usage Statistics - {ctx.guild.name}",
        color=discord.Color.blue()
    )

    # Sort by usage count
    sorted_usage = sorted(usage.items(), key=lambda x: x[1], reverse=True)[:10]

    stats_text = []
    for i, (cmd, count) in enumerate(sorted_usage, 1):
        stats_text.append(f"**{i}.** `!{cmd}` - {count} uses")

    embed.add_field(
        name="Top Commands",
        value="\n".join(stats_text),
        inline=False
    )

    await ctx.send(embed=embed)


# ============================================
# GITHUB INTEGRATION COMMANDS
# ============================================

@bot.command(name='github_status')
async def github_status_command(ctx):
    """Check GitHub integration status (Master only)"""

    if ctx.author.id != MASTER_ID:
        embed = discord.Embed(
            title="🚫 Access Denied",
            description="Only the master user can check GitHub status.",
            color=discord.Color.red()
        )
        return await ctx.send(embed=embed)

    try:
        # Import required functions and variables
        from keep_alive import GITHUB_TOKEN, GITHUB_REPO, GITHUB_BRANCH

        # Check if GitHub is configured
        if not GITHUB_TOKEN or not GITHUB_REPO:
            embed = discord.Embed(
                title="❌ GitHub Not Configured",
                description="GitHub integration is not set up.\n\nSet `GITHUB_TOKEN` and `GITHUB_REPO` environment variables on Render.",
                color=discord.Color.red()
            )
            embed.add_field(
                name="📋 Required Variables",
                value="```env\nGITHUB_TOKEN=ghp_...\nGITHUB_REPO=username/repo-name\nGITHUB_BRANCH=main\n```",
                inline=False
            )
            return await ctx.send(embed=embed)

        # Make a direct API call to check status
        import requests

        headers = {
            'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }

        # Get repository info
        repo_url = f'https://api.github.com/repos/{GITHUB_REPO}'
        repo_response = requests.get(repo_url, headers=headers, timeout=10)

        if repo_response.status_code != 200:
            embed = discord.Embed(
                title="❌ GitHub Connection Failed",
                description=f"Failed to connect to GitHub repository.\n\n**Status Code:** {repo_response.status_code}",
                color=discord.Color.red()
            )
            embed.add_field(
                name="💡 Common Issues",
                value="• Invalid GitHub token\n• Repository doesn't exist\n• Token lacks permissions\n• Repository is private and token can't access it",
                inline=False
            )
            return await ctx.send(embed=embed)

        repo_data = repo_response.json()

        # Get recent commits
        commits_url = f'https://api.github.com/repos/{GITHUB_REPO}/commits'
        commits_response = requests.get(commits_url, headers=headers, params={'per_page': 5}, timeout=10)

        recent_commits = []
        if commits_response.status_code == 200:
            commits_data = commits_response.json()
            recent_commits = [
                {
                    'message': commit['commit']['message'],
                    'author': commit['commit']['author']['name'],
                    'date': commit['commit']['author']['date']
                }
                for commit in commits_data
            ]

        # Create success embed
        embed = discord.Embed(
            title="🔗 GitHub Integration Status",
            description=f"✅ Connected to [{repo_data['full_name']}]({repo_data['html_url']})",
            color=discord.Color.green()
        )

        embed.set_thumbnail(url="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png")

        embed.add_field(
            name="📦 Repository Info",
            value=f"**Name:** {repo_data['name']}\n**Visibility:** {'🔒 Private' if repo_data['private'] else '🌍 Public'}\n**Branch:** `{GITHUB_BRANCH}`\n**Default Branch:** `{repo_data['default_branch']}`",
            inline=True
        )

        # Show recent commits
        if recent_commits:
            commits_text = []
            for i, commit in enumerate(recent_commits[:3], 1):
                msg = commit['message'][:60] + '...' if len(commit['message']) > 60 else commit['message']
                commits_text.append(f"**{i}.** {msg}")

            embed.add_field(
                name="📝 Recent Commits",
                value="\n".join(commits_text),
                inline=False
            )

        embed.add_field(
            name="⚙️ Auto-Sync Status",
            value="✅ **Enabled** - All changes are automatically committed to GitHub",
            inline=False
        )

        embed.set_footer(text="Use !github_sync to manually sync all config files")

        await ctx.send(embed=embed)

    except requests.exceptions.RequestException as e:
        error_embed = discord.Embed(
            title="❌ Network Error",
            description=f"Failed to connect to GitHub API:\n```{str(e)}```",
            color=discord.Color.red()
        )
        error_embed.add_field(
            name="💡 Possible Causes",
            value="• No internet connection\n• GitHub API is down\n• Request timeout\n• Firewall blocking requests",
            inline=False
        )
        await ctx.send(embed=error_embed)

    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error Checking Status",
            description=f"An unexpected error occurred:\n```{str(e)}```",
            color=discord.Color.red()
        )
        error_embed.add_field(
            name="💡 Troubleshooting",
            value="• Check Render logs for detailed errors\n• Verify environment variables are set\n• Ensure GitHub token has correct permissions\n• Try `!api_reload` to refresh configuration",
            inline=False
        )
        await ctx.send(embed=error_embed)


@bot.command(name='github_sync')
async def github_sync_command(ctx):
    """Manually sync all config files to GitHub (Master only)"""

    if ctx.author.id != MASTER_ID:
        embed = discord.Embed(
            title="🚫 Access Denied",
            description="Only the master user can sync to GitHub.",
            color=discord.Color.red()
        )
        return await ctx.send(embed=embed)

    try:
        # Import required functions and variables
        from keep_alive import GITHUB_TOKEN, GITHUB_REPO, GITHUB_BRANCH
        import requests
        import base64
        import json

        # Check if GitHub is configured
        if not GITHUB_TOKEN or not GITHUB_REPO:
            embed = discord.Embed(
                title="❌ GitHub Not Configured",
                description="GitHub integration is not set up.\n\nConfigure environment variables on Render:\n• `GITHUB_TOKEN`\n• `GITHUB_REPO`\n• `GITHUB_BRANCH` (optional)",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        # Show loading message
        loading_embed = discord.Embed(
            title="⏳ Syncing to GitHub...",
            description="Committing all config files to repository...",
            color=discord.Color.blue()
        )
        loading_msg = await ctx.send(embed=loading_embed)

        # Files to sync
        files_to_sync = [
            ('config/guild_commands.json', '🤖 Auto-sync guild commands'),
            ('config/automod_config.json', '🛡️ Auto-sync automod config'),
            ('config/allowed_users.json', '👥 Auto-sync allowed users')
        ]

        results = []
        successful_commits = 0

        headers = {
            'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }

        for file_path, commit_msg in files_to_sync:
            try:
                # Read local file
                if not os.path.exists(file_path):
                    results.append({
                        'file': file_path.split('/')[-1],
                        'success': False,
                        'message': 'File not found locally'
                    })
                    continue

                with open(file_path, 'r') as f:
                    content = f.read()

                # GitHub API endpoint
                api_url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}'

                # Get current file SHA (required for updates)
                response = requests.get(api_url, headers=headers, timeout=10)
                sha = None
                if response.status_code == 200:
                    sha = response.json()['sha']

                # Encode content to base64
                content_encoded = base64.b64encode(content.encode()).decode()

                # Prepare commit data
                data = {
                    'message': f'{commit_msg} - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
                    'content': content_encoded,
                    'branch': GITHUB_BRANCH
                }

                if sha:
                    data['sha'] = sha

                # Make the commit
                commit_response = requests.put(api_url, headers=headers, json=data, timeout=10)

                if commit_response.status_code in [200, 201]:
                    result_data = commit_response.json()
                    results.append({
                        'file': file_path.split('/')[-1],
                        'success': True,
                        'commit_url': result_data['commit']['html_url']
                    })
                    successful_commits += 1
                else:
                    results.append({
                        'file': file_path.split('/')[-1],
                        'success': False,
                        'message': f'HTTP {commit_response.status_code}'
                    })

            except Exception as e:
                results.append({
                    'file': file_path.split('/')[-1],
                    'success': False,
                    'message': str(e)[:100]
                })

        # Create result embed
        if successful_commits == 0:
            embed = discord.Embed(
                title="❌ Sync Failed",
                description="Failed to sync any files to GitHub.",
                color=discord.Color.red()
            )
        else:
            embed = discord.Embed(
                title="✅ GitHub Sync Complete" if successful_commits == len(files_to_sync) else "⚠️ Partial Sync",
                description=f"Successfully synced **{successful_commits}** out of **{len(files_to_sync)}** file(s)",
                color=discord.Color.green() if successful_commits == len(files_to_sync) else discord.Color.orange()
            )

        # Show detailed results
        success_files = []
        failed_files = []

        for result in results:
            if result['success']:
                if 'commit_url' in result:
                    success_files.append(f"✅ [{result['file']}]({result['commit_url']})")
                else:
                    success_files.append(f"✅ {result['file']}")
            else:
                error_msg = result.get('message', 'Unknown error')[:100]
                failed_files.append(f"❌ {result['file']}\n   └ {error_msg}")

        if success_files:
            embed.add_field(
                name="📦 Synced Files",
                value="\n".join(success_files),
                inline=False
            )

        if failed_files:
            embed.add_field(
                name="⚠️ Failed Files",
                value="\n".join(failed_files),
                inline=False
            )

        embed.add_field(
            name="🔗 Repository",
            value=f"Check your [GitHub repository](https://github.com/{GITHUB_REPO}) for the commits",
            inline=False
        )

        embed.set_footer(text=f"Synced to branch: {GITHUB_BRANCH}")

        await loading_msg.edit(embed=embed)

    except requests.exceptions.RequestException as e:
        error_embed = discord.Embed(
            title="❌ Network Error",
            description=f"Failed to connect to GitHub:\n```{str(e)}```",
            color=discord.Color.red()
        )
        error_embed.add_field(
            name="💡 Common Issues",
            value="• No internet connection\n• GitHub API timeout\n• Rate limit exceeded",
            inline=False
        )

        try:
            await loading_msg.edit(embed=error_embed)
        except:
            await ctx.send(embed=error_embed)

    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Sync Error",
            description=f"An error occurred while syncing to GitHub:\n```{str(e)}```",
            color=discord.Color.red()
        )
        error_embed.add_field(
            name="💡 Common Issues",
            value="• Invalid GitHub token\n• Repository not found\n• Insufficient permissions\n• Network error",
            inline=False
        )

        try:
            await loading_msg.edit(embed=error_embed)
        except:
            await ctx.send(embed=error_embed)


@bot.command(name='github_info')
async def github_info_command(ctx):
    """Show information about GitHub integration"""

    embed = discord.Embed(
        title="🔗 GitHub Integration Info",
        description="Automatic backup system for bot configuration",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="✨ Features",
        value="• 🤖 Auto-commits on every config change\n• 📋 Complete version history\n• 🔄 Manual sync command\n• 📊 Commit monitoring\n• 🔐 Secure token-based auth",
        inline=False
    )

    embed.add_field(
        name="📝 Automatic Commits",
        value="Every time you add/remove commands, automod words, or users via the admin panel, changes are automatically committed to GitHub!",
        inline=False
    )

    embed.add_field(
        name="🎯 Commands",
        value="`!github_status` - Check connection status\n`!github_sync` - Manually sync all files\n`!github_info` - Show this information",
        inline=False
    )

    embed.add_field(
        name="🔧 Setup Required",
        value="Set these environment variables on Render:\n```\nGITHUB_TOKEN=ghp_...\nGITHUB_REPO=username/repo\nGITHUB_BRANCH=main\n```",
        inline=False
    )

    # Check if configured
    from keep_alive import GITHUB_TOKEN, GITHUB_REPO

    if GITHUB_TOKEN and GITHUB_REPO:
        embed.add_field(
            name="✅ Status",
            value=f"GitHub integration is **configured**\nRepository: `{GITHUB_REPO}`",
            inline=False
        )
    else:
        embed.add_field(
            name="⚠️ Status",
            value="GitHub integration is **not configured**\nSet environment variables to enable",
            inline=False
        )

    embed.set_footer(text="All config changes are automatically backed up • View full guide with !help github")

    await ctx.send(embed=embed)


import discord
from discord.ext import commands
import os
import wavelink
from music_bot import setup_music_commands, play_next
import logging

# Your existing bot setup here (intents, prefix, etc.)
# bot = commands.Bot(command_prefix="!", intents=intents)

# Setup music commands
setup_music_commands(bot)


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    print(f"📊 Servers: {len(bot.guilds)}")
    setup_galaxy(bot, add_score, MASTER_ID)
    if not daily_galaxy_backup.is_running():
        daily_galaxy_backup.start()
    setup_booster_catch(bot, add_score, scores)
    try:
        # Dual Lavalink System - Primary + Fallback
        nodes = [
            wavelink.Node(
                identifier="PRIMARY",
                uri="wss://lavalinkv4.serenetia.com",
                password="https://dsc.gg/ajidevserver",
                retries=3
            ),
            wavelink.Node(
                identifier="FALLBACK",
                uri="wss://lava-v4.ajieblogs.eu.org:443",
                password="https://dsc.gg/ajidevserver",
                retries=2
            )
        ]

        await wavelink.Pool.connect(nodes=nodes, client=bot)
        print("🎵 Dual Lavalink system initialized!")
        print(f"   ├─ PRIMARY: lavalinkv4.serenetia.com")
        print(f"   └─ FALLBACK: lava-v4.ajieblogs.eu.org")
    except Exception as e:
        print(f"❌ Lavalink connection failed: {e}")
        print("⚠️ Music commands will not work without Lavalink")


@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    """Auto-play next song when current track ends"""
    player = payload.player
    if not player:
        return

    # Skip if player has skip_triggered flag (manual skip)
    if hasattr(player, 'skip_triggered') and player.skip_triggered:
        player.skip_triggered = False
        return

    # Only auto-play if track finished normally
    if payload.reason in ["finished", "loadFailed"]:
        ctx = getattr(player, 'ctx', None)
        if ctx:
            try:
                # Check if already transitioning
                from music_bot import is_playing_next
                if ctx.guild.id in is_playing_next and is_playing_next[ctx.guild.id]:
                    return

                import asyncio
                await asyncio.sleep(0.8)
                await play_next(ctx)
            except Exception as e:
                print(f"Error playing next track: {e}")
                try:
                    await ctx.send(f"❌ Error playing next track: {str(e)[:100]}")
                except:
                    pass


@bot.event
async def on_wavelink_track_start(payload: wavelink.TrackStartEventPayload):
    """Log when tracks start playing"""
    node_name = payload.player.node.identifier if payload.player and payload.player.node else "Unknown"
    track_title = payload.track.title if payload.track else "Unknown"
    print(f"▶️ [{node_name}] Started playing: {track_title}")


@bot.event
async def on_wavelink_track_exception(payload: wavelink.TrackExceptionEventPayload):
    """Handle track playback errors"""
    player = payload.player
    if hasattr(player, 'ctx'):
        ctx = player.ctx
        embed = discord.Embed(
            title="⚠️ Playback Issue",
            description="Track encountered an error. Skipping to next song...",
            color=discord.Color.orange()
        )
        try:
            await ctx.send(embed=embed)
        except:
            pass
        print(f"❌ Track exception: {payload.exception}")

        # Try to play next song
        try:
            from music_bot import get_queue
            q = get_queue(ctx.guild.id)
            q.is_transitioning = False
            if q.queue:
                import asyncio
                await asyncio.sleep(1)
                await play_next(ctx)
        except Exception as e:
            print(f"Error recovering from track exception: {e}")


@bot.event
async def on_wavelink_track_stuck(payload: wavelink.TrackStuckEventPayload):
    """Handle stuck tracks"""
    player = payload.player
    if hasattr(player, 'ctx'):
        ctx = player.ctx
        print(f"⚠️ Track stuck for {payload.threshold}ms on node {player.node.identifier}, skipping...")

        # Force skip to next track
        try:
            from music_bot import get_queue
            q = get_queue(ctx.guild.id)
            q.is_transitioning = False
            if player and player.connected:
                await player.stop()
            import asyncio
            await asyncio.sleep(1)
            await play_next(ctx)
        except Exception as e:
            print(f"Error recovering from stuck track: {e}")


@bot.event
async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload):
    """Called when Lavalink node is ready"""
    node = payload.node

    # Count players for this node
    players_count = 0
    for guild in bot.guilds:
        vc = guild.voice_client
        if vc and isinstance(vc, wavelink.Player) and vc.node == node:
            players_count += 1

    print(f"🎵 Lavalink node [{node.identifier}] is ready!")
    print(f"   └─ URI: {node.uri}")
    print(f"   └─ Players: {players_count}")


@bot.event
async def on_wavelink_websocket_closed(payload: wavelink.WebsocketClosedEventPayload):
    """Handle Lavalink disconnections"""
    print(f"⚠️ Lavalink websocket closed on node {payload.player.node.identifier if payload.player else 'Unknown'}")
    print(f"   └─ Reason: {payload.reason} (code: {payload.code})")

    # Attempt to switch to fallback node if primary fails
    if len(wavelink.Pool.nodes) > 1:
        print(f"🔄 Attempting to use fallback node...")


@bot.event
async def on_command_error(ctx, error):
    """Global error handler"""
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: `{error.param.name}`")
    elif isinstance(error, commands.CheckFailure):
        await ctx.send("❌ You don't have permission to use this command")
    elif isinstance(error, wavelink.LavalinkException):
        await ctx.send("⚠️ Music service temporarily unavailable. Please try again.")
        print(f"Lavalink error: {error}")
    else:
        await ctx.send(f"❌ Error: {str(error)[:100]}")
        print(f"Command error: {error}")


@bot.command()
async def voicetest(ctx):
    """Test voice connection step by step"""

    # Check 1: User in VC?
    if not ctx.author.voice:
        return await ctx.send("❌ Step 1 Failed: You're not in a VC")
    await ctx.send("✅ Step 1: You're in a VC")

    # Check 2: Bot has permissions?
    channel = ctx.author.voice.channel
    perms = channel.permissions_for(ctx.guild.me)
    if not perms.connect or not perms.speak:
        return await ctx.send("❌ Step 2 Failed: Missing Connect/Speak permissions")
    await ctx.send("✅ Step 2: Bot has permissions")

    # Check 3: Lavalink connected?
    try:
        nodes = list(wavelink.Pool.nodes.values()) if hasattr(wavelink.Pool, 'nodes') and isinstance(
            wavelink.Pool.nodes, dict) else []
    except:
        nodes = []

    if not nodes:
        return await ctx.send("❌ Step 3 Failed: No Lavalink nodes connected")

    connected_nodes = [n for n in nodes if n.status == wavelink.NodeStatus.CONNECTED]
    if not connected_nodes:
        return await ctx.send("❌ Step 3 Failed: All Lavalink nodes disconnected")

    await ctx.send(f"✅ Step 3: {len(connected_nodes)}/{len(nodes)} Lavalink nodes connected")

    # Check 4: Can connect?
    try:
        if ctx.voice_client:
            node_name = ctx.voice_client.node.identifier if hasattr(ctx.voice_client,
                                                                    'node') and ctx.voice_client.node else "Unknown"
            await ctx.send(f"✅ Step 4: Already connected to VC (Node: {node_name})")
        else:
            player = await channel.connect(cls=wavelink.Player)
            node_name = player.node.identifier if hasattr(player, 'node') and player.node else "Unknown"
            await ctx.send(f"✅ Step 4: Connected successfully! (Node: {node_name})")
    except Exception as e:
        await ctx.send(f"❌ Step 4 Failed: {e}")





@bot.command()
async def switchnode(ctx):
    """Switch to a different Lavalink node (if available)"""
    if not ctx.voice_client:
        return await ctx.send("❌ Not connected to a voice channel")

    try:
        nodes = list(wavelink.Pool.nodes.values()) if hasattr(wavelink.Pool, 'nodes') and isinstance(
            wavelink.Pool.nodes, dict) else []
    except:
        nodes = []

    if len(nodes) < 2:
        return await ctx.send("❌ No alternative nodes available")

    player = ctx.voice_client
    current_node = player.node if hasattr(player, 'node') else None

    if not current_node:
        return await ctx.send("❌ Unable to determine current node")

    # Find an alternative node
    alternative_nodes = [n for n in nodes
                         if n != current_node and n.status == wavelink.NodeStatus.CONNECTED]

    if not alternative_nodes:
        return await ctx.send("❌ No connected alternative nodes available")

    try:
        new_node = alternative_nodes[0]

        # Store current state
        was_playing = player.playing if hasattr(player, 'playing') else False
        current_position = player.position if hasattr(player, 'position') and player.current else 0
        current_track = player.current if hasattr(player, 'current') else None

        # Move to new node
        await player.move_to(new_node)

        embed = discord.Embed(
            title="🔄 Node Switched",
            description=f"**From:** {current_node.identifier}\n**To:** {new_node.identifier}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

        # Resume playback if it was playing
        if was_playing and current_track:
            await player.play(current_track, start=current_position)

    except Exception as e:
        await ctx.send(f"❌ Failed to switch node: {e}")

bot.run(TOKEN, log_handler=handler, log_level=logging.DEBUG)
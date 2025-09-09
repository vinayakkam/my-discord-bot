from keep_alive import keep_alive
keep_alive()
import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import time


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

@bot.event
async def on_member_join(member):
    # Replace CHANNEL_ID with the ID of the channel where you want to send welcome messages
    channel = bot.get_channel(1411426415450263585)
    if channel:  # Make sure the channel exists
        await channel.send(f"Welcome to the BumbleRat Burocrazy Simulator, {member.name}!")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if "shit" in message.content.lower():
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

@bot.tree.command(name="ping", description="Check the bot's latency", guild=GUILD)
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
    await interaction.edit_original_response(content=None, embed=embed)


bot.run(TOKEN, log_handler=handler, log_level=logging.DEBUG)
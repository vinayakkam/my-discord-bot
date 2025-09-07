import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import yt_dlp

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content=True
intents.members=True

bot=commands.Bot(command_prefix='!',intents=intents)

@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user.name}")

async def on_member_join(member):
    # Replace CHANNEL_ID with the ID of the channel where you want to send welcome messages
    channel = bot.get_channel(1210475350765604876)
    if channel:  # Make sure the channel exists
        await channel.send(f"Welcome to the BumbleRat Bureaucracy Simulator, {member.name}!")


@bot.command()
async def join(ctx):
    """Make the bot join the voice channel"""
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send(f"Joined {channel}")
    else:
        await ctx.send("You need to be in a voice channel first!")

@bot.command()
async def leave(ctx):
    """Disconnect the bot from voice"""
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Left the voice channel.")
    else:
        await ctx.send("I'm not in a voice channel.")

@bot.command()
async def play(ctx, url):
    """Play music from a YouTube URL"""
    if not ctx.voice_client:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            await ctx.send("Join a voice channel first!")
            return

    vc = ctx.voice_client
    if vc.is_playing():
        vc.stop()

    ydl_opts = {'format': 'bestaudio', 'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        audio_url = info['url']

    source = await discord.FFmpegOpusAudio.from_probe(audio_url, method='fallback')
    vc.play(source)
    await ctx.send(f"🎶 Now playing: {info['title']}")

@bot.command()
async def stop(ctx):
    """Stop music"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏹️ Stopped the music.")
    else:
        await ctx.send("No music is playing.")

@bot.command()
async def pause(ctx):
    """Pause music"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ Paused.")
    else:
        await ctx.send("No music is playing.")

@bot.command()
async def resume(ctx):
    """Resume music"""
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ Resumed.")
    else:
        await ctx.send("Music is not paused.")
    
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
    await ctx.send(f"!hello")

bot.run(TOKEN, log_handler=handler, log_level=logging.DEBUG)
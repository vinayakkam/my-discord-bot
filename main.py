import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os

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

@bot.event
async def on_member_join(member):
    await member.send(f"Welcome to the BumbleRat Burocracy Simulator {member.name}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Trigger → list of 3 custom emoji IDs
    triggers = {
        "appbcbash": [
            1414188725163790336,  # replace with your 1st emoji ID
            1414192630165667872,  # replace with your 2nd emoji ID
            1414192628010061824   # replace with your 3rd emoji ID
        ],
        "appbce": [1414188725163790336],
        "appbaa": [1414192630165667872],
        "appsher": [1414192628010061824]
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
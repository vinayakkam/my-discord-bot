from keep_alive import keep_alive
keep_alive()
import discord
from discord.ext import commands, tasks
import logging
from dotenv import load_dotenv
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

# In-memory scoreboard: {user_id: score}
scores = {}

def add_score(user_id, points=1):
    """Increment a user's score."""
    scores[user_id] = scores.get(user_id, 0) + points

# -----------------------------------
# 1️⃣ Rock Paper Scissors
# -----------------------------------
@bot.command(name="rps")
async def rps(ctx, choice: str = None):
    options = ["rock", "paper", "scissors"]

    if choice is None or choice.lower() not in options:
        embed = discord.Embed(
            title="🪨📄✂️ Rock Paper Scissors",
            description="Please choose rock, paper, or scissors.\nExample: `!rps rock`",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    user_choice = choice.lower()
    bot_choice = random.choice(options)

    if user_choice == bot_choice:
        result = "It's a draw! 🤝"
    elif (
        (user_choice == "rock" and bot_choice == "scissors")
        or (user_choice == "paper" and bot_choice == "rock")
        or (user_choice == "scissors" and bot_choice == "paper")
    ):
        result = "You win! 🎉 (+1 point)"
        add_score(ctx.author.id, 1)
    else:
        result = "You lose! 😢"

    embed = discord.Embed(
        title="🪨📄✂️ Rock Paper Scissors",
        color=discord.Color.blue()
    )
    embed.add_field(name="Your Choice", value=user_choice.capitalize())
    embed.add_field(name="Bot's Choice", value=bot_choice.capitalize())
    embed.add_field(name="Result", value=result, inline=False)
    await ctx.send(embed=embed)

# -----------------------------------
# 2️⃣ Coin Flip
# -----------------------------------
@bot.command(name="coinflip")
async def coinflip(ctx, guess: str = None):
    """Flip a coin. Usage: !coinflip heads/tails"""
    result = random.choice(["heads", "tails"])

    if guess and guess.lower() in ["heads", "tails"]:
        if guess.lower() == result:
            desc = f"It’s **{result.capitalize()}**! You guessed right 🎉 (+1 point)"
            add_score(ctx.author.id, 1)
        else:
            desc = f"It’s **{result.capitalize()}**! You guessed wrong 😢"
    else:
        desc = f"It’s **{result.capitalize()}**!"

    embed = discord.Embed(
        title="🪙 Coin Flip",
        description=desc,
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)

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
@bot.command(name="guess")
async def guess(ctx):
    number = random.randint(1, 10)

    prompt_embed = discord.Embed(
        title="🔢 Number Guessing Game",
        description="I picked a number between **1 and 10**. Type your guess below! (15s timeout)",
        color=discord.Color.purple()
    )
    await ctx.send(embed=prompt_embed)

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()

    try:
        guess_msg = await bot.wait_for("message", timeout=15.0, check=check)
        guess_num = int(guess_msg.content)
        if guess_num == number:
            result_embed = discord.Embed(
                title="🎉 Correct!",
                description=f"You guessed it! The number was **{number}** (+1 point).",
                color=discord.Color.green()
            )
            add_score(ctx.author.id, 1)
        else:
            result_embed = discord.Embed(
                title="😢 Wrong Guess",
                description=f"Nope, the number was **{number}**.",
                color=discord.Color.red()
            )
        await ctx.send(embed=result_embed)
    except:
        timeout_embed = discord.Embed(
            title="⏳ Timeout",
            description="You took too long to respond. Try again!",
            color=discord.Color.red()
        )
        await ctx.send(embed=timeout_embed)

# -----------------------------------
# 5️⃣ Scoreboard Commands
# -----------------------------------
@bot.command(name="score")
async def score(ctx, member: discord.Member = None):
    """Check your or another member's score."""
    member = member or ctx.author
    score_value = scores.get(member.id, 0)
    embed = discord.Embed(
        title="🏆 Score",
        description=f"**{member.display_name}** has **{score_value}** points.",
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed)

LEADER_ROLE_ID = 1415720279631593573  # 🔹 paste your role ID here

@bot.command(name="leaderboard")
async def leaderboard(ctx):
    """Show the leaderboard and auto-assign Leader role."""
    if not scores:  # scores should be your loaded dict
        await ctx.send("⚠️ No scores available yet.")
        return

    # Sort scores (highest first)
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_10 = sorted_scores[:10]

    # 🟩 Build leaderboard text
    leaderboard_text = ""
    for i, (user_id, score) in enumerate(top_10, start=1):
        member = ctx.guild.get_member(int(user_id))
        name = member.display_name if member else f"User {user_id}"
        leaderboard_text += f"**{i}.** {name} — {score} points\n"

    # 🟩 Send embed
    embed = discord.Embed(
        title="🏆 Leaderboard",
        description=leaderboard_text,
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)

    # 🟩 Now handle Leader role assignment automatically
    try:
        # Get top user ID
        top_user_id = int(sorted_scores[0][0])
        top_member = ctx.guild.get_member(top_user_id)

        # Get the role
        role = ctx.guild.get_role(LEADER_ROLE_ID)
        if role is None:
            await ctx.send(f"⚠️ Role with ID `{LEADER_ROLE_ID}` not found. Please check the ID.")
            return

        # Remove role from everyone else
        for member in ctx.guild.members:
            if role in member.roles and member.id != top_user_id:
                try:
                    await member.remove_roles(role)
                except discord.Forbidden:
                    await ctx.send("⚠️ I lack permission to remove roles.")
                    return

        # Add role to the top player if not already
        if top_member and role not in top_member.roles:
            try:
                await top_member.add_roles(role)
                await ctx.send(f"🏅 {top_member.mention} is now the **Leaderboard Leader**!")
            except discord.Forbidden:
                await ctx.send("⚠️ I lack permission to add roles.")
    except Exception as e:
        await ctx.send(f"⚠️ Error assigning Leader role: `{e}`")

# 60 Space Trivia Questions (20 each difficulty)
TRIVIA_QUESTIONS = {
    "easy": [
        {"question": "Which planet is closest to the Sun?", "options": ["Mercury", "Venus", "Earth"], "answer": "Mercury"},
        {"question": "Which planet is known as the Red Planet?", "options": ["Mars", "Venus", "Jupiter"], "answer": "Mars"},
        {"question": "What galaxy is Earth located in?", "options": ["Milky Way", "Andromeda", "Triangulum"], "answer": "Milky Way"},
        {"question": "Which planet has rings visible from Earth?", "options": ["Saturn", "Jupiter", "Neptune"], "answer": "Saturn"},
        {"question": "Which planet has the Great Red Spot?", "options": ["Jupiter", "Mars", "Saturn"], "answer": "Jupiter"},
        {"question": "What is the smallest planet in our solar system?", "options": ["Mercury", "Mars", "Venus"], "answer": "Mercury"},
        {"question": "What is the Sun mostly made of?", "options": ["Hydrogen", "Oxygen", "Helium"], "answer": "Hydrogen"},
        {"question": "Which planet is famous for its rings?", "options": ["Saturn", "Uranus", "Neptune"], "answer": "Saturn"},
        {"question": "Which is the third planet from the Sun?", "options": ["Earth", "Venus", "Mars"], "answer": "Earth"},
        {"question": "Which is the hottest planet?", "options": ["Venus", "Mercury", "Mars"], "answer": "Venus"},
        {"question": "What is the Moon’s gravitational pull compared to Earth?", "options": ["1/6th", "1/2", "1/10th"], "answer": "1/6th"},
        {"question": "Which planet rotates on its side?", "options": ["Uranus", "Neptune", "Venus"], "answer": "Uranus"},
        {"question": "Which planet has the fastest rotation?", "options": ["Jupiter", "Saturn", "Earth"], "answer": "Jupiter"},
        {"question": "What’s the name of Earth’s only natural satellite?", "options": ["Moon", "Phobos", "Europa"], "answer": "Moon"},
        {"question": "Which planet has Olympus Mons?", "options": ["Mars", "Earth", "Venus"], "answer": "Mars"},
        {"question": "How many planets are in the Solar System?", "options": ["8", "9", "7"], "answer": "8"},
        {"question": "Which planet has a day longer than its year?", "options": ["Venus", "Mercury", "Mars"], "answer": "Venus"},
        {"question": "Who was the first human in space?", "options": ["Yuri Gagarin", "Neil Armstrong", "Buzz Aldrin"], "answer": "Yuri Gagarin"},
        {"question": "What is the name of our star?", "options": ["Sun", "Sirius", "Proxima"], "answer": "Sun"},
        {"question": "What do we call a large rock in space?", "options": ["Asteroid", "Comet", "Meteor"], "answer": "Asteroid"},
    ],
    "medium": [
        {"question": "Which planet has the most moons?", "options": ["Saturn", "Jupiter", "Neptune"], "answer": "Saturn"},
        {"question": "What’s the name of the first artificial satellite?", "options": ["Sputnik 1", "Explorer 1", "Vostok 1"], "answer": "Sputnik 1"},
        {"question": "Which planet is tilted at 98 degrees?", "options": ["Uranus", "Neptune", "Saturn"], "answer": "Uranus"},
        {"question": "How many planets have rings?", "options": ["4", "2", "1"], "answer": "4"},
        {"question": "Which dwarf planet is in the asteroid belt?", "options": ["Ceres", "Pluto", "Eris"], "answer": "Ceres"},
        {"question": "Which planet has the fastest winds?", "options": ["Neptune", "Saturn", "Mars"], "answer": "Neptune"},
        {"question": "Which space telescope launched in 1990?", "options": ["Hubble", "Kepler", "Chandra"], "answer": "Hubble"},
        {"question": "What’s the largest planet?", "options": ["Jupiter", "Saturn", "Neptune"], "answer": "Jupiter"},
        {"question": "What’s the coldest planet?", "options": ["Neptune", "Uranus", "Pluto"], "answer": "Neptune"},
        {"question": "Which mission first landed humans on the Moon?", "options": ["Apollo 11", "Apollo 12", "Apollo 10"], "answer": "Apollo 11"},
        {"question": "Which planet has methane lakes?", "options": ["Titan (moon)", "Mars", "Venus"], "answer": "Titan (moon)"},
        {"question": "What’s the name of Mars’ largest moon?", "options": ["Phobos", "Deimos", "Europa"], "answer": "Phobos"},
        {"question": "What does NASA stand for?", "options": ["National Aeronautics and Space Administration", "National Aerospace and Space Association", "New Aeronautics Space Agency"], "answer": "National Aeronautics and Space Administration"},
        {"question": "Which probe left the solar system first?", "options": ["Voyager 1", "Voyager 2", "Pioneer 10"], "answer": "Voyager 1"},
        {"question": "What’s the densest planet?", "options": ["Earth", "Jupiter", "Venus"], "answer": "Earth"},
        {"question": "Which planet has the tallest known mountain?", "options": ["Mars", "Venus", "Mercury"], "answer": "Mars"},
        {"question": "What’s the most common type of star?", "options": ["Red Dwarf", "White Dwarf", "Blue Giant"], "answer": "Red Dwarf"},
        {"question": "What’s the boundary of a black hole called?", "options": ["Event Horizon", "Singularity", "Accretion Disk"], "answer": "Event Horizon"},
        {"question": "What is the main gas of Neptune?", "options": ["Hydrogen", "Methane", "Oxygen"], "answer": "Methane"},
        {"question": "Which planet’s day is about 10 hours long?", "options": ["Jupiter", "Mars", "Saturn"], "answer": "Jupiter"},
    ],
    "hard": [
        {"question": "Which moon has the highest albedo (reflectivity)?", "options": ["Enceladus", "Europa", "Ganymede"], "answer": "Enceladus"},
        {"question": "What’s the average distance from Earth to the Sun?", "options": ["1 AU", "93 million miles", "Both"], "answer": "Both"},
        {"question": "Which planet has a hexagon-shaped storm?", "options": ["Saturn", "Jupiter", "Neptune"], "answer": "Saturn"},
        {"question": "What’s the densest moon?", "options": ["Io", "Europa", "Titan"], "answer": "Io"},
        {"question": "Which spacecraft carried the Golden Record?", "options": ["Voyager", "Pioneer", "New Horizons"], "answer": "Voyager"},
        {"question": "What’s the most volcanically active body?", "options": ["Io", "Earth", "Venus"], "answer": "Io"},
        {"question": "How long does sunlight take to reach Earth?", "options": ["8 minutes", "5 minutes", "10 minutes"], "answer": "8 minutes"},
        {"question": "Which exoplanet was the first discovered?", "options": ["51 Pegasi b", "Kepler-22b", "Proxima b"], "answer": "51 Pegasi b"},
        {"question": "What’s the approximate age of the Universe?", "options": ["13.8 billion years", "10 billion years", "15 billion years"], "answer": "13.8 billion years"},
        {"question": "What’s the smallest exoplanet discovered (as of now)?", "options": ["Kepler-37b", "Proxima b", "TRAPPIST-1d"], "answer": "Kepler-37b"},
        {"question": "Which star is closest to our Solar System?", "options": ["Proxima Centauri", "Alpha Centauri A", "Barnard’s Star"], "answer": "Proxima Centauri"},
        {"question": "What’s at the center of the Milky Way?", "options": ["Black Hole", "Neutron Star", "Dark Matter Cloud"], "answer": "Black Hole"},
        {"question": "What element powers the Sun?", "options": ["Hydrogen fusion", "Helium fusion", "Oxygen burning"], "answer": "Hydrogen fusion"},
        {"question": "Which mission landed on Titan?", "options": ["Huygens", "Viking", "New Horizons"], "answer": "Huygens"},
        {"question": "Which planet has a moon called Triton?", "options": ["Neptune", "Uranus", "Saturn"], "answer": "Neptune"},
        {"question": "Which galaxy is colliding with the Milky Way?", "options": ["Andromeda", "Triangulum", "Whirlpool"], "answer": "Andromeda"},
        {"question": "Which type of star explodes as a supernova?", "options": ["Massive Star", "Brown Dwarf", "Red Dwarf"], "answer": "Massive Star"},
        {"question": "What’s the approximate escape velocity from Earth?", "options": ["11.2 km/s", "7.9 km/s", "15 km/s"], "answer": "11.2 km/s"},
        {"question": "Which moon has a subsurface ocean beneath its ice crust?", "options": ["Europa", "Enceladus", "Callisto"], "answer": "Europa"},
        {"question": "What’s the name of the region of icy bodies beyond Neptune?", "options": ["Kuiper Belt", "Oort Cloud", "Asteroid Belt"], "answer": "Kuiper Belt"},
    ],
}

LETTERS = ["A", "B", "C"]

@bot.command(name="trivia")
async def trivia(ctx, difficulty: str = None):
    """Ask a random trivia question. Difficulty: easy/medium/hard."""
    difficulty = (difficulty or "easy").lower()
    if difficulty not in TRIVIA_QUESTIONS:
        await ctx.send("⚠️ Please choose a difficulty: `easy`, `medium`, or `hard`.\nExample: `!trivia medium`")
        return

    q = random.choice(TRIVIA_QUESTIONS[difficulty])

    # Shuffle answers & assign A/B/C dynamically
    options = q["options"][:3]
    random.shuffle(options)
    letter_to_option = {LETTERS[i]: options[i] for i in range(len(options))}
    correct_letter = next((L for L, O in letter_to_option.items()
                           if O.lower() == q["answer"].lower()), None)

    points = 1 if difficulty == "easy" else 2 if difficulty == "medium" else 3

    question_text = f"**[{difficulty.upper()} — {points} point(s)]**\n\n{q['question']}\n\n" + "\n".join(
        [f"{L}) {O}" for L, O in letter_to_option.items()]) + "\n\nType A, B, or C in chat (90s)."
    embed = discord.Embed(title="🎓 Space Trivia Time!",
                          description=question_text,
                          color=discord.Color.teal())
    await ctx.send(embed=embed)

    def check(m):
        return (m.author == ctx.author and
                m.channel == ctx.channel and
                m.content.upper() in letter_to_option.keys())

    try:
        reply = await bot.wait_for("message", timeout=90.0, check=check)
    except Exception:
        timeout_embed = discord.Embed(
            title="⏳ Timeout",
            description="You took too long to answer.",
            color=discord.Color.red())
        await ctx.send(embed=timeout_embed)
        return

    chosen = reply.content.upper()
    chosen_answer = letter_to_option[chosen]

    if chosen == correct_letter:
        add_score(ctx.author.id, points)
        total = scores.get(str(ctx.author.id), 0)
        success_embed = discord.Embed(
            title="✅ Correct!",
            description=f"You answered **{chosen}) {chosen_answer}** — +{points} point(s)!\nTotal points: **{total}**",
            color=discord.Color.green())
        await ctx.send(embed=success_embed)
    else:
        fail_embed = discord.Embed(
            title="❌ Wrong",
            description=f"You answered **{chosen}) {chosen_answer}**.\nCorrect answer: **{correct_letter}) {q['answer']}**.",
            color=discord.Color.red())
        await ctx.send(embed=fail_embed)



# -----------------------------------
# 7️⃣ Math Quiz
# -----------------------------------
@bot.command(name="mathquiz")
async def mathquiz(ctx):
    """Ask a random math question — handles negatives and harder problems."""
    # Random numbers: allow negative numbers sometimes
    a = random.randint(-20, 20)
    b = random.randint(-20, 20)

    # Make sure we don’t divide by zero
    op = random.choice(["+", "-", "*", "//"])
    if op == "//":
        while b == 0:  # re-pick if zero
            b = random.randint(-20, 20)

    question = f"{a} {op} {b}"
    answer = eval(question)

    # Pretty operator name for embed
    op_name = {"//": "÷ (integer division)", "+": "+", "-": "-", "*": "×"}[op]

    embed = discord.Embed(
        title="🧮 Math Quiz",
        description=f"Solve: **{a} {op_name} {b}** (60s timeout)",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)

    def check(m):
        # Accept negative numbers with a leading '-' sign
        content = m.content.strip()
        if content.startswith("-"):
            return content[1:].isdigit() and m.author == ctx.author and m.channel == ctx.channel
        return content.isdigit() and m.author == ctx.author and m.channel == ctx.channel

    try:
        msg = await bot.wait_for("message", timeout=60.0, check=check)
        if int(msg.content) == answer:
            # Add point to your existing scoreboard system
            add_score(ctx.author.id, 1)
            total_points = scores.get(str(ctx.author.id), 0)

            result_embed = discord.Embed(
                title="✅ Correct!",
                description=f"You solved it! (+1 point)\nTotal points: **{total_points}**",
                color=discord.Color.green()
            )
        else:
            result_embed = discord.Embed(
                title="❌ Wrong",
                description=f"The correct answer was **{answer}**.",
                color=discord.Color.red()
            )
        await ctx.send(embed=result_embed)

    except:
        timeout_embed = discord.Embed(
            title="⏳ Timeout",
            description="You took too long to answer.",
            color=discord.Color.red()
        )
        await ctx.send(embed=timeout_embed)

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

@bot.command(name="unscramble")
async def unscramble(ctx, difficulty: str = None):
    """
    Unscramble game with difficulty.
    Usage: !unscramble easy / medium / hard
    """
    difficulty = (difficulty or "easy").lower()
    if difficulty not in UNSCRAMBLE_WORDS:
        await ctx.send("⚠️ Please choose a difficulty: `easy`, `medium`, or `hard`.\nExample: `!unscramble medium`")
        return

    word = random.choice(UNSCRAMBLE_WORDS[difficulty])
    scrambled = ''.join(random.sample(word, len(word)))

    # Point system by difficulty
    points = 1 if difficulty == "easy" else 2 if difficulty == "medium" else 3

    embed = discord.Embed(
        title="🔤 Word Unscramble",
        description=f"**[{difficulty.upper()} — {points} point(s)]**\n\nUnscramble this word: **{scrambled}** (60s timeout)",
        color=discord.Color.purple()
    )
    await ctx.send(embed=embed)

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        msg = await bot.wait_for("message", timeout=60.0, check=check)
        if msg.content.lower() == word.lower():
            add_score(ctx.author.id, points)
            total = scores.get(str(ctx.author.id), 0)
            result_embed = discord.Embed(
                title="✅ Correct!",
                description=f"You unscrambled it! +{points} point(s)\nTotal points: **{total}**",
                color=discord.Color.green()
            )
        else:
            result_embed = discord.Embed(
                title="❌ Wrong",
                description=f"The word was **{word}**.",
                color=discord.Color.red()
            )
        await ctx.send(embed=result_embed)
    except:
        timeout_embed = discord.Embed(
            title="⏳ Timeout",
            description="You took too long to answer.",
            color=discord.Color.red()
        )
        await ctx.send(embed=timeout_embed)

@bot.command(name="starship")
async def starship(ctx):
    """
    Interactive Starship success predictor.
    Asks a few questions and returns a simulated success probability.
    Awards +1 participation point via add_score() if available.
    """
    try:
        # Questions and options
        questions = [
            {
                "prompt": "1) Weather at launch: Choose one\nA) Excellent (clear, low wind)\nB) Moderate (some wind/clouds)\nC) Poor (high wind/storm)",
                "options": {"A": "excellent", "B": "moderate", "C": "poor"},
                "weights": {"excellent": 0.20, "moderate": 0.0, "poor": -0.20}
            },
            {
                "prompt": "2) Vehicle condition: Choose one\nA) Freshly inspected & nominal\nB) Refurb / marginal\nC) Unknown / rushed",
                "options": {"A": "fresh", "B": "refurb", "C": "unknown"},
                "weights": {"fresh": 0.15, "refurb": 0.0, "unknown": -0.15}
            },
            {
                "prompt": "3) Payload mass relative to planned:\nA) Light (< planned)\nB) Nominal (as-planned)\nC) Heavy (> planned)",
                "options": {"A": "light", "B": "nominal", "C": "heavy"},
                "weights": {"light": 0.10, "nominal": 0.0, "heavy": -0.10}
            },
            {
                "prompt": "4) Recent test experience:\nA) Many successful recent tests\nB) Some tests, mixed results\nC) Few/no tests recently",
                "options": {"A": "many", "B": "some", "C": "few"},
                "weights": {"many": 0.15, "some": 0.0, "few": -0.15}
            }
        ]

        answers = {}
        total_weight = 0.0

        # Helper check for replies
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.strip().upper() in ["A","B","C"]

        # Ask each question
        for q in questions:
            await ctx.send(embed=discord.Embed(
                title="Starship Launch Predictor",
                description=q["prompt"] + "\n\nReply with A, B or C (15s).",
                color=discord.Color.dark_teal()
            ))

            try:
                msg = await bot.wait_for("message", timeout=15.0, check=check)
            except Exception:
                await ctx.send(embed=discord.Embed(
                    title="⏳ Timeout",
                    description="You took too long to answer. Run `!starship` again when ready.",
                    color=discord.Color.red()
                ))
                return

            choice = msg.content.strip().upper()
            selected_key = q["options"][choice]
            answers[q["prompt"].split("\n")[0]] = selected_key  # store short key
            total_weight += q["weights"].get(selected_key, 0.0)

        # Base probability (a plausible mid value), then apply weights
        base = 0.55  # 55% baseline for a complex heavy rocket — arbitrary for game
        prob = base + total_weight

        # Add a small random noise to simulate uncertainty
        noise = random.uniform(-0.08, 0.08)
        prob += noise

        # Clamp 0..1
        prob = max(0.01, min(0.99, prob))
        percent = int(round(prob * 100))

        # Build explanation lines
        lines = []
        for i, q in enumerate(questions, start=1):
            key = list(q["options"].values())[list(q["options"].keys()).index(list(q["options"].keys())[0])]  # placeholder (we'll use answers)
        # Better explanation using answers and weights:
        explanation = []
        for q in questions:
            # find prompt title
            title = q["prompt"].split("\n")[0]
            # find the user's choice key (we stored earlier)
            user_choice = answers.get(title)
            weight = q["weights"].get(user_choice, 0.0)
            sign = "+" if weight > 0 else ""
            explanation.append(f"**{title}** — {user_choice.capitalize()} ({sign}{weight:+.2f})")

        # Format a final embed
        embed = discord.Embed(
            title="🚀 Starship Success Predictor",
            description=f"Predicted chance of a successful flight: **{percent}%**",
            color=discord.Color.blue()
        )
        embed.add_field(name="Quick breakdown", value="\n".join(explanation), inline=False)
        embed.add_field(name="Notes", value=(
            "This is a playful simulation — not a real forecast. "
            "Factors are simplified into categories and a bit of randomness."
        ), inline=False)
        embed.set_footer(text=f"Random variance: {int(round(noise*100))}% | Base {int(base*100)}%")

        await ctx.send(embed=embed)

        # Give a participation point if add_score exists
        try:
            if 'add_score' in globals():
                add_score(ctx.author.id, 1)
        except Exception:
            # ignore score errors, but don't crash
            pass

    except Exception as e:
        import traceback
        traceback.print_exc()
        await ctx.send(embed=discord.Embed(
            title="⚠️ Error",
            description="Something went wrong running the predictor. Check the bot logs.",
            color=discord.Color.dark_red()
        ))

@bot.command(name="predict")
async def predict(ctx):
    """
    Simulate Starship ship-only launch success chance based on test outcomes.
    Asks for the ship name first.
    """

    # 1️⃣ Ask for ship name first
    ask_name = discord.Embed(
        title="🚀 Starship Ship Simulation",
        description="Please enter the **Ship Name** (e.g. `S38`) within 15s:",
        color=discord.Color.dark_blue()
    )
    await ctx.send(embed=ask_name)

    def name_check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        name_msg = await bot.wait_for("message", timeout=15.0, check=name_check)
        ship_name = name_msg.content.strip()
    except:
        await ctx.send(embed=discord.Embed(
            title="⏳ Timeout",
            description="You didn’t provide a ship name in time. Cancelling simulation.",
            color=discord.Color.red()
        ))
        return

    # 2️⃣ Define the tests
    tests = [
        "Heat shield tile test",
        "Propellant tank pressure test",
        "RCS thruster test",
        "Vacuum engine static fire",
        "Flight control surfaces test"
    ]

    # Store answers as 'success', 'partial', 'failure'
    user_answers = {}

    # 3️⃣ Ask the test questions one by one
    for test_name in tests:
        embed = discord.Embed(
            title=f"🚀 Testing {ship_name}",
            description=(
                f"**{test_name}**\n"
                f"Reply with `success`, `partial`, or `failure` (15s timeout)."
            ),
            color=discord.Color.dark_blue()
        )
        await ctx.send(embed=embed)

        def check(m):
            return (
                m.author == ctx.author
                and m.channel == ctx.channel
                and m.content.lower() in ["success", "partial", "failure"]
            )

        try:
            msg = await bot.wait_for("message", timeout=15.0, check=check)
            user_answers[test_name] = msg.content.lower()
        except:
            await ctx.send(embed=discord.Embed(
                title="⏳ Timeout",
                description=f"No answer for **{test_name}**, counting as failure.",
                color=discord.Color.red()
            ))
            user_answers[test_name] = "failure"

    # 4️⃣ Compute chance of success based on answers
    score = 0
    for ans in user_answers.values():
        if ans == "success":
            score += 3
        elif ans == "partial":
            score += 1
        # failure = 0

    # Max possible = 5 tests × 3 points = 15
    chance = int((score / 15) * 100)

    # Add random ±5% variability to simulate unknown factors
    chance += random.randint(-5, 5)
    chance = max(0, min(chance, 100))

    # 5️⃣ Create result embed
    result = discord.Embed(
        title=f"🚀 Starship {ship_name} Ship-Only Launch Simulation",
        description=(
            f"Based on your test results for **{ship_name}**:\n\n"
            f"🟩 **{list(user_answers.values()).count('success')} successes**\n"
            f"🟨 **{list(user_answers.values()).count('partial')} partials**\n"
            f"🟥 **{list(user_answers.values()).count('failure')} failures**\n\n"
            f"🔮 **Predicted Launch Success Chance: {chance}%**"
        ),
        color=discord.Color.green() if chance >= 50 else discord.Color.red()
    )

    await ctx.send(embed=result)

    # ✅ Award +1 point for participating (if you have add_score)
    try:
        add_score(ctx.author.id, 1)
    except Exception as e:
        print("add_score error:", e)


player_states = {}  # user_id → state dict

class MissionView(discord.ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=None)
        self.author_id = author_id  # the owner of this mission

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Allow only the original user to click buttons."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "⚠️ This mission’s buttons belong to someone else. You can start your own with `!mission`.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="🚀 Launch", style=discord.ButtonStyle.primary)
    async def launch(self, interaction: discord.Interaction, button: discord.ui.Button):
        await mission_launch(interaction)

    @discord.ui.button(label="⛽ Refuel", style=discord.ButtonStyle.success)
    async def refuel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await mission_refuel(interaction)

    @discord.ui.button(label="🔬 Research", style=discord.ButtonStyle.secondary)
    async def research(self, interaction: discord.Interaction, button: discord.ui.Button):
        await mission_research(interaction)

    @discord.ui.button(label="📊 Status", style=discord.ButtonStyle.gray)
    async def status(self, interaction: discord.Interaction, button: discord.ui.Button):
        await mission_status(interaction)


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

    # view only works for this author
    view = MissionView(ctx.author.id)
    await ctx.send(embed=embed, view=view)


# ----- Mission Logic -----

async def mission_status(interaction):
    """Show public status embed (anyone can see)."""
    state = player_states.get(interaction.user.id)
    embed = discord.Embed(
        title=f"📊 Starship Status for {interaction.user.display_name}",
        description=f"**Fuel:** {state['fuel']}\n"
                    f"**Food:** {state['food']}\n"
                    f"**Research:** {state['research']}\n"
                    f"**Turns:** {state['turns']}",
        color=discord.Color.green()
    )
    # Status visible to everyone
    await interaction.response.send_message(embed=embed, ephemeral=False)


async def mission_launch(interaction):
    state = player_states.get(interaction.user.id)
    fuel_cost = random.randint(5, 10)
    food_cost = random.randint(3, 8)
    state["fuel"] -= fuel_cost
    state["food"] -= food_cost
    state["turns"] += 1
    event_text = f"You launched forward, using **{fuel_cost} fuel** and **{food_cost} food**."

    if random.random() < 0.3:
        bonus = random.randint(5, 15)
        state["research"] += bonus
        event_text += f"\nYou discovered alien tech! **+{bonus} research points**."

    if state["fuel"] <= 0 or state["food"] <= 0:
        state["active"] = False
        embed = discord.Embed(
            title="💥 Mission Failed",
            description=f"You ran out of resources after {state['turns']} turns.",
            color=discord.Color.red()
        )
    else:
        embed = discord.Embed(title="🚀 Launch", description=event_text, color=discord.Color.blue())

    # Action reply private
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def mission_refuel(interaction):
    state = player_states.get(interaction.user.id)
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


async def mission_research(interaction):
    state = player_states.get(interaction.user.id)
    food_cost = random.randint(3, 8)
    state["food"] -= food_cost
    state["turns"] += 1
    gain = random.randint(5, 20)
    state["research"] += gain

    if state["fuel"] <= 0 or state["food"] <= 0:
        state["active"] = False
        embed = discord.Embed(
            title="💥 Mission Failed",
            description=f"You ran out of resources after {state['turns']} turns.",
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
    """Start the Rocket Design Quiz."""
    rocket_design_states[ctx.author.id] = {
        "step": 1,
        "engine": None,
        "tank": None,
        "payload": None
    }

    embed = discord.Embed(
        title="🚀 Rocket Design Quiz",
        description="Welcome! First choose your **engine**:\n\n1️⃣ Raptor (high thrust)\n2️⃣ Merlin (balanced)\n3️⃣ Ion Drive (low thrust, efficient)\n\nReply with 1, 2, or 3.",
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed)

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content in ["1", "2", "3"]

    try:
        msg = await bot.wait_for("message", timeout=30.0, check=check)
    except:
        await ctx.send("⏳ Timeout — game cancelled.")
        rocket_design_states.pop(ctx.author.id, None)
        return

    choice = msg.content
    if choice == "1":
        rocket_design_states[ctx.author.id]["engine"] = "Raptor"
    elif choice == "2":
        rocket_design_states[ctx.author.id]["engine"] = "Merlin"
    else:
        rocket_design_states[ctx.author.id]["engine"] = "Ion Drive"

    # Ask tank size
    embed = discord.Embed(
        title="⛽ Tank Size",
        description="Now choose your **tank size**:\n\n1️⃣ Large Tank (more fuel)\n2️⃣ Medium Tank\n3️⃣ Small Tank (lighter)",
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed)

    try:
        msg = await bot.wait_for("message", timeout=30.0, check=check)
    except:
        await ctx.send("⏳ Timeout — game cancelled.")
        rocket_design_states.pop(ctx.author.id, None)
        return

    choice = msg.content
    if choice == "1":
        rocket_design_states[ctx.author.id]["tank"] = "Large"
    elif choice == "2":
        rocket_design_states[ctx.author.id]["tank"] = "Medium"
    else:
        rocket_design_states[ctx.author.id]["tank"] = "Small"

    # Ask payload
    embed = discord.Embed(
        title="📦 Payload",
        description="Finally choose your **payload**:\n\n1️⃣ Satellite\n2️⃣ Crew Capsule\n3️⃣ Heavy Cargo",
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed)

    try:
        msg = await bot.wait_for("message", timeout=30.0, check=check)
    except:
        await ctx.send("⏳ Timeout — game cancelled.")
        rocket_design_states.pop(ctx.author.id, None)
        return

    choice = msg.content
    if choice == "1":
        rocket_design_states[ctx.author.id]["payload"] = "Satellite"
    elif choice == "2":
        rocket_design_states[ctx.author.id]["payload"] = "Crew Capsule"
    else:
        rocket_design_states[ctx.author.id]["payload"] = "Heavy Cargo"

    # Now compute success chance
    engine = rocket_design_states[ctx.author.id]["engine"]
    tank = rocket_design_states[ctx.author.id]["tank"]
    payload = rocket_design_states[ctx.author.id]["payload"]

    # Base chance
    success_chance = 50

    # Adjust based on engine
    if engine == "Raptor":
        success_chance += 15
    elif engine == "Ion Drive":
        success_chance -= 10

    # Adjust based on tank
    if tank == "Large":
        success_chance += 10
    elif tank == "Small":
        success_chance -= 5

    # Adjust based on payload
    if payload == "Heavy Cargo":
        success_chance -= 15
    elif payload == "Satellite":
        success_chance += 5

    result = random.randint(1, 100)
    if result <= success_chance:
        points = 2  # Award points on success
        add_score(ctx.author.id, points)
        total = scores.get(str(ctx.author.id), 0)
        embed = discord.Embed(
            title="✅ Launch Successful!",
            description=f"Your rocket launched successfully!\nEngine: **{engine}**\nTank: **{tank}**\nPayload: **{payload}**\n\nYou earned **{points} points**.\nTotal points: **{total}**",
            color=discord.Color.green()
        )
    else:
        embed = discord.Embed(
            title="💥 Launch Failed",
            description=f"Your rocket failed to launch.\nEngine: **{engine}**\nTank: **{tank}**\nPayload: **{payload}**\n\nBetter luck next time!",
            color=discord.Color.red()
        )

    await ctx.send(embed=embed)
    rocket_design_states.pop(ctx.author.id, None)


# Booster Catch Game
@bot.command(name="catchbooster")
async def catchbooster(ctx):
    """Booster catching simulation with SpaceX-style countdown, timeline and animated flames."""

    drift = random.choice(["left", "right", "center"])
    speed = random.randint(160, 280)
    altitude = random.randint(150, 220)
    timeline = []

    # booster flames by stage
    flames = ["🔥", "🟧", "🟨", "🟩", "🟦"]

    def make_bar(current, max_val, length=10, emoji="█"):
        filled = max(0, min(length, int(current / max_val * length)))
        return emoji * filled + "░" * (length - filled)

    # booster ASCII with flames
    def booster_ascii(stage):
        flame = flames[min(stage, len(flames)-1)]
        tower = [
            "🗼 |    |",
            "   |    |",
            "   |    |",
            "   |    |",
            "   |    |",
        ]
        booster = [
            f"    ^ {flame}",
            f"   /|\\ {flame}",
            f"  /_|_\\ {flame}",
            f"    |  {flame}"
        ]
        offset = min(stage, len(tower)-1)
        lines = tower[:len(tower)-offset] + booster + tower[len(tower)-offset:]
        return "\n".join(lines)

    async def update_embed(stage, message=None, status=""):
        altitude_bar = make_bar(altitude, 220, emoji="🟩")
        speed_bar = make_bar(speed, 280, emoji="🟦")
        art = f"```{booster_ascii(stage)}```"
        timeline_text = "\n".join([f"• {event}" for event in timeline[-5:]]) or "—"
        e = discord.Embed(
            title="🚀 Booster Catch — Live Telemetry",
            description=(
                art +
                f"**Altitude:** {altitude} m  {altitude_bar}\n"
                f"**Speed:** {speed} m/s  {speed_bar}\n"
                f"**Wind Drift:** {drift.upper()}\n\n"
                f"**Status:** {status}\n\n"
                f"**Timeline:**\n{timeline_text}"
            ),
            color=discord.Color.blurple()
        )
        if message:
            await message.edit(embed=e)
        else:
            return await ctx.send(embed=e)

    # Phase 0 — initial
    timeline.append("Booster detected on radar")
    msg = await update_embed(stage=0, status="Incoming booster…")
    await asyncio.sleep(1.2)

    # Phase 1 — Position arms
    timeline.append("Preparing arms for capture")
    await update_embed(stage=1, message=msg, status="Type `left`, `right` or `center` to position the arms.")
    def position_check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ["left","right","center"]
    try:
        pmsg = await bot.wait_for("message", timeout=6.0, check=position_check)
        chosen_position = pmsg.content.lower()
        timeline.append(f"Arms moved to {chosen_position.upper()}")
    except asyncio.TimeoutError:
        timeline.append("Missed arm positioning window")
        await ctx.send("❌ Too slow. Booster crashed.")
        return
    correct_position = chosen_position == drift
    altitude -= random.randint(30, 50)
    speed -= random.randint(20, 50)
    await update_embed(stage=2, message=msg, status="Arms in position")

    # Phase 2 — Countdown T-5 to T-0 with flames changing
    for t in range(5, 0, -1):
        timeline.append(f"T-{t} seconds to catch window")
        altitude -= random.randint(5, 15)
        speed -= random.randint(5, 15)
        # stage controls flames height
        stage = 3 + (5 - t)
        await update_embed(stage=stage, message=msg, status=f"Countdown T-{t}s — booster slowing 🔥")
        await asyncio.sleep(1.0)
    timeline.append("T-0 Catch window opens")

    # Phase 3 — Catch
    await update_embed(stage=4, message=msg, status="🔒 CATCH NOW! Type **catch** within 3.5s!")
    def catch_check(m): return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() == "catch"
    try:
        start_time = asyncio.get_event_loop().time()
        await bot.wait_for("message", timeout=3.5, check=catch_check)
        reaction_time = asyncio.get_event_loop().time() - start_time
        timeline.append(f"Catch command received ({reaction_time:.2f}s)")
    except asyncio.TimeoutError:
        timeline.append("Missed catch window")
        await ctx.send("💥 Missed the timing. Booster splashed down.")
        return

    # SCORING
    if correct_position:
        if reaction_time < 1.2:
            points = 6
            quality = "🌟 Perfect Catch!"
        else:
            points = 4
            quality = "✅ Good Catch!"
    else:
        points = 0
        quality = "💥 Catastrophic Failure"

    if points > 0:
        add_score(ctx.author.id, points)
        total = scores.get(str(ctx.author.id), 0)
        timeline.append(f"Booster secured. +{points} points.")
        e = discord.Embed(
            title=quality,
            description=f"{ctx.author.mention} caught the booster!\nEarned **{points} points**.\nTotal points: **{total}**",
            color=discord.Color.green()
        )
    else:
        timeline.append("Booster lost")
        e = discord.Embed(
            title=quality,
            description=f"{ctx.author.mention} lost the booster. No points awarded.",
            color=discord.Color.red()
        )
    await ctx.send(embed=e)




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
    embed = discord.Embed(
        title="🎮 Mini-Game Bot — Full Games List",
        description="Choose from fun mini-games below (points vary by difficulty):",
        color=discord.Color.blurple()
    )

    # Quick play mini-games
    embed.add_field(
        name="🪨📄✂️ Rock Paper Scissors",
        value="`!rps <rock|paper|scissors>` — Play with the bot. (+1 point if you win)",
        inline=False
    )
    embed.add_field(
        name="🪙 Coin Flip",
        value="`!coinflip <heads|tails>` — Guess a coin flip. (+1 point if correct)",
        inline=False
    )
    embed.add_field(
        name="🎲 Dice Roll",
        value="`!dice <guess> <sides>` — Roll dice (optional guess & sides). (+1 point if guess matches)",
        inline=False
    )
    embed.add_field(
        name="🔢 Number Guess",
        value="`!guess` — Guess a number between 1 and 10 in 15s (+1 point if correct).",
        inline=False
    )

    # Trivia / quiz games
    embed.add_field(
        name="🎓 Trivia Quiz",
        value=(
            "Answer space-themed questions:\n"
            "`!trivia easy` (+1 pt) • `!trivia medium` (+2 pt) • `!trivia hard` (+3 pt)"
        ),
        inline=False
    )
    embed.add_field(
        name="🧮 Math Quiz",
        value="`!mathquiz` — Solve a random math question (+1 point if correct).",
        inline=False
    )
    embed.add_field(
        name="🔤 Word Unscramble",
        value=(
            "`!unscramble easy` — Easy words (+1 pt)\n"
            "`!unscramble medium` — Moderate words (+2 pt)\n"
            "`!unscramble hard` — Space/technical words (+3 pt)"
        ),
        inline=False
    )

    # Resource Management / Mission game
    embed.add_field(
        name="🛰️ Starship Mission (Resource Management)",
        value=(
            "`!mission` — Start your mission and manage Fuel, Food, and Research.\n"
            "`!mission launch` — Travel forward\n"
            "`!mission refuel` — Gather supplies\n"
            "`!mission research` — Earn research points\n"
            "`!mission status` — View your stats\n"
            "Survive as many turns as possible to earn points!"
        ),
        inline=False
    )

    # Booster catching + Rocket building
    embed.add_field(
        name="🪝 Booster Catch Game (Complex)",
        value="`!catchbooster` — Position the arms and time your catch like Mechazilla.io! Points scale with accuracy and reaction time.",
        inline=False
    )
    embed.add_field(
        name="7️⃣ Rocket Design Quiz",
        value="(Coming Soon) Pick engines, tank size, and stage design to create your own rocket. Success chance based on your choices!",
        inline=False
    )

    # Starship predictors
    embed.add_field(
        name="🚀 Starship Predictor (Booster+Ship)",
        value="`!starship` — Answer quick questions to simulate SpaceX Starship full launch success chance.",
        inline=False
    )
    embed.add_field(
        name="🚀 Starship Ship Simulation (Ship only)",
        value="`!predict` — Predict launch success chance for a specific Starship **ship only** (asks for ship name).",
        inline=False
    )

    # Leaderboard
    embed.add_field(
        name="🏆 Leaderboard",
        value="`!leaderboard` — View the top 10 players and their total points.",
        inline=False
    )

    embed.set_footer(
        text="✅ Points: Easy +1 • Medium +2 • Hard +3 — stored in scores.json. Some games scale points based on performance!"
    )

    await ctx.send(embed=embed)


bot.run(TOKEN, log_handler=handler, log_level=logging.DEBUG)
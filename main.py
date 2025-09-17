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

class DifficultyDropdown(discord.ui.Select):
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

        await interaction.message.edit(content=f"🎲 Loading {difficulty.capitalize()} question…", view=None)
        await send_trivia_question(self.ctx, difficulty)


class DifficultyView(discord.ui.View):
    def __init__(self, ctx, timeout=60):
        super().__init__(timeout=timeout)
        self.add_item(DifficultyDropdown(ctx))


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

        if chosen == correct_letter:
            add_score(interaction.user.id, points)
            total = scores.get(str(interaction.user.id), 0)
            result_embed = discord.Embed(
                title="✅ Correct!",
                description=f"You answered **{chosen}) {chosen_answer}** — +{points} point(s)!\n"
                            f"Total points: **{total}**",
                color=discord.Color.green())
        else:
            result_embed = discord.Embed(
                title="❌ Wrong",
                description=f"You answered **{chosen}) {chosen_answer}**.\n"
                            f"Correct answer: **{correct_letter}) {q['answer']}**.",
                color=discord.Color.red())

        # Edit original question embed but keep question text
        question_embed = interaction.message.embeds[0]
        question_embed.add_field(name="Result", value=result_embed.description, inline=False)
        await interaction.message.edit(embed=question_embed, view=PlayAgainView(view.ctx))


class PlayAgainView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.add_item(PlayAgainButton(ctx))


class PlayAgainButton(discord.ui.Button):
    def __init__(self, ctx):
        self.ctx = ctx
        super().__init__(label="Play Again", style=discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ This is not your trivia session.", ephemeral=True)
            return
        await interaction.response.defer()
        await interaction.message.edit(content="🎯 Select a difficulty to start trivia:", embed=None, view=DifficultyView(self.ctx))


async def send_trivia_question(ctx, difficulty):
    q = random.choice(TRIVIA_QUESTIONS[difficulty])

    options = q["options"][:3]
    random.shuffle(options)
    letter_to_option = {LETTERS[i]: options[i] for i in range(len(options))}
    correct_letter = next((L for L, O in letter_to_option.items()
                           if O.lower() == q["answer"].lower()), None)
    points = 1 if difficulty == "easy" else 2 if difficulty == "medium" else 3

    question_text = f"**[{difficulty.upper()} — {points} point(s)]**\n\n{q['question']}\n\n" + \
                    "\n".join([f"{L}) {O}" for L, O in letter_to_option.items()])

    embed = discord.Embed(title="🎓 Space Trivia Time!",
                          description=question_text,
                          color=discord.Color.teal())

    view = AnswerButtons(ctx, correct_letter, points, letter_to_option, q, difficulty)
    await ctx.send(embed=embed, view=view)


# === Main command ===
@bot.command(name="trivia")
async def trivia(ctx):
    """Launch the trivia UI."""
    await ctx.send("🎯 Select a difficulty to start trivia:", view=DifficultyView(ctx))



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

    @discord.ui.button(label='🤏 CATCH!', style=discord.ButtonStyle.success, emoji='🤏')
    async def catch_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user == self.game.ctx.author:
            self.game.handle_action('catch')
            self.update_button_states()
            await interaction.response.defer()


class EnhancedCatchGame:
    def __init__(self, ctx):
        self.ctx = ctx
        self.game_state = {
            'booster_x': 12,  # Center position (0-24 range)
            'booster_y': 0,  # Top of screen
            'booster_vel_x': random.uniform(-0.5, 0.5),
            'booster_vel_y': 0.3,
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
            title="🦾 ENHANCED MECHZILLA.IO v2.0",
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
            "`!trivia`"
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
from keep_alive import keep_alive
keep_alive()
import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import time
import random
import json

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

@bot.command(name="leaderboard")
async def leaderboard(ctx):
    """Show the top players."""
    if not scores:
        embed = discord.Embed(
            title="🏆 Leaderboard",
            description="No scores yet. Play some games!",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)
        return

    # Sort scores descending
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    description = ""

    for i, (user_id, score_value) in enumerate(sorted_scores[:10], start=1):
        # clamp negatives
        if score_value < 0:
            score_value = 0

        # ensure user_id is int
        user_id = int(user_id)

        # Try to get member from current guild
        member = ctx.guild.get_member(user_id)
        if member is None:
            # Try to fetch globally if not found in guild
            try:
                member = await bot.fetch_user(user_id)
            except discord.NotFound:
                member = None

        if member:
            # display_name if in guild, name if global user
            name = getattr(member, "display_name", member.name)
        else:
            name = f"User {user_id}"

        crown = "👑 " if i == 1 else ""
        description += f"**{i}. {crown}{name}** — {score_value} points\n"

    embed = discord.Embed(
        title="🏆 Leaderboard",
        description=description,
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed)

# -----------------------------------
# 6️⃣ Trivia Game
# -----------------------------------
TRIVIA_QUESTIONS = [
    {"question": "What is the capital of France?",
     "options": ["Paris", "Berlin", "Rome"], "answer": "Paris"},
    {"question": "Which planet is known as the Red Planet?",
     "options": ["Mars", "Venus", "Jupiter"], "answer": "Mars"},
    {"question": "Who wrote 'Romeo and Juliet'?",
     "options": ["Shakespeare", "Dickens", "Tolkien"], "answer": "Shakespeare"},
    {"question": "Which ocean is the largest?",
     "options": ["Pacific", "Atlantic", "Indian"], "answer": "Pacific"},
    {"question": "Which is the smallest prime number?",
     "options": ["2", "3", "1"], "answer": "2"},

    # Space related
    {"question": "Which planet has the most moons?",
     "options": ["Saturn", "Jupiter", "Neptune"], "answer": "Saturn"},
    {"question": "What is the hottest planet in our Solar System?",
     "options": ["Venus", "Mercury", "Mars"], "answer": "Venus"},
    {"question": "Which planet is known for its Great Red Spot?",
     "options": ["Jupiter", "Mars", "Saturn"], "answer": "Jupiter"},
    {"question": "What galaxy is Earth located in?",
     "options": ["Milky Way", "Andromeda", "Triangulum"], "answer": "Milky Way"},
    {"question": "Who was the first person in space?",
     "options": ["Yuri Gagarin", "Neil Armstrong", "Buzz Aldrin"], "answer": "Yuri Gagarin"},
    {"question": "What is the name of the first artificial Earth satellite?",
     "options": ["Sputnik 1", "Explorer 1", "Vostok 1"], "answer": "Sputnik 1"},
    {"question": "Which planet rotates on its side?",
     "options": ["Uranus", "Neptune", "Venus"], "answer": "Uranus"},
    {"question": "What is the largest planet in our Solar System?",
     "options": ["Jupiter", "Saturn", "Neptune"], "answer": "Jupiter"},
    {"question": "Which planet has the fastest winds?",
     "options": ["Neptune", "Saturn", "Mars"], "answer": "Neptune"},
    {"question": "Which planet has a day longer than its year?",
     "options": ["Venus", "Mercury", "Mars"], "answer": "Venus"},
]

LETTERS = ["A", "B", "C"]

@bot.command(name="trivia")
async def trivia(ctx):
    """Ask a random trivia question. Awards +1 point if correct."""
    q = random.choice(TRIVIA_QUESTIONS)

    # Shuffle answers & assign A/B/C dynamically
    options = q["options"][:3]
    random.shuffle(options)
    letter_to_option = {LETTERS[i]: options[i] for i in range(len(options))}
    correct_letter = next((L for L, O in letter_to_option.items()
                           if O.lower() == q["answer"].lower()), None)

    # Build embed question
    question_text = q["question"] + "\n\n" + "\n".join(
        [f"{L}) {O}" for L, O in letter_to_option.items()]) + "\n\nType A, B, or C in chat (15s)."
    embed = discord.Embed(title="🎓 Trivia Time!",
                          description=question_text,
                          color=discord.Color.teal())
    await ctx.send(embed=embed)

    def check(m):
        return (m.author == ctx.author and
                m.channel == ctx.channel and
                m.content.upper() in letter_to_option.keys())

    try:
        reply = await bot.wait_for("message", timeout=15.0, check=check)
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
        # use your existing add_score
        add_score(ctx.author.id, 1)
        total = scores.get(str(ctx.author.id), 0)
        success_embed = discord.Embed(
            title="✅ Correct!",
            description=f"You answered **{chosen}) {chosen_answer}** — +1 point!\nTotal points: **{total}**",
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
    a, b = random.randint(1, 10), random.randint(1, 10)
    op = random.choice(["+", "-", "*"])
    question = f"{a} {op} {b}"
    answer = eval(question)

    embed = discord.Embed(
        title="🧮 Math Quiz",
        description=f"Solve: **{question}** (15s timeout)",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()

    try:
        msg = await bot.wait_for("message", timeout=15.0, check=check)
        if int(msg.content) == answer:
            result_embed = discord.Embed(
                title="✅ Correct!",
                description=f"You solved it! (+1 point)",
                color=discord.Color.green()
            )
            add_score(ctx.author.id, 1)
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
words = ["python", "discord", "bot", "game", "rocket", "planet", "leaderboard"]

@bot.command(name="unscramble")
async def unscramble(ctx):
    word = random.choice(words)
    scrambled = ''.join(random.sample(word, len(word)))

    embed = discord.Embed(
        title="🔤 Word Unscramble",
        description=f"Unscramble this word: **{scrambled}** (15s timeout)",
        color=discord.Color.purple()
    )
    await ctx.send(embed=embed)

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        msg = await bot.wait_for("message", timeout=15.0, check=check)
        if msg.content.lower() == word:
            result_embed = discord.Embed(
                title="✅ Correct!",
                description="You unscrambled it! (+1 point)",
                color=discord.Color.green()
            )
            add_score(ctx.author.id, 1)
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
        title="🎮 Mini-Game Bot — Games List",
        description="All the mini-games you can play:",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="🪨📄✂️ Rock Paper Scissors",
        value="`!rps <rock|paper|scissors>` — Play with the bot.",
        inline=False
    )
    embed.add_field(
        name="🪙 Coin Flip",
        value="`!coinflip <heads|tails>` — Guess a coin flip.",
        inline=False
    )
    embed.add_field(
        name="🎲 Dice Roll",
        value="`!dice <guess> <sides>` — Roll dice (optional guess & sides).",
        inline=False
    )
    embed.add_field(
        name="🔢 Number Guess",
        value="`!guess` — Guess a number between 1 and 10 in 15s.",
        inline=False
    )
    embed.add_field(
        name="🎓 Trivia Quiz",
        value="`!trivia` — Answer a multiple-choice question (A/B/C).",
        inline=False
    )
    embed.add_field(
        name="🧮 Math Quiz",
        value="`!mathquiz` — Solve a random math question.",
        inline=False
    )
    embed.add_field(
        name="🔤 Word Unscramble",
        value="`!unscramble` — Unscramble a word in 15s.",
        inline=False
    )
    embed.add_field(
        name="🏆 Score",
        value="`!score [@user]` — View your or another user’s score.",
        inline=False
    )
    embed.add_field(
        name="🏆 Leaderboard",
        value="`!leaderboard` — View the top 10 players.",
        inline=False
    )

    embed.set_footer(
        text="All correct answers or wins add +1 point to your score (stored in scores.json)."
    )

    await ctx.send(embed=embed)

bot.run(TOKEN, log_handler=handler, log_level=logging.DEBUG)
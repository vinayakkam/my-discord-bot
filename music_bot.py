import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os

# =========================
# COOKIE AUTO SWITCH
# =========================

RENDER_COOKIE_PATH = "/etc/secrets/cookies.txt"
LOCAL_COOKIE_PATH = os.path.join(os.getcwd(), "cookies.txt")

if os.path.exists(RENDER_COOKIE_PATH):
    COOKIE_FILE = RENDER_COOKIE_PATH
    print("🍪 Using Render secret cookies")
elif os.path.exists(LOCAL_COOKIE_PATH):
    COOKIE_FILE = LOCAL_COOKIE_PATH
    print("🍪 Using local cookies.txt")
else:
    COOKIE_FILE = None
    print("⚠️ No cookies file found")

# =========================
# YT-DLP / FFMPEG CONFIG
# =========================

YDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "cookiefile": COOKIE_FILE,
    "geo_bypass": True,
    "nocheckcertificate": True,
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -ss 0",
    "options": "-vn"
}

# =========================
# QUEUE SYSTEM
# =========================

music_queues = {}

class MusicQueue:
    def __init__(self):
        self.queue = []
        self.current = None
        self.voice = None
        self.loop = False
        self.volume = 0.5

def get_queue(guild_id):
    if guild_id not in music_queues:
        music_queues[guild_id] = MusicQueue()
    return music_queues[guild_id]

# =========================
# PLAYER
# =========================

async def play_next(ctx):
    q = get_queue(ctx.guild.id)

    if q.loop and q.current:
        q.queue.insert(0, q.current)

    if not q.queue:
        q.current = None
        return

    song = q.queue.pop(0)
    q.current = song

    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        info = ydl.extract_info(song["url"], download=False)
        audio_url = info["url"]

    source = discord.PCMVolumeTransformer(
        discord.FFmpegPCMAudio(audio_url, **FFMPEG_OPTIONS),
        volume=q.volume
    )

    q.voice.play(
        source,
        after=lambda _: asyncio.run_coroutine_threadsafe(
            play_next(ctx), ctx.bot.loop
        )
    )

    embed = discord.Embed(
        title="🎵 Now Playing",
        description=f"**{song['title']}**",
        color=discord.Color.green()
    )

    await ctx.send(embed=embed, view=MusicControls(ctx))

# =========================
# BUTTON UI
# =========================

class MusicControls(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=None)
        self.ctx = ctx

    @discord.ui.button(label="▶", style=discord.ButtonStyle.green)
    async def resume(self, interaction, _):
        q = get_queue(interaction.guild.id)
        if q.voice and q.voice.is_paused():
            q.voice.resume()
        await interaction.response.defer()

    @discord.ui.button(label="⏸", style=discord.ButtonStyle.gray)
    async def pause(self, interaction, _):
        q = get_queue(interaction.guild.id)
        if q.voice and q.voice.is_playing():
            q.voice.pause()
        await interaction.response.defer()

    @discord.ui.button(label="⏭", style=discord.ButtonStyle.blurple)
    async def skip(self, interaction, _):
        q = get_queue(interaction.guild.id)
        if q.voice:
            q.voice.stop()
        await interaction.response.defer()

    @discord.ui.button(label="⏹", style=discord.ButtonStyle.red)
    async def stop(self, interaction, _):
        q = get_queue(interaction.guild.id)
        q.queue.clear()
        q.current = None
        if q.voice:
            await q.voice.disconnect()
            q.voice = None
        await interaction.response.send_message(
            "⏹ Stopped, queue cleared & disconnected",
            ephemeral=True
        )

    @discord.ui.button(label="🔁 Loop", style=discord.ButtonStyle.secondary)
    async def loop(self, interaction, _):
        q = get_queue(interaction.guild.id)
        q.loop = not q.loop
        await interaction.response.send_message(
            f"🔁 Loop {'ON' if q.loop else 'OFF'}",
            ephemeral=True
        )

    @discord.ui.button(label="🔊 +", style=discord.ButtonStyle.secondary)
    async def vol_up(self, interaction, _):
        q = get_queue(interaction.guild.id)
        q.volume = min(q.volume + 0.1, 1.0)
        if q.voice and q.voice.source:
            q.voice.source.volume = q.volume
        await interaction.response.defer()

    @discord.ui.button(label="🔉 -", style=discord.ButtonStyle.secondary)
    async def vol_down(self, interaction, _):
        q = get_queue(interaction.guild.id)
        q.volume = max(q.volume - 0.1, 0.1)
        if q.voice and q.voice.source:
            q.voice.source.volume = q.volume
        await interaction.response.defer()

# =========================
# QUEUE PAGINATION
# =========================

class QueueView(discord.ui.View):
    def __init__(self, ctx, page=0):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.page = page

    async def render(self, interaction):
        q = get_queue(interaction.guild.id)
        start = self.page * 10
        end = start + 10
        songs = q.queue[start:end]

        embed = discord.Embed(title="📜 Music Queue", color=discord.Color.blue())
        if not songs:
            embed.description = "Queue is empty."
        else:
            embed.description = "\n".join(
                f"{i+start+1}. {s['title']}" for i, s in enumerate(songs)
            )

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⏮", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction, _):
        self.page = max(0, self.page - 1)
        await self.render(interaction)

    @discord.ui.button(label="⏭", style=discord.ButtonStyle.secondary)
    async def next(self, interaction, _):
        self.page += 1
        await self.render(interaction)

# =========================
# COMMANDS
# =========================

def setup_music_commands(bot):

    @bot.command(name="join", aliases=["j"])
    async def join(ctx):
        if not ctx.author.voice:
            return await ctx.send("❌ Join a voice channel first")
        q = get_queue(ctx.guild.id)
        q.voice = await ctx.author.voice.channel.connect()
        await ctx.send("✅ Joined voice channel")

    @bot.command(name="play", aliases=["p"])
    async def play(ctx, *, query):
        if not ctx.author.voice:
            return await ctx.send("❌ Join a voice channel first")

        q = get_queue(ctx.guild.id)
        if not q.voice:
            q.voice = await ctx.author.voice.channel.connect()

        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)["entries"][0]

        song = {"title": info["title"], "url": info["webpage_url"]}
        q.queue.append(song)

        if not q.voice.is_playing():
            await play_next(ctx)
        else:
            await ctx.send(f"➕ Added **{song['title']}**")

    @bot.command(name="queue", aliases=["q"])
    async def queue_cmd(ctx):
        embed = discord.Embed(title="📜 Music Queue", color=discord.Color.blue())
        await ctx.send(embed=embed, view=QueueView(ctx))

    @bot.command(name="musichelp", aliases=["mh"])
    async def music_help(ctx):
        embed = discord.Embed(title="🎵 Music Help", color=discord.Color.gold())
        embed.description = (
            "**Commands**\n"
            "`!play / !p <song>`\n"
            "`!join / !j`\n"
            "`!queue / !q`\n"
            "`!musichelp / !mh`\n\n"
            "**Buttons**\n"
            "▶ ⏸ ⏭ ⏹ 🔁 🔊"
        )
        await ctx.send(embed=embed)

    print("✅ Music system fully loaded")

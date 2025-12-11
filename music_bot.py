import discord
from discord.ext import commands
import asyncio
import yt_dlp
import os
import sys
import zipfile
import requests
import platform


# Auto-download FFmpeg if not found
def download_ffmpeg():
    """Download FFmpeg static binary (works on Render free plan and all systems)"""
    system = platform.system()
    machine = platform.machine().lower()

    print(f"Downloading FFmpeg for {system}...")

    # Create directory for FFmpeg in current working directory
    ffmpeg_dir = os.path.join(os.getcwd(), "ffmpeg_bin")
    os.makedirs(ffmpeg_dir, exist_ok=True)

    if system == "Windows":
        url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
        filename = os.path.join(ffmpeg_dir, "ffmpeg.zip")
        executable = "ffmpeg.exe"

    elif system == "Linux":
        # Use static builds that work without installation
        if "arm" in machine or "aarch64" in machine:
            url = "https://johnvansickle.com/ffmpeg/builds/ffmpeg-git-arm64-static.tar.xz"
        else:
            url = "https://johnvansickle.com/ffmpeg/builds/ffmpeg-git-amd64-static.tar.xz"
        filename = os.path.join(ffmpeg_dir, "ffmpeg.tar.xz")
        executable = "ffmpeg"

    elif system == "Darwin":  # macOS
        url = "https://evermeet.cx/ffmpeg/ffmpeg-6.1.zip"
        filename = os.path.join(ffmpeg_dir, "ffmpeg.zip")
        executable = "ffmpeg"
    else:
        print(f"❌ Unsupported operating system: {system}")
        sys.exit(1)

    try:
        # Download FFmpeg
        print(f"Downloading from {url}...")
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()

        with open(filename, "wb") as f:
            total = int(response.headers.get('content-length', 0))
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    percent = (downloaded / total) * 100
                    print(f"Progress: {percent:.1f}%", end='\r')

        print("\n📦 Extracting FFmpeg...")

        # Extract based on file type
        extract_dir = os.path.join(ffmpeg_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)

        if filename.endswith(".zip"):
            with zipfile.ZipFile(filename, "r") as zip_ref:
                zip_ref.extractall(extract_dir)
        else:  # tar.xz for Linux
            import tarfile
            with tarfile.open(filename, "r:xz") as tar_ref:
                tar_ref.extractall(extract_dir)

        # Find and setup FFmpeg executable
        ffmpeg_path = None
        for root, dirs, files in os.walk(extract_dir):
            if executable in files:
                ffmpeg_path = os.path.join(root, executable)
                break

        if ffmpeg_path:
            # Copy to bin directory for easier access
            final_path = os.path.join(ffmpeg_dir, executable)
            import shutil
            shutil.copy2(ffmpeg_path, final_path)

            # Make executable on Unix systems
            if system in ["Linux", "Darwin"]:
                os.chmod(final_path, 0o755)

            # Add to PATH
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

            print(f"✅ FFmpeg ready at: {final_path}")

            # Cleanup downloaded archive and extracted files
            try:
                if os.path.exists(filename):
                    os.remove(filename)
                if os.path.exists(extract_dir):
                    shutil.rmtree(extract_dir)
            except:
                pass  # Cleanup is optional

            return final_path
        else:
            print("❌ Could not find FFmpeg executable after extraction")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Error downloading FFmpeg: {e}")
        print("\n⚠️ Manual installation instructions:")
        if system == "Windows":
            print("Windows: Download from https://ffmpeg.org/download.html")
        elif system == "Linux":
            print("Linux: sudo apt install ffmpeg")
        elif system == "Darwin":
            print("Mac: brew install ffmpeg")
        sys.exit(1)


# Check if FFmpeg is available
try:
    import subprocess

    subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("✅ FFmpeg found!")
except FileNotFoundError:
    print("❌ FFmpeg not found. Attempting to download...")
    download_ffmpeg()

# yt-dlp options
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'extract_flat': False
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

# Store music queues per guild
music_queues = {}


class MusicQueue:
    def __init__(self):
        self.queue = []
        self.current = None
        self.voice_client = None
        self.loop = False

    def add(self, song):
        self.queue.append(song)

    def get_next(self):
        if self.queue:
            return self.queue.pop(0)
        return None

    def clear(self):
        self.queue.clear()
        self.current = None
        self.loop = False


def get_queue(guild_id):
    if guild_id not in music_queues:
        music_queues[guild_id] = MusicQueue()
    return music_queues[guild_id]


async def play_next(ctx):
    queue = get_queue(ctx.guild.id)

    if queue.voice_client:
        # If loop is enabled, re-add current song to queue
        if queue.loop and queue.current:
            queue.add(queue.current)

        if len(queue.queue) > 0:
            song = queue.get_next()
            queue.current = song

            try:
                with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                    info = ydl.extract_info(song['url'], download=False)
                    url = info['url']

                source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
                queue.voice_client.play(source,
                                        after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), ctx.bot.loop))

                embed = discord.Embed(title="🎵 Now Playing", description=f"**{song['title']}**",
                                      color=discord.Color.green())
                if queue.loop:
                    embed.set_footer(text="🔁 Loop enabled")
                await ctx.send(embed=embed)
            except Exception as e:
                await ctx.send(f"❌ Error playing song: {str(e)}")
                await play_next(ctx)
        else:
            queue.current = None


def setup_music_commands(bot):
    """Setup music commands for your existing bot"""

    @bot.command(name='join', aliases=['j'], help='Makes the bot join your voice channel')
    async def join(ctx):
        if not ctx.author.voice:
            await ctx.send("❌ You need to be in a voice channel!")
            return

        channel = ctx.author.voice.channel
        queue = get_queue(ctx.guild.id)

        if queue.voice_client:
            await queue.voice_client.move_to(channel)
        else:
            queue.voice_client = await channel.connect()

        await ctx.send(f"✅ Joined **{channel.name}**")

    @bot.command(name='leave', aliases=['disconnect', 'dc'], help='Makes the bot leave the voice channel')
    async def leave(ctx):
        queue = get_queue(ctx.guild.id)

        if queue.voice_client:
            queue.clear()
            await queue.voice_client.disconnect()
            queue.voice_client = None
            await ctx.send("👋 Left the voice channel")
        else:
            await ctx.send("❌ I'm not in a voice channel!")

    @bot.command(name='play', aliases=['p'], help='Plays a song from YouTube (usage: !play <song name or URL>)')
    async def play(ctx, *, query):
        if not ctx.author.voice:
            await ctx.send("❌ You need to be in a voice channel!")
            return

        queue = get_queue(ctx.guild.id)

        if not queue.voice_client:
            channel = ctx.author.voice.channel
            queue.voice_client = await channel.connect()

        async with ctx.typing():
            try:
                with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                    info = ydl.extract_info(f"ytsearch:{query}", download=False)
                    if 'entries' in info:
                        info = info['entries'][0]

                    song = {
                        'url': info['webpage_url'],
                        'title': info['title'],
                        'duration': info.get('duration', 0),
                        'thumbnail': info.get('thumbnail', '')
                    }

                    queue.add(song)

                    if not queue.voice_client.is_playing():
                        await play_next(ctx)
                    else:
                        embed = discord.Embed(title="➕ Added to Queue", description=f"**{song['title']}**",
                                              color=discord.Color.blue())
                        embed.add_field(name="Position", value=f"#{len(queue.queue)}", inline=True)
                        if song['thumbnail']:
                            embed.set_thumbnail(url=song['thumbnail'])
                        await ctx.send(embed=embed)

            except Exception as e:
                await ctx.send(f"❌ Error: Could not find or play that song")
                print(f"Error: {e}")

    @bot.command(name='pause', help='Pauses the current song')
    async def pause(ctx):
        queue = get_queue(ctx.guild.id)

        if queue.voice_client and queue.voice_client.is_playing():
            queue.voice_client.pause()
            await ctx.send("⏸️ Paused")
        else:
            await ctx.send("❌ Nothing is playing!")

    @bot.command(name='resume', aliases=['r'], help='Resumes the paused song')
    async def resume(ctx):
        queue = get_queue(ctx.guild.id)

        if queue.voice_client and queue.voice_client.is_paused():
            queue.voice_client.resume()
            await ctx.send("▶️ Resumed")
        else:
            await ctx.send("❌ Nothing is paused!")

    @bot.command(name='skip', aliases=['s'], help='Skips the current song')
    async def skip(ctx):
        queue = get_queue(ctx.guild.id)

        if queue.voice_client and queue.voice_client.is_playing():
            queue.voice_client.stop()
            await ctx.send("⏭️ Skipped")
        else:
            await ctx.send("❌ Nothing is playing!")

    @bot.command(name='queue', aliases=['q'], help='Shows the current music queue')
    async def show_queue(ctx):
        queue = get_queue(ctx.guild.id)

        if not queue.queue and not queue.current:
            await ctx.send("📭 Queue is empty!")
            return

        embed = discord.Embed(title="🎵 Music Queue", color=discord.Color.blue())

        if queue.current:
            embed.add_field(name="Now Playing", value=f"**{queue.current['title']}**", inline=False)

        if queue.queue:
            upcoming = "\n".join([f"{i + 1}. {song['title']}" for i, song in enumerate(queue.queue[:10])])
            embed.add_field(name="Up Next", value=upcoming, inline=False)

            if len(queue.queue) > 10:
                embed.set_footer(text=f"And {len(queue.queue) - 10} more...")

        if queue.loop:
            embed.add_field(name="Loop", value="🔁 Enabled", inline=True)

        await ctx.send(embed=embed)

    @bot.command(name='clear', aliases=['c'], help='Clears the music queue')
    async def clear(ctx):
        queue = get_queue(ctx.guild.id)
        queue.clear()

        if queue.voice_client and queue.voice_client.is_playing():
            queue.voice_client.stop()

        await ctx.send("🗑️ Queue cleared!")

    @bot.command(name='nowplaying', aliases=['np'], help='Shows the currently playing song')
    async def now_playing(ctx):
        queue = get_queue(ctx.guild.id)

        if queue.current:
            embed = discord.Embed(title="🎵 Now Playing", description=f"**{queue.current['title']}**",
                                  color=discord.Color.green())
            if queue.current.get('thumbnail'):
                embed.set_thumbnail(url=queue.current['thumbnail'])
            if queue.loop:
                embed.set_footer(text="🔁 Loop enabled")
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Nothing is playing!")

    @bot.command(name='loop', aliases=['repeat'], help='Toggle loop for current song')
    async def loop(ctx):
        queue = get_queue(ctx.guild.id)
        queue.loop = not queue.loop

        status = "enabled" if queue.loop else "disabled"
        await ctx.send(f"🔁 Loop {status}")

    @bot.command(name='volume', aliases=['vol'], help='Adjust volume (0-100)')
    async def volume(ctx, vol: int):
        queue = get_queue(ctx.guild.id)

        if not queue.voice_client or not queue.voice_client.is_playing():
            await ctx.send("❌ Nothing is playing!")
            return

        if 0 <= vol <= 100:
            queue.voice_client.source.volume = vol / 100
            await ctx.send(f"🔊 Volume set to {vol}%")
        else:
            await ctx.send("❌ Volume must be between 0 and 100")

    print("✅ Music commands loaded successfully!")

# Example usage with your existing bot:
# from music_bot import setup_music_commands
# setup_music_commands(bot)
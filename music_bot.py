import discord
from discord.ext import commands
from discord import ui
import wavelink
import os
import random
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv
import asyncio

load_dotenv()

RADIO_STREAMS = [
    "https://stream.revma.ihrhls.com/zc185",  # Pop
    "https://stream.revma.ihrhls.com/zc438",  # EDM
    "https://stream.revma.ihrhls.com/zc506",  # Hip Hop
    "https://stream.revma.ihrhls.com/zc488",  # Rock
    "https://stream.revma.ihrhls.com/zc891",  # Bollywood
]

# Initialize Spotify client
try:
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET")
    ))
except Exception as e:
    print(f"⚠️ Spotify client initialization failed: {e}")
    sp = None

music_queues = {}


class MusicQueue:
    def __init__(self):
        self.queue = []
        self.current = None
        self.loop = False


def get_queue(guild_id):
    if guild_id not in music_queues:
        music_queues[guild_id] = MusicQueue()
    return music_queues[guild_id]


def spotify_meta(query):
    """Search Spotify for better track metadata"""
    if not sp:
        return query

    try:
        r = sp.search(q=query, type="track", limit=1)
        if r["tracks"]["items"]:
            t = r["tracks"]["items"][0]
            return f"{t['name']} {t['artists'][0]['name']}"
    except Exception as e:
        print(f"Spotify search error: {e}")

    return query


# ============= UI COMPONENTS =============

class MusicControlView(ui.View):
    """Interactive music control buttons"""

    def __init__(self, ctx):
        super().__init__(timeout=None)
        self.ctx = ctx

    @ui.button(label="⏸️ Pause", style=discord.ButtonStyle.primary, custom_id="pause_btn")
    async def pause_button(self, interaction: discord.Interaction, button: ui.Button):
        if not self.ctx.voice_client:
            return await interaction.response.send_message("❌ Not in a voice channel", ephemeral=True)

        player: wavelink.Player = self.ctx.voice_client
        if player.playing and not player.paused:
            await player.pause(True)
            button.label = "▶️ Resume"
            button.style = discord.ButtonStyle.success
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("⏸️ Paused", ephemeral=True)
        elif player.paused:
            await player.pause(False)
            button.label = "⏸️ Pause"
            button.style = discord.ButtonStyle.primary
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("▶️ Resumed", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Nothing is playing", ephemeral=True)

    @ui.button(label="⏭️ Skip", style=discord.ButtonStyle.secondary, custom_id="skip_btn")
    async def skip_button(self, interaction: discord.Interaction, button: ui.Button):
        if not self.ctx.voice_client:
            return await interaction.response.send_message("❌ Not in a voice channel", ephemeral=True)

        player: wavelink.Player = self.ctx.voice_client
        if player.playing:
            await player.stop()
            await interaction.response.send_message("⏭️ Skipped", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Nothing is playing", ephemeral=True)

    @ui.button(label="⏹️ Stop", style=discord.ButtonStyle.danger, custom_id="stop_btn")
    async def stop_button(self, interaction: discord.Interaction, button: ui.Button):
        if not self.ctx.voice_client:
            return await interaction.response.send_message("❌ Not in a voice channel", ephemeral=True)

        player: wavelink.Player = self.ctx.voice_client
        await player.stop()
        get_queue(self.ctx.guild.id).queue.clear()
        get_queue(self.ctx.guild.id).current = None
        await interaction.response.send_message("⏹️ Stopped and cleared queue", ephemeral=True)

    @ui.button(label="🔁 Loop: OFF", style=discord.ButtonStyle.secondary, custom_id="loop_btn")
    async def loop_button(self, interaction: discord.Interaction, button: ui.Button):
        q = get_queue(self.ctx.guild.id)
        q.loop = not q.loop

        if q.loop:
            button.label = "🔁 Loop: ON"
            button.style = discord.ButtonStyle.success
        else:
            button.label = "🔁 Loop: OFF"
            button.style = discord.ButtonStyle.secondary

        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"🔁 Loop {'enabled' if q.loop else 'disabled'}", ephemeral=True)

    @ui.button(label="📋 Queue", style=discord.ButtonStyle.secondary, custom_id="queue_btn")
    async def queue_button(self, interaction: discord.Interaction, button: ui.Button):
        q = get_queue(self.ctx.guild.id)

        if not q.queue and not q.current:
            return await interaction.response.send_message("📭 Queue is empty", ephemeral=True)

        embed = create_queue_embed(self.ctx.guild.id)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class VolumeModal(ui.Modal, title="Set Volume"):
    volume_input = ui.TextInput(
        label="Volume (0-100)",
        placeholder="Enter volume level...",
        default="50",
        min_length=1,
        max_length=3
    )

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx

    async def on_submit(self, interaction: discord.Interaction):
        try:
            vol = int(self.volume_input.value)
            if not 0 <= vol <= 100:
                return await interaction.response.send_message("❌ Volume must be between 0 and 100", ephemeral=True)

            if not self.ctx.voice_client:
                return await interaction.response.send_message("❌ Not in a voice channel", ephemeral=True)

            player: wavelink.Player = self.ctx.voice_client
            await player.set_volume(vol)
            await interaction.response.send_message(f"🔊 Volume set to **{vol}%**", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number", ephemeral=True)


class VolumeControlView(ui.View):
    """Volume control buttons"""

    def __init__(self, ctx):
        super().__init__(timeout=180)
        self.ctx = ctx

    @ui.button(label="🔉 -10", style=discord.ButtonStyle.secondary)
    async def volume_down(self, interaction: discord.Interaction, button: ui.Button):
        if not self.ctx.voice_client:
            return await interaction.response.send_message("❌ Not in a voice channel", ephemeral=True)

        player: wavelink.Player = self.ctx.voice_client
        new_vol = max(0, player.volume - 10)
        await player.set_volume(new_vol)
        await interaction.response.send_message(f"🔉 Volume: **{new_vol}%**", ephemeral=True)

    @ui.button(label="🔊 +10", style=discord.ButtonStyle.secondary)
    async def volume_up(self, interaction: discord.Interaction, button: ui.Button):
        if not self.ctx.voice_client:
            return await interaction.response.send_message("❌ Not in a voice channel", ephemeral=True)

        player: wavelink.Player = self.ctx.voice_client
        new_vol = min(100, player.volume + 10)
        await player.set_volume(new_vol)
        await interaction.response.send_message(f"🔊 Volume: **{new_vol}%**", ephemeral=True)

    @ui.button(label="🎚️ Custom", style=discord.ButtonStyle.primary)
    async def volume_custom(self, interaction: discord.Interaction, button: ui.Button):
        modal = VolumeModal(self.ctx)
        await interaction.response.send_modal(modal)


# ============= EMBED CREATORS =============

def create_now_playing_embed(track_name, requester=None):
    """Create a beautiful now playing embed"""
    embed = discord.Embed(
        title="🎵 Now Playing",
        description=f"**{track_name}**",
        color=discord.Color.from_rgb(114, 137, 218)
    )
    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1419678020972581006/1454149961666003151/ChatGPT_Image_Dec_26_2025_09_52_19_PM.png?ex=69500a2f&is=694eb8af&hm=8f119491505da0a339eaa20da660238c5c903eabf08d434944d38b5ad551de57")

    if requester:
        embed.set_footer(text=f"Requested by {requester}", icon_url=requester.avatar.url if requester.avatar else None)

    return embed


def create_queue_embed(guild_id):
    """Create a beautiful queue embed"""
    q = get_queue(guild_id)

    embed = discord.Embed(
        title="🎵 Music Queue",
        color=discord.Color.from_rgb(88, 101, 242)
    )

    if q.current:
        embed.add_field(
            name="▶️ Now Playing",
            value=f"```{q.current}```",
            inline=False
        )

    if q.queue:
        queue_list = "\n".join([f"`{i + 1}.` {t}" for i, t in enumerate(q.queue[:10])])
        if len(q.queue) > 10:
            queue_list += f"\n*... and {len(q.queue) - 10} more*"
        embed.add_field(
            name=f"📋 Up Next ({len(q.queue)} songs)",
            value=queue_list,
            inline=False
        )

    if q.loop:
        embed.set_footer(text="🔁 Loop mode enabled")

    embed.set_thumbnail(url="https://i.imgur.com/cLvW9ND.gif")

    return embed


def create_added_embed(track_name, position=None):
    """Create embed for added song"""
    embed = discord.Embed(
        title="➕ Added to Queue",
        description=f"**{track_name}**",
        color=discord.Color.green()
    )

    if position:
        embed.add_field(name="Position", value=f"#{position}")

    return embed


# ============= PLAYBACK FUNCTIONS =============

async def play_next(ctx):
    """Play the next song in queue"""
    q = get_queue(ctx.guild.id)

    if not ctx.voice_client or not q.queue:
        q.current = None
        if ctx.voice_client and not ctx.voice_client.playing:
            embed = discord.Embed(
                title="✅ Queue Finished",
                description="All songs have been played!",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
        return

    if q.loop and q.current:
        q.queue.append(q.current)

    q.current = q.queue.pop(0)
    query = spotify_meta(q.current)

    player: wavelink.Player = ctx.voice_client
    player.ctx = ctx

    try:
        tracks: wavelink.Search = await wavelink.Playable.search(query)

        if tracks:
            await player.play(tracks[0])

            embed = create_now_playing_embed(tracks[0].title, ctx.author)
            view = MusicControlView(ctx)
            await ctx.send(embed=embed, view=view)
            return

        # Fallback to radio stream
        stream = random.choice(RADIO_STREAMS)
        radio = await wavelink.Playable.search(stream)
        if radio:
            await player.play(radio[0])
            embed = discord.Embed(
                title="📻 Radio Station",
                description="Playing live radio (fallback)",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Could not find any playable content")

    except Exception as e:
        embed = discord.Embed(
            title="❌ Playback Error",
            description=f"```{str(e)}```",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        print(f"Playback error: {e}")


# ============= SETUP COMMANDS =============

def setup_music_commands(bot):
    @bot.command(aliases=["j", "connect", "summon"])
    async def join(ctx):
        """Join your voice channel"""
        if not ctx.author.voice:
            embed = discord.Embed(
                title="❌ Error",
                description="You need to be in a voice channel first!",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        try:
            channel = ctx.author.voice.channel

            perms = channel.permissions_for(ctx.guild.me)
            if not perms.connect or not perms.speak:
                embed = discord.Embed(
                    title="❌ Missing Permissions",
                    description="I need **Connect** and **Speak** permissions in that channel.",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)

            if ctx.voice_client:
                if ctx.voice_client.channel.id == channel.id:
                    embed = discord.Embed(
                        title="✅ Already Connected",
                        description=f"I'm already in **{channel.name}**",
                        color=discord.Color.green()
                    )
                    return await ctx.send(embed=embed)
                else:
                    await ctx.voice_client.move_to(channel)
                    embed = discord.Embed(
                        title="✅ Moved",
                        description=f"Moved to **{channel.name}**",
                        color=discord.Color.green()
                    )
                    return await ctx.send(embed=embed)

            await channel.connect(cls=wavelink.Player)
            embed = discord.Embed(
                title="✅ Connected",
                description=f"Joined **{channel.name}**",
                color=discord.Color.green()
            )
            embed.set_footer(text="Use !play <song> to start playing music")
            await ctx.send(embed=embed)

        except Exception as e:
            embed = discord.Embed(
                title="❌ Connection Error",
                description=f"```{str(e)}```",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @bot.command(aliases=["dc", "disconnect", "bye", "leavevc"])
    async def leave(ctx):
        """Leave voice channel"""
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            get_queue(ctx.guild.id).queue.clear()
            get_queue(ctx.guild.id).current = None

            embed = discord.Embed(
                title="👋 Disconnected",
                description="Cleared queue and left voice channel",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Error",
                description="I'm not in a voice channel",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @bot.command(name="play", aliases=["p", "add", "song"])
    async def play(ctx, *, query: str):
        """Play a song or add to queue"""
        if not ctx.voice_client:
            if not ctx.author.voice:
                embed = discord.Embed(
                    title="❌ Error",
                    description="Join a voice channel first!",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)

            try:
                channel = ctx.author.voice.channel
                await channel.connect(cls=wavelink.Player)
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Connection Error",
                    description=f"```{str(e)}```",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)

        q = get_queue(ctx.guild.id)
        q.queue.append(query)

        player: wavelink.Player = ctx.voice_client
        if not player.playing:
            await play_next(ctx)
        else:
            embed = create_added_embed(query, len(q.queue))
            await ctx.send(embed=embed)

    @bot.command(aliases=["s", "next"])
    async def skip(ctx):
        """Skip current song"""
        if not ctx.voice_client:
            return await ctx.send("❌ Not in a voice channel")

        player: wavelink.Player = ctx.voice_client
        if player.playing:
            await player.stop()
            embed = discord.Embed(
                title="⏭️ Skipped",
                description="Playing next song...",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Nothing is playing")

    @bot.command(aliases=["pause"])
    async def pause_cmd(ctx):
        """Pause playback"""
        if not ctx.voice_client:
            return await ctx.send("❌ Not in a voice channel")

        player: wavelink.Player = ctx.voice_client
        if player.playing and not player.paused:
            await player.pause(True)
            embed = discord.Embed(title="⏸️ Paused", color=discord.Color.blue())
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Nothing is playing")

    @bot.command(aliases=["resume", "unpause"])
    async def resume_cmd(ctx):
        """Resume playback"""
        if not ctx.voice_client:
            return await ctx.send("❌ Not in a voice channel")

        player: wavelink.Player = ctx.voice_client
        if player.paused:
            await player.pause(False)
            embed = discord.Embed(title="▶️ Resumed", color=discord.Color.green())
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Not paused")

    @bot.command(aliases=["repeat", "r"])
    async def loop(ctx):
        """Toggle loop mode"""
        q = get_queue(ctx.guild.id)
        q.loop = not q.loop

        embed = discord.Embed(
            title=f"🔁 Loop {'Enabled' if q.loop else 'Disabled'}",
            description="Current song will repeat" if q.loop else "Loop mode turned off",
            color=discord.Color.green() if q.loop else discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @bot.command(aliases=["q", "list"])
    async def queue(ctx):
        """Show current queue"""
        q = get_queue(ctx.guild.id)

        if not q.queue and not q.current:
            embed = discord.Embed(
                title="📭 Queue Empty",
                description="Add songs with `!play <song>`",
                color=discord.Color.blue()
            )
            return await ctx.send(embed=embed)

        embed = create_queue_embed(ctx.guild.id)
        await ctx.send(embed=embed)

    @bot.command(aliases=["np", "nowplaying", "current"])
    async def now(ctx):
        """Show currently playing song with controls"""
        if not ctx.voice_client:
            return await ctx.send("❌ Not in a voice channel")

        player: wavelink.Player = ctx.voice_client
        if not player.playing:
            return await ctx.send("❌ Nothing is playing")

        q = get_queue(ctx.guild.id)
        if q.current:
            embed = create_now_playing_embed(q.current, ctx.author)
            view = MusicControlView(ctx)
            await ctx.send(embed=embed, view=view)
        else:
            await ctx.send("❌ No track information available")

    @bot.command(aliases=["vol"])
    async def volume(ctx, vol: int = None):
        """Volume control with buttons"""
        if not ctx.voice_client:
            return await ctx.send("❌ Not in a voice channel")

        player: wavelink.Player = ctx.voice_client

        if vol is None:
            embed = discord.Embed(
                title="🔊 Volume Control",
                description=f"Current volume: **{player.volume}%**",
                color=discord.Color.blue()
            )
            view = VolumeControlView(ctx)
            await ctx.send(embed=embed, view=view)
        else:
            if not 0 <= vol <= 100:
                return await ctx.send("❌ Volume must be between 0 and 100")

            await player.set_volume(vol)
            embed = discord.Embed(
                title="🔊 Volume Changed",
                description=f"Set to **{vol}%**",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

    @bot.command(aliases=["clear", "empty"])
    async def clearqueue(ctx):
        """Clear the queue"""
        q = get_queue(ctx.guild.id)
        cleared_count = len(q.queue)
        q.queue.clear()

        embed = discord.Embed(
            title="🗑️ Queue Cleared",
            description=f"Removed {cleared_count} songs",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)

    @bot.command()
    async def radio(ctx):
        """Play random radio station"""
        if not ctx.voice_client:
            if not ctx.author.voice:
                return await ctx.send("❌ Join a voice channel first.")
            await ctx.author.voice.channel.connect(cls=wavelink.Player)

        try:
            stream = random.choice(RADIO_STREAMS)
            radio = await wavelink.Playable.search(stream)

            if radio:
                player: wavelink.Player = ctx.voice_client
                await player.play(radio[0])

                embed = discord.Embed(
                    title="📻 Radio Station",
                    description="Playing random live radio",
                    color=discord.Color.purple()
                )
                embed.set_thumbnail(url="https://i.imgur.com/YZ0H7GF.gif")
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ Could not load radio stream")
        except Exception as e:
            await ctx.send(f"❌ Error playing radio: {e}")

    @bot.command()
    async def stop(ctx):
        """Stop playback and clear queue"""
        if not ctx.voice_client:
            return await ctx.send("❌ Not in a voice channel")

        player: wavelink.Player = ctx.voice_client
        await player.stop()
        get_queue(ctx.guild.id).queue.clear()
        get_queue(ctx.guild.id).current = None

        embed = discord.Embed(
            title="⏹️ Stopped",
            description="Playback stopped and queue cleared",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

    print("✅ Music commands loaded with UI elements")
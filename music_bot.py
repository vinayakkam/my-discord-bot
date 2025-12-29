import discord
from discord.ext import commands
from discord import ui
import wavelink
import asyncio
import random
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os
from datetime import datetime

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
control_messages = {}


class MusicQueue:
    def __init__(self):
        self.queue = []
        self.current = None
        self.loop = False
        self.loop_queue = False


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

    def __init__(self, ctx, guild_id):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.guild_id = guild_id
        self.update_button_states()

    def update_button_states(self):
        """Update button states based on player status"""
        if not self.ctx.voice_client:
            return

        player = self.ctx.voice_client
        q = get_queue(self.guild_id)

        for item in self.children:
            if item.custom_id == "pause_btn":
                if player.paused:
                    item.label = "▶️ Resume"
                    item.style = discord.ButtonStyle.success
                else:
                    item.label = "⏸️ Pause"
                    item.style = discord.ButtonStyle.primary
            elif item.custom_id == "loop_btn":
                if q.loop:
                    item.label = "🔁 Loop: ON"
                    item.style = discord.ButtonStyle.success
                else:
                    item.label = "🔁 Loop: OFF"
                    item.style = discord.ButtonStyle.secondary

    @ui.button(label="⏸️ Pause", style=discord.ButtonStyle.primary, custom_id="pause_btn")
    async def pause_button(self, interaction: discord.Interaction, button: ui.Button):
        if not self.ctx.voice_client:
            return await interaction.response.send_message("❌ Not in a voice channel", ephemeral=True)

        player = self.ctx.voice_client
        if player.playing and not player.paused:
            await player.pause(True)
            button.label = "▶️ Resume"
            button.style = discord.ButtonStyle.success
            await interaction.response.edit_message(view=self)
        elif player.paused:
            await player.pause(False)
            button.label = "⏸️ Pause"
            button.style = discord.ButtonStyle.primary
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message("❌ Nothing is playing", ephemeral=True)

    @ui.button(label="⏭️ Skip", style=discord.ButtonStyle.secondary, custom_id="skip_btn")
    async def skip_button(self, interaction: discord.Interaction, button: ui.Button):
        if not self.ctx.voice_client:
            return await interaction.response.send_message("❌ Not in a voice channel", ephemeral=True)

        player = self.ctx.voice_client
        if player.playing or player.paused:
            await interaction.response.defer(ephemeral=True)

            # Store that we're skipping manually
            player.skip_triggered = True
            await player.stop()

            # Wait and manually trigger next
            await asyncio.sleep(0.3)
            await play_next(self.ctx)

            await interaction.followup.send("⏭️ Skipped", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Nothing is playing", ephemeral=True)

    @ui.button(label="⏹️ Stop", style=discord.ButtonStyle.danger, custom_id="stop_btn")
    async def stop_button(self, interaction: discord.Interaction, button: ui.Button):
        if not self.ctx.voice_client:
            return await interaction.response.send_message("❌ Not in a voice channel", ephemeral=True)

        player = self.ctx.voice_client
        await interaction.response.defer(ephemeral=True)
        await player.stop()
        get_queue(self.guild_id).queue.clear()
        get_queue(self.guild_id).current = None
        await interaction.followup.send("⏹️ Stopped and cleared queue", ephemeral=True)

    @ui.button(label="🔁 Loop: OFF", style=discord.ButtonStyle.secondary, custom_id="loop_btn")
    async def loop_button(self, interaction: discord.Interaction, button: ui.Button):
        q = get_queue(self.guild_id)
        q.loop = not q.loop

        if q.loop:
            button.label = "🔁 Loop: ON"
            button.style = discord.ButtonStyle.success
            await interaction.response.edit_message(view=self)
        else:
            button.label = "🔁 Loop: OFF"
            button.style = discord.ButtonStyle.secondary
            await interaction.response.edit_message(view=self)

    @ui.button(label="📋 Queue", style=discord.ButtonStyle.secondary, custom_id="queue_btn")
    async def queue_button(self, interaction: discord.Interaction, button: ui.Button):
        q = get_queue(self.guild_id)

        if not q.queue and not q.current:
            return await interaction.response.send_message("📭 Queue is empty", ephemeral=True)

        embed = create_queue_embed(self.guild_id)
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

            player = self.ctx.voice_client
            await player.set_volume(vol)
            await interaction.response.send_message(f"🔊 Volume set to **{vol}%**", ephemeral=True)

            # Update main now playing embed
            q = get_queue(self.ctx.guild.id)
            if self.ctx.guild.id in control_messages and q.current:
                try:
                    main_embed = create_now_playing_embed(q.current, self.ctx.author, player)
                    view = MusicControlView(self.ctx, self.ctx.guild.id)
                    await control_messages[self.ctx.guild.id].edit(embed=main_embed, view=view)
                except:
                    pass
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number", ephemeral=True)


class VolumeControlView(ui.View):
    """Volume control buttons"""

    def __init__(self, ctx, message=None):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.message = message

    async def update_volume_display(self, interaction, new_vol):
        """Update the volume display in the embed"""
        filled = int(new_vol / 10)
        bar = "█" * filled + "░" * (10 - filled)

        embed = discord.Embed(
            title="🔊 Volume Control",
            description=f"Current volume: **{new_vol}%**",
            color=discord.Color.blue()
        )
        embed.add_field(name="Level", value=f"`{bar}` {new_vol}%", inline=False)

        try:
            await interaction.message.edit(embed=embed, view=self)
        except:
            pass

        # Update main now playing embed if it exists
        q = get_queue(self.ctx.guild.id)
        if self.ctx.guild.id in control_messages and q.current:
            try:
                player = self.ctx.voice_client
                main_embed = create_now_playing_embed(q.current, self.ctx.author, player)
                view = MusicControlView(self.ctx, self.ctx.guild.id)
                await control_messages[self.ctx.guild.id].edit(embed=main_embed, view=view)
            except:
                pass

    @ui.button(label="🔉 -10", style=discord.ButtonStyle.secondary)
    async def volume_down(self, interaction: discord.Interaction, button: ui.Button):
        if not self.ctx.voice_client:
            return await interaction.response.send_message("❌ Not in a voice channel", ephemeral=True)

        player = self.ctx.voice_client
        new_vol = max(0, player.volume - 10)
        await player.set_volume(new_vol)
        await interaction.response.defer()
        await self.update_volume_display(interaction, new_vol)

    @ui.button(label="🔊 +10", style=discord.ButtonStyle.secondary)
    async def volume_up(self, interaction: discord.Interaction, button: ui.Button):
        if not self.ctx.voice_client:
            return await interaction.response.send_message("❌ Not in a voice channel", ephemeral=True)

        player = self.ctx.voice_client
        new_vol = min(100, player.volume + 10)
        await player.set_volume(new_vol)
        await interaction.response.defer()
        await self.update_volume_display(interaction, new_vol)

    @ui.button(label="🎚️ Custom", style=discord.ButtonStyle.primary)
    async def volume_custom(self, interaction: discord.Interaction, button: ui.Button):
        modal = VolumeModal(self.ctx)
        await interaction.response.send_modal(modal)


# ============= EMBED CREATORS =============

def create_now_playing_embed(track_name, requester=None, player=None):
    """Create a beautiful now playing embed"""
    embed = discord.Embed(
        title="🎵 Now Playing",
        description=f"**{track_name}**",
        color=discord.Color.from_rgb(114, 137, 218),
        timestamp=datetime.utcnow()
    )

    embed.add_field(name="━━━━━━━━━━━━━━━━━━━━", value="", inline=False)

    if player:
        filled = int(player.volume / 10)
        vol_bar = "█" * filled + "░" * (10 - filled)
        embed.add_field(name="🔊 Volume", value=f"`{vol_bar}` {player.volume}%", inline=True)

        status = "⏸️ Paused" if player.paused else "▶️ Playing"
        embed.add_field(name="Status", value=status, inline=True)

    embed.set_thumbnail(
        url="https://cdn.discordapp.com/attachments/1419678020972581006/1454149961666003151/ChatGPT_Image_Dec_26_2025_09_52_19_PM.png")

    if requester:
        embed.set_footer(
            text=f"Requested by {requester.name}",
            icon_url=requester.avatar.url if requester.avatar else requester.default_avatar.url
        )

    return embed


def create_queue_embed(guild_id):
    """Create a beautiful queue embed"""
    q = get_queue(guild_id)

    embed = discord.Embed(
        title="🎵 Music Queue",
        color=discord.Color.from_rgb(88, 101, 242),
        timestamp=datetime.utcnow()
    )

    if q.current:
        embed.add_field(
            name="▶️ Now Playing",
            value=f"```ini\n[{q.current}]\n```",
            inline=False
        )

    if q.queue:
        queue_text = []
        for i, track in enumerate(q.queue[:10], 1):
            queue_text.append(f"`{i:2d}.` {track}")

        if len(q.queue) > 10:
            queue_text.append(f"\n*... and {len(q.queue) - 10} more songs*")

        embed.add_field(
            name=f"📋 Up Next • {len(q.queue)} song{'s' if len(q.queue) != 1 else ''}",
            value="\n".join(queue_text),
            inline=False
        )
    else:
        embed.add_field(
            name="📋 Up Next",
            value="*Queue is empty*",
            inline=False
        )

    status_icons = []
    if q.loop:
        status_icons.append("🔁 Loop")
    if q.loop_queue:
        status_icons.append("🔄 Queue Loop")

    if status_icons:
        embed.set_footer(text=" • ".join(status_icons))

    embed.set_thumbnail(
        url="https://cdn.discordapp.com/attachments/1419678020972581006/1454149961666003151/ChatGPT_Image_Dec_26_2025_09_52_19_PM.png")
    return embed


def create_added_embed(track_name, position=None):
    """Create embed for added song"""
    embed = discord.Embed(
        title="➕ Added to Queue",
        description=f"**{track_name}**",
        color=discord.Color.green()
    )

    if position:
        embed.add_field(name="Position in Queue", value=f"#{position}", inline=True)

    embed.set_thumbnail(
        url="https://cdn.discordapp.com/attachments/1419678020972581006/1454149961666003151/ChatGPT_Image_Dec_26_2025_09_52_19_PM.png")
    return embed


# ============= PLAYBACK FUNCTIONS =============

async def play_next(ctx):
    """Play the next song in queue"""
    q = get_queue(ctx.guild.id)

    if not ctx.voice_client or (not q.queue and not (q.loop and q.current)):
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
        query = spotify_meta(q.current)
    else:
        if not q.queue:
            q.current = None
            return

        previous = q.current
        q.current = q.queue.pop(0)

        if q.loop_queue and previous:
            q.queue.append(previous)

        query = spotify_meta(q.current)

    player = ctx.voice_client
    player.ctx = ctx

    try:
        tracks = await asyncio.wait_for(
            wavelink.Playable.search(query),
            timeout=10.0
        )

        if tracks:
            await player.play(tracks[0])

            embed = create_now_playing_embed(tracks[0].title, ctx.author, player)
            view = MusicControlView(ctx, ctx.guild.id)

            if ctx.guild.id in control_messages:
                try:
                    await control_messages[ctx.guild.id].delete()
                except:
                    pass

            msg = await ctx.send(embed=embed, view=view)
            control_messages[ctx.guild.id] = msg
            return

        # If no tracks found, skip to next song instead of radio fallback
        embed = discord.Embed(
            title="❌ Track Not Found",
            description=f"Could not find: **{query}**\nSkipping to next song...",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)
        if q.queue:
            await play_next(ctx)

    except asyncio.TimeoutError:
        embed = discord.Embed(
            title="⏱️ Search Timeout",
            description="Search took too long. Skipping to next song...",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)
        if q.queue:
            await play_next(ctx)
    except Exception as e:
        embed = discord.Embed(
            title="❌ Playback Error",
            description=f"```{str(e)}```",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        print(f"Playback error: {e}")
        if q.queue:
            await play_next(ctx)


# ============= SETUP COMMANDS =============

def setup_music_commands(bot):
    @bot.event
    async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
        """Automatically play next song when current one ends (for natural endings)"""
        player = payload.player
        if not player:
            return

        # Only auto-play if this wasn't a manual skip
        if hasattr(player, 'skip_triggered') and player.skip_triggered:
            player.skip_triggered = False
            return

        # Get the context from the player
        if hasattr(player, 'ctx'):
            ctx = player.ctx
            await asyncio.sleep(0.5)
            await play_next(ctx)
        else:
            print("⚠️ Player has no context, cannot auto-play next track")

    @bot.command(aliases=["musichelp", "mh", "commands"])
    async def mhelp(ctx):
        """Show all music commands"""
        embed = discord.Embed(
            title="🎵 Music Bot Commands",
            description="Complete list of available music commands",
            color=discord.Color.from_rgb(88, 101, 242),
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(
            url="https://cdn.discordapp.com/attachments/1419678020972581006/1454149961666003151/ChatGPT_Image_Dec_26_2025_09_52_19_PM.png")

        # Playback Commands
        playback = [
            "**!play** `<song>` - Play a song or add to queue",
            "**!pause** - Pause current song",
            "**!resume** - Resume playback",
            "**!skip** - Skip current song",
            "**!stop** - Stop playback and clear queue",
            "**!now** - Show currently playing song with controls"
        ]
        embed.add_field(
            name="▶️ Playback",
            value="\n".join(playback),
            inline=False
        )

        # Queue Commands
        queue_cmds = [
            "**!queue** - View current queue",
            "**!clearqueue** - Clear all songs from queue",
            "**!shufflequeue** - Shuffle queue order",
            "**!removetrack** `<position>` - Remove song by position"
        ]
        embed.add_field(
            name="📋 Queue Management",
            value="\n".join(queue_cmds),
            inline=False
        )

        # Voice Commands
        voice = [
            "**!join** - Join your voice channel",
            "**!leave** - Leave voice channel and clear queue"
        ]
        embed.add_field(
            name="🔊 Voice",
            value="\n".join(voice),
            inline=False
        )

        # Settings Commands
        settings = [
            "**!volume** `[0-100]` - View or set volume",
            "**!loop** - Toggle loop for current song",
            "**!queueloop** - Toggle loop for entire queue"
        ]
        embed.add_field(
            name="⚙️ Settings",
            value="\n".join(settings),
            inline=False
        )

        # Extra Commands
        extra = [
            "**!radio** - Play a random radio station"
        ]
        embed.add_field(
            name="📻 Extra",
            value="\n".join(extra),
            inline=False
        )

        # Aliases info
        embed.add_field(
            name="💡 Tips",
            value="• Most commands have short aliases (e.g., `!p` for play, `!s` for skip)\n"
                  "• Use interactive buttons for easier control\n"
                  "• Queue supports multiple songs at once",
            inline=False
        )

        embed.set_footer(
            text=f"Requested by {ctx.author.name}",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
        )

        await ctx.send(embed=embed)

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

            player = await asyncio.wait_for(
                channel.connect(cls=wavelink.Player),
                timeout=10.0
            )

            embed = discord.Embed(
                title="✅ Connected",
                description=f"Joined **{channel.name}**",
                color=discord.Color.green()
            )
            embed.set_footer(text="Use !play <song> to start playing music")
            await ctx.send(embed=embed)

        except asyncio.TimeoutError:
            embed = discord.Embed(
                title="⏱️ Connection Timeout",
                description="Could not connect to voice channel within 10 seconds. Please try again.",
                color=discord.Color.orange()
            )
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

            if ctx.guild.id in control_messages:
                try:
                    await control_messages[ctx.guild.id].delete()
                except:
                    pass
                del control_messages[ctx.guild.id]

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
                await asyncio.wait_for(
                    channel.connect(cls=wavelink.Player),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                embed = discord.Embed(
                    title="⏱️ Connection Timeout",
                    description="Could not connect to voice channel. Please try `!join` first.",
                    color=discord.Color.orange()
                )
                return await ctx.send(embed=embed)
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Connection Error",
                    description=f"```{str(e)}```",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)

        q = get_queue(ctx.guild.id)
        q.queue.append(query)

        player = ctx.voice_client
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

        player = ctx.voice_client
        q = get_queue(ctx.guild.id)

        if player.playing or player.paused:
            # Store that we're skipping manually
            player.skip_triggered = True
            await player.stop()

            # Wait a moment for the stop to process
            await asyncio.sleep(0.3)

            # Manually trigger next song
            await play_next(ctx)

            embed = discord.Embed(
                title="⏭️ Skipped",
                description="Playing next song..." if q.queue or q.current else "Queue is empty",
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

        player = ctx.voice_client
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

        player = ctx.voice_client
        if player.paused:
            await player.pause(False)
            embed = discord.Embed(title="▶️ Resumed", color=discord.Color.green())
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Not paused")

    @bot.command(aliases=["repeat", "r"])
    async def loop(ctx):
        """Toggle loop mode for current song"""
        q = get_queue(ctx.guild.id)
        q.loop = not q.loop

        embed = discord.Embed(
            title=f"🔁 Loop {'Enabled' if q.loop else 'Disabled'}",
            description="Current song will repeat" if q.loop else "Loop mode turned off",
            color=discord.Color.green() if q.loop else discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @bot.command(aliases=["loopqueue", "lq"])
    async def queueloop(ctx):
        """Toggle loop mode for entire queue"""
        q = get_queue(ctx.guild.id)
        q.loop_queue = not q.loop_queue

        embed = discord.Embed(
            title=f"🔄 Queue Loop {'Enabled' if q.loop_queue else 'Disabled'}",
            description="Entire queue will repeat" if q.loop_queue else "Queue loop turned off",
            color=discord.Color.green() if q.loop_queue else discord.Color.blue()
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

        player = ctx.voice_client
        q = get_queue(ctx.guild.id)

        # Check if we have a current track in queue, even if player hasn't started yet
        if q.current:
            embed = create_now_playing_embed(q.current, ctx.author, player)
            view = MusicControlView(ctx, ctx.guild.id)
            await ctx.send(embed=embed, view=view)
        elif player.playing or player.paused:
            # Fallback to player's current track
            if player.current:
                embed = create_now_playing_embed(player.current.title, ctx.author, player)
                view = MusicControlView(ctx, ctx.guild.id)
                await ctx.send(embed=embed, view=view)
            else:
                await ctx.send("❌ No track information available")
        else:
            await ctx.send("❌ Nothing is playing")

    @bot.command(aliases=["vol"])
    async def volume(ctx, vol: int = None):
        """Volume control with buttons"""
        if not ctx.voice_client:
            return await ctx.send("❌ Not in a voice channel")

        player = ctx.voice_client

        if vol is None:
            filled = int(player.volume / 10)
            bar = "█" * filled + "░" * (10 - filled)

            embed = discord.Embed(
                title="🔊 Volume Control",
                description=f"Current volume: **{player.volume}%**",
                color=discord.Color.blue()
            )
            embed.add_field(name="Level", value=f"`{bar}` {player.volume}%", inline=False)

            view = VolumeControlView(ctx)
            msg = await ctx.send(embed=embed, view=view)
            view.message = msg

            # Delete after 30 seconds
            await asyncio.sleep(30)
            try:
                await msg.delete()
            except:
                pass
        else:
            if not 0 <= vol <= 100:
                return await ctx.send("❌ Volume must be between 0 and 100")

            await player.set_volume(vol)

            filled = int(vol / 10)
            bar = "█" * filled + "░" * (10 - filled)

            embed = discord.Embed(
                title="🔊 Volume Changed",
                description=f"Set to **{vol}%**",
                color=discord.Color.green()
            )
            embed.add_field(name="Level", value=f"`{bar}` {vol}%", inline=False)
            msg = await ctx.send(embed=embed)

            # Update main now playing embed if it exists
            q = get_queue(ctx.guild.id)
            if ctx.guild.id in control_messages and q.current:
                try:
                    main_embed = create_now_playing_embed(q.current, ctx.author, player)
                    view = MusicControlView(ctx, ctx.guild.id)
                    await control_messages[ctx.guild.id].edit(embed=main_embed, view=view)
                except:
                    pass

            # Delete volume change message after 10 seconds
            await asyncio.sleep(10)
            try:
                await msg.delete()
            except:
                pass

    @bot.command(aliases=["clear", "empty"])
    async def clearqueue(ctx):
        """Clear the queue"""
        q = get_queue(ctx.guild.id)
        cleared_count = len(q.queue)
        q.queue.clear()

        embed = discord.Embed(
            title="🗑️ Queue Cleared",
            description=f"Removed **{cleared_count}** song{'s' if cleared_count != 1 else ''}",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)

    @bot.command()
    async def radio(ctx):
        """Play random radio station"""
        if not ctx.voice_client:
            if not ctx.author.voice:
                return await ctx.send("❌ Join a voice channel first.")
            try:
                await asyncio.wait_for(
                    ctx.author.voice.channel.connect(cls=wavelink.Player),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                return await ctx.send("⏱️ Connection timeout. Please try again.")
            except Exception as e:
                return await ctx.send(f"❌ Connection error: {e}")

        player = ctx.voice_client

        # Try searching for popular radio stations instead
        radio_searches = [
            "BBC Radio 1 live",
            "Capital FM live",
            "Heart Radio live",
            "Absolute Radio live",
            "Classic FM live"
        ]

        search_query = random.choice(radio_searches)

        try:
            tracks = await wavelink.Playable.search(search_query)

            if tracks:
                await player.play(tracks[0])

                embed = discord.Embed(
                    title="📻 Radio Station",
                    description=f"Now playing: **{tracks[0].title}**",
                    color=discord.Color.purple()
                )
                embed.set_thumbnail(
                    url="https://cdn.discordapp.com/attachments/1419678020972581006/1454149961666003151/ChatGPT_Image_Dec_26_2025_09_52_19_PM.png")
                embed.set_footer(text="Live radio stream")
                await ctx.send(embed=embed)
                return
            else:
                await ctx.send("❌ Could not find radio stations. Try `!play <song name>` instead.")

        except Exception as e:
            print(f"Radio error: {e}")
            await ctx.send("❌ Radio is currently unavailable. Try `!play <song name>` for music!")

    @bot.command()
    async def stop(ctx):
        """Stop playback and clear queue"""
        if not ctx.voice_client:
            return await ctx.send("❌ Not in a voice channel")

        player = ctx.voice_client
        await player.stop()
        get_queue(ctx.guild.id).queue.clear()
        get_queue(ctx.guild.id).current = None

        embed = discord.Embed(
            title="⏹️ Stopped",
            description="Playback stopped and queue cleared",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

    @bot.command(aliases=["shuffle"])
    async def shufflequeue(ctx):
        """Shuffle the current queue"""
        q = get_queue(ctx.guild.id)

        if len(q.queue) < 2:
            return await ctx.send("❌ Need at least 2 songs in queue to shuffle")

        random.shuffle(q.queue)

        embed = discord.Embed(
            title="🔀 Queue Shuffled",
            description=f"Randomized **{len(q.queue)}** songs",
            color=discord.Color.blue()
        )
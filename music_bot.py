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
is_playing_next = {}  # Track if play_next is already running


class MusicQueue:
    def __init__(self):
        self.queue = []
        self.current = None
        self.loop = False
        self.loop_queue = False
        self.is_transitioning = False  # Prevent race conditions


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

        try:
            if not player.connected:
                return await interaction.response.send_message("❌ Player disconnected", ephemeral=True)

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
        except Exception as e:
            print(f"Pause button error: {e}")
            await interaction.response.send_message("❌ Action failed", ephemeral=True)

    @ui.button(label="⏭️ Skip", style=discord.ButtonStyle.secondary, custom_id="skip_btn")
    async def skip_button(self, interaction: discord.Interaction, button: ui.Button):
        if not self.ctx.voice_client:
            return await interaction.response.send_message("❌ Not in a voice channel", ephemeral=True)

        player = self.ctx.voice_client
        q = get_queue(self.guild_id)

        if player.playing or player.paused:
            await interaction.response.defer(ephemeral=True)

            # Store that we're skipping manually
            player.skip_triggered = True
            q.is_transitioning = False  # Reset transition flag

            # Force stop and clear buffer
            await player.stop()

            # Wait longer for clean buffer clear
            await asyncio.sleep(1.2)
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

        try:
            if player.connected:
                await player.stop()
        except Exception as e:
            print(f"Stop button error: {e}")

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
    guild_id = ctx.guild.id
    q = get_queue(guild_id)

    # Prevent multiple play_next calls running simultaneously
    if guild_id in is_playing_next and is_playing_next[guild_id]:
        print(f"⚠️ play_next already running for guild {guild_id}, skipping")
        return

    if q.is_transitioning:
        print(f"⚠️ Queue is transitioning for guild {guild_id}, skipping")
        return

    q.is_transitioning = True
    is_playing_next[guild_id] = True

    try:
        # Check if voice client is still valid
        if not ctx.voice_client or not ctx.voice_client.connected:
            q.current = None
            q.is_transitioning = False
            is_playing_next[guild_id] = False
            return

        if not q.queue and not (q.loop and q.current):
            q.current = None
            q.is_transitioning = False
            is_playing_next[guild_id] = False
            if ctx.voice_client and not ctx.voice_client.playing:
                embed = discord.Embed(
                    title="✅ Queue Finished",
                    description="All songs have been played!",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed)
            return

        # Handle loop mode
        if q.loop and q.current:
            query = spotify_meta(q.current)
        else:
            if not q.queue:
                q.current = None
                q.is_transitioning = False
                is_playing_next[guild_id] = False
                return

            previous = q.current
            q.current = q.queue.pop(0)

            # Only add to queue loop if loop_queue is enabled AND loop is OFF
            if q.loop_queue and previous and not q.loop:
                q.queue.append(previous)

            query = spotify_meta(q.current)

        player = ctx.voice_client
        player.ctx = ctx

        try:
            tracks = await asyncio.wait_for(
                wavelink.Playable.search(query),
                timeout=15.0
            )

            if tracks:
                # Check player is still connected before playing
                if not player.connected:
                    q.is_transitioning = False
                    is_playing_next[guild_id] = False
                    return

                # CRITICAL: Stop current track and wait for clean stop
                try:
                    if player.playing or player.paused:
                        await player.stop()
                        # Increased wait time for clean buffer clear
                        await asyncio.sleep(1.0)
                except Exception as stop_err:
                    print(f"Stop error (non-critical): {stop_err}")

                # Double check nothing is playing before starting new track
                if player.playing:
                    print("⚠️ Player still playing after stop, forcing cleanup")
                    await asyncio.sleep(0.5)

                # Play the track
                try:
                    await player.play(tracks[0])

                    # Wait a moment to ensure playback started
                    await asyncio.sleep(0.3)

                except Exception as play_error:
                    print(f"Play error: {play_error}")
                    # If play fails, try next song
                    q.is_transitioning = False
                    is_playing_next[guild_id] = False
                    # Don't skip if loop is on, just end
                    if q.queue and not q.loop:
                        await asyncio.sleep(1)
                        await play_next(ctx)
                    return

                # Configure player to prevent buffering issues
                try:
                    player.autoplay = wavelink.AutoPlayMode.disabled
                except:
                    pass

                embed = create_now_playing_embed(tracks[0].title, ctx.author, player)
                view = MusicControlView(ctx, guild_id)

                if guild_id in control_messages:
                    try:
                        await control_messages[guild_id].delete()
                    except:
                        pass

                msg = await ctx.send(embed=embed, view=view)
                control_messages[guild_id] = msg
            else:
                # If no tracks found, skip to next song (but not if looping)
                embed = discord.Embed(
                    title="❌ Track Not Found",
                    description=f"Could not find: **{query}**" +
                                ("\nSkipping to next song..." if q.queue else ""),
                    color=discord.Color.orange()
                )
                await ctx.send(embed=embed)
                q.is_transitioning = False
                is_playing_next[guild_id] = False

                # Only skip to next if not in loop mode
                if q.queue and not q.loop:
                    await play_next(ctx)
                return

        except asyncio.TimeoutError:
            embed = discord.Embed(
                title="⏱️ Search Timeout",
                description="Search took too long." +
                            (" Skipping to next song..." if q.queue else ""),
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            q.is_transitioning = False
            is_playing_next[guild_id] = False

            # Only skip to next if not in loop mode
            if q.queue and not q.loop:
                await play_next(ctx)
            return
        except Exception as e:
            embed = discord.Embed(
                title="❌ Playback Error",
                description=f"```{str(e)[:100]}```",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            print(f"Playback error: {e}")
            q.is_transitioning = False
            is_playing_next[guild_id] = False

            # Only skip to next if not in loop mode
            if q.queue and not q.loop:
                await asyncio.sleep(1)
                await play_next(ctx)
            return

    except Exception as outer_error:
        print(f"Outer play_next error: {outer_error}")
        q.is_transitioning = False
        is_playing_next[guild_id] = False
    finally:
        # Always reset the flags after a delay to ensure clean state
        await asyncio.sleep(0.5)
        q.is_transitioning = False
        is_playing_next[guild_id] = False


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

        # Check if track ended naturally (not stopped/replaced)
        if payload.reason not in ["finished", "loadFailed"]:
            return

        # Get the context from the player
        if hasattr(player, 'ctx'):
            ctx = player.ctx
            guild_id = ctx.guild.id

            # Prevent multiple simultaneous calls
            if guild_id in is_playing_next and is_playing_next[guild_id]:
                return

            await asyncio.sleep(0.8)  # Slightly longer delay for stability
            await play_next(ctx)
        else:
            print("⚠️ Player has no context, cannot auto-play next track")

    @bot.event
    async def on_wavelink_track_start(payload: wavelink.TrackStartEventPayload):
        """Log when tracks start playing"""
        print(f"▶️ Started playing: {payload.track.title if payload.track else 'Unknown'}")

    @bot.event
    async def on_wavelink_track_exception(payload: wavelink.TrackExceptionEventPayload):
        """Handle track playback errors"""
        player = payload.player
        if hasattr(player, 'ctx'):
            ctx = player.ctx
            embed = discord.Embed(
                title="⚠️ Playback Issue",
                description="Track encountered an error. Skipping to next song...",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            print(f"❌ Track exception: {payload.exception}")

            # Try to play next song
            q = get_queue(ctx.guild.id)
            q.is_transitioning = False
            if q.queue:
                await asyncio.sleep(1)
                await play_next(ctx)

    @bot.event
    async def on_wavelink_track_stuck(payload: wavelink.TrackStuckEventPayload):
        """Handle stuck tracks"""
        player = payload.player
        if hasattr(player, 'ctx'):
            ctx = player.ctx
            print(f"⚠️ Track stuck for {payload.threshold}ms, skipping...")

            # Force skip to next track
            q = get_queue(ctx.guild.id)
            q.is_transitioning = False
            if player:
                await player.stop()
            await asyncio.sleep(1)
            await play_next(ctx)

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
            "**!play** `<song/link>` - Play or queue (YT, SC, Spotify)",
            "**!playsc** `<song/link>` - Play from SoundCloud",
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
            "**!leave** - Leave voice channel and clear queue",
            "**!reconnect** - Force reconnect (fixes issues)"
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

        # Radio Commands
        radio = [
            "**!radio** `[genre]` - Play radio station",
            "**!radiolist** - Show all available genres",
            "Genres: pop, rock, edm, hiphop, jazz, classical, country, indie, lofi, bollywood"
        ]
        embed.add_field(
            name="📻 Radio",
            value="\n".join(radio),
            inline=False
        )

        # Admin/Debug Commands
        admin = [
            "**!nodeinfo** - Check Lavalink nodes status",
            "**!lavalinkstats** - Detailed node statistics",
            "**!switchnode** - Switch to different Lavalink node",
            "**!voicetest** - Test voice connection step-by-step"
        ]
        embed.add_field(
            name="🔧 Admin & Debug",
            value="\n".join(admin),
            inline=False
        )

        # Tips
        embed.add_field(
            name="💡 Tips",
            value="• Supports YouTube, SoundCloud, and Spotify links\n"
                  "• Use `!playsc` for SoundCloud-specific search\n"
                  "• Most commands have short aliases (e.g., `!p` for play, `!s` for skip)\n"
                  "• Use interactive buttons for easier control\n"
                  "• Try `!radio lofi` for chill background music\n"
                  "• Use `!reconnect` if bot has audio issues",
            inline=False
        )

        embed.set_footer(
            text=f"Requested by {ctx.author.name} • OLIT Music V6",
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
                    try:
                        await ctx.voice_client.move_to(channel)
                        embed = discord.Embed(
                            title="✅ Moved",
                            description=f"Moved to **{channel.name}**",
                            color=discord.Color.green()
                        )
                        return await ctx.send(embed=embed)
                    except:
                        # If move fails, disconnect and reconnect
                        await ctx.voice_client.disconnect(force=True)
                        await asyncio.sleep(1)

            # Send connecting message
            connecting_msg = await ctx.send("🔄 Connecting to voice channel...")

            # Try to connect with increased timeout
            try:
                player = await asyncio.wait_for(
                    channel.connect(cls=wavelink.Player, self_deaf=True),
                    timeout=15.0
                )

                # Configure player settings
                await player.set_volume(50)

                await connecting_msg.delete()

                embed = discord.Embed(
                    title="✅ Connected",
                    description=f"Joined **{channel.name}**",
                    color=discord.Color.green()
                )
                embed.set_footer(text="Use !play <song> to start playing music")
                await ctx.send(embed=embed)

            except asyncio.TimeoutError:
                await connecting_msg.delete()

                # Retry once more
                try:
                    await ctx.send("⚠️ First attempt timed out, retrying...")
                    player = await asyncio.wait_for(
                        channel.connect(cls=wavelink.Player, self_deaf=True),
                        timeout=20.0
                    )
                    await player.set_volume(50)

                    embed = discord.Embed(
                        title="✅ Connected",
                        description=f"Joined **{channel.name}** (retry successful)",
                        color=discord.Color.green()
                    )
                    embed.set_footer(text="Use !play <song> to start playing music")
                    await ctx.send(embed=embed)
                except asyncio.TimeoutError:
                    embed = discord.Embed(
                        title="⏱️ Connection Timeout",
                        description="Failed to connect after multiple attempts. Please try again or check:\n"
                                    "• Bot has proper permissions\n"
                                    "• Voice channel isn't full\n"
                                    "• Lavalink server is responding",
                        color=discord.Color.orange()
                    )
                    await ctx.send(embed=embed)

        except discord.ClientException as e:
            embed = discord.Embed(
                title="❌ Connection Error",
                description=f"Already connected to another channel. Use `!leave` first.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Connection Error",
                description=f"```{str(e)[:200]}```",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            print(f"Join error: {e}")

    @bot.command(aliases=["dc", "disconnect", "bye", "leavevc"])
    async def leave(ctx):
        """Leave voice channel"""
        if ctx.voice_client:
            try:
                await ctx.voice_client.disconnect(force=True)
            except:
                pass

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
        """Play a song or add to queue (supports YouTube, SoundCloud, Spotify links, and search)"""
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
                connecting_msg = await ctx.send("🔄 Connecting...")

                # Try to connect with timeout
                try:
                    await asyncio.wait_for(
                        channel.connect(cls=wavelink.Player, self_deaf=True),
                        timeout=15.0
                    )
                    await connecting_msg.delete()
                except asyncio.TimeoutError:
                    await connecting_msg.edit(content="⚠️ Connection timeout, retrying...")
                    try:
                        await asyncio.wait_for(
                            channel.connect(cls=wavelink.Player, self_deaf=True),
                            timeout=20.0
                        )
                        await connecting_msg.delete()
                    except asyncio.TimeoutError:
                        await connecting_msg.delete()
                        embed = discord.Embed(
                            title="⏱️ Connection Timeout",
                            description="Could not connect to voice channel. Please use `!join` first or try again.",
                            color=discord.Color.orange()
                        )
                        return await ctx.send(embed=embed)
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Connection Error",
                    description=f"```{str(e)[:200]}```",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)

        q = get_queue(ctx.guild.id)

        # Detect if it's a URL (SoundCloud, YouTube, Spotify, etc.)
        is_url = query.startswith("http://") or query.startswith("https://")

        # Show what we're searching for
        if is_url:
            if "soundcloud.com" in query:
                source_emoji = "☁️"
                source_name = "SoundCloud"
            elif "spotify.com" in query:
                source_emoji = "🎵"
                source_name = "Spotify"
            elif "youtube.com" in query or "youtu.be" in query:
                source_emoji = "📺"
                source_name = "YouTube"
            else:
                source_emoji = "🔗"
                source_name = "Link"

            searching_msg = await ctx.send(f"🔍 Loading from {source_name}...")
        else:
            searching_msg = await ctx.send(f"🔍 Searching: **{query[:50]}**...")

        # Try to get track info immediately for better feedback
        try:
            tracks = await asyncio.wait_for(
                wavelink.Playable.search(query),
                timeout=10.0
            )

            if tracks:
                track_name = tracks[0].title if hasattr(tracks[0], 'title') else query

                # Delete searching message
                try:
                    await searching_msg.delete()
                except:
                    pass

                q.queue.append(query)

                player = ctx.voice_client
                if not player.playing:
                    await play_next(ctx)
                else:
                    embed = create_added_embed(track_name, len(q.queue))

                    # Add source indicator
                    if is_url:
                        if "soundcloud.com" in query:
                            embed.set_footer(text="☁️ SoundCloud",
                                             icon_url="https://cdn.discordapp.com/attachments/1419678020972581006/1454149961666003151/ChatGPT_Image_Dec_26_2025_09_52_19_PM.png")
                        elif "spotify.com" in query:
                            embed.set_footer(text="🎵 Spotify",
                                             icon_url="https://cdn.discordapp.com/attachments/1419678020972581006/1454149961666003151/ChatGPT_Image_Dec_26_2025_09_52_19_PM.png")
                        elif "youtube.com" in query or "youtu.be" in query:
                            embed.set_footer(text="📺 YouTube",
                                             icon_url="https://cdn.discordapp.com/attachments/1419678020972581006/1454149961666003151/ChatGPT_Image_Dec_26_2025_09_52_19_PM.png")

                    await ctx.send(embed=embed)
            else:
                try:
                    await searching_msg.delete()
                except:
                    pass

                embed = discord.Embed(
                    title="❌ Not Found",
                    description=f"Could not find or load: **{query[:100]}**",
                    color=discord.Color.red()
                )

                if is_url and "soundcloud.com" in query:
                    embed.add_field(
                        name="💡 SoundCloud Tips",
                        value="• Make sure the track is public\n• Try copying the share link from SoundCloud\n• Check if the track is available in your region\n• Note: SoundCloud support depends on Lavalink server configuration",
                        inline=False
                    )

                await ctx.send(embed=embed)

        except wavelink.NodeException as e:
            try:
                await searching_msg.delete()
            except:
                pass

            # Check if it's a SoundCloud link
            if is_url and "soundcloud.com" in query:
                embed = discord.Embed(
                    title="⚠️ SoundCloud Not Supported",
                    description="This Lavalink server doesn't have SoundCloud configured.",
                    color=discord.Color.orange()
                )
                embed.add_field(
                    name="What You Can Do",
                    value="• Try searching for the song name instead: `!play <song name>`\n• Use YouTube links\n• Use Spotify links (if supported)",
                    inline=False
                )
            else:
                embed = discord.Embed(
                    title="❌ Playback Error",
                    description="Lavalink node error occurred.",
                    color=discord.Color.red()
                )

            print(f"NodeException in play: {e}")
            await ctx.send(embed=embed)

        except asyncio.TimeoutError:
            try:
                await searching_msg.delete()
            except:
                pass

            embed = discord.Embed(
                title="⏱️ Search Timeout",
                description="Search took too long. The source might be slow or unavailable.",
                color=discord.Color.orange()
            )
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
            q.is_transitioning = False  # Reset transition flag

            # Force stop and clear buffer
            await player.stop()

            # Wait longer for clean buffer clear
            await asyncio.sleep(1.2)

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

        try:
            if not player.connected:
                return await ctx.send("❌ Player disconnected")

            if player.playing and not player.paused:
                await player.pause(True)
                embed = discord.Embed(title="⏸️ Paused", color=discord.Color.blue())
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ Nothing is playing")
        except Exception as e:
            print(f"Pause error: {e}")
            await ctx.send("❌ Failed to pause playback")

    @bot.command(aliases=["resume", "unpause"])
    async def resume_cmd(ctx):
        """Resume playback"""
        if not ctx.voice_client:
            return await ctx.send("❌ Not in a voice channel")

        player = ctx.voice_client

        try:
            if not player.connected:
                return await ctx.send("❌ Player disconnected")

            if player.paused:
                await player.pause(False)
                embed = discord.Embed(title="▶️ Resumed", color=discord.Color.green())
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ Not paused")
        except Exception as e:
            print(f"Resume error: {e}")
            await ctx.send("❌ Failed to resume playback")

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

        try:
            if player.connected:
                await player.stop()
        except Exception as e:
            print(f"Stop error: {e}")

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
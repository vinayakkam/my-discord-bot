import discord
from discord import ui
from discord.ext import commands
import random
import asyncio
import time
from typing import Callable


# ─── MODULE-LEVEL REFS (injected by setup_booster_catch) ───────────
_bot:        commands.Bot | None = None
_add_score:  Callable | None     = None
_scores_ref: dict | None         = None


def setup_booster_catch(bot: commands.Bot, add_score_fn: Callable, scores_dict: dict):
    """
    Call once from on_ready in main.py:
        setup_booster_catch(bot, add_score, scores)

    Parameters
    ----------
    bot           : your main.py bot instance
    add_score_fn  : your add_score() function from main.py
    scores_dict   : your scores {} dict from main.py (passed by reference)
    """
    global _bot, _add_score, _scores_ref
    _bot        = bot
    _add_score  = add_score_fn
    _scores_ref = scores_dict
    _register_commands(bot)
    print("[BOOSTER CATCH] Module loaded — !catchbooster is ready")


# ─── GAME VIEW (BUTTONS) ───────────────────────────────────────────

class CatchGameView(discord.ui.View):
    def __init__(self, game_instance):
        super().__init__(timeout=120)
        self.game = game_instance
        self.update_button_states()

    def update_button_states(self):
        """Sync button availability with game state."""
        self.thrust_button.disabled = self.game.state["fuel"] <= 0
        self.catch_button.disabled  = not self.game.state["catch_ready"]
        self.left_button.disabled   = self.game.state["arm_left"] <= 2
        self.right_button.disabled  = self.game.state["arm_right"] >= 22

        if self.game.state["game_over"]:
            for item in self.children:
                item.disabled = True

    @discord.ui.button(label="← Arms Left",  style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def left_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user == self.game.ctx.author:
            self.game.handle_action("left")
            self.update_button_states()
            await interaction.response.defer()

    @discord.ui.button(label="Arms Right →", style=discord.ButtonStyle.secondary, emoji="➡️")
    async def right_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user == self.game.ctx.author:
            self.game.handle_action("right")
            self.update_button_states()
            await interaction.response.defer()

    @discord.ui.button(label="🔥 THRUST", style=discord.ButtonStyle.danger, emoji="⬆️")
    async def thrust_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user == self.game.ctx.author:
            self.game.handle_action("thrust")
            self.update_button_states()
            await interaction.response.defer()

    @discord.ui.button(label="CATCH!", style=discord.ButtonStyle.success, emoji="🥢")
    async def catch_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user == self.game.ctx.author:
            self.game.handle_action("catch")
            self.update_button_states()
            await interaction.response.defer()


# ─── GAME ENGINE ───────────────────────────────────────────────────

class BoosterCatchGame:
    """
    Full physics simulation of a Mechzilla-style booster catch.
    Ported from EnhancedCatchGame in main.py with zero logic changes.
    """

    def __init__(self, ctx):
        self.ctx  = ctx
        self.view = None

        self.state = {
            "booster_x":               6.0,    # 0–24 range
            "booster_y":               0.0,    # 0 = top, 12 = ground
            "booster_vel_x":           random.uniform(-0.5, 0.5),
            "booster_vel_y":           0.05,
            "arm_left":                8,
            "arm_right":               16,
            "fuel":                    100,
            "wind":                    random.uniform(-0.2, 0.2),
            "phase":                   "falling",
            "catch_ready":             False,
            "game_over":               False,
            "success":                 False,
            "score":                   0,
            "engine_light":            False,
            "auto_engine_active":      False,
            "landing_burn_active":     False,
            "landing_burn_initiated":  False,
            "optimal_burn_altitude":   None,
            "thrust_particles":        [],
            "animation_frame":         0,
            "altitude_warnings":       0,
            "atmospheric_effects":     [],
            "debris_particles":        [],
            "tower_lights":            0,
            "sonic_boom_frame":        -1,
        }

        self.timeline    = ["🚀 **Mechzilla Mission Initiated**"]
        self._last_arm_pos = (self.state["arm_left"], self.state["arm_right"])

    # ── VISUAL HELPERS ──────────────────────────────────────────────

    def _atmospheric_effects(self):
        effects = []
        bx = int(self.state["booster_x"])
        by = int(self.state["booster_y"])
        frame = self.state["animation_frame"]

        if self.state["booster_vel_y"] > 0.8 and by < 8:
            self.state["sonic_boom_frame"] = frame

        if (frame - self.state["sonic_boom_frame"]) < 3:
            boom_r = frame - self.state["sonic_boom_frame"] + 1
            for offset in range(-boom_r, boom_r + 1):
                if 0 <= bx + offset < 25 and by - 1 >= 0:
                    effects.append((by - 1, bx + offset, "○"))

        if by < 4 and self.state["booster_vel_y"] > 0.5:
            if random.random() < 0.6:
                for i in range(-2, 3):
                    if 0 <= bx + i < 25 and by + 1 < 12:
                        effects.append((by + 1, bx + i, random.choice(["·", "°", "∘"])))

        if by < 6 and self.state["booster_vel_y"] > 0.6:
            trail_len = min(4, int(self.state["booster_vel_y"] * 3))
            for i in range(1, trail_len):
                if by - i >= 0 and 0 <= bx < 25:
                    intensity = trail_len - i
                    effects.append((by - i, bx, ["˙", "·", "▪"][min(intensity - 1, 2)]))

        return effects

    def _booster_sprite(self):
        frame    = self.state["animation_frame"] % 8
        velocity = self.state["booster_vel_y"]

        if self.state["landing_burn_active"]:
            return ["🔥", "💥", "⚡", "🌟", "🔥", "💥", "⚡", "🌟"][frame]
        elif self.state["engine_light"] or self.state["auto_engine_active"]:
            return ["🚀", "🔥", "💨", "⚡", "🛸", "💥", "🌟", "✨"][frame]
        elif self.state["phase"] == "catch_zone":
            return "🚀" if frame < 4 else "📍"
        elif velocity > 0.8:
            return ["🚀", "🛸", "🌟", "💫", "🔥", "⚡", "✨", "💥"][frame]
        else:
            return ["🚀", "🛸", "🚁", "🛰️", "🚀", "🛸", "🚁", "🛰️"][frame]

    def _particles(self):
        if not (self.state["engine_light"] or self.state["auto_engine_active"]
                or self.state["landing_burn_active"]):
            return []

        particles = []
        bx    = int(self.state["booster_x"])
        by    = int(self.state["booster_y"])
        frame = self.state["animation_frame"] % 8

        if self.state["landing_burn_active"]:
            mult = 1.5 if frame < 4 else 1.0
            for i in range(1, int(6 * mult)):
                if by + i < 12 and 0 <= bx < 25:
                    d = i / (6 * mult)
                    particles.append((by + i, bx,
                                      "🔥" if d < 0.3 else "💥" if d < 0.5 else "💨" if d < 0.7 else "·"))
            for side in [-1, 1]:
                if 0 <= bx + side < 25:
                    for i in range(1, 4):
                        if by + i < 12:
                            particles.append((by + i, bx + side, "💨" if i == 1 else "·"))
            if frame < 3:
                for i in range(2, 6, 2):
                    if by + i < 12 and 0 <= bx < 25:
                        particles.append((by + i, bx, "◊"))
        else:
            thrust_len = 4 if self.state["engine_light"] else 3
            for i in range(1, thrust_len + 1):
                if by + i < 12 and 0 <= bx < 25:
                    particles.append((by + i, bx, ["🔥", "💨", "·", "˙"][min(i - 1, 3)]))
            if frame % 2 == 0:
                for side in [-1, 1]:
                    if 0 <= bx + side < 25 and by + 1 < 12:
                        particles.append((by + 1, bx + side, "°"))

        return particles

    def _tower_light(self):
        frame = self.state["animation_frame"] % 16
        if self.state["catch_ready"]:
            return "●" if frame < 8 else "○"
        elif self.state["booster_y"] > 6:
            return "●" if frame < 12 else "○"
        return "●"

    def make_field(self):
        """Build the ASCII game grid."""
        lines       = []
        particles   = self._particles()
        atmospheric = self._atmospheric_effects()
        tower_light = self._tower_light()
        frame       = self.state["animation_frame"] % 8

        for row in range(12):
            line = [" "] * 25

            # Twinkling stars in upper sky
            if row < 4 and random.random() < 0.03:
                line[random.randint(0, 24)] = random.choice(["·", "✦", "○", "◦", "∘", "°", "˙"])

            # Wind indicator row
            if row == 1:
                ws = abs(self.state["wind"])
                if ws > 0.15:
                    line[23] = "🌪️" if self.state["wind"] > 0 else "💨"
                elif ws > 0.05:
                    line[23] = "~" if self.state["wind"] > 0 else "≈"

            # Atmospheric heating shimmer
            if row < 6:
                heat = (6 - row) * 0.1
                if random.random() < heat * 0.05:
                    line[random.randint(5, 19)] = random.choice(["°", "·", "˙"])

            # Draw booster
            brow = int(self.state["booster_y"])
            bcol = max(0, min(24, int(self.state["booster_x"])))
            if row == brow:
                line[bcol] = self._booster_sprite()

            # Particles & atmospheric effects
            for p_row, p_col, p_char in particles + atmospheric:
                if p_row == row and 0 <= p_col < 25 and line[p_col] == " ":
                    line[p_col] = p_char

            # Altitude ruler markers
            if row in [2, 5, 8]:
                line[0]  = "┤" if row == 2 else "├" if row == 8 else "│"
                line[24] = "┤" if row == 2 else "├" if row == 8 else "│"

            # Trajectory prediction arrow when in catch zone
            if self.state["catch_ready"] and row == brow + 1:
                pred_x = int(self.state["booster_x"] + self.state["booster_vel_x"] * 2)
                if 0 <= pred_x < 25 and line[pred_x] == " ":
                    line[pred_x] = "↓"

            lines.append("".join(line))

        # ── Tower row ──
        tower      = ["═"] * 25
        base_chars = ["█", "▓", "▒", "░", "▒", "▓"]

        left_pos = max(0, int(self.state["arm_left"]))
        for i in range(left_pos, min(left_pos + 3, 25)):
            tower[i] = "╫" if self.state["catch_ready"] else "╪" if i == left_pos else "═" if i == left_pos + 1 else "─"

        right_pos = min(24, int(self.state["arm_right"]))
        for i in range(max(0, right_pos - 2), right_pos + 1):
            tower[i] = "╫" if self.state["catch_ready"] else "╪" if i == right_pos else "═" if i == right_pos - 1 else "─"

        tower[0]  = "║";  tower[1]  = tower_light
        tower[24] = "║";  tower[23] = tower_light

        if self.state["catch_ready"]:
            center = (self.state["arm_left"] + self.state["arm_right"]) // 2
            if 3 <= center <= 21:
                tower[center] = "🎯" if frame < 4 else "⭕"

        # Energy field when arms just moved
        if self._last_arm_pos != (self.state["arm_left"], self.state["arm_right"]):
            for i in range(max(0, left_pos - 1), min(25, right_pos + 2)):
                if tower[i] == "═" and random.random() < 0.3:
                    tower[i] = "⚡" if frame < 2 else "═"
        self._last_arm_pos = (self.state["arm_left"], self.state["arm_right"])

        lines.append("".join(tower))

        # ── Ground row ──
        ground = ["█"] * 25
        if self.state["game_over"] and not self.state["success"]:
            ix = int(self.state["booster_x"])
            for i in range(max(0, ix - 2), min(25, ix + 3)):
                d = abs(i - ix)
                ground[i] = "💥" if d == 0 else "▓" if d == 1 else "▒"
        lines.append("".join(ground))

        return "\n".join(lines)

    # ── PHYSICS ─────────────────────────────────────────────────────

    def _calc_burn_altitude(self):
        vel = self.state["booster_vel_y"]
        if vel <= 0:
            return None
        reduction = vel - 0.4
        burn_time = reduction / 0.25
        dist      = vel * burn_time + 0.5 * (0.025 - 0.25) * burn_time ** 2
        return max(1.5, (12 - self.state["booster_y"]) - dist)

    def _landing_burn(self):
        altitude = 12 - self.state["booster_y"]

        if self.state["optimal_burn_altitude"] is None:
            self.state["optimal_burn_altitude"] = self._calc_burn_altitude()

        if (not self.state["landing_burn_initiated"]
                and self.state["optimal_burn_altitude"]
                and altitude <= self.state["optimal_burn_altitude"]
                and self.state["fuel"] > 10):
            self.state["landing_burn_initiated"] = True
            self.timeline.append("🔥 **LANDING BURN SEQUENCE INITIATED**")

        if (self.state["landing_burn_initiated"]
                and not self.state["landing_burn_active"]
                and self.state["fuel"] > 5
                and self.state["booster_vel_y"] > 0.4):
            self.state["landing_burn_active"]   = True
            self.state["booster_vel_y"]         -= 0.3
            self.state["fuel"]                  -= 12
            if altitude <= 2.0:
                self.timeline.append("🌟 **FINAL LANDING BURN - MAXIMUM THRUST**")
            elif altitude <= 3.5:
                self.timeline.append("⚡ **LANDING BURN - TRAJECTORY CORRECTION**")

        elif (self.state["landing_burn_active"]
              and self.state["fuel"] > 0
              and self.state["booster_vel_y"] > 0.35):
            err = self.state["booster_vel_y"] - 0.4
            if err > 0.1:
                adj = min(0.2, err * 0.8)
                self.state["booster_vel_y"] -= adj
                self.state["fuel"]          -= int(adj * 40)

        elif (self.state["landing_burn_active"]
              and (self.state["booster_vel_y"] <= 0.35 or self.state["fuel"] <= 5)):
            self.state["landing_burn_active"] = False
            if self.state["booster_vel_y"] <= 0.35:
                self.timeline.append("✅ **Landing burn complete - Optimal velocity achieved**")
            else:
                self.timeline.append("⚠️ **Landing burn terminated - Low fuel**")

    def _auto_engine(self):
        if (self.state["booster_vel_y"] > 1.2
                and self.state["fuel"] > 15
                and not self.state["landing_burn_initiated"]):
            self.state["auto_engine_active"] = True
            self.state["booster_vel_y"]      -= 0.15
            self.state["fuel"]               -= 8
        else:
            self.state["auto_engine_active"] = False

    def update_game(self):
        """One physics tick."""
        self.state["animation_frame"] += 1

        # Wind gusts + decay
        if random.random() < 0.15:
            self.state["wind"] += random.uniform(-0.03, 0.03)
            self.state["wind"]  = max(-0.25, min(0.25, self.state["wind"]))
        self.state["wind"] *= 0.98

        # Wind drift (altitude-scaled)
        alt_factor = max(0.5, (12 - self.state["booster_y"]) / 12)
        self.state["booster_vel_x"] += self.state["wind"] * alt_factor * 0.06

        # Gravity with atmospheric drag
        drag    = 1.0 - self.state["booster_vel_y"] * 0.01
        self.state["booster_vel_y"] += 0.025 * drag

        # Burn systems
        self._landing_burn()
        if not self.state["landing_burn_active"] and not self.state["landing_burn_initiated"]:
            self._auto_engine()

        # Clear manual engine flag
        if self.state["engine_light"]:
            self.state["engine_light"] = False

        # Move booster
        self.state["booster_x"] += self.state["booster_vel_x"]
        self.state["booster_y"] += self.state["booster_vel_y"]

        # Wall bounces
        if self.state["booster_x"] <= 0:
            self.state["booster_x"]     = 0
            self.state["booster_vel_x"] = abs(self.state["booster_vel_x"]) * 0.3
            self.timeline.append("💥 **Left wall collision!**")
        elif self.state["booster_x"] >= 24:
            self.state["booster_x"]     = 24
            self.state["booster_vel_x"] = -abs(self.state["booster_vel_x"]) * 0.3
            self.timeline.append("💥 **Right wall collision!**")

        # Altitude warnings
        altitude = 12 - self.state["booster_y"]
        warn     = self.state["altitude_warnings"]
        if altitude <= 5 and warn == 0:
            self.timeline.append("⚠️ **ALTITUDE WARNING - 5km remaining**")
            self.state["altitude_warnings"] = 1
        elif altitude <= 3 and warn == 1:
            self.timeline.append("🚨 **CRITICAL ALTITUDE - 3km remaining**")
            self.state["altitude_warnings"] = 2
        elif altitude <= 1.5 and warn == 2:
            self.timeline.append("🔴 **FINAL APPROACH - CATCH IMMEDIATELY!**")
            self.state["altitude_warnings"] = 3

        # Catch zone activation
        if self.state["booster_y"] >= 9.5 and not self.state["catch_ready"]:
            self.state["catch_ready"] = True
            self.state["phase"]       = "catch_zone"
            self.timeline.append("🎯 **CATCH ZONE ACTIVE - WINDOW OPEN!**")

        # Crash detection
        if self.state["booster_y"] >= 11.5:
            self.state["game_over"] = True
            spd = self.state["booster_vel_y"]
            self.timeline.append(
                "💥 **CATASTROPHIC IMPACT - Total loss!**"   if spd > 1.5 else
                "💥 **Hard impact - Major damage sustained**" if spd > 1.0 else
                "💥 **Rough landing - Minor damage**"
            )

    # ── ACTION HANDLER ──────────────────────────────────────────────

    def check_catch(self):
        bx, by = self.state["booster_x"], self.state["booster_y"]
        left   = self.state["arm_left"]  + 1
        right  = self.state["arm_right"] - 1

        pos_ok  = left <= bx <= right
        alt_ok  = 10.5 <= by <= 11.2
        vel_ok  = abs(self.state["booster_vel_y"]) < 0.7
        lat_ok  = abs(self.state["booster_vel_x"]) < 0.5

        if pos_ok and alt_ok and abs(self.state["booster_vel_y"]) < 0.5 and lat_ok:
            return "perfect"
        elif pos_ok and alt_ok and vel_ok:
            return "good"
        elif pos_ok and alt_ok:
            return "rough"
        elif abs(bx - (left + right) / 2) < 3 and alt_ok:
            return "near_miss"
        return "miss"

    def handle_action(self, action: str) -> bool:
        if self.state["game_over"]:
            return False

        if action == "left" and self.state["arm_left"] > 2:
            self.state["arm_left"]  -= 2
            self.state["arm_right"] -= 2
            self.timeline.append("⬅️ **Arms repositioned LEFT**")
            return True

        if action == "right" and self.state["arm_right"] < 22:
            self.state["arm_left"]  += 2
            self.state["arm_right"] += 2
            self.timeline.append("➡️ **Arms repositioned RIGHT**")
            return True

        if action == "thrust" and self.state["fuel"] > 0:
            power = min(20, self.state["fuel"])
            self.state["booster_vel_y"] -= 0.25 * (power / 20)
            self.state["fuel"]          -= power
            self.state["engine_light"]   = True
            self.timeline.append("🔥 **Full thrust burn!**" if power >= 15 else "💨 **Low power thrust**")
            return True

        if action == "catch" and self.state["catch_ready"]:
            result = self.check_catch()
            scores_map = {"perfect": 200, "good": 150, "rough": 100}
            msgs_map   = {
                "perfect":   "🌟 **PERFECT CATCH! FLAWLESS EXECUTION!**",
                "good":      "✅ **Excellent catch! Well executed!**",
                "rough":     "✅ **Rough but successful catch!**",
                "near_miss": "⚠️ **Near miss! Adjust and try again!**",
                "miss":      "❌ **Catch attempt failed - Booster missed!**",
            }
            self.timeline.append(msgs_map[result])
            if result in scores_map:
                self.state["success"]   = True
                self.state["game_over"] = True
                self.state["score"]     = scores_map[result]
            return True

        return False

    # ── EMBED ───────────────────────────────────────────────────────

    def make_embed(self, status: str = "") -> discord.Embed:
        field = f"```ansi\n{self.make_field()}\n```"

        # Fuel bar
        fuel_pct    = self.state["fuel"] / 100
        fuel_blocks = int(fuel_pct * 15)
        fuel_dot    = "🟢" if fuel_pct > 0.7 else "🟡" if fuel_pct > 0.4 else "🟠" if fuel_pct > 0.2 else "🔴"
        fuel_bar    = fuel_dot * fuel_blocks + "⚫" * (15 - fuel_blocks)

        # Wind indicator
        ws = abs(self.state["wind"])
        if ws < 0.05:
            wind_str = "🟢 Calm"
        elif ws < 0.10:
            wind_str = f"🟡 {'←' if self.state['wind'] < 0 else '→'} Light Breeze"
        elif ws < 0.20:
            wind_str = f"🟠 {'⬅️' if self.state['wind'] < 0 else '➡️'} Moderate Wind"
        else:
            wind_str = f"🔴 {'⬅️⬅️' if self.state['wind'] < 0 else '➡️➡️'} Strong Gust"

        # Phase label
        phase_labels = {
            "falling":    f"🛸 **Atmospheric Entry** (Alt: {12 - self.state['booster_y']:.1f}km)",
            "catch_zone": "🎯 **🚨 CATCH ZONE ACTIVE 🚨**",
        }

        # Auto-system status
        if self.state["landing_burn_active"]:
            sys_str = "🔥 Landing Burn ACTIVE"
        elif self.state["auto_engine_active"]:
            sys_str = "🤖 Auto-Stabilizer ON"
        elif self.state["landing_burn_initiated"]:
            sys_str = "⏳ Landing Burn READY"
        else:
            sys_str = "⚫ Manual Control"

        # Dynamic embed colour
        if self.state["catch_ready"]:
            color = 0xFF0000
        elif self.state["booster_y"] > 8:
            color = 0xFF6B00
        elif self.state["landing_burn_active"]:
            color = 0x00FF00
        else:
            color = 0x0099FF

        embed = discord.Embed(title="🚀 Catch Booster 16 — Mechzilla", description=field, color=color)

        embed.add_field(
            name="📊 Mission Control",
            value=(
                f"**Fuel:** {fuel_bar} {self.state['fuel']}%\n"
                f"**Wind:** {wind_str}\n"
                f"**Phase:** {phase_labels.get(self.state['phase'], self.state['phase'].upper())}\n"
                f"**Systems:** {sys_str}"
            ),
            inline=True,
        )

        altitude = 12 - self.state["booster_y"]
        vy       = self.state["booster_vel_y"]
        vx       = self.state["booster_vel_x"]
        v_ind    = "↓" if vy > 0.5 else "→" if vy > 0 else "↑"
        h_ind    = "→" if vx > 0 else "←" if vx < 0 else "•"

        embed.add_field(
            name="📡 Flight Data",
            value=(
                f"**Altitude:** {altitude:.1f}km {v_ind}\n"
                f"**V-Speed:** {abs(vy):.2f}m/s\n"
                f"**H-Speed:** {abs(vx):.2f}m/s {h_ind}\n"
                f"**Position:** {self.state['booster_x']:.1f}m\n"
                f"**Arms Gap:** {self.state['arm_right'] - self.state['arm_left']:.0f}m"
            ),
            inline=True,
        )

        if self.timeline:
            embed.add_field(
                name="📺 Mission Log",
                value="\n".join(self.timeline[-4:]),
                inline=False,
            )

        if status:
            embed.add_field(name="🚨 STATUS UPDATE", value=f"**{status}**", inline=False)

        tips = [
            "🎮 Use buttons to control • 🔥 Advanced Auto-Landing System active",
            "💡 TIP: Position arms early for better catches!",
            "⚡ TIP: Save fuel for final approach corrections!",
            "🎯 TIP: Watch horizontal velocity in the catch zone!",
        ]
        embed.set_footer(text=tips[self.state["animation_frame"] % len(tips)])
        return embed


# ─── COMMAND REGISTRATION ──────────────────────────────────────────

def _register_commands(bot: commands.Bot):

    @bot.command(name="catchbooster", aliases=["booster","mechzilla","catch16"])
    async def cmd_catchbooster(ctx):
        """
        Mechzilla.io-style booster catching game.
        Use the arm buttons to position the chopstick arms,
        thrust to slow the descent, and hit CATCH! at the right moment.
        """
        game = BoosterCatchGame(ctx)
        view = CatchGameView(game)
        game.view = view

        embed = game.make_embed("🚀 **Mission Control Online — Booster separation confirmed!**")
        msg   = await ctx.send(embed=embed, view=view)

        await asyncio.sleep(2)
        start_time       = time.time()
        last_update_time = time.time()

        # ── GAME LOOP ──
        while not game.state["game_over"]:
            now = time.time()
            game.update_game()

            interval = (
                0.4 if game.state["catch_ready"]   else
                0.5 if game.state["booster_y"] > 8 else
                0.6
            )

            if now - last_update_time >= interval:
                altitude = 12 - game.state["booster_y"]
                velocity = game.state["booster_vel_y"]

                if game.state["catch_ready"]:
                    status_msg = "🚨 **CATCH WINDOW OPEN — EXECUTE IMMEDIATELY!** 🚨"
                elif game.state["landing_burn_active"]:
                    status_msg = "🔥 **LANDING BURN ACTIVE — Automatic control engaged**"
                elif altitude <= 2:
                    status_msg = "🔴 **FINAL APPROACH — Last chance for corrections!**"
                elif altitude <= 4:
                    status_msg = "⚠️ **Critical altitude — Position arms NOW!**"
                elif velocity > 1.0:
                    status_msg = "⚡ **High velocity detected — Consider thrust burn**"
                elif game.state["auto_engine_active"]:
                    status_msg = "🤖 **Auto-stabilizers maintaining safe trajectory**"
                elif altitude <= 8:
                    status_msg = "🎯 **Approach phase — Monitor systems closely**"
                else:
                    status_msg = "🚀 **Descent phase — All systems nominal**"

                view.update_button_states()
                try:
                    await msg.edit(embed=game.make_embed(status_msg), view=view)
                    last_update_time = now
                except discord.errors.NotFound:
                    break
                except discord.errors.HTTPException:
                    await asyncio.sleep(0.2)

            await asyncio.sleep(0.1)

        # Disable all buttons
        for item in view.children:
            item.disabled = True

        # ── SCORING ──
        elapsed  = time.time() - start_time
        user_id  = ctx.author.id

        if game.state["success"]:
            base_score      = game.state["score"]
            time_bonus      = max(0, int(100 - elapsed * 2))
            fuel_bonus      = game.state["fuel"] // 2
            arm_center      = (game.state["arm_left"] + game.state["arm_right"]) / 2
            precision_err   = abs(arm_center - game.state["booster_x"])
            precision_bonus = max(0, int(50 - precision_err * 10))
            vel_bonus       = max(0, int(30 - abs(game.state["booster_vel_y"]) * 20))
            auto_penalty    = 20 if hasattr(game, "_auto_engine_used") else 0
            total_score     = base_score + time_bonus + fuel_bonus + precision_bonus + vel_bonus - auto_penalty

            if _add_score:
                _add_score(user_id, total_score)
            user_total = (_scores_ref or {}).get(str(user_id), 0)

            final = discord.Embed(
                title="🏆 MISSION SUCCESS! BOOSTER RECOVERED!",
                description=f"**{ctx.author.display_name}** caught the booster with Mechzilla!",
                color=0x00FF00,
            )
            final.add_field(
                name="📊 Detailed Scoring",
                value=(
                    f"**Base Score:** {base_score} pts\n"
                    f"**Time Bonus:** +{time_bonus} pts\n"
                    f"**Fuel Bonus:** +{fuel_bonus} pts\n"
                    f"**Precision Bonus:** +{precision_bonus} pts\n"
                    f"**Velocity Bonus:** +{vel_bonus} pts\n"
                    f"**Auto-Pilot Penalty:** -{auto_penalty} pts\n"
                    f"**MISSION TOTAL:** **{total_score} pts**"
                ),
                inline=True,
            )
            final.add_field(
                name="⏱️ Mission Stats",
                value=(
                    f"**Duration:** {elapsed:.1f}s\n"
                    f"**Fuel Remaining:** {game.state['fuel']}%\n"
                    f"**Final Velocity:** {abs(game.state['booster_vel_y']):.2f}m/s\n"
                    f"**Precision Error:** {precision_err:.1f}m"
                ),
                inline=True,
            )

            achievements = []
            if base_score >= 200:    achievements.append("🌟 Perfect Landing Master")
            if fuel_bonus >= 40:     achievements.append("⛽ Fuel Conservation Expert")
            if time_bonus >= 60:     achievements.append("⚡ Lightning Fast Pilot")
            if precision_bonus >= 40:achievements.append("🎯 Precision Specialist")
            if vel_bonus >= 25:      achievements.append("🪶 Feather Touch Landing")
            if auto_penalty == 0:    achievements.append("🎮 Manual Flight Ace")
            if total_score >= 300:   achievements.append("👨‍🚀 Elite Space Pilot")
            if achievements:
                final.add_field(name="🏅 Achievements", value="\n".join(achievements), inline=False)

            final.add_field(
                name="🏆 Career Statistics",
                value=f"**Total Career Points:** {user_total:,} pts\nCheck `!leaderboard` for rank!",
                inline=False,
            )

        else:
            final = discord.Embed(
                title="💥 MISSION FAILED — BOOSTER LOST",
                description="Mission analysis and recommendations:",
                color=0xFF0000,
            )
            final.add_field(
                name="📋 Failure Analysis",
                value=(
                    f"**Impact Velocity:** {game.state['booster_vel_y']:.2f}m/s\n"
                    f"**Final Position:** {game.state['booster_x']:.1f}m\n"
                    f"**Fuel Remaining:** {game.state['fuel']}%\n"
                    f"**Mission Duration:** {elapsed:.1f}s"
                ),
                inline=True,
            )

            recs = []
            if game.state["booster_vel_y"] > 1.5:  recs.append("• Use thrust burns earlier to slow descent")
            if game.state["fuel"] > 50:             recs.append("• Don't hoard fuel — use it for control")
            if abs(game.state["booster_x"] - 12) > 5: recs.append("• Reposition arms earlier in the descent")
            recs.append("• Watch the auto-landing burn — it fires automatically")
            final.add_field(name="💡 Recommendations", value="\n".join(recs), inline=True)
            final.add_field(
                name="📺 Final Event",
                value=game.timeline[-1] if game.timeline else "System malfunction",
                inline=False,
            )

            consolation = 10
            if _add_score:
                _add_score(user_id, consolation)
            user_total = (_scores_ref or {}).get(str(user_id), 0)
            final.add_field(
                name="🎖️ Participation Award",
                value=f"+{consolation} pts for mission attempt\n**Career Total:** {user_total:,} pts",
                inline=False,
            )

        final.set_footer(text="🚀 Use !catchbooster again to retry! • !leaderboard for rankings")

        try:
            await msg.edit(embed=final, view=view)
        except Exception:
            await ctx.send(embed=final)

    @bot.command(name="catchhelp", aliases=["boosterhelp"])
    async def cmd_catchhelp(ctx):
        """How to play Booster Catch."""
        emb = discord.Embed(
            title="🚀 Booster Catch — How to Play",
            description=(
                "Catch Booster 16 with Mechzilla's chopstick arms before it hits the ground!\n\n"
                "The booster falls from the top of the screen. You control the catch tower."
            ),
            color=0x0099FF,
        )
        emb.add_field(
            name="🎮 Controls",
            value=(
                "**← Arms Left / Arms Right →** — Move the chopstick arms horizontally\n"
                "**🔥 THRUST** — Fire the booster's engines to slow descent (uses fuel!)\n"
                "**🥢 CATCH!** — Attempt to grab the booster (only active in catch zone)"
            ),
            inline=False,
        )
        emb.add_field(
            name="🏆 Catch Ratings",
            value=(
                "🌟 **Perfect** — 200 pts (ideal speed, position, and altitude)\n"
                "✅ **Good** — 150 pts\n"
                "✅ **Rough** — 100 pts\n"
                "⚠️ **Near Miss** — 0 pts, try again!\n"
                "❌ **Miss** — 0 pts"
            ),
            inline=False,
        )
        emb.add_field(
            name="💡 Tips",
            value=(
                "• Position arms **before** the booster enters the catch zone\n"
                "• The auto-landing burn fires automatically — trust it\n"
                "• Use thrust early if velocity is high (>1.0m/s)\n"
                "• Watch the **H-Speed** — horizontal drift makes catches harder\n"
                "• Bonuses for time, fuel, precision and low final velocity"
            ),
            inline=False,
        )
        emb.set_footer(text="Start a game: !catchbooster")
        await ctx.send(embed=emb)
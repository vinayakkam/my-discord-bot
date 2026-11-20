import discord
from discord.ext import commands
import random, asyncio, time, math
from typing import Callable, Optional

# ─── MODULE REFS ───────────────────────────────────────────────────
_bot: commands.Bot | None = None
_add_score: Callable | None = None
_scores_ref: dict | None = None


def setup_booster_catch(bot: commands.Bot, add_score_fn: Callable, scores_dict: dict):
    global _bot, _add_score, _scores_ref
    _bot = bot
    _add_score = add_score_fn
    _scores_ref = scores_dict
    _register_commands(bot)
    print("[BOOSTER CATCH] Multi-server Slash & Prefix Module Loaded!")


# ══════════════════════════════════════════════════════════════════
#  GRID & PHYSICS CONSTANTS
# ══════════════════════════════════════════════════════════════════

GRID_W = 32
GRID_H = 18
TOWER_ROW = 18
GROUND_ROW = 19

# Rendered canvas: GRID_H rows of sky, the chopstick arm row, two rows of open
# tower below the arms, then the ground. Physics never reads these.
_ARM_ROW = GRID_H
_GROUND_ROW = GRID_H + 3
_CANVAS_H = GRID_H + 4
_TOWER_TOP = 7  # first lattice row of the Mechzilla tower

WALL_L = 3  # left wall — booster bounces off this column
WALL_R = 28  # right wall

# Physics
GRAVITY = 0.11
DRAG_COEFF = 0.12
DRY_MASS = 10.0
FULL_FUEL_KG = 10.0
ENGINE_THRUST = 20.0
FUEL_FLOW = 0.9
THRUST_PULSE_DURATION = 1.2

WIND_BASE_ACCEL = 0.5
WIND_OU_THETA = 1.5  # mean-reversion speed
WIND_OU_SIGMA = 0.22  # diffusion noise
WIND_SUPPRESS_DURATION = 0.5  # seconds

# Catch geometry
CATCH_ZONE_Y = 14.0
CRASH_Y = 19.5
ARM_HALF = 5
ARM_INNER_MARGIN = 1

ARM_CENTER_MIN = WALL_L + ARM_HALF - ARM_INNER_MARGIN  # = 7
ARM_CENTER_MAX = WALL_R - ARM_HALF + ARM_INNER_MARGIN  # = 24

# Catch quality thresholds (wu/s)
PERFECT_VY = 0.8;
GOOD_VY = 1.6;
ROUGH_VY = 2.8
PERFECT_VX = 0.5;
GOOD_VX = 1.2

ADVISORY_VY = 1.5

# Game loop timing
PHYS_DT = 0.12
DISP_FAST = 0.85
DISP_SLOW = 1.30


# ══════════════════════════════════════════════════════════════════
#  STAR FIELD
# ══════════════════════════════════════════════════════════════════

# Single-width glyphs only: the field is shown in a monospace code block.
_STAR_CHARS = ("·", "·", "˙", ".", "∙", "'")


def _make_star_field(seed: int) -> list:
    rng = random.Random(seed)
    field = [[""] * GRID_W for _ in range(GRID_H)]
    for row in range(GRID_H):
        density = 0.06 * (1.0 - row / GRID_H * 0.7)
        for col in range(1, GRID_W - 1):
            if rng.random() < density:
                field[row][col] = rng.choice(_STAR_CHARS)
    return field


# ══════════════════════════════════════════════════════════════════
#  VIEW (BUTTONS)
# ══════════════════════════════════════════════════════════════════

class CatchGameView(discord.ui.View):
    def __init__(self, game: "BoosterCatchGame"):
        super().__init__(timeout=300)
        self.game = game
        self.sync_buttons()

    def sync_buttons(self):
        g = self.game
        self.btn_thrust.disabled = (g.fuel_kg <= 0 or g.state == "over" or g.thrust_timer > 0)
        self.btn_catch.disabled = (not g.catch_window_open or g.state == "over")
        self.btn_left.disabled = (g.arm_center <= ARM_CENTER_MIN or g.state == "over")
        self.btn_right.disabled = (g.arm_center >= ARM_CENTER_MAX or g.state == "over")
        if g.state == "over":
            for item in self.children:
                item.disabled = True

    def _ok(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.game.author_id

    @discord.ui.button(label="← Arms", style=discord.ButtonStyle.secondary, emoji="⬅️", row=0)
    async def btn_left(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._ok(interaction):
            self.game.action_move_arms(-4)
            self.sync_buttons()
        try:
            await interaction.response.defer()
        except Exception:
            pass

    @discord.ui.button(label="Arms →", style=discord.ButtonStyle.secondary, emoji="➡️", row=0)
    async def btn_right(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._ok(interaction):
            self.game.action_move_arms(+4)
            self.sync_buttons()
        try:
            await interaction.response.defer()
        except Exception:
            pass

    @discord.ui.button(label="🔥 THRUST", style=discord.ButtonStyle.danger, emoji="⬆️", row=0)
    async def btn_thrust(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._ok(interaction):
            self.game.action_thrust()
            self.sync_buttons()
        try:
            await interaction.response.defer()
        except Exception:
            pass

    @discord.ui.button(label="🥢 CATCH!", style=discord.ButtonStyle.success, row=0)
    async def btn_catch(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._ok(interaction):
            self.game.action_catch()
            self.sync_buttons()
        try:
            await interaction.response.defer()
        except Exception:
            pass

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


# ══════════════════════════════════════════════════════════════════
#  GAME ENGINE
# ══════════════════════════════════════════════════════════════════

class BoosterCatchGame:
    ARM_HALF = ARM_HALF
    ARM_SPEED = 4

    def __init__(self, author_id: int, author_name: str):
        self.author_id = author_id
        self.author_name = author_name

        # Kinematics
        self.pos_x: float = random.uniform(WALL_L + 4.0, WALL_R - 4.0)
        self.pos_y: float = 0.0
        self.vel_x: float = random.uniform(-0.5, 0.5)
        self.vel_y: float = 0.2

        # Fuel & mass
        self.fuel_kg: float = float(FULL_FUEL_KG)

        # Wind
        self.wind_accel: float = random.uniform(-0.1, 0.1)
        self._wind_suppress: float = 0.0

        # Arms
        self.arm_center: float = float(GRID_W // 2)
        self._last_arm_center = self.arm_center

        # Engine
        self.thrust_timer: float = 0.0
        self.engine_on: bool = False
        self.manual_burns: int = 0

        # Animation
        self.anim_frame: int = 0
        self._star_field = _make_star_field(random.randint(0, 99999))
        rng = random.Random(random.randint(0, 9999))
        self._twinkle_cells = [
            (rng.randint(0, GRID_H - 5), rng.randint(1, GRID_W - 2))
            for _ in range(8)
        ]
        self._sonic_boom_frame: int = -999
        self._last_vel_y: float = 0.0

        self._wind_arrow_frame: int = 0

        # Game state
        self.state: str = "falling"
        self.catch_window_open: bool = False
        self.catch_result: str = ""
        self.success: bool = False
        self.score: int = 0
        self.altitude_warned: int = 0
        self._advisory_shown: bool = False
        self._catch_vel_y: float = 0.0

        self.timeline: list = ["🚀 **Booster 16 separation confirmed**"]

    @property
    def mass(self) -> float:
        return DRY_MASS + max(0.0, self.fuel_kg)

    @property
    def altitude(self) -> float:
        return max(0.0, CRASH_Y - self.pos_y)

    @property
    def fuel_pct(self) -> int:
        return int(100 * max(0.0, self.fuel_kg) / FULL_FUEL_KG)

    @property
    def arm_left(self) -> float:
        return self.arm_center - self.ARM_HALF

    @property
    def arm_right(self) -> float:
        return self.arm_center + self.ARM_HALF

    def update_physics(self, dt: float):
        if self.state == "over":
            return

        self.anim_frame += 1
        self._last_vel_y = self.vel_y
        self._wind_arrow_frame += 1

        # ── 1. Wind ──────────────────────────────────────────────────
        if self._wind_suppress > 0:
            self._wind_suppress -= dt
            self.wind_accel *= max(0.0, 1.0 - dt * 4)
        else:
            dW = (-WIND_OU_THETA * self.wind_accel * dt
                  + WIND_OU_SIGMA * math.sqrt(dt) * random.gauss(0, 1))
            self.wind_accel += dW
        self.wind_accel = max(-WIND_BASE_ACCEL, min(WIND_BASE_ACCEL, self.wind_accel))

        # ── 2. Engine ────────────────────────────────────────────────
        if self.thrust_timer > 0 and self.fuel_kg > 0:
            self.engine_on = True
            burn_dt = min(dt, self.thrust_timer)
            self.thrust_timer = max(0.0, self.thrust_timer - burn_dt)
            self.fuel_kg = max(0.0, self.fuel_kg - FUEL_FLOW * burn_dt)
            if self.fuel_kg == 0.0:
                self.thrust_timer = 0.0
                self.timeline.append("⛽ **FUEL DEPLETED — Engine cut**")
        else:
            self.engine_on = False
            self.thrust_timer = max(0.0, self.thrust_timer)

        # ── 3. Forces ────────────────────────────────────────────────
        m = self.mass
        acc_y = (
                GRAVITY
                - DRAG_COEFF * self.vel_y * abs(self.vel_y) / m
                + (-ENGINE_THRUST / m if self.engine_on else 0.0)
        )
        acc_x = (
                -DRAG_COEFF * self.vel_x * abs(self.vel_x) / m
                + self.wind_accel
        )

        # ── 4. Euler integration ──────────────────────────────────────
        self.vel_y += acc_y * dt
        self.vel_x += acc_x * dt
        self.vel_x = max(-6.0, min(6.0, self.vel_x))
        self.pos_y += self.vel_y * dt
        self.pos_x += self.vel_x * dt

        if self._last_vel_y < 3.0 <= self.vel_y:
            self._sonic_boom_frame = self.anim_frame

        # ── 5. Wall boundaries ───────────────────────────────────────
        if self.pos_x < WALL_L:
            self.pos_x = float(WALL_L)
            bounce_speed = abs(self.vel_x)
            self.vel_x = bounce_speed * 0.65

            if bounce_speed > 1.5:
                self.timeline.append(f"💥 **WALL SLAM (left) — {bounce_speed:.1f} wu/s**")
            elif bounce_speed > 0.5:
                self.timeline.append("⚡ **Left wall deflection**")
            else:
                self.timeline.append("· Grazed left boundary")

            self.wind_accel = abs(self.wind_accel) * 0.4
            self._wind_suppress = WIND_SUPPRESS_DURATION

        elif self.pos_x > WALL_R:
            self.pos_x = float(WALL_R)
            bounce_speed = abs(self.vel_x)
            self.vel_x = -bounce_speed * 0.65

            if bounce_speed > 1.5:
                self.timeline.append(f"💥 **WALL SLAM (right) — {bounce_speed:.1f} wu/s**")
            elif bounce_speed > 0.5:
                self.timeline.append("⚡ **Right wall deflection**")
            else:
                self.timeline.append("· Grazed right boundary")

            self.wind_accel = -abs(self.wind_accel) * 0.4
            self._wind_suppress = WIND_SUPPRESS_DURATION

        # ── 6. Altitude warnings ─────────────────────────────────────
        alt = self.altitude
        if alt <= 12.0 and not (self.altitude_warned & 1):
            self.timeline.append("⚠️ **ALTITUDE 12 km — Begin approach checks**")
            self.altitude_warned |= 1
        if alt <= 6.0 and not (self.altitude_warned & 2):
            self.timeline.append("🚨 **ALTITUDE 6 km — CRITICAL**")
            self.altitude_warned |= 2
        if alt <= 3.0 and not (self.altitude_warned & 4):
            self.timeline.append("🔴 **FINAL APPROACH — CATCH NOW**")
            self.altitude_warned |= 4

        # ── 7. Landing burn advisory ─────────────────────────────────
        if not self._advisory_shown and self.fuel_kg > 0 and alt < 10.0:
            pred = math.sqrt(max(0.0, self.vel_y ** 2 + 2 * GRAVITY * max(0.0, alt - 1.0)))
            if pred > ADVISORY_VY:
                self.timeline.append(
                    f"🔥 **BURN ADVISORY — Predicted impact {pred:.1f} wu/s — fire engines!**")
                self._advisory_shown = True

        # ── 8. Catch zone ────────────────────────────────────────────
        if self.pos_y >= CATCH_ZONE_Y and not self.catch_window_open:
            self.catch_window_open = True
            self.state = "catch_zone"
            self.timeline.append("🎯 **CATCH ZONE ACTIVE — Window open!**")

        # ── 9. Crash ─────────────────────────────────────────────────
        if self.pos_y >= CRASH_Y:
            self.state = "over"
            self.success = False
            spd = self.vel_y
            self.timeline.append(
                "💥 **CATASTROPHIC IMPACT — Total loss**" if spd > 3.5 else
                "💥 **Hard impact — Severe damage**" if spd > 2.0 else
                "💥 **Rough contact — Booster buckled**"
            )

    def action_move_arms(self, direction: int):
        nc = max(ARM_CENTER_MIN, min(ARM_CENTER_MAX, self.arm_center + direction))
        self.arm_center = float(nc)
        self.timeline.append(
            f"{'⬅️' if direction < 0 else '➡️'} **Arms → col {int(self.arm_center)}**")

    def action_thrust(self):
        if self.fuel_kg <= 0 or self.thrust_timer > 0:
            return
        self.thrust_timer = THRUST_PULSE_DURATION
        self.manual_burns += 1
        low = " ⚠️ Low fuel!" if self.fuel_pct < 20 else ""
        self.timeline.append(f"🔥 **Burn #{self.manual_burns} ignited**{low}")

    def action_catch(self):
        if not self.catch_window_open or self.state == "over":
            return
        il = self.arm_left + ARM_INNER_MARGIN
        ir = self.arm_right - ARM_INNER_MARGIN
        ok = il <= self.pos_x <= ir
        dist_from_center = abs(self.pos_x - self.arm_center)
        near = dist_from_center < (self.ARM_HALF + 2.5)

        if not ok:
            cols_off = max(0.0, dist_from_center - self.ARM_HALF)
            if near:
                self.catch_result = "near_miss"
                self.timeline.append(
                    f"⚠️ **Near miss — {cols_off:.1f} cols off center — adjust and retry!**")
            else:
                self.catch_result = "miss"
                self.timeline.append(
                    f"❌ **Missed — booster {cols_off:.1f} cols outside arms**")
            return

        vy = abs(self.vel_y)
        vx = abs(self.vel_x)
        self._catch_vel_y = self.vel_y

        if vy < PERFECT_VY and vx < PERFECT_VX:
            self.catch_result, self.score = "perfect", 250
        elif vy < GOOD_VY and vx < GOOD_VX:
            self.catch_result, self.score = "good", 170
        elif vy < ROUGH_VY:
            self.catch_result, self.score = "rough", 90
        else:
            self.catch_result, self.score = "buckle", 30

        msgs = {
            "perfect": f"🌟 **PERFECT CATCH — {vy:.2f} wu/s — Textbook execution!**",
            "good": f"✅ **Clean catch — {vy:.2f} wu/s — Well done!**",
            "rough": f"✅ **Rough catch — {vy:.2f} wu/s — Arms held!**",
            "buckle": f"⚠️ **Arms buckled — {vy:.2f} wu/s — Barely held on!**",
        }
        self.timeline.append(msgs[self.catch_result])
        self.success = True
        self.state = "over"

    # ── RENDERING ──────────────────────────────────────────────────
    # The field is drawn inside a ``` code block, so every glyph here is
    # single-width: box drawing, block elements and plain ASCII. Emoji render
    # two columns wide in Discord and would shove the rest of their row
    # sideways, which is what made the old frames jitter.

    def _booster_top_row(self) -> int:
        """Canvas row of the grid fins.

        Maps pos_y 0..CRASH_Y onto rows 0.._ARM_ROW, so the engines (three
        rows below the fins) reach the ground row exactly at physics impact.
        """
        return max(0, min(_ARM_ROW, int(round(self.pos_y * _ARM_ROW / CRASH_Y))))

    def _booster_sprite(self) -> list:
        """The booster's four rows, top (grid fins) to bottom (engine skirt)."""
        # Grid fins alternate slowly so they read as actively steering.
        fins = "╪█╪" if (self.anim_frame // 2) % 2 == 0 else "╫█╫"
        if self.engine_on:
            engines = "▐▓▌"          # engines lit
        elif self.vel_y > 3.0:
            engines = "▝▒▘"          # skirt glowing from re-entry heating
        else:
            engines = "▝▀▘"
        return [fins, "▐█▌", "▐█▌", engines]

    def make_field(self) -> str:
        f8 = self.anim_frame % 8
        frame = self.anim_frame % 16
        canvas = [[" "] * GRID_W for _ in range(_CANVAS_H)]
        soft = set(_STAR_CHARS) | {" ", "+"}  # cells effects may draw over

        def put(row: int, col: int, ch: str, force: bool = False) -> None:
            # Draw one cell, clipped to the canvas; effects never cover structure.
            if 0 <= row < _CANVAS_H and 0 <= col < GRID_W:
                if force or canvas[row][col] in soft:
                    canvas[row][col] = ch

        bcol = max(WALL_L, min(WALL_R, int(self.pos_x)))
        top = self._booster_top_row()
        crashed = self.state == "over" and not self.success
        caught = self.state == "over" and self.success
        if caught:
            top = _ARM_ROW - 1   # held by the arms: body sits in the arm row
        engine_row = top + 3

        # ── Sky: static stars plus a few that twinkle ──
        for row in range(GRID_H):
            for col, ch in enumerate(self._star_field[row]):
                if ch:
                    canvas[row][col] = ch
        for i, (r, c) in enumerate(self._twinkle_cells):
            phase = (self.anim_frame + i) % 3
            if phase != 2:
                put(r, c, "+" if phase == 0 else "·")

        # ── Wind: edge indicator plus streaks drifting downwind ──
        ws = abs(self.wind_accel)
        downwind = 1 if self.wind_accel > 0 else -1
        if ws > WIND_BASE_ACCEL * 0.55:
            put(2, GRID_W - 3, ("»" if downwind > 0 else "«") if f8 < 4 else
                               ("›" if downwind > 0 else "‹"), force=True)
        elif ws > WIND_BASE_ACCEL * 0.20:
            put(2, GRID_W - 3, "~" if downwind > 0 else "≈", force=True)
        if ws > WIND_BASE_ACCEL * 0.20:
            streak = "-" if ws < WIND_BASE_ACCEL * 0.55 else "="
            for n, row in enumerate((4, 9, 13)):
                x = (n * 11 + self._wind_arrow_frame * 2 * downwind) % (WALL_R - WALL_L)
                put(row, WALL_L + x, streak)
                put(row, WALL_L + x + 1, streak)

        # ── Mechzilla tower: lattice on the right, warning light on top ──
        t_light = ("●" if frame < 8 else "○") if self.catch_window_open else \
            ("●" if frame < 13 else "○") if self.pos_y > GRID_H * 0.6 else "●"
        put(_TOWER_TOP - 1, GRID_W - 1, t_light, force=True)
        for row in range(_TOWER_TOP, _GROUND_ROW):
            canvas[row][GRID_W - 2] = "╲" if row % 2 == 0 else "╱"
            canvas[row][GRID_W - 1] = "╱" if row % 2 == 0 else "╲"

        # ── Chopstick arms on their carriage ──
        al = max(0, int(self.arm_left))
        ar = min(GRID_W - 3, int(self.arm_right))
        arms = canvas[_ARM_ROW]
        for i in range(al, min(al + 4, GRID_W)):
            arms[i] = ("╠" if self.catch_window_open else "╞") if i == al else \
                ("═" if i == al + 1 else "╪" if i == al + 2 else "┤")
        for i in range(max(0, ar - 3), ar + 1):
            arms[i] = ("╣" if self.catch_window_open else "╡") if i == ar else \
                ("═" if i == ar - 1 else "╪" if i == ar - 2 else "├")
        for i in range(ar + 1, GRID_W - 2):
            arms[i] = "─"                      # beam back to the tower
        arms[GRID_W - 2] = "█"                 # carriage on the tower
        if self.catch_window_open and not caught:
            # Catch guides between the arm tips, target blinking at center.
            for i in range(al + 4, ar - 3):
                arms[i] = "┄"
            gc = int(self.arm_center)
            if al + 4 <= gc < ar - 3:
                arms[gc] = "┼" if f8 < 4 else "┄"
        if abs(self.arm_center - self._last_arm_center) > 0.1:
            # Sparks along the arms while the carriage is moving.
            for i in range(al, ar + 1):
                if arms[i] in ("═", "─") and random.random() < 0.35:
                    arms[i] = "*" if f8 < 2 else arms[i]
        self._last_arm_center = self.arm_center

        # ── Ground ──
        for col in range(GRID_W):
            canvas[_GROUND_ROW][col] = "▓"
        canvas[_GROUND_ROW][GRID_W - 2] = "█"
        canvas[_GROUND_ROW][GRID_W - 1] = "█"

        # ── Re-entry heating: streaks trailing above a fast booster ──
        if self.vel_y >= 2.0 and not self.engine_on and self.state != "over":
            trail = min(6, int(self.vel_y * 1.2))
            for i in range(1, trail + 1):
                put(top - i, bcol, "│" if i == 1 else "╎" if i <= 3 else "┆" if i <= 4 else "·")
            if self.vel_y > 3.5:
                for side in (-2, 2):
                    put(top + random.randint(0, 2), bcol + side, random.choice(["'", "·", "~"]))

        # ── Sonic boom: a shock ring expanding sideways ──
        age = self.anim_frame - self._sonic_boom_frame
        if 0 <= age <= 5 and self.state != "over":
            r = age + 2
            for row in (top + 1, top + 2):
                put(row, bcol - r, "(")
                put(row, bcol + r, ")")

        # ── Engine plume: widening cone with shock diamonds ──
        if self.engine_on and self.state != "over":
            length = 6 if f8 < 4 else 4    # pulses as the engines throttle
            for i in range(1, length + 1):
                row = engine_row + i
                d = i / length
                core = "█" if i == 1 else ("◊" if i % 2 == 0 else "▓") if d < 0.6 else \
                    "▒" if d < 0.85 else "░"
                put(row, bcol, core)
                if i >= 2 and d < 0.9:
                    put(row, bcol - 1, "▒" if d < 0.5 else "░")
                    put(row, bcol + 1, "▒" if d < 0.5 else "░")
                if i >= 3 and 0.5 < d < 0.9:
                    put(row, bcol - 2, "░")
                    put(row, bcol + 2, "░")
            if engine_row + length >= _GROUND_ROW - 1:
                # Exhaust hitting the pad kicks up a dust cloud.
                for dx in range(-4, 5):
                    put(_GROUND_ROW - 1, bcol + dx, "▒" if abs(dx) <= 1 else "░")

        # ── Predicted touchdown column while the catch window is open ──
        if self.catch_window_open and self.state != "over":
            pred_x = max(WALL_L, min(WALL_R, int(self.pos_x + self.vel_x * 0.5)))
            on_guides = 0 <= engine_row + 1 < _CANVAS_H and \
                canvas[engine_row + 1][pred_x] in ("┄", "┼")
            put(engine_row + 1, pred_x, "↓", force=on_guides)

        # ── The booster itself, or what is left of it ──
        if crashed:
            fireball = ["  ░░░  ", " ░▒▓▒░ ", "░▒▓█▓▒░", "▀▄▀▄▀▄▀"]
            for dy, line in enumerate(fireball):
                for dx, ch in enumerate(line):
                    if ch != " ":
                        put(_ARM_ROW + dy, bcol - 3 + dx, ch, force=True)
        else:
            for dy, line in enumerate(self._booster_sprite()):
                for dx, ch in enumerate(line):
                    put(top + dy, bcol - 1 + dx, ch, force=True)
            if caught:
                # Arms closed: fill the gap so both tips meet the booster body.
                for i in range(al + 1, ar):
                    if not (bcol - 1 <= i <= bcol + 1) and arms[i] in ("┄", "┼", " "):
                        arms[i] = "═"

        # ── Altitude labels, one per mark, on the row the fins pass at that height ──
        labels = {
            int(round((CRASH_Y - km) * _ARM_ROW / CRASH_Y)): f"{km:>2}"
            for km in (15, 10, 6, 3)
        }
        lines = []
        for row in range(_CANVAS_H):
            label = labels.get(row, "  ") if row < GRID_H else "  "
            lines.append(label + "│" + "".join(canvas[row]))
        return "\n".join(lines)

    # ── EMBED ──────────────────────────────────────────────────────

    def make_embed(self, status: str = "") -> discord.Embed:
        fp = self.fuel_pct
        fblk = int(fp / 100 * 16)
        dot = "🟢" if fp > 60 else "🟡" if fp > 35 else "🟠" if fp > 15 else "🔴"
        fuel_bar = dot * fblk + "⚫" * (16 - fblk)

        ws = abs(self.wind_accel)
        if self._wind_suppress > 0:
            wind_str = f"🔇 Suppressed ({self._wind_suppress:.1f}s)"
        elif ws < WIND_BASE_ACCEL * 0.15:
            wind_str = "🟢 Calm"
        elif ws < WIND_BASE_ACCEL * 0.40:
            wind_str = f"🟡 {'←' if self.wind_accel < 0 else '→'} Light ({ws:.2f})"
        elif ws < WIND_BASE_ACCEL * 0.75:
            wind_str = f"🟠 {'⬅️' if self.wind_accel < 0 else '➡️'} Moderate ({ws:.2f})"
        else:
            wind_str = f"🔴 {'⬅️⬅️' if self.wind_accel < 0 else '➡️➡️'} STRONG ({ws:.2f})"

        if self.state == "catch_zone":
            phase_str = "🎯 **🚨 CATCH ZONE 🚨**"
        elif self.engine_on:
            phase_str = f"🔥 **FIRING** — {self.thrust_timer:.1f}s"
        else:
            phase_str = f"🛸 Descent — {self.altitude:.1f} km"

        eng_str = (f"🔥 Firing {self.thrust_timer:.1f}s" if self.engine_on else
                   "⛽ Depleted" if self.fuel_kg <= 0 else
                   f"⚫ Idle ({fp}%)")

        color = (0xFF0000 if self.state == "catch_zone" else
                 0x00FF00 if self.engine_on else
                 0xFF6B00 if self.pos_y > GRID_H * 0.6 else 0x0099FF)

        emb = discord.Embed(
            title="🚀 Catch Booster 16 — Mechzilla",
            description=f"```\n{self.make_field()}\n```",
            color=color,
        )
        emb.add_field(
            name="📊 Mission Control",
            value=(
                f"**Fuel:** {fuel_bar} {fp}%\n"
                f"**Wind:** {wind_str}\n"
                f"**Phase:** {phase_str}\n"
                f"**Engine:** {eng_str}"
            ),
            inline=True,
        )
        vy_ind = "↓↓" if self.vel_y > 2.5 else "↓" if self.vel_y > 0 else "↑"
        vx_ind = ("→" if self.vel_x > 0 else "←") if abs(self.vel_x) > 0.1 else "•"
        emb.add_field(
            name="📡 Telemetry",
            value=(
                f"**Alt:** {self.altitude:.2f} km\n"
                f"**V:** {self.vel_y:+.2f} wu/s {vy_ind}\n"
                f"**H:** {self.vel_x:+.2f} wu/s {vx_ind}\n"
                f"**Mass:** {self.mass:.1f} kg\n"
                f"**Arms:** col {int(self.arm_center)}"
            ),
            inline=True,
        )
        if self.timeline:
            emb.add_field(name="📺 Mission Log",
                          value="\n".join(self.timeline[-5:]), inline=False)
        if status:
            emb.add_field(name="🚨 STATUS", value=f"**{status}**", inline=False)

        tips = [
            "🔥 Each THRUST fires engine for 1.2 s — one well-timed burn beats three panicked ones",
            "💡 Arms span ±5 cols — position them under the booster's predicted path",
            "🎯 V-Speed at catch determines quality — aim for < 0.8 wu/s for perfect",
            "🌬️ Wind oscillates naturally — watch the H telemetry, not just the indicator",
            "📏 Altitude labels on the left show km remaining — plan burns at 10 km",
            "⚡ Burn penalty above 2 burns — precision > mashing",
            "🏓 Wall bounce reverses wind direction — use it to shed lateral drift",
        ]
        emb.set_footer(text=tips[self.anim_frame % len(tips)])
        return emb


# ══════════════════════════════════════════════════════════════════
#  COMMAND REGISTRATION + GAME LOOP
# ══════════════════════════════════════════════════════════════════

def _register_commands(bot: commands.Bot):
    # Helper function to handle sending responses across slash and prefix contexts
    async def _start_game(ctx: commands.Context):
        game = BoosterCatchGame(ctx.author.id, ctx.author.display_name)
        view = CatchGameView(game)

        # Initial embed
        embed = game.make_embed("🚀 **Booster 16 separation confirmed — Descent begun**")

        # Defer/Respond properly depending on trigger type (slash vs prefix)
        if ctx.interaction:
            await ctx.interaction.response.send_message(embed=embed, view=view)
            msg = await ctx.interaction.original_response()
        else:
            msg = await ctx.send(embed=embed, view=view)

        start_wall = time.monotonic()
        last_tick = time.monotonic()
        last_display = time.monotonic()

        while game.state != "over":
            now = time.monotonic()
            dt = now - last_tick
            last_tick = now

            game.update_physics(dt)

            if game.state == "catch_zone":
                status = "🚨 **CATCH WINDOW OPEN — EXECUTE NOW!** 🚨"
                disp = DISP_FAST
            elif game.engine_on:
                status = f"🔥 **ENGINE FIRING — {game.thrust_timer:.1f}s remaining**"
                disp = DISP_FAST
            elif game.altitude <= 3.0:
                status = "🔴 **FINAL APPROACH — Last chance!**"
                disp = DISP_FAST
            elif game.altitude <= 6.0:
                status = "⚠️ **Critical altitude — Slow down now!**"
                disp = DISP_FAST
            elif game.vel_y > 3.0:
                status = "⚡ **High descent rate — Consider a burn**"
                disp = DISP_SLOW
            else:
                status = "🚀 **Descent nominal — All systems active**"
                disp = DISP_SLOW

            if now - last_display >= disp:
                view.sync_buttons()
                try:
                    await msg.edit(embed=game.make_embed(status), view=view)
                    last_display = now
                except discord.errors.NotFound:
                    return
                except discord.errors.HTTPException:
                    await asyncio.sleep(0.4)

            await asyncio.sleep(PHYS_DT)

        for item in view.children:
            item.disabled = True

        elapsed = time.monotonic() - start_wall
        uid = ctx.author.id

        if game.success:
            base = game.score
            time_bonus = max(0, min(80, int(120 - elapsed * 0.8)))
            fuel_bonus = int((game.fuel_kg / FULL_FUEL_KG) * 60)
            vel_bonus = max(0, int(45 - abs(game._catch_vel_y) * 14))
            offset = abs(game.pos_x - game.arm_center)
            prec_bonus = max(0, int(40 - offset * 7))
            burn_penalty = max(0, (game.manual_burns - 2) * 8)
            total = base + time_bonus + fuel_bonus + vel_bonus + prec_bonus - burn_penalty

            if _add_score:
                try:
                    _add_score(uid, total)
                except Exception:
                    pass

            career = (_scores_ref.get(str(uid), 0) if isinstance(_scores_ref, dict) else 0)

            final = discord.Embed(
                title="🏆 MISSION SUCCESS — BOOSTER RECOVERED",
                description=(f"**{ctx.author.display_name}** caught Booster 16 with Mechzilla!\n"
                             f"```\n{game.make_field()}\n```"),
                color=0x00FF00,
            )
            final.add_field(
                name="📊 Score Breakdown",
                value=(
                    f"**Base ({game.catch_result}):** {base} pts\n"
                    f"**Time Bonus:** +{time_bonus} pts\n"
                    f"**Fuel Bonus:** +{fuel_bonus} pts\n"
                    f"**Velocity Bonus:** +{vel_bonus} pts  *(catch V: {abs(game._catch_vel_y):.2f} wu/s)*\n"
                    f"**Precision Bonus:** +{prec_bonus} pts  *(offset: {offset:.1f} col)*\n"
                    f"**Burn Penalty ({game.manual_burns} burns):** −{burn_penalty} pts\n"
                    f"━━━━━━━━━━━━━\n"
                    f"**TOTAL: {total} pts**"
                ),
                inline=True,
            )
            final.add_field(
                name="⏱️ Mission Stats",
                value=(
                    f"**Duration:** {elapsed:.1f} s\n"
                    f"**Fuel remaining:** {game.fuel_pct}%\n"
                    f"**Catch V-speed:** {abs(game._catch_vel_y):.2f} wu/s\n"
                    f"**Arm offset:** {offset:.1f} col"
                ),
                inline=True,
            )
            ach = []
            if game.catch_result == "perfect": ach.append("🌟 Perfect Landing Master")
            if game.manual_burns <= 1:         ach.append("🎮 One-Burn Ace")
            if game.fuel_pct >= 50:            ach.append("⛽ Fuel Miser")
            if time_bonus >= 65:               ach.append("⚡ Lightning Pilot")
            if prec_bonus >= 35:               ach.append("🎯 Precision Specialist")
            if vel_bonus >= 38:               ach.append("🪶 Feather Touch")
            if total >= 350:                   ach.append("👨‍🚀 Elite Space Pilot")
            if ach:
                final.add_field(name="🏅 Achievements", value="\n".join(ach), inline=False)
            final.add_field(name="🏆 Career",
                            value=f"**Total:** {career:,} pts", inline=False)
        else:
            consolation = 10
            if _add_score:
                try:
                    _add_score(uid, consolation)
                except Exception:
                    pass

            career = (_scores_ref.get(str(uid), 0) if isinstance(_scores_ref, dict) else 0)

            final = discord.Embed(
                title="💥 MISSION FAILED — BOOSTER LOST",
                description=f"Post-mission analysis:\n```\n{game.make_field()}\n```",
                color=0xFF0000,
            )
            final.add_field(
                name="📋 Failure Data",
                value=(
                    f"**Impact V-speed:** {game.vel_y:.2f} wu/s\n"
                    f"**Impact H-speed:** {abs(game.vel_x):.2f} wu/s\n"
                    f"**Final position:** col {game.pos_x:.1f}\n"
                    f"**Fuel remaining:** {game.fuel_pct}%\n"
                    f"**Duration:** {elapsed:.1f} s"
                ),
                inline=True,
            )
            recs = []
            if game.vel_y > 2.5:        recs.append("• Ignite engine earlier — descent speed too high")
            if game.fuel_pct > 40:      recs.append("• You had fuel to spare — use it")
            if game.manual_burns == 0:  recs.append("• You never fired the engine!")
            recs.append("• Wind now mean-reverts — trust it to change, don't panic-move arms")
            recs.append("• Watch altitude labels on the left — plan burns at 10 km")
            final.add_field(name="💡 Recommendations", value="\n".join(recs), inline=True)
            final.add_field(name="📺 Final Event",
                            value=game.timeline[-1] if game.timeline else "Telemetry lost",
                            inline=False)
            final.add_field(name="🎖️ Participation",
                            value=f"+{consolation} pts  |  **Career:** {career:,} pts",
                            inline=False)

        final.set_footer(text="!catchbooster to retry  •  !leaderboard for rankings  •  !catchhelp for tips")
        try:
            await msg.edit(embed=final, view=view)
        except Exception:
            await ctx.send(embed=final)

    # ── HYBRID COMMANDS ─────────────────────────────────────────────

    @bot.hybrid_command(
        name="catchbooster",
        aliases=["booster", "mechzilla", "catch16"],
        description="Play Mechzilla booster catch game"
    )
    async def cmd_catchbooster(ctx: commands.Context):
        await _start_game(ctx)

    @bot.hybrid_command(
        name="catchhelp",
        aliases=["boosterhelp"],
        description="Display guide and physics info for booster catch"
    )
    async def cmd_catchhelp(ctx: commands.Context):
        emb = discord.Embed(
            title="🚀 Booster Catch — Controls & Physics",
            description="Catch Booster 16 using Mechzilla chopstick arms. ~17 s cinematic descent.",
            color=0x0099FF,
        )
        emb.add_field(name="🎮 Controls", value=(
            "**← Arms / Arms →** — Move arms 4 cols per press\n"
            "**🔥 THRUST** — Fire engines for 1.2 s (burns real fuel)\n"
            "**🥢 CATCH!** — Grab booster when window opens"
        ), inline=False)
        emb.add_field(name="⚙️ Physics", value=(
            "• **Gravity** — constant downward pull\n"
            "• **Drag** — quadratic, limits terminal velocity\n"
            "• **Engine TWR** — thrust / current mass; lighter = more responsive\n"
            "• **Fuel mass** — booster gets lighter as fuel burns\n"
            "• **Wind** — Ornstein-Uhlenbeck process — oscillates, can't stay extreme\n"
            "• **Wall bounce** — elastic with wind reversal, can't get permanently stuck"
        ), inline=False)
        emb.add_field(name="🏆 Catch Ratings", value=(
            f"🌟 **Perfect** 250 pts — V < {PERFECT_VY} & H < {PERFECT_VX} wu/s\n"
            f"✅ **Good**    170 pts — V < {GOOD_VY} & H < {GOOD_VX} wu/s\n"
            f"✅ **Rough**    90 pts — V < {ROUGH_VY} wu/s\n"
            f"⚠️ **Buckle**  30 pts — in position but too fast\n"
            f"⚠️ **Near miss** 0 pts — try again (shows cols off)\n"
            f"❌ **Miss**      0 pts"
        ), inline=False)
        emb.add_field(name="💡 Tips", value=(
            "• Watch altitude labels on the left — fire engines at 10 km\n"
            "• Aim for V-speed < 1.5 wu/s before the catch zone\n"
            "• 1–2 precise burns > mashing (−8 pts per extra burn)\n"
            "• Wind now oscillates — wait it out instead of panic-moving arms\n"
            "• Near-miss tells you exactly how many cols to adjust"
        ), inline=False)
        emb.set_footer(text="!catchbooster to start")
        await ctx.send(embed=emb)

    # ── UTILITY ADMIN COMMAND FOR SLASH COMMAND SYNCING ────────────

    @bot.command(name="sync", hidden=True)
    @commands.is_owner()
    async def sync_tree(ctx: commands.Context, guild_id: Optional[int] = None):
        """
        Owner command to sync slash commands across Discord.
        Usage:
            !sync          -> Syncs globally (Takes up to 1 hr to propagate)
            !sync <guild>  -> Syncs immediately to a specific server ID
        """
        if guild_id:
            guild = discord.Object(id=guild_id)
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            await ctx.send(f"✅ Synced **{len(synced)}** commands directly to Guild ID `{guild_id}`!")
        else:
            synced = await bot.tree.sync()
            await ctx.send(
                f"🌐 Globally synced **{len(synced)}** slash commands! (May take up to 1 hr to show up globally)")
    @bot.command(name="clearguild", hidden=True)
    @commands.is_owner()
    async def clear_guild_commands(ctx):
        guild = discord.Object(id=ctx.guild.id)
        # Clear all commands attached to this specific guild
        bot.tree.clear_commands(guild=guild)
        await bot.tree.sync(guild=guild)
        await ctx.send("🧹 Cleared guild-specific commands! Duplicate commands should disappear in a few seconds.")
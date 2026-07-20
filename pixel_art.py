import discord
from discord.ext import commands
from PIL import Image, ImageEnhance, ImageFilter
import io


def setup_pixel_art(bot: commands.Bot):
    _register_commands(bot)
    print("[PIXEL ART] Interactive UI module loaded — !pixelart ready (Max 256px + Presets)")


# ─── PRESET RETRO PALETTES ───────────────────────────────────────────
PALETTES = {
    "gameboy": [
        (15, 56, 15), (48, 98, 48), (139, 172, 15), (155, 188, 15)
    ],
    "pico8": [
        (0, 0, 0), (29, 43, 83), (126, 37, 83), (0, 135, 81), (171, 82, 54), (95, 87, 79),
        (194, 195, 199), (255, 241, 232), (255, 0, 77), (255, 163, 0), (255, 236, 39),
        (0, 228, 54), (41, 173, 255), (131, 118, 156), (255, 119, 168), (255, 204, 170)
    ],
    "cyberpunk": [
        (13, 2, 33), (112, 0, 255), (255, 0, 128), (0, 240, 255), (255, 230, 0), (255, 255, 255)
    ],
    "nes": [
        (0, 0, 0), (255, 255, 255), (124, 124, 124), (252, 188, 176), (248, 56, 0),
        (228, 0, 88), (172, 0, 40), (104, 136, 0), (0, 168, 0), (0, 168, 68), (0, 136, 136),
        (0, 120, 248), (0, 0, 252), (184, 0, 248), (216, 0, 204)
    ]
}


def _apply_custom_palette(img: Image.Image, palette_colors: list) -> Image.Image:
    pal_img = Image.new("P", (1, 1))
    flat_palette = []
    for color in palette_colors:
        flat_palette.extend(color)
    flat_palette.extend([0] * (768 - len(flat_palette)))
    pal_img.putpalette(flat_palette)

    rgb_img = img.convert("RGB")
    quantized = rgb_img.quantize(palette=pal_img, dither=Image.Dither.NONE)
    return quantized.convert("RGBA")


def convert_to_pixel_art(
        image_bytes: bytes,
        resolution: int = 64,
        colors: int = 32,
        outline: bool = True,
        style: str = "default"
) -> io.BytesIO:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

    # Enhance contrast & vibrancy
    img = ImageEnhance.Contrast(img).enhance(1.25)
    img = ImageEnhance.Color(img).enhance(1.3)

    # Downscale dimensions
    w, h = img.size
    if w > h:
        new_w = resolution
        new_h = max(1, int(h * (resolution / w)))
    else:
        new_h = resolution
        new_w = max(1, int(w * (resolution / h)))

    small_img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # Edge Outline
    if outline:
        gray = small_img.convert("L")
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edges = edges.point(lambda p: 255 if p > 90 else 0)

        outline_layer = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))
        for y in range(new_h):
            for x in range(new_w):
                if edges.getpixel((x, y)) > 0:
                    outline_layer.putpixel((x, y), (20, 20, 20, 255))

        small_img = Image.alpha_composite(small_img, outline_layer)

    # Quantize palette
    alpha = small_img.getchannel("A")
    if style in PALETTES:
        pixelated = _apply_custom_palette(small_img, PALETTES[style])
    else:
        rgb_img = small_img.convert("RGB")
        quantized = rgb_img.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
        pixelated = quantized.convert("RGBA")

    alpha_mask = alpha.point(lambda p: 255 if p > 100 else 0)
    pixelated.putalpha(alpha_mask)

    # Crisp Upscaling
    target_width = max(512, new_w * 2)
    scale = max(1, target_width // new_w)
    out_w, out_h = new_w * scale, new_h * scale
    final_output = pixelated.resize((out_w, out_h), Image.Resampling.NEAREST)

    buf = io.BytesIO()
    final_output.save(buf, format="PNG")
    buf.seek(0)
    return buf


# ─── DISCORD MODAL (SETTINGS POP-UP) ──────────────────────────────────
class PixelSettingsModal(discord.ui.Modal, title="⚙️ Custom Pixel Settings"):
    res_input = discord.ui.TextInput(
        label="Grid Resolution (16 - 256)",
        placeholder="e.g. 128 or 256",
        default="64",
        min_length=2,
        max_length=3,
    )
    colors_input = discord.ui.TextInput(
        label="Color Count (4 - 64)",
        placeholder="e.g. 32",
        default="32",
        min_length=1,
        max_length=2,
    )

    def __init__(self, view: "PixelArtUI"):
        super().__init__()
        self.view = view
        self.res_input.default = str(view.resolution)
        self.colors_input.default = str(view.colors)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val_res = max(16, min(256, int(self.res_input.value)))
            val_col = max(4, min(64, int(self.colors_input.value)))
            self.view.resolution = val_res
            self.view.colors = val_col
            self.view.style = "default"
            await interaction.response.defer()
            await self.view.render_and_update(interaction)
        except ValueError:
            await interaction.response.send_message("❌ Invalid numbers entered.", ephemeral=True)


# ─── DISCORD INTERACTIVE VIEW ─────────────────────────────────────────
class PixelArtUI(discord.ui.View):
    STYLES = ["default", "gameboy", "pico8", "cyberpunk", "nes"]

    def __init__(self, bot: commands.Bot, author_id: int, image_bytes: bytes):
        super().__init__(timeout=300)
        self.bot = bot
        self.author_id = author_id
        self.image_bytes = image_bytes
        self.resolution = 64
        self.colors = 32
        self.outline = True
        self.style_idx = 0
        self.style = "default"
        self.message: discord.Message | None = None

    def _ok(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author_id

    async def render_and_update(self, interaction: discord.Interaction, remove_ui: bool = False):
        out_stream = await self.bot.loop.run_in_executor(
            None,
            convert_to_pixel_art,
            self.image_bytes,
            self.resolution,
            self.colors,
            self.outline,
            self.style
        )
        file = discord.File(fp=out_stream, filename="pixel_art.png")

        style_lbl = self.style.upper() if self.style != "default" else f"{self.colors} Colors"

        emb = discord.Embed(
            title="🎨 Pixel Art Result" if remove_ui else "🎨 Pixel Art Generator UI",
            description=(
                f"**Grid Size:** {self.resolution}px  •  "
                f"**Palette:** {style_lbl}  •  "
                f"**Outline:** {'On' if self.outline else 'Off'}"
            ),
            color=0x0099FF
        )
        emb.set_image(url="attachment://pixel_art.png")

        if remove_ui:
            emb.set_footer(text="Pixel art finalized.")
        else:
            emb.set_footer(text="Use preset buttons or controls below to tweak! Max Grid: 256px")

        if self.message:
            if remove_ui:
                await self.message.edit(embed=emb, attachments=[file], view=None)
                self.stop()
            else:
                await self.message.edit(embed=emb, attachments=[file], view=self)

    # ── ROW 0: QUICK PRESETS ─────────────────────────────────────────
    @discord.ui.button(label="32px", style=discord.ButtonStyle.secondary, row=0)
    async def btn_preset_32(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._ok(interaction): return await interaction.response.defer()
        self.resolution = 32
        await interaction.response.defer()
        await self.render_and_update(interaction)

    @discord.ui.button(label="64px", style=discord.ButtonStyle.secondary, row=0)
    async def btn_preset_64(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._ok(interaction): return await interaction.response.defer()
        self.resolution = 64
        await interaction.response.defer()
        await self.render_and_update(interaction)

    @discord.ui.button(label="128px", style=discord.ButtonStyle.secondary, row=0)
    async def btn_preset_128(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._ok(interaction): return await interaction.response.defer()
        self.resolution = 128
        await interaction.response.defer()
        await self.render_and_update(interaction)

    @discord.ui.button(label="256px", style=discord.ButtonStyle.secondary, row=0)
    async def btn_preset_256(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._ok(interaction): return await interaction.response.defer()
        self.resolution = 256
        await interaction.response.defer()
        await self.render_and_update(interaction)

    # ── ROW 1: FINE CONTROLS & PALETTES ────────────────────────────────
    @discord.ui.button(label="Grid −", style=discord.ButtonStyle.primary, row=1)
    async def btn_res_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._ok(interaction): return await interaction.response.defer()
        self.resolution = max(16, self.resolution - 16)
        await interaction.response.defer()
        await self.render_and_update(interaction)

    @discord.ui.button(label="Grid +", style=discord.ButtonStyle.primary, row=1)
    async def btn_res_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._ok(interaction): return await interaction.response.defer()
        self.resolution = min(256, self.resolution + 16)
        await interaction.response.defer()
        await self.render_and_update(interaction)

    @discord.ui.button(label="🎨 Palette Shift", style=discord.ButtonStyle.primary, row=1)
    async def btn_style(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._ok(interaction): return await interaction.response.defer()
        self.style_idx = (self.style_idx + 1) % len(self.STYLES)
        self.style = self.STYLES[self.style_idx]
        await interaction.response.defer()
        await self.render_and_update(interaction)

    @discord.ui.button(label="✏️ Outline", style=discord.ButtonStyle.primary, row=1)
    async def btn_outline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._ok(interaction): return await interaction.response.defer()
        self.outline = not self.outline
        await interaction.response.defer()
        await self.render_and_update(interaction)

    # ── ROW 2: ADVANCED & FINALIZATION ───────────────────────────────
    @discord.ui.button(label="⚙️ Settings", style=discord.ButtonStyle.success, row=2)
    async def btn_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._ok(interaction): return await interaction.response.defer()
        modal = PixelSettingsModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="📌 Lock Image", style=discord.ButtonStyle.danger, row=2)
    async def btn_lock(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._ok(interaction): return await interaction.response.defer()
        await interaction.response.defer()
        await self.render_and_update(interaction, remove_ui=True)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


# ─── COMMAND REGISTRATION ────────────────────────────────────────────
def _register_commands(bot: commands.Bot):
    @bot.command(name="pixelart", aliases=["pixel", "pixelfy", "retroart"])
    async def cmd_pixelart(ctx, *, args: str = ""):
        """
        Generates pixel art with an interactive UI (16 - 256px resolution).
        Upload an image, reply to an image, or pass an image URL!
        """
        attachment = None

        if ctx.message.attachments:
            attachment = ctx.message.attachments[0]
        elif ctx.message.reference and ctx.message.reference.message_id:
            referenced_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            if referenced_msg.attachments:
                attachment = referenced_msg.attachments[0]

        if not attachment or not attachment.content_type.startswith("image/"):
            emb = discord.Embed(
                title="🖼️ Missing Image",
                description=(
                    "Please **attach an image**, reply to an image message, "
                    "or type `!pixelart` with an upload!"
                ),
                color=0xFFCC00
            )
            return await ctx.send(embed=emb)

        status_msg = await ctx.send("🎨 **Processing image & launching UI...**")

        try:
            img_bytes = await attachment.read()
            view = PixelArtUI(bot, ctx.author.id, img_bytes)

            out_stream = await bot.loop.run_in_executor(
                None, convert_to_pixel_art, img_bytes, view.resolution, view.colors, view.outline, view.style
            )
            file = discord.File(fp=out_stream, filename="pixel_art.png")

            emb = discord.Embed(
                title="🎨 Pixel Art Generator UI",
                description=f"**Grid Size:** {view.resolution}px  •  **Palette:** {view.colors} Colors  •  **Outline:** On",
                color=0x0099FF
            )
            emb.set_image(url="attachment://pixel_art.png")
            emb.set_footer(text=f"Requested by {ctx.author.display_name} • Click buttons to adjust UI")

            await status_msg.delete()
            sent_msg = await ctx.send(file=file, embed=emb, view=view)
            view.message = sent_msg

        except Exception as e:
            await status_msg.delete()
            err_emb = discord.Embed(
                title="❌ Conversion Failed",
                description=f"An error occurred: `{str(e)}`",
                color=0xFF0000
            )
            await ctx.send(embed=err_emb)
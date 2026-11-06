"""Shared base class for the minigame views.

Every interactive game in main.py reimplemented (or forgot) the same two
behaviours:

- **An author lock.** Without `interaction_check`, anyone in the channel can
  click someone else's game. For the trivia views that meant a bystander could
  answer another player's question and take the points.
- **Timeout cleanup.** Without `on_timeout`, an abandoned game leaves buttons
  that still look live; clicking one gives the user Discord's unhelpful "This
  interaction failed". Only two of the twelve views handled this.

`GameView` provides both, plus a short helper for sending a message and
remembering it so the timeout handler can edit it.
"""

from typing import Optional

import discord


class GameView(discord.ui.View):
    """A view locked to one player that tidies up after itself.

    Pass `author_id=None` to make the view public (anyone may interact).
    """

    #: Shown when someone else tries to use the view.
    not_yours_message = "⚠️ This game isn't yours — start your own!"

    #: Appended to the embed footer once the view expires.
    timeout_notice = "⏱️ This game has expired."

    def __init__(self, *, author_id: Optional[int] = None,
                 timeout: Optional[float] = 60.0):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        # Set by send() or assigned by the caller, so on_timeout can edit it.
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Allow only the player who started the game, if one was recorded."""
        if self.author_id is None or interaction.user.id == self.author_id:
            return True
        await interaction.response.send_message(
            self.not_yours_message, ephemeral=True
        )
        return False

    def disable_all(self) -> None:
        """Grey out every component."""
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True

    async def send(self, ctx, **kwargs) -> discord.Message:
        """Send this view and remember the message for later edits."""
        self.message = await ctx.send(view=self, **kwargs)
        return self.message

    async def on_timeout(self) -> None:
        """Disable the controls and mark the message as expired."""
        self.disable_all()
        if self.message is None:
            return

        try:
            embed = None
            if self.message.embeds:
                embed = self.message.embeds[0]
                existing = embed.footer.text or ""
                if self.timeout_notice not in existing:
                    embed.set_footer(
                        text=(f"{existing} • {self.timeout_notice}".strip(" •")
                              if existing else self.timeout_notice)
                    )
            await self.message.edit(embed=embed, view=self)
        except discord.HTTPException:
            # Message deleted, or we lost permission to edit it.
            pass


def streak_bonus(streak: int, per_step: int = 1, cap: int = 5) -> int:
    """Bonus points for a run of consecutive wins.

    The first win in a run earns nothing extra; each subsequent win adds
    `per_step`, up to `cap`.
    """
    return min(max(0, streak - 1) * per_step, cap)

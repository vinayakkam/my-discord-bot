"""The bot's one and only on_command_error handler."""
import traceback

from discord.ext import commands


def setup(bot: commands.Bot) -> None:
    """Register the single command error handler on `bot`."""

    @bot.event
    async def on_command_error(ctx, error):
        """The bot's single command error handler.

        There must be exactly one @bot.event for a given event name: a second
        definition silently replaces the first rather than chaining. main.py used to
        define this twice, so the earlier handler's ChannelNotFound branch never
        ran.
        """
        if isinstance(error, commands.CommandNotFound):
            # Unknown "!word" may be a custom dashboard command, already handled in
            # on_message. Staying quiet avoids yelling at ordinary chatter.
            return

        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command!")
        elif isinstance(error, commands.BotMissingPermissions):
            missing = ", ".join(error.missing_permissions)
            await ctx.send(f"❌ I'm missing the required permissions: {missing}")
        elif isinstance(error, commands.ChannelNotFound):
            await ctx.send("❌ Channel not found! Please mention a valid channel.")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ I couldn't find that member in this server.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                f"❌ Missing argument `{error.param.name}`.\n"
                f"Usage: `{ctx.prefix}{ctx.command.qualified_name} "
                f"{ctx.command.signature}`"
            )
        elif isinstance(error, commands.BadArgument):
            await ctx.send(
                f"❌ Bad argument: {error}\n"
                f"Usage: `{ctx.prefix}{ctx.command.qualified_name} "
                f"{ctx.command.signature}`"
            )
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"⏳ That command is on cooldown. Try again in "
                f"{error.retry_after:.1f}s."
            )
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.send("❌ That command only works inside a server.")
        else:
            # Unexpected: log the full traceback for debugging rather than only the
            # message, but keep the user-facing text short.
            print(f"[COMMAND ERROR] {ctx.command} raised {type(error).__name__}: {error}")
            traceback.print_exception(type(error), error, error.__traceback__)
            await ctx.send("❌ Something went wrong running that command.")

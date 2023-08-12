"""Model for error handling."""
import discord
from discord.ext import commands
from loguru import logger

from valentina.utils import errors
from valentina.views.embeds import user_error_embed


class ErrorReporter:
    """Error handler reports errors to channels and logs."""

    def __init__(self) -> None:
        """Initialize the error reporter."""
        self.bot: commands.Bot = None
        self.channel: discord.TextChannel = None

    def _handle_known_exceptions(
        self, ctx: discord.ApplicationContext, error: Exception
    ) -> tuple[str | None, str | None, bool]:
        """Handle known exceptions and return user message, log message, and traceback flag."""
        user_msg = None
        log_msg = None
        show_traceback = False

        if isinstance(
            error,
            commands.errors.MissingAnyRole
            | commands.errors.MissingRole
            | commands.MissingPermissions
            | commands.NotOwner,
        ):
            user_msg = "Sorry, you don't have permission to run this command!"
            log_msg = f"COMMAND: `{ctx.user.display_name}` tried to run `/{ctx.command}` without the correct permissions"

        if isinstance(
            error,
            errors.CharacterClaimedError
            | errors.CharacterNotFoundError
            | errors.DuplicateRollResultThumbError
            | errors.MacroNotFoundError
            | errors.NoActiveChronicleError
            | errors.NoClaimError
            | errors.SectionExistsError
            | errors.SectionNotFoundError
            | errors.TraitNotFoundError,
        ):
            user_msg = str(error)

        if isinstance(error, errors.MessageTooLongError):
            user_msg = "Message too long to send. This is a bug has been reported."
            log_msg = "ERROR: Message too long to send. Check the logs for the message."
            show_traceback = True

        if isinstance(error, errors.BotMissingPermissionsError):
            user_msg = "Sorry, I don't have permission to run this command!"
            log_msg = f"ERROR: Bot tried to run `/{ctx.command}` without the correct permissions"
            show_traceback = True

        if isinstance(error, commands.BadArgument):
            user_msg = "Invalid argument provided"

        if isinstance(error, commands.NoPrivateMessage):
            user_msg = "Sorry, this command can only be run in a server!"

        if isinstance(error, discord.errors.DiscordServerError | ValueError):
            # There's nothing we can do about these
            user_msg = "Discord server error detected"
            log_msg = "SERVER: Discord server error detected"
            show_traceback = True

        return user_msg, log_msg, show_traceback

    async def report_error(self, ctx: discord.ApplicationContext, error: Exception) -> None:
        """Report an error to the error log channel and application log.

        Args:
            ctx (Union[discord.ApplicationContext, discord.Interaction]): The context of the command.
            error (Exception): The exception to be reported.

        Returns:
            None
        """
        user_msg = None
        log_msg = None
        show_traceback = False

        error = getattr(error, "original", error)
        respond = (
            ctx.respond
            if isinstance(ctx, discord.ApplicationContext)
            else (ctx.followup.send if ctx.response.is_done() else ctx.response.send_message)
        )

        user_msg, log_msg, show_traceback = self._handle_known_exceptions(ctx, error)

        # Handle unknown exceptions
        if not user_msg and not log_msg and not show_traceback:
            user_msg = "An error has occurred. This is a bug and has been reported."
            log_msg = f"A `{error.__class__.__name__}` error has occurred. Check the logs for more information."
            show_traceback = True

        # Send the messages
        if user_msg:
            embed_message = user_error_embed(ctx, user_msg, str(error))
            try:
                await respond(embed=embed_message, ephemeral=True, delete_after=15)
            except discord.HTTPException:
                await respond(
                    embed=user_error_embed(
                        ctx, "Message too long to send", "This is a bug has been reported"
                    ),
                    ephemeral=True,
                    delete_after=15,
                )
                log_msg = f"NEW ERROR: Message too long to send. Check the logs for the message.\n\nOriginal error: {error.__class__.__name__}"
                show_traceback = True

        if log_msg:
            log_method = logger.opt(exception=error).error if show_traceback else logger.warning
            log_method(log_msg)
            await ctx.bot.guild_svc.send_to_error_log(ctx, log_msg, error)  # type: ignore [attr-defined] # It exists, really

        if show_traceback:
            logger.opt(exception=error).error(f"ERROR: {error}")


reporter = ErrorReporter()

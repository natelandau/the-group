"""Prebuilt embeds for Valentina."""

import traceback
from datetime import datetime
from typing import Any

import discord

from valentina.constants import EmbedColor
from valentina.models.bot import ValentinaContext


async def error_log_embed(
    ctx: ValentinaContext | discord.Interaction, msg: str, error: Exception
) -> discord.Embed:
    """Create an embed for logging errors.

    Args:
        ctx: The context object for the command invocation or interaction.
        msg: A message to include in the error log.
        error: The exception that was raised.

    Returns:
        A discord.Embed object representing the error log.
    """
    description = f"{msg}\n"
    description += "\n".join(traceback.format_exception(error))

    # If we can, we use the command name to try to pinpoint where the error
    # took place. The stack trace usually makes this clear, but not always!
    if isinstance(ctx, ValentinaContext):
        command_name = ctx.command.qualified_name.upper()
    else:
        command_name = "INTERACTION"

    error_name = type(error).__name__

    embed = discord.Embed(
        title=f"{command_name}: {error_name}",
        description=description,
        color=EmbedColor.INFO.value,
        timestamp=datetime.now(),
    )

    if ctx.guild is not None:
        guild_name = ctx.guild.name
        guild_icon = ctx.guild.icon or ""
    else:
        guild_name = "DM"
        guild_icon = ""

    embed.set_author(name=f"{ctx.user.name} on {guild_name}", icon_url=guild_icon)

    return embed


def user_error_embed(ctx: ValentinaContext, msg: str, error: str) -> discord.Embed:
    """Create an embed for user errors.

    Args:
        ctx (ValentinaContext): The context of the command.
        msg (str): The message to display in the embed.
        error (str): The error to display in the embed.

    Returns:
        discord.Embed: The embed to send.
    """
    description = "" if error == msg else error

    embed = discord.Embed(title=msg, description=description, color=EmbedColor.ERROR.value)
    embed.timestamp = datetime.now()

    if hasattr(ctx, "command"):
        embed.set_footer(text=f"Command: /{ctx.command}")

    return embed


async def present_embed(
    ctx: ValentinaContext,
    title: str = "",
    description: str = "",
    footer: str | None = None,
    level: str = "INFO",
    ephemeral: bool = False,
    fields: list[tuple[str, str]] = [],
    image: str | None = None,
    inline_fields: bool = False,
    thumbnail: str | None = None,
    author: str | None = None,
    author_avatar: str | None = None,
    show_author: bool = False,
    timestamp: bool = False,
    view: Any = None,
    delete_after: float = 120.0,  # 2 minutes by default
) -> discord.Interaction:
    """Display a nice embed.

    Args:
        ctx: The Discord context for sending the response.
        title: The title of the embed.
        description: The description of the embed.
        ephemeral: Whether the embed should be ephemeral.
        level: The level of the embed. Effects the color.(INFO, ERROR, WARNING, SUCCESS)
        fields: list(tuple(str,  str)): Fields to add to the embed. (fields.0 is name; fields.1 is value)
        delete_after (optional, float): Number of seconds to wait before deleting the message.
        footer (str): Footer text to display.
        image (str): URL of the image to display.
        inline_fields (bool): Whether the fields should be inline (Default: False).
        thumbnail (str): URL of the thumbnail to display.
        show_author (bool): Whether to show the author of the embed.
        author (str): Name of the author to display.
        author_avatar (str): URL of the author's avatar to display.
        timestamp (bool): Whether to show the timestamp.
        view (discord.ui.View): The view to add to the embed.
    """
    color = EmbedColor[level.upper()].value

    embed = discord.Embed(title=title, colour=color)
    if show_author:
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)

    embed.description = description

    if author and author_avatar:
        embed.set_author(name=author, icon_url=author_avatar)
    elif author:
        embed.set_author(name=author)

    if thumbnail:
        embed.set_thumbnail(url=thumbnail)

    for name, value in fields:
        embed.add_field(name=name, value=value, inline=inline_fields)

    if image:
        embed.set_image(url=image)

    if footer:
        embed.set_footer(text=footer)

    if timestamp:
        embed.timestamp = datetime.now()

    respond_kwargs = {
        "embed": embed,
        "ephemeral": ephemeral,
        "delete_after": delete_after,
    }
    if view:
        respond_kwargs["view"] = view
    return await ctx.respond(**respond_kwargs)  # type: ignore [return-value]

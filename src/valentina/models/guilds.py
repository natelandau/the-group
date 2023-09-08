"""Guild models.

Note, due to ForeignKey constraints, the Guild database model is defined in database.py.
"""
from datetime import datetime

import discord
from loguru import logger

from valentina.constants import GUILD_DEFAULTS, ChannelPermission, EmbedColor
from valentina.utils import errors
from valentina.utils.helpers import set_channel_perms, time_now

from .db_tables import Guild, RollThumbnail


class GuildService:
    """Manage guilds in the database. Guilds are created on bot connect."""

    def __init__(self) -> None:
        self.settings_cache: dict[int, dict[str, str | int | bool]] = {}
        self.roll_result_thumbs: dict[int, dict[str, list[str]]] = {}

    def fetch_guild_settings(self, ctx: discord.ApplicationContext) -> dict[str, str | int | bool]:
        """Fetch all guild settings.

        This method fetches the settings for a guild, either from a cache or from the database.
        It stores the settings in a cache to improve performance on subsequent requests.

        Args:
            ctx (ApplicationContext): The application context.

        Returns:
            dict[str, str | int | bool]: A dictionary of guild settings.

        Raises:
            peewee.DoesNotExist: If the guild does not exist in the database.
        """
        if ctx.guild.id not in self.settings_cache:
            guild = Guild.get_by_id(ctx.guild.id).set_default_data_values()

            # Store all guild settings in the cache
            self.settings_cache[ctx.guild.id] = guild.data

            logger.debug(f"DATABASE: Fetch guild settings for '{ctx.guild.name}'")
        else:
            logger.debug(f"CACHE: Fetch guild settings for '{ctx.guild.name}'")

        return self.settings_cache[ctx.guild.id]

    def add_roll_result_thumb(
        self, ctx: discord.ApplicationContext, roll_type: str, url: str
    ) -> None:
        """Add a roll result thumbnail to the database."""
        ctx.bot.user_svc.fetch_user(ctx)  # type: ignore [attr-defined] # it really is defined

        self.roll_result_thumbs.pop(ctx.guild.id, None)

        already_exists = RollThumbnail.get_or_none(guild=ctx.guild.id, url=url)
        if already_exists:
            raise errors.ValidationError("That thumbnail already exists")

        RollThumbnail.create(guild=ctx.guild.id, user=ctx.author.id, url=url, roll_type=roll_type)
        logger.info(f"DATABASE: Add roll result thumbnail for '{ctx.author.display_name}'")

    async def channel_update_or_add(
        self,
        ctx: discord.ApplicationContext,
        channel: str | discord.TextChannel,
        topic: str,
        permissions: tuple[ChannelPermission, ChannelPermission, ChannelPermission],
    ) -> discord.TextChannel:  # pragma: no cover
        """Create or update a channel in the guild.

        Either create a new text channel in the guild or update an existing one
        based on the name. Set permissions for default role, player role,
        and storyteller role. If a member is a bot, set permissions to manage.

        Args:
            ctx (discord.ApplicationContext): Application context.
            channel (str|discord.TextChannel): Channel name or object.
            topic (str): Channel topic.
            permissions (tuple[ChannelPermission, ChannelPermission, ChannelPermission]): Tuple containing channel permissions for default_role, player_role, storyteller_role.

        Returns:
            discord.TextChannel: The created or updated text channel.

        """
        # Fetch roles
        player_role = discord.utils.get(ctx.guild.roles, name="Player")
        storyteller_role = discord.utils.get(ctx.guild.roles, name="Storyteller")

        # Initialize permission overwrites
        overwrites = {
            ctx.guild.default_role: set_channel_perms(permissions[0]),
            player_role: set_channel_perms(permissions[1]),
            storyteller_role: set_channel_perms(permissions[2]),
            **{
                user: set_channel_perms(ChannelPermission.MANAGE)
                for user in ctx.guild.members
                if user.bot
            },
        }

        # Determine channel object and name
        if isinstance(channel, discord.TextChannel):
            channel_object = channel
        elif isinstance(channel, str):
            channel_name = channel.lower().strip()
            channel_object = discord.utils.get(ctx.guild.text_channels, name=channel_name)

            # Create the channel if it doesn't exist
            if not channel_object:
                logger.debug(f"GUILD: Create channel '{channel_object.name}' on '{ctx.guild.name}'")
                return await ctx.guild.create_text_channel(
                    channel_name,
                    overwrites=overwrites,
                    topic=topic,
                )

        # Update existing channel
        logger.debug(f"GUILD: Update channel '{channel_object.name}' on '{ctx.guild.name}'")
        await channel_object.edit(overwrites=overwrites, topic=topic)

        return channel_object

    def fetch_roll_result_thumbs(self, ctx: discord.ApplicationContext) -> dict[str, list[str]]:
        """Get all roll result thumbnails for a guild."""
        # Fetch from cache if it exists
        if ctx.guild.id in self.roll_result_thumbs:
            logger.debug(f"CACHE: Fetch roll result thumbnails for '{ctx.guild.name}'")
            return self.roll_result_thumbs[ctx.guild.id]

        # Fetch from database
        logger.debug(f"DATABASE: Fetch roll result thumbnails for '{ctx.guild.name}'")
        self.roll_result_thumbs[ctx.guild.id] = {}

        for thumb in RollThumbnail.select().where(RollThumbnail.guild == ctx.guild.id):
            if thumb.roll_type not in self.roll_result_thumbs[ctx.guild.id]:
                self.roll_result_thumbs[ctx.guild.id][thumb.roll_type] = [thumb.url]
            else:
                self.roll_result_thumbs[ctx.guild.id][thumb.roll_type].append(thumb.url)

        return self.roll_result_thumbs[ctx.guild.id]

    def purge_cache(
        self,
        ctx: discord.ApplicationContext | discord.AutocompleteContext | None = None,
        guild: discord.Guild | None = None,
    ) -> None:
        """Purge the cache for a guild or all guilds.

        Args:
            ctx (optional, ApplicationContext | AutocompleteContext): The application context.
            guild (optional, discord.Guild): The guild to purge the cache for.
        """
        if ctx and not guild:
            guild = (
                ctx.guild if isinstance(ctx, discord.ApplicationContext) else ctx.interaction.guild
            )

        if ctx or guild:
            self.settings_cache.pop(guild.id, None)
            self.roll_result_thumbs.pop(guild.id, None)
            logger.debug(f"CACHE: Purge guild cache for '{guild.name}'")
        else:
            self.settings_cache = {}
            self.roll_result_thumbs = {}
            logger.debug("CACHE: Purge all guild caches")

    async def send_to_audit_log(
        self, ctx: discord.ApplicationContext, message: str | discord.Embed
    ) -> None:  # pragma: no cover
        """Send a message to the audit log channel for a guild.

        If a string is passed in, an embed will be created from it. If an embed is passed in, it will be sent as is.

        Args:
            ctx (discord.ApplicationContext): The context in which the command was invoked.
            message (str|discord.Embed): The message to be sent to the log channel.

        Raises:
            discord.DiscordException: If the message could not be sent.
        """
        settings = self.fetch_guild_settings(ctx)
        audit_log_channel = (
            discord.utils.get(ctx.guild.text_channels, id=settings["log_channel_id"])
            if settings["log_channel_id"]
            else None
        )

        if settings["use_audit_log"] and audit_log_channel:
            audit_log_channel = (
                discord.utils.get(ctx.guild.text_channels, id=settings["log_channel_id"])
                if settings["log_channel_id"]
                else None
            )
            embed = self._message_to_embed(message, ctx) if isinstance(message, str) else message

            try:
                await audit_log_channel.send(embed=embed)
            except discord.HTTPException as e:
                raise errors.MessageTooLongError from e

    async def send_to_error_log(
        self, ctx: discord.ApplicationContext, message: str | discord.Embed, error: Exception
    ) -> None:  # pragma: no cover
        """Send a message to the error log channel for a guild.

        If a string is passed in, an embed will be created from it. If an embed is passed in, it will be sent as is.

        Args:
            ctx (discord.ApplicationContext): The context in which the command was invoked.
            error (Exception): The exception that was raised.
            message (str|discord.Embed): The message to be sent to the error log channel.

        Raises:
            discord.DiscordException: If the message could not be sent.
        """
        settings = self.fetch_guild_settings(ctx)
        error_log_channel = (
            discord.utils.get(ctx.guild.text_channels, id=settings["error_log_channel_id"])
            if settings["error_log_channel_id"]
            else None
        )

        if settings["use_error_log_channel"] and error_log_channel:
            embed = self._message_to_embed(message, ctx) if isinstance(message, str) else message
            try:
                await error_log_channel.send(embed=embed)
            except discord.HTTPException:
                embed = discord.Embed(
                    title=f"A {error.__class__.__name__} exception was raised",
                    description="The error was too long to fit! Check the logs for full traceback",
                    color=EmbedColor.ERROR.value,
                    timestamp=discord.utils.utcnow(),
                )
                await error_log_channel.send(embed=embed)

    def _message_to_embed(
        self, message: str, ctx: discord.ApplicationContext
    ) -> discord.Embed:  # pragma: no cover
        """Convert a string message to a discord embed.

        Args:
            message (str): The message to be converted.
            ctx (discord.ApplicationContext): The context in which the command was invoked.

        Returns:
            discord.Embed: The created embed.
        """
        # Set color based on command
        if hasattr(ctx, "command") and (
            ctx.command.qualified_name.startswith("admin")
            or ctx.command.qualified_name.startswith("owner")
            or ctx.command.qualified_name.startswith("developer")
        ):
            color = EmbedColor.WARNING.value
        elif hasattr(ctx, "command") and ctx.command.qualified_name.startswith("storyteller"):
            color = EmbedColor.SUCCESS.value
        elif hasattr(ctx, "command") and ctx.command.qualified_name.startswith("gameplay"):
            color = EmbedColor.GRAY.value
        elif hasattr(ctx, "command") and ctx.command.qualified_name.startswith("campaign"):
            color = EmbedColor.DEFAULT.value
        else:
            color = EmbedColor.INFO.value

        embed = discord.Embed(title=message, color=color)
        embed.timestamp = datetime.now()

        footer = ""
        if hasattr(ctx, "command"):
            footer += f"Command: /{ctx.command.qualified_name}"
        else:
            footer += "Command: Unknown"

        if hasattr(ctx, "author"):
            footer += f" | User: @{ctx.author.display_name}"
        if hasattr(ctx, "channel"):
            footer += f" | Channel: #{ctx.channel.name}"

        embed.set_footer(text=footer)

        return embed

    def update_or_add(
        self,
        guild: discord.Guild | None = None,
        ctx: discord.ApplicationContext | None = None,
        updates: dict[str, str | int | bool] | None = None,
    ) -> Guild:
        """Add a guild to the database or update it if it already exists."""
        if (ctx and guild) or (not ctx and not guild):
            raise ValueError("Need to pass either a guild or a context")

        # Purge the guild from the cache
        if ctx:
            self.purge_cache(ctx)
            guild = ctx.guild
        elif guild:
            self.purge_cache(guild=guild)

        # Create initialization data
        initial_data = GUILD_DEFAULTS.copy() | {"modified": str(time_now())} | (updates or {})

        db_guild, is_created = Guild.get_or_create(
            id=guild.id,
            defaults={
                "name": guild.name,
                "created": time_now(),
                "data": initial_data,
            },
        )

        if is_created:
            logger.info(f"DATABASE: Created guild {db_guild.name}")
        elif updates:
            logger.debug(f"DATABASE: Updated guild '{db_guild.name}'")
            updates["modified"] = str(time_now())

            for key, value in updates.items():
                logger.debug(f"DATABASE: Update guild {db_guild.name}: {key} to {value}")

            # Make requested updates to the guild
            Guild.update(data=Guild.data.update(updates)).where(Guild.id == guild.id).execute()

            # Ensure default data values are set
            Guild.get_by_id(guild.id).set_default_data_values()

        return Guild.get_by_id(guild.id)

"""Guild models.

Note, due to ForeignKey constraints, the Guild database model is defined in database.py.
"""
from datetime import datetime

import discord
from discord import ApplicationContext
from loguru import logger

from valentina.models.constants import (
    ChannelPermission,
    EmbedColor,
    TraitPermissions,
    XPPermissions,
)
from valentina.utils import errors
from valentina.utils.helpers import set_channel_perms, time_now

from .db_tables import Guild, RollThumbnail


class GuildService:
    """Manage guilds in the database. Guilds are created on bot connect."""

    def __init__(self) -> None:
        self.settings_cache: dict[int, dict[str, str | int | bool]] = {}
        self.roll_result_thumbs: dict[int, dict[str, list[str]]] = {}

    async def get_setting_review_embed(self, ctx: ApplicationContext) -> discord.Embed:
        """Get an embed of all guild settings."""
        # Confirm channels exist in discord
        current_settings = self.fetch_guild_settings(ctx)

        audit_log_channel = (
            discord.utils.get(ctx.guild.text_channels, id=current_settings["log_channel_id"])
            if current_settings["log_channel_id"]
            else None
        )
        storyteller_channel = (
            discord.utils.get(
                ctx.guild.text_channels, id=current_settings["storyteller_channel_id"]
            )
            if current_settings["storyteller_channel_id"]
            else None
        )
        error_log_channel = (
            discord.utils.get(ctx.guild.text_channels, id=current_settings["error_log_channel_id"])
            if current_settings["error_log_channel_id"]
            else None
        )

        # Build the embed
        embed = discord.Embed(
            title=f"Settings for {ctx.guild.name}",
            color=EmbedColor.INFO.value,
        )

        embed.add_field(name="\u200b", value="**CHARACTER  PERMISSIONS**", inline=False)
        embed.add_field(
            name="Editing XP",
            value=XPPermissions(current_settings["xp_permissions"]).name.title(),
            inline=True,
        )
        embed.add_field(
            name="Editing Traits",
            value=TraitPermissions(current_settings["trait_permissions"]).name.title(),
            inline=True,
        )

        embed.add_field(name="\u200b", value="**LOGGING**", inline=False)

        desc = "Status: "
        desc += "`Enabled`" if current_settings["use_audit_log"] else "`Disabled`"
        desc += "\nChannel: "
        desc += audit_log_channel.mention if audit_log_channel else "Not set"
        embed.add_field(name="Audit Log", value=desc, inline=True)

        desc = "Status: "
        desc += "`Enabled`" if current_settings["use_error_log_channel"] else "`Disabled`"
        desc += "\nChannel: "
        desc += error_log_channel.mention if error_log_channel else "Not set"
        embed.add_field(name="Error Log", value=desc, inline=True)

        embed.add_field(name="\u200b", value="**STORYTELLER**", inline=False)
        desc = "Status: "
        desc += "`Enabled`" if current_settings["use_storyteller_channel"] else "`Disabled`"
        desc += "\nChannel: "
        desc += storyteller_channel.mention if storyteller_channel else "Not set"
        embed.add_field(name="Private Storyteller Channel", value=desc, inline=True)

        return embed

    def fetch_guild_settings(self, ctx: ApplicationContext) -> dict[str, str | int | bool]:
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
            guild = Guild.get_by_id(ctx.guild.id)

            # Store all guild settings in the cache
            self.settings_cache[ctx.guild.id] = guild.data

            logger.debug(f"DATABASE: Fetch guild settings for '{ctx.guild.name}'")
        else:
            logger.debug(f"CACHE: Fetch guild settings for '{ctx.guild.name}'")

        return self.settings_cache[ctx.guild.id]

    def add_roll_result_thumb(self, ctx: ApplicationContext, roll_type: str, url: str) -> None:
        """Add a roll result thumbnail to the database."""
        # TODO: Move this to Dicerolls
        ctx.bot.user_svc.fetch_user(ctx)  # type: ignore [attr-defined] # it really is defined

        self.roll_result_thumbs.pop(ctx.guild.id, None)

        already_exists = RollThumbnail.get_or_none(guild=ctx.guild.id, url=url)
        if already_exists:
            raise errors.ValidationError("That thumbnail already exists")

        RollThumbnail.create(guild=ctx.guild.id, user=ctx.author.id, url=url, roll_type=roll_type)
        logger.info(f"DATABASE: Add roll result thumbnail for '{ctx.author.display_name}'")

    async def create_channel(
        self,
        ctx: ApplicationContext,
        channel_name: str,
        topic: str,
        position: int,
        database_key: str,
        default_role: ChannelPermission,
        player: ChannelPermission,
        storyteller: ChannelPermission,
    ) -> discord.TextChannel:  # pragma: no cover
        """Create or update a channel in the guild.

        This method creates a new text channel in the guild or updates an existing channel
        if one with the same name already exists. It sets the permissions for the default role,
        player role, and storyteller role. If the member is a bot, it sets the permissions to manage.

        Args:
            ctx (ApplicationContext): The application context.
            channel_name (str): The name of the channel.
            topic (str): The topic of the channel.
            position (int): The position of the channel in the channel list.
            database_key (str): The key for the channel (value) in the database.
            default_role (ChannelPermission): The permissions for the default role.
            player (ChannelPermission): The permissions for the player role.
            storyteller (ChannelPermission): The permissions for the storyteller role.

        Returns:
            discord.TextChannel: The created or updated discord text channel.

        Raises:
            peewee.DoesNotExist: If the guild does not exist in the database.
        """
        self.settings_cache.pop(ctx.guild.id, None)
        guild_object = Guild.get(id=ctx.guild.id)

        player_role = discord.utils.get(ctx.guild.roles, name="Player")
        storyteller_role = discord.utils.get(ctx.guild.roles, name="Storyteller")

        overwrites = {
            ctx.guild.default_role: set_channel_perms(default_role),
            player_role: set_channel_perms(player),
            storyteller_role: set_channel_perms(storyteller),
            **{
                user: set_channel_perms(ChannelPermission.MANAGE)
                for user in ctx.guild.members
                if user.bot
            },
        }

        channel = discord.utils.get(ctx.guild.text_channels, name=channel_name.lower().strip())

        if channel:
            await channel.edit(overwrites=overwrites, topic=topic, position=position)
            setattr(guild_object, database_key, channel.id)
            guild_object.save()
        else:
            channel = await ctx.guild.create_text_channel(
                channel_name,
                overwrites=overwrites,
                topic=topic,
                position=position,
            )
            setattr(guild_object, database_key, channel.id)
            guild_object.save()

        logger.debug(f"GUILD: Created or updated channel '{channel_name}' for '{ctx.guild.name}'")
        return channel

    def fetch_roll_result_thumbs(self, ctx: ApplicationContext) -> dict[str, list[str]]:
        """Get all roll result thumbnails for a guild."""
        # TODO: Move this to Dicerolls
        if ctx.guild.id not in self.roll_result_thumbs:
            self.roll_result_thumbs[ctx.guild.id] = {}

            logger.debug(f"DATABASE: Fetch roll result thumbnails for '{ctx.guild.name}'")
            for thumb in RollThumbnail.select().where(RollThumbnail.guild == ctx.guild.id):
                if thumb.roll_type not in self.roll_result_thumbs[ctx.guild.id]:
                    self.roll_result_thumbs[ctx.guild.id][thumb.roll_type] = [thumb.url]
                else:
                    self.roll_result_thumbs[ctx.guild.id][thumb.roll_type].append(thumb.url)

        return self.roll_result_thumbs[ctx.guild.id]

    def purge_cache(self, guild: discord.Guild | None = None) -> None:
        """Purge the cache for a guild or all guilds.

        Args:
            guild (discord.Guild, optional): The guild to purge the cache for. Defaults to None.
        """
        if guild:
            self.settings_cache.pop(guild.id, None)
            self.roll_result_thumbs.pop(guild.id, None)
            logger.debug(f"CACHE: Purge guild cache for '{guild.name}'")
        else:
            self.settings_cache = {}
            self.roll_result_thumbs = {}
            logger.debug("CACHE: Purge all guild caches")

    async def send_to_audit_log(
        self, ctx: ApplicationContext, message: str | discord.Embed
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
        self, ctx: ApplicationContext, message: str | discord.Embed, error: Exception
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
        embed = discord.Embed(title=message, color=EmbedColor.INFO.value)
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

    def verify_guild_defaults(self, guild: discord.Guild) -> None:
        """Verify that the guild defaults are set.  If any keys are missing, they are added to the guild's data with default values.

        Args:
            guild (discord.Guild): The guild to verify.


        """
        default_values = {
            "log_channel_id": None,
            "use_audit_log": False,
            "trait_permissions": TraitPermissions.WITHIN_24_HOURS.value,
            "xp_permissions": XPPermissions.WITHIN_24_HOURS.value,
            "use_storyteller_channel": False,
            "storyteller_channel_id": None,
            "use_error_log_channel": False,
            "error_log_channel_id": None,
        }

        instance = Guild.get_by_id(guild.id)
        instance.data = instance.data or {}  # Ensure data is not None

        updated = False
        for default_key, default_value in default_values.items():
            if default_key not in instance.data:
                logger.info(
                    f"DATABASE: Updated guild '{guild.name}' with default '{default_key}: {default_value}'"
                )
                instance.data[default_key] = default_value
                updated = True

        if updated:
            instance.save()
        else:
            logger.info(f"DATABASE: Guild '{guild.name}' defaults are up to date")

    def update_or_add(
        self,
        guild: discord.Guild,
        updates: dict[str, str | int | bool] | None = None,
    ) -> None:
        """Add a guild to the database or update it if it already exists."""
        self.purge_cache(guild)

        db_guild, is_created = Guild.get_or_create(
            id=guild.id,
            defaults={
                "name": guild.name,
                "created": time_now(),
                "data": {
                    "modified": str(time_now()),
                    "log_channel_id": None,
                    "use_audit_log": False,
                    "trait_permissions": TraitPermissions.WITHIN_24_HOURS.value,
                    "xp_permissions": XPPermissions.WITHIN_24_HOURS.value,
                    "use_storyteller_channel": False,
                    "storyteller_channel_id": None,
                    "use_error_log_channel": False,
                    "error_log_channel_id": None,
                },
            },
        )

        if is_created:
            logger.info(f"DATABASE: Created guild {db_guild.name}")
        else:
            data_dict = updates or {}
            data_dict["modified"] = str(time_now())

            for key, value in data_dict.items():
                logger.debug(f"DATABASE: Update guild {db_guild.name}: {key} to {value}")

            Guild.update(data=Guild.data.update(data_dict)).where(Guild.id == guild.id).execute()
            logger.debug(f"DATABASE: Updated guild '{db_guild.name}'")
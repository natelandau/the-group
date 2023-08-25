"""Discord user database models and services.

Note, due to ForeignKey constraints, models are defined in database.py.
"""
from collections.abc import Callable
from datetime import timedelta

import arrow
import discord
from loguru import logger

from valentina.constants import PermissionManageCampaign, PermissionsEditTrait, PermissionsEditXP
from valentina.models.db_tables import Character, GuildUser, User
from valentina.utils.helpers import time_now


class UserService:
    """User manager and in-memory cache."""

    def __init__(self) -> None:
        """Initialize the UserService."""
        self.user_cache: dict[str, User] = {}  # {user_key: User, ...}

    @staticmethod
    def __get_user_key(guild: discord.Guild | int, user: discord.User | int) -> str:
        """Construct a string key from guild and user IDs. Used for keys in the user cache.

        Use the 'guild' and 'user' arguments to retrieve IDs. If 'guild' or 'user' is an
        instance of discord.Guild or discord.User, get the 'id' attribute. If they're
        integers, use them directly.

        Args:
            guild (discord.Guild | int): A discord.Guild instance or a guild ID.
            user (discord.User | int): A discord.User instance or a user ID.

        Returns:
            str: A string composed of guild and user IDs, joined by an underscore.
        """
        guild_id = guild.id if isinstance(guild, discord.Guild) else guild
        user_id = user.id if isinstance(user, discord.User) else user

        return f"{guild_id}_{user_id}"

    def purge_cache(self, ctx: discord.ApplicationContext | None = None) -> None:
        """Purge the user service cache.

            If 'ctx' is provided, purge the cache for the specific user. If 'ctx' is None,
        purge all user caches.

        Args:
            ctx (ApplicationContext | None, optional): The application context. Defaults to None.
        """
        if ctx:
            for key in list(self.user_cache.keys()):
                if key.startswith(f"{ctx.guild.id}_"):
                    self.user_cache.pop(key, None)
                    logger.debug(f"CACHE: Purge user cache: {key}")
        else:
            self.user_cache = {}
            logger.debug("CACHE: Purge all user caches")

    def fetch_user(self, ctx: discord.ApplicationContext) -> User:
        """Retrieve a User object from the cache or the database.

        Use the application context 'ctx' to fetch a User. If the User isn't present
        in the cache or the database, create a new User in the database and the cache.

        Args:
            ctx (ApplicationContext): Application context used to fetch the user.

        Returns:
            User: User model instance
        """
        key = self.__get_user_key(ctx.guild.id, ctx.author.id)
        if key in self.user_cache:
            logger.info(f"CACHE: Return user with ID {ctx.author.id}")
            return self.user_cache[key]

        user, created = User.get_or_create(
            id=ctx.author.id,
            defaults={
                "name": ctx.author.display_name,
                "username": ctx.author.name,
                "mention": ctx.author.mention,
                "first_seen": time_now(),
                "last_seen": time_now(),
            },
        )

        if created:
            GuildUser.get_or_create(user=ctx.author.id, guild=ctx.guild.id)
            logger.info(f"DATABASE: Create user '{ctx.author.display_name}'")
        else:
            user.last_seen = time_now()
            user.save()
            logger.debug(f"DATABASE: Update last_seen for user '{ctx.author.display_name}'")

        self.user_cache[key] = user
        logger.debug(f"CACHE: Add user '{ctx.author.display_name}'")

        return user

    def can_update_xp(self, ctx: discord.ApplicationContext, character: Character = None) -> bool:
        """Check if the user has permissions to add experience points.

        The function checks the following conditions in order:
        - If the author is an administrator, return True.
        - Fetch the guild settings. If they cannot be fetched, return False.
        - Use a mapping from xp permissions to functions to check the corresponding permission type and return the result.

        Args:
            ctx (ApplicationContext): The application context.
            character (Character, optional): The character to check permissions for. Defaults to None.

        Returns:
            bool: True if the user has permissions to add xp, False otherwise.
        """
        permissions_dict: dict[
            PermissionsEditXP, Callable[[discord.ApplicationContext, Character], bool]
        ] = {
            PermissionsEditXP.UNRESTRICTED: lambda ctx, character: True,  # noqa: ARG005
            PermissionsEditXP.CHARACTER_OWNER_ONLY: lambda ctx, character: character
            and character.created_by.id == ctx.author.id,
            PermissionsEditXP.WITHIN_24_HOURS: lambda ctx, character: character
            and character.created_by.id == ctx.author.id
            and (arrow.utcnow() - arrow.get(character.created) <= timedelta(hours=24)),
            PermissionsEditXP.STORYTELLER_ONLY: lambda ctx, character: "Storyteller"  # noqa: ARG005
            in [x.name for x in ctx.author.roles],
        }

        if ctx.author.guild_permissions.administrator:
            return True

        settings = ctx.bot.guild_svc.fetch_guild_settings(ctx)  # type: ignore [attr-defined]
        if not settings:
            return False

        permission = PermissionsEditXP(settings["permissions_edit_xp"])
        check_permission = permissions_dict.get(permission)
        if check_permission:
            return check_permission(ctx, character)

        return False

    def can_update_traits(
        self, ctx: discord.ApplicationContext, character: Character = None
    ) -> bool:
        """Check if the user has permissions to update character trait values.

        The function checks the following conditions in order:
        - If the author is an administrator, return True.
        - Fetch the guild settings. If they cannot be fetched, return False.
        - Use a mapping from trait permissions to functions to check the corresponding permission type and return the result.

        Args:
            ctx (ApplicationContext): The application context.
            character (Character, optional): The character to check permissions for. Defaults to None.

        Returns:
            bool: True if the user has permissions to update traits, False otherwise.
        """
        permissions_dict: dict[
            PermissionsEditTrait, Callable[[discord.ApplicationContext, Character], bool]
        ] = {
            PermissionsEditTrait.UNRESTRICTED: lambda ctx, character: True,  # noqa: ARG005
            PermissionsEditTrait.CHARACTER_OWNER_ONLY: lambda ctx, character: character
            and character.created_by.id == ctx.author.id,
            PermissionsEditTrait.WITHIN_24_HOURS: lambda ctx, character: character
            and character.created_by.id == ctx.author.id
            and (arrow.utcnow() - arrow.get(character.created) <= timedelta(hours=24)),
            PermissionsEditTrait.STORYTELLER_ONLY: lambda ctx, character: "Storyteller"  # noqa: ARG005
            in [x.name for x in ctx.author.roles],
        }

        if ctx.author.guild_permissions.administrator:
            return True

        settings = ctx.bot.guild_svc.fetch_guild_settings(ctx)  # type: ignore [attr-defined]
        if not settings:
            return False

        permission = PermissionsEditTrait(settings["permissions_edit_trait"])
        check_permission = permissions_dict.get(permission)
        if check_permission:
            return check_permission(ctx, character)

        return False

    def can_manage_campaign(self, ctx: discord.ApplicationContext) -> bool:
        """Check if the user has permissions to manage campaigns.

        The function checks the following conditions in order:
        - If the author is an administrator, return True.
        - Fetch the guild settings. If they cannot be fetched, return False.
        - Use a mapping from trait permissions to functions to check the corresponding permission type and return the result.

        Args:
            ctx (ApplicationContext): The application context.


        Returns:
            bool: True if the user has permissions to update traits, False otherwise.
        """
        permissions_dict: dict[
            PermissionManageCampaign, Callable[[discord.ApplicationContext], bool]
        ] = {
            PermissionManageCampaign.UNRESTRICTED: lambda x: True,  # noqa: ARG005
            PermissionManageCampaign.STORYTELLER_ONLY: lambda ctx: "Storyteller"
            in [x.name for x in ctx.author.roles],
        }

        if ctx.author.guild_permissions.administrator:
            return True

        settings = ctx.bot.guild_svc.fetch_guild_settings(ctx)  # type: ignore [attr-defined]
        if not settings:
            return False

        permission = PermissionManageCampaign(settings["permissions_manage_campaigns"])
        check_permission = permissions_dict.get(permission)
        if check_permission:
            return check_permission(ctx)

        return False

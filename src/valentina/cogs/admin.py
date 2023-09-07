# mypy: disable-error-code="valid-type"
"""Administration commands for Valentina."""

from io import BytesIO

import discord
import inflect
from aiohttp import ClientSession
from discord import OptionChoice
from discord.commands import Option
from discord.ext import commands
from discord.ext.commands import MemberConverter

from valentina.constants import (
    ChannelPermission,
    PermissionManageCampaign,
    PermissionsEditTrait,
    PermissionsEditXP,
    RollResultType,
)
from valentina.models.bot import Valentina
from valentina.utils import errors
from valentina.utils.converters import ValidChannelName
from valentina.utils.helpers import assert_permissions
from valentina.views import (
    SettingsManager,
    ThumbnailReview,
    confirm_action,
    present_embed,
)

p = inflect.engine()


class Admin(commands.Cog):
    """Valentina settings, debugging, and administration."""

    def __init__(self, bot: Valentina) -> None:
        self.bot = bot

    admin = discord.SlashCommandGroup(
        "admin",
        "Administer Valentina",
        default_member_permissions=discord.Permissions(administrator=True),
    )
    user = admin.create_subgroup(
        "user",
        "Administer users",
        default_member_permissions=discord.Permissions(administrator=True),
    )
    guild = admin.create_subgroup(
        "guild",
        "Administer guild",
        default_member_permissions=discord.Permissions(administrator=True),
    )
    channel = admin.create_subgroup(
        "channel",
        "Administer the current channel",
        default_member_permissions=discord.Permissions(administrator=True),
    )

    ### USER ADMINISTRATION COMMANDS ################################################################

    @user.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def add_role(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member,
        role: discord.Role,
        reason: Option(str, description="Reason for adding role", default="No reason provided"),
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Add user to role."""
        # Confirm the action
        title = f"Add {member.display_name} to {role.name}"
        is_confirmed, confirmation_response_msg = await confirm_action(
            ctx, title, description=reason, hidden=hidden
        )
        if not is_confirmed:
            return

        await member.add_roles(role, reason=reason)

        await confirmation_response_msg

    @user.command()
    @discord.guild_only()
    @commands.has_permissions(administrator=True)
    async def kick(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member,
        *,
        reason: str = "No reason given",
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Kick a target member, by ID or mention."""
        if member.id == ctx.author.id:
            raise errors.ValidationError("You cannot kick yourself.")

        if member.top_role >= ctx.author.top_role:
            raise errors.ValidationError("You cannot kick this member.")

        # Confirm the action
        title = f"Kick {member.display_name} from this guild"
        is_confirmed, confirmation_response_msg = await confirm_action(
            ctx, title, description=reason, hidden=hidden
        )
        if not is_confirmed:
            return

        await member.kick(reason=reason)

        await confirmation_response_msg

    @user.command()
    @discord.guild_only()
    @commands.has_permissions(ban_members=True)
    async def ban(
        self,
        ctx: discord.ApplicationContext,
        user: discord.User,
        *,
        reason: str = "No reason given",
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Ban a target member, by ID or mention."""
        await assert_permissions(ctx, ban_members=True)
        if user := discord.utils.get(ctx.guild.members, id=user.id):
            if user.id == ctx.author.id:
                raise errors.ValidationError("You cannot ban yourself.")

            if user.top_role >= ctx.author.top_role:
                raise errors.ValidationError("You cannot ban this member.")

        # Confirm the action
        title = f"Ban {user.display_name} from this guild"
        is_confirmed, confirmation_response_msg = await confirm_action(
            ctx, title, description=reason, hidden=hidden
        )
        if not is_confirmed:
            return

        await ctx.guild.ban(
            discord.Object(id=user.id), reason=f"{ctx.author} ({ctx.author.id}): {reason}"
        )

        await confirmation_response_msg

    @user.command()
    @discord.guild_only()
    @commands.has_permissions(administrator=True)
    async def unban(
        self,
        ctx: discord.ApplicationContext,
        user: discord.User,
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Revoke ban from a banned user."""
        # Confirm the action
        title = f"Unban {user.display_name} from this guild"
        is_confirmed, confirmation_response_msg = await confirm_action(ctx, title, hidden=hidden)
        if not is_confirmed:
            return

        try:
            await ctx.guild.unban(user)
        except discord.HTTPException:
            await present_embed(
                ctx,
                title=f"{user.display_name} ({user.id}) was not banned",
                level="info",
                ephemeral=True,
            )
            return

        await confirmation_response_msg

    @user.command()
    @discord.guild_only()
    @commands.has_permissions(administrator=True)
    async def massban(
        self,
        ctx: discord.ApplicationContext,
        members: Option(
            str, "The mentions, usernames, or IDs of the members to ban. Separated by spaces"
        ),
        *,
        reason: Option(
            str,
            description="The reason for the ban",
            default="No reason provided",
        ),
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Ban the supplied members from the guild. Limited to 10 at a time."""
        await assert_permissions(ctx, ban_members=True)
        converter = MemberConverter()
        converted_members = [
            await converter.convert(ctx, member) for member in members.split()  # type: ignore # mismatching context type
        ]
        if (count := len(converted_members)) > 10:  # noqa: PLR2004
            await present_embed(
                ctx,
                title="Too many members",
                description="You can only ban 10 members at a time",
                level="error",
                ephemeral=True,
            )
            return

        # Confirm the action
        title = f"Mass ban {count} {p.plural_noun('member',count)} from this guild"
        is_confirmed, confirmation_response_msg = await confirm_action(
            ctx, title, description=reason, hidden=hidden
        )
        if not is_confirmed:
            return

        for user in converted_members:
            if user := discord.utils.get(ctx.guild.members, id=user.id):
                if user.id == ctx.author.id:
                    raise errors.ValidationError("You cannot ban yourself.")

                if user.top_role >= ctx.author.top_role:
                    raise errors.ValidationError("You cannot ban this member.")

            await ctx.guild.ban(user, reason=f"{ctx.author} ({ctx.author.id}): {reason}")

        await confirmation_response_msg

    ## SETTINGS COMMANDS #############################################################################

    @admin.command(name="settings", description="Manage Guild Settings")
    async def settings_manager(self, ctx: discord.ApplicationContext) -> None:
        """Manage Guild Settings."""
        manager = SettingsManager(ctx)
        paginator = manager.display_settings_manager()
        await paginator.respond(ctx.interaction, ephemeral=True)
        await paginator.wait()

    ### GUILD ADMINISTRATION COMMANDS ################################################################
    @guild.command(name="show_settings", description="Show server settings for this guild")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def show_settings(
        self,
        ctx: discord.ApplicationContext,
        hidden: Option(
            bool,
            description="Make the response only visible to you (default true).",
            default=True,
        ),
    ) -> None:
        """Show server settings for this guild."""
        embed = await self.bot.guild_svc.get_setting_review_embed(ctx)
        await ctx.respond(embed=embed, ephemeral=hidden)

    @guild.command(description="Configure the settings for this guild")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def settings_old(
        self,
        ctx: discord.ApplicationContext,
        trait_permissions: Option(
            str,
            "Whether users should be allowed to edit their traits.",
            choices=[
                OptionChoice(x.name.title().replace("_", " "), str(x.value))
                for x in PermissionsEditTrait
            ],
            required=False,
        ),
        xp_permissions: Option(
            str,
            "Whether users should be allowed to edit their XP totals.",
            choices=[
                OptionChoice(x.name.title().replace("_", " "), str(x.value))
                for x in PermissionsEditXP
            ],
            required=False,
        ),
        manage_campaigns: Option(
            str,
            "Which roles can manage campaigns.",
            choices=[
                OptionChoice(x.name.title().replace("_", " "), str(x.value))
                for x in PermissionManageCampaign
            ],
            required=False,
        ),
        use_audit_log: Option(
            bool,
            "Send audit logs to channel",
            choices=[OptionChoice("Enable", True), OptionChoice("Disable", False)],
            required=False,
            default=None,
        ),
        audit_log_channel_name: Option(
            ValidChannelName,
            "Audit command usage to this channel",
            required=False,
            default=None,
        ),
        use_error_log_channel: Option(
            bool,
            "Log errors to a specified channel",
            choices=[OptionChoice("Enable", True), OptionChoice("Disable", False)],
            required=False,
            default=None,
        ),
        error_log_channel_name: Option(
            ValidChannelName,
            "Name for the error log channel",
            required=False,
            default=None,
        ),
        use_storyteller_channel: Option(
            bool,
            "Use a private storyteller channel",
            choices=[OptionChoice("Enable", True), OptionChoice("Disable", False)],
            required=False,
            default=None,
        ),
        storyteller_channel_name: Option(
            ValidChannelName,
            "Name the private storyteller channel",
            required=False,
            default=None,
        ),
    ) -> None:
        """Manage Valentina's settings for this guild.

        Args:
            ctx (discord.ApplicationContext): The command context.
            trait_permissions (str, optional): Whether users should be allowed to edit their traits.
            xp_permissions (str, optional): Whether users should be allowed to edit their XP totals.
            manage_campaigns (str, optional): Which roles can manage campaigns.
            use_audit_log (bool, optional): Send audit logs to channel.
            audit_log_channel_name (str, optional): Audit command usage to this channel.
            use_error_log_channel (bool, optional): Log errors to a specified channel.
            error_log_channel_name (str, optional): Name for the error log channel.
            use_storyteller_channel (bool, optional): Use a private storyteller channel.
            storyteller_channel_name (str, optional): Name the private storyteller channel.

        Returns:
            None
        """
        current_settings = self.bot.guild_svc.fetch_guild_settings(ctx)
        fields = []
        update_data: dict[str, str | int | bool] = {}

        # Handle permissions
        permission_mapping = {
            "xp_permissions": (PermissionsEditXP, "permissions_edit_xp"),
            "trait_permissions": (PermissionsEditTrait, "permissions_edit_trait"),
            "manage_campaigns": (PermissionManageCampaign, "permissions_manage_campaigns"),
        }

        for option, (enum_class, db_key) in permission_mapping.items():
            value = locals()[option]
            if value is not None:
                fields.append(
                    (option.replace("_", " ").title(), enum_class(int(value)).name.title())
                )
                update_data[db_key] = int(value)

        # Handle channel-related settings with specific permissions
        channel_settings = [
            (
                "use_audit_log",
                "log_channel_id",
                "audit_log_channel_name",
                "Audit logs",
                100,
                ChannelPermission.HIDDEN,
                ChannelPermission.HIDDEN,
                ChannelPermission.READ_ONLY,
            ),
            (
                "use_storyteller_channel",
                "storyteller_channel_id",
                "storyteller_channel_name",
                "Storyteller channel",
                90,
                ChannelPermission.HIDDEN,
                ChannelPermission.HIDDEN,
                ChannelPermission.POST,
            ),
            (
                "use_error_log_channel",
                "error_log_channel_id",
                "error_log_channel_name",
                "Error log channel",
                90,
                ChannelPermission.HIDDEN,
                ChannelPermission.HIDDEN,
                ChannelPermission.HIDDEN,
            ),
        ]

        for (
            setting,
            db_key,
            channel_name_key,
            topic,
            position,
            default_role,
            player,
            storyteller,
        ) in channel_settings:
            use_setting = locals()[setting]
            channel_name = locals()[channel_name_key]

            if use_setting is not None:
                if use_setting and not current_settings[db_key] and not channel_name:
                    await present_embed(
                        ctx,
                        title=f"No {setting.replace('_', ' ').title()} Channel",
                        description=f"Please rerun the command and enter a name for the {setting.replace('_', ' ').title()} channel",
                        level="error",
                        ephemeral=True,
                    )
                    return

                fields.append(
                    (setting.replace("_", " ").title(), "Enabled" if use_setting else "Disabled")
                )
                update_data[setting] = use_setting

            if channel_name is not None:
                created_channel = await self.bot.guild_svc.create_channel(
                    ctx, channel_name, topic, position, db_key, default_role, player, storyteller
                )
                fields.append((setting.replace("_", " ").title(), created_channel.mention))
                update_data[db_key] = created_channel.id

        # Show results
        if fields:
            self.bot.guild_svc.update_or_add(ctx=ctx, updates=update_data)
            updates = ", ".join(f"`{k}={v}`" for k, v in update_data.items() if k != "modified")
            await self.bot.guild_svc.send_to_audit_log(ctx, f"Settings updated: {updates}")
            await present_embed(
                ctx, title="Settings Updated", fields=fields, level="success", ephemeral=True
            )
        else:
            await present_embed(ctx, title="No settings updated", level="info", ephemeral=True)

    @guild.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def review_result_thumbnails(
        self, ctx: discord.ApplicationContext, roll_type: Option(RollResultType, required=True)
    ) -> None:
        """Review all result thumbnails for this guild."""
        await ThumbnailReview(ctx, roll_type).send(ctx)

    @guild.command(name="emoji_add")
    @discord.option("name", description="The name of the emoji.")
    @discord.option("url", description="The image url of the emoji.")
    async def emoji_add(
        self,
        ctx: discord.ApplicationContext,
        name: str,
        url: str,
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Add a custom emoji to this guild."""
        await assert_permissions(ctx, manage_emojis=True)

        async with ClientSession() as session, session.get(url) as res:
            if 300 > res.status >= 200:  # noqa: PLR2004
                await ctx.guild.create_custom_emoji(
                    name=name, image=BytesIO(await res.read()).getvalue()
                )

                await self.bot.guild_svc.send_to_audit_log(
                    ctx, f"Add emoji to guild: `:{name}:`\n{url}"
                )

                await present_embed(
                    ctx,
                    title=f"Custom emoji `:{name}:` added",
                    image=url,
                    level="success",
                    ephemeral=hidden,
                )

            else:
                await present_embed(
                    ctx,
                    title="Emoji Creation Failed",
                    description=f"An HTTP error occurred while fetching the image: {res.status} {res.reason}",
                    level="error",
                    ephemeral=True,
                )

    @guild.command(name="emoji_delete")
    @discord.option("name", description="The name of the emoji to delete.")
    async def emoji_delete(
        self,
        ctx: discord.ApplicationContext,
        name: str,
        reason: Option(
            str,
            description="The reason for deleting this emoji",
            default="No reason provided",
        ),
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Delete a custom emoji from this guild."""
        await assert_permissions(ctx, manage_emojis=True)
        for emoji in ctx.guild.emojis:
            if emoji.name == name:
                await emoji.delete(reason=reason)

                await self.bot.guild_svc.send_to_audit_log(
                    ctx, f"Delete emoji from guild: `:{name}:`"
                )

                await present_embed(
                    ctx,
                    title=f"Emoji `:{name}:` deleted",
                    description=reason,
                    level="success",
                    ephemeral=hidden,
                )
                return

        await present_embed(
            ctx,
            title="Emoji Not Found",
            description=f"Could not find a custom emoji name `:{name}:`",
            level="error",
            ephemeral=True,
        )

    ### CHANNEL ADMINISTRATION COMMANDS ################################################################
    @channel.command(name="slowmode", description="Set slowmode for the current channel")
    @discord.guild_only()
    @commands.has_permissions(administrator=True)
    async def slowmode(
        self,
        ctx: discord.ApplicationContext,
        seconds: Option(int, description="The slowmode cooldown in seconds, 0 to disable slowmode"),
        hidden: Option(
            bool,
            description="Make the response only visible to you (default true).",
            default=True,
        ),
    ) -> None:
        """Set slowmode for the current channel."""
        if not isinstance(ctx.channel, discord.TextChannel):
            raise commands.BadArgument("Slowmode can only be set in text channels.")

        await assert_permissions(ctx, manage_channels=True)

        if not 21600 >= seconds >= 0:  # noqa: PLR2004
            await present_embed(
                ctx,
                title="Error setting slowmode",
                description="Slowmode should be between `21600` and `0` seconds",
                level="error",
                ephemeral=hidden,
            )
            return

        # Confirm the action
        title = f"Set slowmode to {seconds} seconds"
        is_confirmed, confirmation_response_msg = await confirm_action(ctx, title, hidden=hidden)
        if not is_confirmed:
            return

        await ctx.channel.edit(slowmode_delay=seconds)

        await confirmation_response_msg

    @channel.command()
    @discord.guild_only()
    @commands.has_permissions(administrator=True)
    async def lock(
        self,
        ctx: discord.ApplicationContext,
        *,
        reason: Option(
            str,
            description="The reason for locking this channel",
            default="No reason provided",
        ),
        hidden: Option(
            bool,
            description="Make the response only visible to you (default false).",
            default=False,
        ),
    ) -> None:
        """Disable the `Send Message` permission for the default role."""
        await assert_permissions(ctx, manage_roles=True)

        if not isinstance(ctx.channel, discord.TextChannel):
            raise commands.BadArgument("Only text channels can be locked")

        if ctx.channel.overwrites_for(ctx.guild.default_role).send_messages is False:
            await ctx.respond("This channel is already locked.", ephemeral=True)
            return

        # Confirm the action
        title = "Lock this channel"
        is_confirmed, confirmation_response_msg = await confirm_action(
            ctx, title, description=reason, hidden=hidden
        )
        if not is_confirmed:
            return

        await ctx.channel.edit(
            overwrites={ctx.guild.default_role: discord.PermissionOverwrite(send_messages=False)},
            reason=f"{ctx.author} ({ctx.author.id}): {reason}",
        )

        await confirmation_response_msg

    @channel.command()
    @discord.guild_only()
    @commands.has_permissions(administrator=True)
    async def unlock(
        self,
        ctx: discord.ApplicationContext,
        *,
        reason: Option(
            str,
            description="The reason for unlocking this channel",
            default="No reason provided",
        ),
        hidden: Option(
            bool,
            description="Make the response only visible to you (default false).",
            default=False,
        ),
    ) -> None:
        """Set the `Send Message` permission to the default state for the default role."""
        await assert_permissions(ctx, manage_roles=True)
        if not isinstance(ctx.channel, discord.TextChannel):
            raise commands.BadArgument("Only text channels can be locked or unlocked")

        if ctx.channel.overwrites_for(ctx.guild.default_role).send_messages is not False:
            await ctx.respond("This channel isn't locked.", ephemeral=True)
            return

        # Confirm the action
        title = "Unlock this channel"
        is_confirmed, confirmation_response_msg = await confirm_action(
            ctx, title, description=reason, hidden=hidden
        )
        if not is_confirmed:
            return

        await ctx.channel.edit(
            overwrites={ctx.guild.default_role: discord.PermissionOverwrite(send_messages=None)},
            reason=f"{ctx.author} ({ctx.author.id}): {reason}",
        )
        await confirmation_response_msg

    @channel.command()
    @commands.has_permissions(administrator=True)
    @discord.option(
        "limit",
        description="The amount of messages to delete",
        min_value=1,
        max_value=100,
    )
    async def purge_old_messages(
        self,
        ctx: discord.ApplicationContext,
        limit: int,
        *,
        reason: Option(
            str,
            description="The reason for purging messages.",
            default="No reason provided",
        ),
    ) -> None:
        """Delete messages from this channel."""
        await assert_permissions(ctx, read_message_history=True, manage_messages=True)

        if purge := getattr(ctx.channel, "purge", None):
            count = len(await purge(limit=limit, reason=reason))
            await present_embed(
                ctx,
                title=f"Purged `{count}` {p.plural_noun('message', count)} from this channel",
                level="warning",
                ephemeral=True,
            )
            return

        await ctx.respond("This channel cannot be purged", ephemeral=True)
        return

    @channel.command()
    @commands.has_permissions(administrator=True)
    @discord.option(
        "member",
        description="The member whose messages will be deleted.",
    )
    @discord.option(
        "limit",
        description="The amount of messages to search.",
        min_value=1,
        max_value=100,
    )
    async def purge_by_member(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member,
        limit: int,
        *,
        reason: Option(
            str,
            description="The reason for purging messages",
            default="No reason provided",
        ),
    ) -> None:
        """Purge a member's messages from this channel."""
        await assert_permissions(ctx, read_message_history=True, manage_messages=True)

        if purge := getattr(ctx.channel, "purge", None):
            count = len(
                await purge(limit=limit, reason=reason, check=lambda m: m.author.id == member.id)
            )
            await present_embed(
                ctx,
                title=f"Purged `{count}` {p.plural_noun('message', count)} from `{member.display_name}` in this channel",
                level="warning",
                ephemeral=True,
            )
            return

        await ctx.respond("This channel cannot be purged", ephemeral=True)
        return

    @channel.command()
    @commands.has_permissions(administrator=True)
    @discord.option(
        "limit",
        description="The amount of messages to search.",
        min_value=1,
        max_value=100,
    )
    async def purge_bot_messages(
        self,
        ctx: discord.ApplicationContext,
        limit: int,
        *,
        reason: Option(
            str,
            description="The reason for purging messages",
            default="No reason provided",
        ),
    ) -> None:
        """Purge bot messages from this channel."""
        await assert_permissions(ctx, read_message_history=True, manage_messages=True)

        if purge := getattr(ctx.channel, "purge", None):
            count = len(await purge(limit=limit, reason=reason, check=lambda m: m.author.bot))
            await present_embed(
                ctx,
                title=f"Purged `{count}` bot {p.plural_noun('message',count)} in this channel",
                level="warning",
                ephemeral=True,
            )
            return

        await ctx.respond("This channel cannot be purged", ephemeral=True)
        return

    @channel.command()
    @commands.has_permissions(administrator=True)
    @discord.option(
        "phrase",
        description="The phrase to delete messages containing it.",
    )
    @discord.option(
        "limit",
        description="The amount of messages to search.",
        min_value=1,
        max_value=100,
    )
    async def purge_containing(
        self,
        ctx: discord.ApplicationContext,
        phrase: str,
        limit: int,
        *,
        reason: Option(
            str,
            description="The reason for purging messages",
            default="No reason provided",
        ),
    ) -> None:
        """Purge messages containing a specific phrase from this channel."""
        await assert_permissions(ctx, read_message_history=True, manage_messages=True)

        if purge := getattr(ctx.channel, "purge", None):
            count = len(
                await purge(limit=limit, reason=reason, check=lambda m: phrase in m.content)
            )
            await present_embed(
                ctx,
                title=f"Purged `{count}` {p.plural_noun('message',count)} containing `{phrase}` in this channel",
                level="warning",
                ephemeral=True,
            )
            return

        await ctx.respond("This channel cannot be purged", ephemeral=True)
        return


def setup(bot: Valentina) -> None:
    """Add the cog to the bot."""
    bot.add_cog(Admin(bot))

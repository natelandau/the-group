# mypy: disable-error-code="valid-type"
"""Administration commands for Valentina."""

from io import BytesIO

import discord
import inflect
from discord import OptionChoice
from discord.commands import Option
from discord.ext import commands
from discord.ext.commands import MemberConverter

from valentina.constants import (
    ChannelPermission,
    PermissionsEditTrait,
    PermissionsEditXP,
    RollResultType,
)
from valentina.models import Statistics
from valentina.models.bot import Valentina
from valentina.utils import errors
from valentina.utils.converters import ValidChannelName
from valentina.utils.helpers import assert_permissions
from valentina.views import ThumbnailReview, present_embed

p = inflect.engine()


class Admin(commands.Cog):
    """Valentina settings, debugging, and administration."""

    def __init__(self, bot: Valentina) -> None:
        self.bot = bot

    ### BOT ADMINISTRATION COMMANDS ################################################################

    admin = discord.SlashCommandGroup(
        "admin",
        "Administer Valentina",
        default_member_permissions=discord.Permissions(administrator=True),
    )

    @admin.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def add_role(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member,
        role: discord.Role,
        reason: Option(str, description="Reason for adding role", default="No reason provided"),
    ) -> None:
        """Add user to role."""
        await member.add_roles(role, reason=reason)
        await present_embed(
            ctx,
            title="Role Added",
            description=f"{member.display_name} was added to {role.mention}",
            level="success",
            ephemeral=True,
        )

    @admin.command()
    @discord.guild_only()
    @commands.has_permissions(administrator=True)
    async def userinfo(
        self,
        ctx: discord.ApplicationContext,
        user: Option(
            discord.User,
            description="The user to view information for",
            required=True,
        ),
        hidden: Option(
            bool,
            description="Make the response only visible to you (default true).",
            default=True,
        ),
    ) -> None:
        """View information about a user."""
        target = user or ctx.author

        creation = ((target.id >> 22) + 1420070400000) // 1000

        fields = [("Account Created", f"<t:{creation}:R> on <t:{creation}:D>")]
        if isinstance(target, discord.Member):
            fields.append(
                (
                    "Joined Server",
                    f"<t:{int(target.joined_at.timestamp())}:R> on <t:{int(target.joined_at.timestamp())}:D>",
                )
            )
            fields.append(
                (
                    f"Roles ({len(target._roles)})",
                    ", ".join(r.mention for r in target.roles[::-1][:-1])
                    or "_Member has no roles_",
                )
            )
            if boost := target.premium_since:
                fields.append(
                    (
                        "Boosting Since",
                        f"<t:{int(boost.timestamp())}:R> on <t:{int(boost.timestamp())}:D>",
                    )
                )
            else:
                fields.append(("Boosting Server?", "No"))

            roll_stats = Statistics(ctx, user=target)
            fields.append(("Roll Statistics", roll_stats.get_text(with_title=False)))

        await present_embed(
            ctx,
            title=f"{target.display_name}",
            fields=fields,
            inline_fields=False,
            thumbnail=target.display_avatar.url,
            author=str(target),
            author_avatar=target.display_avatar.url,
            footer=f"Requested by {ctx.author}",
            ephemeral=hidden,
            level="info",
        )

    @admin.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def settings(  # noqa: C901, PLR0912
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
        """Manage Valentina's settings for this guild."""
        current_settings = self.bot.guild_svc.fetch_guild_settings(ctx)
        fields = []
        update_data: dict[str, str | int | bool] = {}
        if xp_permissions is not None:
            fields.append(("XP Permissions", PermissionsEditXP(int(xp_permissions)).name.title()))
            update_data["xp_permissions"] = int(xp_permissions)

        if trait_permissions is not None:
            fields.append(
                ("Trait Permissions", PermissionsEditTrait(int(trait_permissions)).name.title())
            )
            update_data["trait_permissions"] = int(trait_permissions)

        if use_audit_log is not None:
            if (
                use_audit_log
                and not current_settings["log_channel_id"]
                and not audit_log_channel_name
            ):
                await present_embed(
                    ctx,
                    title="No audit log channel",
                    description="Please rerun the command and enter a channel name for audit logging",
                    level="error",
                    ephemeral=True,
                )
                return
            fields.append(("Audit Logging", "Enabled" if use_audit_log else "Disabled"))
            update_data["use_audit_log"] = use_audit_log

        if audit_log_channel_name is not None:
            channel = await self.bot.guild_svc.create_channel(
                ctx,
                audit_log_channel_name,
                topic="Audit logs",
                position=100,
                database_key="log_channel_id",
                default_role=ChannelPermission.HIDDEN,
                player=ChannelPermission.HIDDEN,
                storyteller=ChannelPermission.READ_ONLY,
            )
            fields.append(("Audit Log Channel", channel.mention))
            update_data["log_channel_id"] = channel.id

        if use_storyteller_channel is not None:
            if (
                use_storyteller_channel
                and not current_settings["storyteller_channel_id"]
                and not storyteller_channel_name
            ):
                await present_embed(
                    ctx,
                    title="No storyteller log channel",
                    description="Please rerun the command and enter a name for the storyteller channel",
                    level="error",
                    ephemeral=True,
                )
                return
            fields.append(
                ("Storyteller Channel", "Enabled" if use_storyteller_channel else "Disabled")
            )
            update_data["use_storyteller_channel"] = use_storyteller_channel

        if storyteller_channel_name is not None:
            channel = await self.bot.guild_svc.create_channel(
                ctx,
                storyteller_channel_name,
                topic="Storyteller channel",
                position=90,
                database_key="storyteller_channel_id",
                default_role=ChannelPermission.HIDDEN,
                player=ChannelPermission.HIDDEN,
                storyteller=ChannelPermission.POST,
            )

            fields.append(("Storyteller Channel", channel.mention))
            update_data["storyteller_channel_id"] = channel.id

        if use_error_log_channel is not None:
            if (
                use_error_log_channel
                and not current_settings["error_log_channel_id"]
                and not error_log_channel_name
            ):
                await present_embed(
                    ctx,
                    title="No Error Log channel",
                    description="Please rerun the command and enter a name for the Error Log channel",
                    level="error",
                    ephemeral=True,
                )
                return
            fields.append(("Error Log Channel", "Enabled" if use_error_log_channel else "Disabled"))
            update_data["use_error_log_channel"] = use_error_log_channel

        if error_log_channel_name is not None:
            channel = await self.bot.guild_svc.create_channel(
                ctx,
                error_log_channel_name,
                topic="Error log channel",
                position=90,
                database_key="error_log_channel_id",
                default_role=ChannelPermission.HIDDEN,
                player=ChannelPermission.HIDDEN,
                storyteller=ChannelPermission.HIDDEN,
            )

            fields.append(("Error Log Channel", channel.mention))
            update_data["error_log_channel_id"] = channel.id
        # Show results
        if len(fields) > 0:
            self.bot.guild_svc.update_or_add(ctx.guild, update_data)

            updates = ", ".join(f"`{k}={v}`" for k, v in update_data.items() if k != "modified")

            await self.bot.guild_svc.send_to_audit_log(ctx, f"Settings updated: {updates}")

            await present_embed(
                ctx,
                title="Settings Updated",
                fields=fields,
                level="success",
                ephemeral=True,
            )

        else:
            await present_embed(ctx, title="No settings updated", level="info", ephemeral=True)

    @admin.command()
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

    @admin.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def review_result_thumbnails(
        self, ctx: discord.ApplicationContext, roll_type: Option(RollResultType, required=True)
    ) -> None:
        """Review all result thumbnails for this guild."""
        await ThumbnailReview(ctx, roll_type).send(ctx)

    ### MODERATION COMMANDS ################################################################

    moderate = discord.SlashCommandGroup(
        "mod",
        "Moderation commands",
        default_member_permissions=discord.Permissions(administrator=True),
    )

    @moderate.command()
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

        await member.kick(reason=reason)

        await present_embed(
            ctx,
            title=f"{member.mention} ({member.id}) kicked from guild",
            description=reason,
            level="warning",
            ephemeral=hidden,
            log=True,
        )

    @moderate.command()
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
        if user := discord.utils.get(ctx.guild.members, id=user.id):
            if user.id == ctx.author.id:
                raise errors.ValidationError("You cannot ban yourself.")

            if user.top_role >= ctx.author.top_role:
                raise errors.ValidationError("You cannot ban this member.")

        await ctx.guild.ban(
            discord.Object(id=user.id), reason=f"{ctx.author} ({ctx.author.id}): {reason}"
        )

        await present_embed(
            ctx,
            title=f"{user.mention} ({user.id}) banned from guild",
            description=reason,
            level="warning",
            ephemeral=hidden,
            log=True,
        )

    @moderate.command()
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

        await present_embed(
            ctx,
            description=f"Unban `{user.display_name} ({user.id})`.",
            level="warning",
            ephemeral=hidden,
            log=True,
        )

    @moderate.command()
    @discord.guild_only()
    @commands.has_permissions(administrator=True)
    async def massban(
        self,
        ctx: discord.ApplicationContext,
        members: Option(
            str, "The mentions, usernames, or IDs of the members to ban. Seperated by spaces"
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

        for user in converted_members:
            if user := discord.utils.get(ctx.guild.members, id=user.id):
                if user.id == ctx.author.id:
                    raise errors.ValidationError("You cannot ban yourself.")

                if user.top_role >= ctx.author.top_role:
                    raise errors.ValidationError("You cannot ban this member.")
            await ctx.guild.ban(user, reason=f"{ctx.author} ({ctx.author.id}): {reason}")

        await present_embed(
            ctx,
            title="Mass Ban Successful",
            description=f"Banned **{count}** {p.plural_noun('member', count)}",
            level="warning",
            ephemeral=hidden,
            log=True,
        )

    @moderate.command()
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

        await ctx.channel.edit(slowmode_delay=seconds)
        await present_embed(
            ctx,
            title="Slowmode set",
            description=f"The slowmode cooldown is now `{seconds}` {p.plural_noun('second', seconds)}"
            if seconds > 0
            else "Slowmode is now disabled",
            level="warning",
        )

        return

    @moderate.command()
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

        await ctx.channel.edit(
            overwrites={ctx.guild.default_role: discord.PermissionOverwrite(send_messages=False)},
            reason=f"{ctx.author} ({ctx.author.id}): {reason}",
        )
        await present_embed(
            ctx,
            title=f"{ctx.author.display_name} locked this channel",
            description=reason,
            level="warning",
            ephemeral=hidden,
        )

        return

    @moderate.command()
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

        await ctx.channel.edit(
            overwrites={ctx.guild.default_role: discord.PermissionOverwrite(send_messages=None)},
            reason=f"{ctx.author} ({ctx.author.id}): {reason}",
        )
        await present_embed(
            ctx,
            title=f"{ctx.author.display_name} unlocked this channel",
            description=reason,
            level="warning",
            ephemeral=hidden,
        )

    @moderate.command()
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

    @moderate.command()
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
            description="The reason for purging messsages",
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

    @moderate.command()
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

    @moderate.command()
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

    ### EMOJI COMMANDS ################################################################

    emoji = discord.SlashCommandGroup(
        "emoji",
        "Add/remove custom emojis",
        default_member_permissions=discord.Permissions(manage_emojis=True),
    )

    @emoji.command(name="add")
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
        async with self.bot.http_session.get(url) as res:
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
                    description=f"An HTTP error ocurred while fetching the image: {res.status} {res.reason}",
                    level="error",
                    ephemeral=True,
                )

    @emoji.command(name="delete")
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


def setup(bot: Valentina) -> None:
    """Add the cog to the bot."""
    bot.add_cog(Admin(bot))

# mypy: disable-error-code="valid-type"
"""Experience commands."""
import discord
import inflect
from discord.commands import Option
from discord.ext import commands

from valentina.constants import COOL_POINT_VALUE, XPMultiplier
from valentina.models.bot import Valentina
from valentina.utils.converters import (
    ValidCharacterObject,
    ValidCharTrait,
)
from valentina.utils.helpers import (
    fetch_clan_disciplines,
    get_max_trait_value,
    get_trait_multiplier,
    get_trait_new_value,
)
from valentina.utils.options import select_player_character, select_trait_from_char_option
from valentina.views import confirm_action, present_embed

p = inflect.engine()


class Experience(commands.Cog):
    """Experience commands."""

    def __init__(self, bot: Valentina) -> None:
        self.bot: Valentina = bot

    xp = discord.SlashCommandGroup("xp", "Add, spend, or view experience points")

    @xp.command(name="add", description="Add experience to a user")
    async def xp_add(
        self,
        ctx: discord.ApplicationContext,
        amount: Option(int, description="The amount of experience to add", required=True),
        user: Option(
            discord.User,
            description="The user to grant experience to",
            required=False,
            default=None,
        ),
        hidden: Option(
            bool,
            description="Make the response visible only to you (default false).",
            default=False,
        ),
    ) -> None:
        """Add experience to a user."""
        if not user:
            user = await self.bot.user_svc.fetch_user(ctx)
        else:
            user = await self.bot.user_svc.fetch_user(ctx, user=user)

        # TODO: Add check for permissions
        campaign = self.bot.campaign_svc.fetch_active(ctx).id

        campaign_xp = user.data.get(f"{campaign}_experience", 0)
        campaign_total_xp = user.data.get(f"{campaign}_total_experience", 0)
        lifetime_xp = user.data.get("lifetime_experience", 0)

        new_xp = campaign_xp + amount
        new_total_xp = campaign_total_xp + amount
        new_lifetime_xp = lifetime_xp + amount

        title = f"Add `{amount}` xp to `{user.data['display_name']}`"
        is_confirmed, confirmation_response_msg = await confirm_action(ctx, title, hidden=hidden)

        if not is_confirmed:
            return

        await self.bot.user_svc.update_or_add(
            ctx,
            user=user,
            data={
                f"{campaign}_experience": new_xp,
                f"{campaign}_total_experience": new_total_xp,
                "lifetime_experience": new_lifetime_xp,
            },
        )

        await self.bot.guild_svc.send_to_audit_log(ctx, title)
        await confirmation_response_msg

    @xp.command(name="cool_point", description="Add a cool point to a user")
    async def cp_add(
        self,
        ctx: discord.ApplicationContext,
        amount: Option(int, description="The amount of experience to add (default 1)", default=1),
        user: Option(
            discord.User,
            description="The user to grant experience to",
            required=False,
            default=None,
        ),
        hidden: Option(
            bool,
            description="Make the response visible only to you (default false).",
            default=False,
        ),
    ) -> None:
        """Add experience to a user."""
        if not user:
            user = await self.bot.user_svc.fetch_user(ctx)
        else:
            user = await self.bot.user_svc.fetch_user(ctx, user=user)

        # TODO: Add check for permissions
        campaign = self.bot.campaign_svc.fetch_active(ctx).id

        campaign_xp = user.data.get(f"{campaign}_experience", 0)
        campaign_total_xp = user.data.get(f"{campaign}_total_experience", 0)
        campaign_total_cp = user.data.get(f"{campaign}_total_cool_points", 0)
        lifetime_xp = user.data.get("lifetime_experience", 0)
        lifetime_cp = user.data.get("lifetime_cool_points", 0)

        xp_amount = amount * COOL_POINT_VALUE
        new_xp = campaign_xp + xp_amount
        new_total_xp = campaign_total_xp + xp_amount
        new_lifetime_xp = lifetime_xp + xp_amount
        new_lifetime_cp = lifetime_cp + amount

        title = (
            f"Add `{amount}` cool {p.plural_noun('point', amount)} to `{user.data['display_name']}`"
        )
        is_confirmed, confirmation_response_msg = await confirm_action(ctx, title, hidden=hidden)

        if not is_confirmed:
            return

        await self.bot.user_svc.update_or_add(
            ctx,
            user=user,
            data={
                f"{campaign}_experience": new_xp,
                f"{campaign}_total_experience": new_total_xp,
                f"{campaign}_total_cool_points": campaign_total_cp + amount,
                "lifetime_cool_points": new_lifetime_cp,
                "lifetime_experience": new_lifetime_xp,
            },
        )

        await self.bot.guild_svc.send_to_audit_log(ctx, title)
        await confirmation_response_msg

    @xp.command(name="spend", description="Spend experience points")
    async def xp_spend(
        self,
        ctx: discord.ApplicationContext,
        character: Option(
            ValidCharacterObject,
            description="The character to view",
            autocomplete=select_player_character,
            required=True,
        ),
        trait: Option(
            ValidCharTrait,
            description="Trait to raise with xp",
            required=True,
            autocomplete=select_trait_from_char_option,
        ),
        hidden: Option(
            bool,
            description="Make the response visible only to you (default false).",
            default=False,
        ),
    ) -> None:
        """Spend experience points."""
        campaign = self.bot.campaign_svc.fetch_active(ctx).id
        old_trait_value = character.get_trait_value(trait)
        category = trait.category.name

        # Compute the cost of the upgrade
        if character.char_class.name == "Vampire" and trait.name in fetch_clan_disciplines(
            character.clan_name
        ):
            multiplier = XPMultiplier.CLAN_DISCIPLINE.value
        else:
            multiplier = get_trait_multiplier(trait.name, category)

        if old_trait_value > 0:
            upgrade_cost = (old_trait_value + 1) * multiplier

        if old_trait_value == 0:
            upgrade_cost = get_trait_new_value(trait.name, category)

        if old_trait_value >= get_max_trait_value(trait.name, category):
            await present_embed(
                ctx,
                title=f"Error: {trait.name} at max value",
                description=f"**{trait.name}** is already at max value of `{old_trait_value}`",
                level="error",
                ephemeral=True,
            )
            return

        current_xp = character.owned_by.data.get(f"{campaign}_experience", 0)
        remaining_xp = current_xp - upgrade_cost
        new_trait_value = old_trait_value + 1
        new_experience = current_xp - upgrade_cost

        if remaining_xp < 0:
            await present_embed(
                ctx,
                title="Error: Not enough XP",
                description=f"**{trait.name}** upgrade cost is `{upgrade_cost}` xp.  You only have `{current_xp}` xp.",
                level="error",
                ephemeral=True,
            )
            return

        title = f"Upgrade `{trait.name}` from `{old_trait_value}` {p.plural_noun('dot', old_trait_value)} to `{new_trait_value}` {p.plural_noun('dot', new_trait_value)} for `{upgrade_cost}` xp"
        is_confirmed, confirmation_response_msg = await confirm_action(ctx, title, hidden=hidden)
        if not is_confirmed:
            return

        # Make the database updates
        character.set_trait_value(trait, new_trait_value)
        await self.bot.user_svc.update_or_add(
            ctx,
            user=character.owned_by,
            data={f"{campaign}_experience": new_experience},
        )

        await self.bot.guild_svc.send_to_audit_log(ctx, title)
        await confirmation_response_msg


def setup(bot: Valentina) -> None:
    """Add the cog to the bot."""
    bot.add_cog(Experience(bot))

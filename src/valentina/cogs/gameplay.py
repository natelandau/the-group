# mypy: disable-error-code="valid-type"
"""Gameplay cog for Valentina."""

import discord
from discord.commands import Option
from discord.ext import commands
from loguru import logger

from valentina import Valentina, char_svc, user_svc
from valentina.models.constants import MAX_OPTION_LIST_SIZE
from valentina.models.dicerolls import DiceRoll
from valentina.utils.errors import NoClaimError, TraitNotFoundError
from valentina.views import present_embed
from valentina.views.roll_display import RollDisplay


class Roll(commands.Cog):
    """Commands used during gameplay."""

    def __init__(self, bot: Valentina) -> None:
        self.bot = bot

    async def __trait_one_autocomplete(self, ctx: discord.ApplicationContext) -> list[str]:
        """Populates the autocomplete for the trait option."""
        try:
            character = char_svc.fetch_claim(ctx.interaction.guild.id, ctx.interaction.user.id)
        except NoClaimError:
            return ["No character claimed"]

        traits = []
        for trait in char_svc.fetch_all_character_traits(character, flat_list=True):
            if trait.lower().startswith(ctx.options["trait_one"].lower()):
                traits.append(trait)
            if len(traits) >= MAX_OPTION_LIST_SIZE:
                break
        return traits

    async def __trait_two_autocomplete(self, ctx: discord.ApplicationContext) -> list[str]:
        """Populates the autocomplete for the trait option."""
        try:
            character = char_svc.fetch_claim(ctx.interaction.guild.id, ctx.interaction.user.id)
        except NoClaimError:
            return ["No character claimed"]

        traits = []
        for trait in char_svc.fetch_all_character_traits(character, flat_list=True):
            if trait.lower().startswith(ctx.options["trait_two"].lower()):
                traits.append(trait)
            if len(traits) >= MAX_OPTION_LIST_SIZE:
                break
        return traits

    async def __macro_autocomplete(self, ctx: discord.ApplicationContext) -> list[str]:
        """Populate a select list with a users' macros."""
        macros = []
        for macro in user_svc.fetch_macros(ctx):
            if macro.name.lower().startswith(ctx.options["macro"].lower()):
                macros.append(f"{macro.name} ({macro.abbreviation})")
            if len(macros) >= MAX_OPTION_LIST_SIZE:
                break
        return macros

    roll = discord.SlashCommandGroup("roll", "Roll dice")

    @roll.command(description="Throw a roll of d10s.")
    async def throw(
        self,
        ctx: discord.ApplicationContext,
        pool: discord.Option(int, "The number of dice to roll", required=True),
        difficulty: Option(
            int,
            "The difficulty of the roll",
            required=True,
        ),
        comment: Option(str, "A comment to display with the roll", required=False, default=None),
    ) -> None:
        """Roll the dice.

        Args:
            comment (str, optional): A comment to display with the roll. Defaults to None.
            ctx (discord.ApplicationContext): The context of the command
            difficulty (int): The difficulty of the roll
            pool (int): The number of dice to roll
        """
        try:
            roll = DiceRoll(pool=pool, difficulty=difficulty, dice_size=10)
            logger.debug(f"ROLL: {ctx.author.display_name} rolled {roll.roll}")
            await RollDisplay(ctx, roll, comment).display()
        except ValueError as e:
            await ctx.respond(f"Error rolling dice: {e}", ephemeral=True)

    @roll.command(name="traits", description="Throw a roll based on trait names")
    @logger.catch
    async def traits(
        self,
        ctx: discord.ApplicationContext,
        trait_one: Option(
            str,
            description="First trait to roll",
            required=True,
            autocomplete=__trait_one_autocomplete,
        ),
        trait_two: Option(
            str,
            description="Second trait to roll",
            required=False,
            autocomplete=__trait_two_autocomplete,
            default=None,
        ),
        difficulty: Option(
            int,
            "The difficulty of the roll",
            required=False,
            default=6,
        ),
        comment: Option(str, "A comment to display with the roll", required=False, default=None),
    ) -> None:
        """Roll the total number of d10s for two given traits against a difficulty."""
        try:
            character = char_svc.fetch_claim(ctx.guild.id, ctx.user.id)
            trait_one_value = char_svc.fetch_trait_value(character, trait_one)
            trait_two_value = char_svc.fetch_trait_value(character, trait_two) if trait_two else 0
            pool = trait_one_value + trait_two_value

            roll = DiceRoll(pool=pool, difficulty=difficulty, dice_size=10)
            logger.debug(f"ROLL: {ctx.author.display_name} rolled {roll.roll}")
            await RollDisplay(
                ctx,
                roll=roll,
                comment=comment,
                trait_one_name=trait_one,
                trait_one_value=trait_one_value,
                trait_two_name=trait_two,
                trait_two_value=trait_two_value,
            ).display()

        except NoClaimError:
            await present_embed(
                ctx=ctx,
                title="Error: No character claimed",
                description="You must claim a character before you can update its bio.\nTo claim a character, use `/character claim`.",
                level="error",
                ephemeral=True,
            )
            return
        except TraitNotFoundError as e:
            await present_embed(
                ctx=ctx,
                title="Error: Trait not found",
                description=str(e),
                level="error",
                ephemeral=True,
            )
            return

    @roll.command(description="Simple dice roll of any size.")
    async def simple(
        self,
        ctx: discord.ApplicationContext,
        pool: discord.Option(int, "The number of dice to roll", required=True),
        dice_size: Option(int, "Number of sides on the dice.", required=True),
        comment: Option(str, "A comment to display with the roll", required=False, default=None),
    ) -> None:
        """Roll any type of dice.

        Args:
            comment (str, optional): A comment to display with the roll. Defaults to None.
            ctx (discord.ApplicationContext): The context of the command
            dice_size (int): The number of sides on the dice
            pool (int): The number of dice to roll
        """
        try:
            roll = DiceRoll(pool=pool, dice_size=dice_size, difficulty=0)
            logger.debug(f"ROLL: {ctx.author.display_name} rolled {roll.roll}")
            await RollDisplay(ctx, roll, comment).display()
        except ValueError as e:
            await ctx.respond(f"Error rolling dice: {e}", ephemeral=True)

    @roll.command(name="macro", description="Roll a macro")
    @logger.catch
    async def roll_macro(
        self,
        ctx: discord.ApplicationContext,
        macro: Option(
            str,
            description="Macro to roll",
            required=True,
            autocomplete=__macro_autocomplete,
        ),
        difficulty: Option(
            int,
            "The difficulty of the roll",
            required=False,
            default=6,
        ),
        comment: Option(str, "A comment to display with the roll", required=False, default=None),
    ) -> None:
        """Roll a macro."""
        m = user_svc.fetch_macro(ctx, macro.split("(")[0].strip())
        if not m:
            await ctx.respond(f"Macro {macro} not found", ephemeral=True)
            return
        try:
            character = char_svc.fetch_claim(ctx.guild.id, ctx.user.id)
            trait_one_value = char_svc.fetch_trait_value(character, m.trait_one)
            trait_two_value = (
                char_svc.fetch_trait_value(character, m.trait_two) if m.trait_two else 0
            )
            pool = trait_one_value + trait_two_value

            roll = DiceRoll(pool=pool, difficulty=difficulty, dice_size=10)
            logger.debug(f"ROLL: {ctx.author.display_name} macro {m.name} rolled {roll.roll}")
            await RollDisplay(
                ctx,
                roll=roll,
                comment=comment,
                trait_one_name=m.trait_one,
                trait_one_value=trait_one_value,
                trait_two_name=m.trait_two,
                trait_two_value=trait_two_value,
            ).display()

        except NoClaimError:
            await present_embed(
                ctx=ctx,
                title="Error: No character claimed",
                description="You must claim a character before you can update its bio.\nTo claim a character, use `/character claim`.",
                level="error",
                ephemeral=True,
            )
            return
        except TraitNotFoundError as e:
            await present_embed(
                ctx=ctx,
                title="Error: Trait not found",
                description=str(e),
                level="error",
                ephemeral=True,
            )
            return


def setup(bot: Valentina) -> None:
    """Add the cog to the bot."""
    bot.add_cog(Roll(bot))

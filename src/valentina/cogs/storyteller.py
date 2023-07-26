# mypy: disable-error-code="valid-type"
"""Commands for the storyteller."""
import discord
from discord.commands import Option
from discord.ext import commands
from loguru import logger
from peewee import fn

from valentina.models.bot import Valentina
from valentina.models.database import VampireClan
from valentina.utils.converters import ValidCharacterClass, ValidCharacterObject, ValidClan
from valentina.utils.helpers import fetch_random_name
from valentina.utils.options import (
    select_char_class,
    select_country,
    select_storyteller_character,
    select_vampire_clan,
)
from valentina.utils.storyteller import storyteller_character_traits
from valentina.views import ConfirmCancelButtons, present_embed
from valentina.views.character_sheet import sheet_embed, show_sheet


class StoryTeller(commands.Cog):
    """Commands for the storyteller."""

    def __init__(self, bot: Valentina) -> None:
        self.bot = bot

    async def cog_command_error(
        self, ctx: discord.ApplicationContext, error: discord.ApplicationCommandError | Exception
    ) -> None:
        """Handle exceptions and errors from the cog."""
        exceptions_to_ignore = [
            discord.ext.commands.errors.MissingAnyRole,
            discord.ext.commands.errors.MissingRole,
        ]

        if hasattr(error, "original"):
            error = error.original

        if type(error) not in exceptions_to_ignore:
            logger.exception(error)

        command_name = ""
        if ctx.command.parent and ctx.command.parent.name:
            command_name = f"{ctx.command.parent.name} "
        command_name += ctx.command.name

        await present_embed(
            ctx,
            title=f"Error running `{command_name}` command",
            description=str(error),
            level="error",
            ephemeral=True,
            delete_after=15,
        )

    storyteller = discord.SlashCommandGroup(
        "storyteller",
        "Commands for the storyteller",
        checks=[commands.has_any_role("Storyteller", "Admin").predicate],  # type: ignore [attr-defined]
    )

    @storyteller.command(name="new_character", description="Create a new character")
    async def create_story_char(
        self,
        ctx: discord.ApplicationContext,
        gender: Option(
            str,
            name="gender",
            description="The character's gender",
            choices=["male", "female"],
            required=True,
        ),
        char_class: Option(
            ValidCharacterClass,
            name="char_class",
            description="The character's class",
            autocomplete=select_char_class,
            required=True,
        ),
        level: Option(
            str,
            name="level",
            description="The character's level",
            required=True,
            choices=[
                "Weakling",
                "Average",
                "Strong",
                "Super",
            ],
        ),
        specialty: Option(
            str,
            name="specialty",
            description="The character's specialty",
            required=True,
            choices=["No Specialty", "Fighter", "Thinker", "Leader"],
            default="No Specialty",
        ),
        name_type: Option(
            str,
            name="name_type",
            description="The character's name type",
            autocomplete=select_country,
            default="us",
        ),
        vampire_clan: Option(
            ValidClan,
            name="vampire_clan",
            description="The character's clan (only for vampires)",
            autocomplete=select_vampire_clan,
            required=False,
            default=None,
        ),
    ) -> None:
        """Test command."""
        first_name, last_name = await fetch_random_name(gender=gender, country=name_type)

        if char_class.name.lower() == "vampire" and not vampire_clan:
            vampire_clan = VampireClan.select().order_by(fn.Random()).limit(1)[0]

        character = self.bot.char_svc.create_character(
            ctx,
            first_name=first_name,
            last_name=last_name,
            nickname=char_class.name,
            char_class=char_class,
            clan=vampire_clan,
            storyteller_character=True,
        )

        fetched_traits = self.bot.trait_svc.fetch_all_class_traits(char_class.name)
        trait_values = storyteller_character_traits(
            fetched_traits,
            level=level,
            specialty=specialty,
            clan=vampire_clan.name if vampire_clan else None,
        )

        self.bot.char_svc.update_traits_by_id(ctx, character, trait_values)

        # Confirm character creation
        view = ConfirmCancelButtons(ctx.author)
        embed = await sheet_embed(ctx, character, title=f"Confirm creation of {character.name}")
        msg = await ctx.respond(embed=embed, view=view, ephemeral=True)

        await view.wait()
        if not view.confirmed:
            character.delete_instance(delete_nullable=True, recursive=True)

            await msg.edit_original_response(  # type: ignore [union-attr]
                embed=discord.Embed(
                    title=f"{character.name} discarded",
                    color=discord.Color.red(),
                ),
            )
            return

        await msg.edit_original_response(  # type: ignore [union-attr]
            embed=discord.Embed(
                title=f"{character.name} saved",
                color=discord.Color.green(),
            ),
        )

    @storyteller.command(name="list_characters", description="List all characters")
    async def list_characters(
        self,
        ctx: discord.ApplicationContext,
    ) -> None:
        """List all storyteller characters."""
        characters = self.bot.char_svc.fetch_all_storyteller_characters(ctx=ctx)

        if len(characters) == 0:
            await present_embed(
                ctx,
                title="No Storyteller Characters",
                description="There are no characters.\nCreate one with `/storyteller new_character`",
                level="error",
            )
            return

        fields = []
        plural = "s" if len(characters) > 1 else ""
        description = f"**{len(characters)}** character{plural} on this server\n\u200b"

        for character in sorted(characters, key=lambda x: x.name):
            fields.append((character.name, ""))

        await present_embed(
            ctx=ctx,
            title="List of characters",
            description=description,
            fields=fields,
            inline_fields=False,
            level="info",
        )

    @storyteller.command(name="sheet", description="View a character sheet")
    async def view_character_sheet(
        self,
        ctx: discord.ApplicationContext,
        character: Option(
            ValidCharacterObject,
            description="The character to view",
            autocomplete=select_storyteller_character,
            required=True,
        ),
    ) -> None:
        """View a character sheet for a storyteller character."""
        await show_sheet(ctx, character=character, claimed_by=None)


def setup(bot: Valentina) -> None:
    """Add the cog to the bot."""
    bot.add_cog(StoryTeller(bot))
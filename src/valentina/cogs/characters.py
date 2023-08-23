# mypy: disable-error-code="valid-type"
"""Gameplay cog for Valentina."""

import discord
from discord.commands import Option
from discord.ext import commands
from loguru import logger

from valentina.constants import EmbedColor
from valentina.models.bot import Valentina
from valentina.utils import errors
from valentina.utils.cogs import confirm_action
from valentina.utils.converters import (
    ValidCharacterClass,
    ValidCharacterName,
    ValidCharacterObject,
    ValidCharTrait,
    ValidClan,
    ValidCustomSection,
    ValidCustomTrait,
    ValidTraitCategory,
    ValidYYYYMMDD,
)
from valentina.utils.options import (
    select_char_class,
    select_char_trait,
    select_custom_section,
    select_custom_trait,
    select_player_character,
    select_trait_category,
    select_vampire_clan,
)
from valentina.views import (
    BioModal,
    CharGenWizard,
    CustomSectionModal,
    ProfileModal,
    present_embed,
    show_sheet,
)


class Characters(commands.Cog, name="Character"):
    """Create, manage, update, and claim characters."""

    def __init__(self, bot: Valentina) -> None:
        self.bot = bot

    chars = discord.SlashCommandGroup("character", "Work with characters")
    update = chars.create_subgroup("update", "Make edits to character information")
    add = chars.create_subgroup("add", "Add new information to characters")
    delete = chars.create_subgroup("delete", "Delete information from characters")

    @chars.command(name="create", description="Create a new character")
    async def create_character(
        self,
        ctx: discord.ApplicationContext,
        char_class: Option(
            ValidCharacterClass,
            name="char_class",
            description="The character's class",
            autocomplete=select_char_class,
            required=True,
        ),
        first_name: Option(ValidCharacterName, "Character's name", required=True),
        last_name: Option(ValidCharacterName, "Character's last name", required=True),
        nickname: Option(ValidCharacterName, "Character's nickname", required=False, default=None),
        vampire_clan: Option(
            ValidClan,
            name="vampire_clan",
            description="The character's clan (only for vampires)",
            autocomplete=select_vampire_clan,
            required=False,
            default=None,
        ),
    ) -> None:
        """Create a new character.

        Args:
            char_class (CharacterClass): The character's class
            ctx (discord.ApplicationContext): The context of the command
            first_name (str): The character's first name
            last_name (str, optional): The character's last name. Defaults to None.
            nickname (str, optional): The character's nickname. Defaults to None.
            vampire_clan (VampireClan, optional): The character's vampire clan. Defaults to None.
        """
        # Ensure the user is in the database
        self.bot.user_svc.fetch_user(ctx)

        # Require a clan for vampires
        if char_class.name.lower() == "vampire" and not vampire_clan:
            await present_embed(
                ctx,
                title="Vampire clan required",
                description="Please select a vampire clan",
                level="error",
            )
            return

        # Fetch all traits and set them
        fetched_traits = self.bot.trait_svc.fetch_all_class_traits(char_class.name)

        wizard = CharGenWizard(
            ctx,
            fetched_traits,
            first_name=first_name,
            last_name=last_name,
            nickname=nickname,
        )
        await wizard.begin_chargen()
        trait_values_from_chargen = await wizard.wait_until_done()

        # Create the character and traits in the db
        data: dict[str, str | int | bool] = {
            "first_name": first_name,
            "last_name": last_name,
            "nickname": nickname,
            "player_character": True,
        }

        character = self.bot.char_svc.update_or_add(
            ctx,
            data=data,
            char_class=char_class,
            clan=vampire_clan,
        )

        for trait, value in trait_values_from_chargen:
            character.set_trait_value(trait, value)

        await self.bot.guild_svc.send_to_audit_log(
            ctx, f"Created player character: `{character.full_name}` as a `{char_class.name}`"
        )
        logger.info(f"CHARACTER: Create character {character}")

    @chars.command(name="sheet", description="View a character sheet")
    async def view_character_sheet(
        self,
        ctx: discord.ApplicationContext,
        character: Option(
            ValidCharacterObject,
            description="The character to view",
            autocomplete=select_player_character,
            required=True,
        ),
        hidden: Option(
            bool,
            description="Make the sheet only visible to you (default true).",
            default=True,
        ),
    ) -> None:
        """Displays a character sheet in the channel."""
        if self.bot.char_svc.is_char_claimed(ctx.guild.id, character.id):
            user_id_num = self.bot.char_svc.fetch_user_of_character(ctx.guild.id, character.id)
            claimed_by = self.bot.get_user(user_id_num)
        else:
            claimed_by = None

        await show_sheet(ctx, character=character, claimed_by=claimed_by, ephemeral=hidden)

    @chars.command(name="claim")
    async def claim_character(
        self,
        ctx: discord.ApplicationContext,
        character: Option(
            ValidCharacterObject,
            description="The character to claim",
            autocomplete=select_player_character,
            required=True,
            name="character",
        ),
    ) -> None:
        """Claim a character to your user. Allows rolling with traits, editing the character, etc."""
        self.bot.char_svc.add_claim(ctx.guild.id, character.id, ctx.user.id)

        logger.info(f"CLAIM: {character.name} claimed by {ctx.author.name}")
        await present_embed(
            ctx=ctx,
            title="Character Claimed",
            description=f"**{character.name}** has been claimed by **{ctx.author.display_name}**",
            level="success",
        )

    @chars.command(name="unclaim")
    async def unclaim_character(
        self,
        ctx: discord.ApplicationContext,
    ) -> None:
        """Unclaim currently claimed character. Allows claiming a new character."""
        if self.bot.char_svc.user_has_claim(ctx):
            character = self.bot.char_svc.fetch_claim(ctx)
            self.bot.char_svc.remove_claim(ctx.guild.id, ctx.author.id)
            await present_embed(
                ctx=ctx,
                title="Character Unclaimed",
                description=f"**{character.name}** unclaimed by **{ctx.author.display_name}**",
                level="success",
            )
        else:
            await present_embed(
                ctx=ctx,
                title="You have no character claimed",
                description="To claim a character, use `/character claim`.",
                level="error",
                ephemeral=True,
            )

    @chars.command(name="list", description="List all characters")
    async def list_characters(
        self,
        ctx: discord.ApplicationContext,
        hidden: Option(
            bool,
            description="Make the list only visible to you (default true).",
            default=True,
        ),
    ) -> None:
        """List all player characters in this guild."""
        characters = self.bot.char_svc.fetch_all_player_characters(ctx.guild.id)
        if len(characters) == 0:
            await present_embed(
                ctx,
                title="No Characters",
                description="There are no characters.\nCreate one with `/character create`",
                level="error",
                ephemeral=hidden,
            )
            return

        fields = []
        plural = "s" if len(characters) > 1 else ""
        description = f"**{len(characters)}** character{plural} on this server\n\u200b"

        for character in sorted(characters, key=lambda x: x.name):
            user_id = self.bot.char_svc.fetch_user_of_character(ctx.guild.id, character.id)
            user = self.bot.get_user(user_id).display_name if user_id else ""
            fields.append(
                (character.name, f"Class: {character.char_class.name}\nClaimed by: {user}")
            )

        await present_embed(
            ctx=ctx,
            title="List of characters",
            description=description,
            fields=fields,
            inline_fields=False,
            level="info",
        )

    ### ADD COMMANDS ####################################################################

    @add.command(name="date_of_birth")
    async def date_of_birth(
        self,
        ctx: discord.ApplicationContext,
        dob: Option(ValidYYYYMMDD, description="DOB in the format of YYYY-MM-DD", required=True),
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Set the DOB of a character."""
        character = self.bot.char_svc.fetch_claim(ctx)

        self.bot.char_svc.update_or_add(ctx, character=character, data={"date_of_birth": dob})

        await self.bot.guild_svc.send_to_audit_log(
            ctx, f"`{character.name}` DOB set to `{dob:%Y-%m-%d}`"
        )
        await present_embed(
            ctx,
            title="Date of Birth Updated",
            description=f"`{character.name}` DOB set to `{dob:%Y-%m-%d}`",
            level="success",
            ephemeral=hidden,
        )

    @add.command(name="trait", description="Add a custom trait to a character")
    async def add_custom_trait(
        self,
        ctx: discord.ApplicationContext,
        name: Option(str, "Name of of trait to add.", required=True),
        category: Option(
            ValidTraitCategory,
            name="category",
            description="The category to add the trait to",
            required=True,
            autocomplete=select_trait_category,
        ),
        value: Option(int, "The value of the trait", required=True, min_value=0, max_value=20),
        max_value: Option(
            int,
            "The maximum value of the trait (Defaults to 5)",
            required=False,
            min_value=1,
            max_value=20,
            default=5,
        ),
        description: Option(str, "A description of the trait", required=False),
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Add a custom trait to a character."""
        character = self.bot.char_svc.fetch_claim(ctx)

        title = f"Create custom trait: `{name.title()}` at `{value}` dots for {character.full_name}"
        confirmed, msg = await confirm_action(ctx, title, hidden=hidden)

        if not confirmed:
            return

        ###############################################33

        character.add_custom_trait(
            name=name,
            category=category,
            value=value,
            max_value=max_value,
            description=description,
        )

        await self.bot.guild_svc.send_to_audit_log(ctx, title)
        await msg.edit_original_response(
            embed=discord.Embed(title=title, color=EmbedColor.SUCCESS.value), view=None
        )

    @add.command(name="custom_section", description="Add a custom section to the character sheet")
    async def add_custom_section(
        self,
        ctx: discord.ApplicationContext,
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Add a custom section to the character sheet."""
        character = self.bot.char_svc.fetch_claim(ctx)

        modal = CustomSectionModal(title=f"Custom section for {character.name}")
        await ctx.send_modal(modal)
        await modal.wait()

        section_title = modal.section_title.strip().title()
        section_description = modal.section_description.strip()

        existing_sections = character.custom_sections
        if section_title.replace("-", "_").replace(" ", "_").lower() in [
            x.title.replace("-", "_").replace(" ", "_").lower() for x in existing_sections
        ]:
            raise errors.ValidationError("Custom section already exists")

        self.bot.char_svc.custom_section_update_or_add(
            ctx, character, section_title, section_description
        )

        await self.bot.guild_svc.send_to_audit_log(
            ctx, f"Add section `{section_title}` to `{character.name}`"
        )

        await present_embed(
            ctx,
            f"Add section `{section_title}` to `{character.name}`",
            description=f"**{section_title}**\n{section_description}",
            ephemeral=hidden,
            level="success",
        )

    ### UPDATE COMMANDS ####################################################################
    @update.command(name="bio", description="Add or update a character's bio")
    async def update_bio(
        self,
        ctx: discord.ApplicationContext,
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Update a character's bio."""
        character = self.bot.char_svc.fetch_claim(ctx)

        modal = BioModal(
            title=f"Enter the biography for {character.name}", current_bio=character.bio
        )
        await ctx.send_modal(modal)
        await modal.wait()
        biography = modal.bio.strip()

        self.bot.char_svc.update_or_add(ctx, character=character, data={"bio": biography})

        await self.bot.guild_svc.send_to_audit_log(ctx, f"Update biography for `{character.name}`")

        await present_embed(
            ctx,
            title=f"Update biography for `{character.name}`",
            description=f"**Biography**\n{biography}",
            level="success",
            ephemeral=hidden,
        )

    @update.command(name="custom_section", description="Update a custom section")
    async def update_custom_section(
        self,
        ctx: discord.ApplicationContext,
        custom_section: Option(
            ValidCustomSection,
            description="Custom section to update",
            required=True,
            autocomplete=select_custom_section,
        ),
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Update a custom section."""
        character = self.bot.char_svc.fetch_claim(ctx)

        modal = CustomSectionModal(
            section_title=custom_section.title,
            section_description=custom_section.description,
            title=f"Custom section for {character.name}",
        )
        await ctx.send_modal(modal)
        await modal.wait()

        section_title = modal.section_title.strip().title()
        section_description = modal.section_description.strip()

        self.bot.char_service.custom_section_update_or_add(
            ctx,
            character,
            section_title=section_description,
            section_description=section_description,
        )

        await self.bot.guild_svc.send_to_audit_log(
            ctx, f"Update section `{section_title}` for `{character.name}`"
        )

        await present_embed(
            ctx,
            title=f"Update section `{section_title}` for `{character.name}`",
            description=f"**{section_title}**\n{section_description}",
            ephemeral=hidden,
            level="success",
        )

    @chars.command(name="profile", description="Update a character's profile")
    async def update_profile(
        self,
        ctx: discord.ApplicationContext,
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Update a character's profile."""
        character = self.bot.char_svc.fetch_claim(ctx)

        modal = ProfileModal(title=f"Profile for {character}", character=character)
        await ctx.send_modal(modal)
        await modal.wait()
        if modal.confirmed:
            update_data: dict = {}
            for k, v in modal.results.items():
                if v:
                    update_data[k] = v

            self.bot.char_svc.update_or_add(ctx, character=character, data=update_data)

            await self.bot.guild_svc.send_to_audit_log(
                ctx, f"Update profile for `{character.name}`"
            )

            await present_embed(
                ctx,
                title=f"Update profile for `{character.name}`",
                level="success",
                ephemeral=hidden,
            )

    @update.command(name="trait", description="Update the value of a trait for a character")
    async def update_trait(
        self,
        ctx: discord.ApplicationContext,
        trait: Option(
            ValidCharTrait,
            description="Trait to update",
            required=True,
            autocomplete=select_char_trait,
        ),
        new_value: Option(
            int, description="New value for the trait", required=True, min_value=0, max_value=20
        ),
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Update the value of a trait."""
        character = self.bot.char_svc.fetch_claim(ctx)

        if not self.bot.user_svc.has_trait_permissions(ctx, character):
            await present_embed(
                ctx,
                title="Permission error",
                description="You do not have permissions to update traits on this character\nSpeak to an administrator",
                level="error",
                ephemeral=True,
                delete_after=30,
            )
            return

        old_value = character.get_trait_value(trait)

        title = (
            f"Update `{trait.name}` from `{old_value}` to `{new_value}` for `{character.full_name}`"
        )
        confirmed, msg = await confirm_action(ctx, title, hidden=hidden)

        if not confirmed:
            return

        character.set_trait_value(trait, new_value)

        await self.bot.guild_svc.send_to_audit_log(ctx, title)
        await msg.edit_original_response(
            embed=discord.Embed(title=title, color=EmbedColor.SUCCESS.value), view=None
        )

    ### DELETE COMMANDS ####################################################################
    @delete.command(name="trait", description="Delete a custom trait from a character")
    async def delete_custom_trait(
        self,
        ctx: discord.ApplicationContext,
        trait: Option(
            ValidCustomTrait,
            description="Trait to delete",
            required=True,
            autocomplete=select_custom_trait,
        ),
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Delete a custom trait from a character."""
        character = self.bot.char_svc.fetch_claim(ctx)

        title = f"Delete custom trait `{trait.name}` from `{character.name}`"
        confirmed, msg = await confirm_action(ctx, title, hidden=hidden)

        if not confirmed:
            return

        trait.delete_instance()

        await self.bot.guild_svc.send_to_audit_log(ctx, title)
        await msg.edit_original_response(
            embed=discord.Embed(title=title, color=EmbedColor.SUCCESS.value), view=None
        )

    @delete.command(name="custom_section", description="Delete a custom section from a character")
    async def delete_custom_section(
        self,
        ctx: discord.ApplicationContext,
        custom_section: Option(
            ValidCustomSection,
            description="Custom section to delete",
            required=True,
            autocomplete=select_custom_section,
        ),
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Delete a custom trait from a character."""
        character = self.bot.char_svc.fetch_claim(ctx)

        title = f"Delete section `{custom_section.title}` from `{character.full_name}`"
        confirmed, msg = await confirm_action(ctx, title, hidden=hidden)

        if not confirmed:
            return

        custom_section.delete_instance()
        await self.bot.guild_svc.send_to_audit_log(ctx, title)
        await msg.edit_original_response(
            embed=discord.Embed(title=title, color=EmbedColor.SUCCESS.value), view=None
        )


def setup(bot: Valentina) -> None:
    """Add the cog to the bot."""
    bot.add_cog(Characters(bot))

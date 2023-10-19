"""View a character sheet."""
from typing import Any, cast

import arrow
import discord
from discord.ext import pages

from valentina.constants import (
    MAX_DOT_DISPLAY,
    CharClassType,
    CharSheetSection,
    EmbedColor,
    Emoji,
    TraitCategories,
)
from valentina.models.aws import AWSService
from valentina.models.mongo_collections import Character, CharacterTrait
from valentina.models.statistics import Statistics
from valentina.utils import errors


def __embed1(  # noqa: C901
    ctx: discord.ApplicationContext,
    character: Character,
    owned_by_user: discord.User | None = None,
    title: str | None = None,
    desc_prefix: str | None = None,
    desc_suffix: str | None = None,
    show_footer: bool = True,
) -> discord.Embed:
    """Builds the first embed of a character sheet. This embed contains the character's name, class, experience, cool points, and attributes and abilities."""
    modified = arrow.get(character.date_modified).humanize()

    if title is None:
        title = character.full_name

    embed = discord.Embed(title=title, description=desc_prefix, color=EmbedColor.INFO.value)

    if show_footer:
        footer = f"Owned by: {owned_by_user.display_name} • " if owned_by_user else ""
        footer += f"Last updated: {modified}"
        embed.set_footer(text=footer)

    # FIXME: This needs to be migrated to mongodb
    # try:
    #     campaign = ctx.bot.campaign_svc.fetch_active(ctx)  # type: ignore [attr-defined] # it exists
    #     if campaign.current_date and character.data.get("date_of_birth"):
    #         age = arrow.get(campaign.current_date) - arrow.get(character.data["date_of_birth"])
    #         embed.add_field(name="Age", value=f"`{age.days // 365}`", inline=True)
    # except errors.NoActiveCampaignError:
    #     pass

    embed.add_field(
        name="Alive",
        value=Emoji.ALIVE.value if character.is_alive else Emoji.DEAD.value,
    )

    embed.add_field(
        name="Class",
        value=character.char_class_name.title() if character.char_class_name else "-",
        inline=True,
    )

    embed.add_field(
        name="Concept",
        value=character.concept_name.title() if character.concept_name else "-",
        inline=True,
    )

    if character.char_class == CharClassType.HUNTER:
        embed.add_field(
            name="Creed",
            value=character.creed_name.title() if character.creed_name else "-",
            inline=True,
        )

    if character.char_class == CharClassType.VAMPIRE:
        embed.add_field(name="Clan", value=character.clan.name, inline=True)
        embed.add_field(
            name="Generation",
            value=character.generation.title() if character.generation else "-",
            inline=True,
        )
        embed.add_field(
            name="Sire", value=character.sire.title() if character.sire else "-", inline=True
        )

    if character.char_class == CharClassType.MAGE:
        embed.add_field(
            name="Tradition",
            value=character.tradition.title() if character.tradition else "-",
            inline=True,
        )
        embed.add_field(
            name="Essence",
            value=character.essence.title() if character.essence else "-",
            inline=True,
        )

    if character.char_class == CharClassType.WEREWOLF:
        embed.add_field(
            name="Tribe", value=character.tribe.title() if character.tribe else "-", inline=True
        )
        embed.add_field(
            name="Auspice",
            value=character.auspice.title() if character.auspice else "-",
            inline=True,
        )
        embed.add_field(
            name="Breed", value=character.breed.title() if character.breed else "-", inline=True
        )

    # Add the trait sections to the sheet
    for section in sorted(CharSheetSection, key=lambda x: x.value["order"]):
        if section != CharSheetSection.NONE:
            embed.add_field(
                name="\u200b",
                value=f"**{section.name.upper()}**",
                inline=False,
            )

        for cat in sorted(
            [x for x in TraitCategories if x.value["section"] == section],
            key=lambda x: x.value["order"],
        ):
            trait_values = [
                f"`{x.name:14}: {x.dots}`"
                if x.value <= MAX_DOT_DISPLAY
                else f"`{x.name:14}: {x.value}/{x.max_value}`"
                for x in cast(list[CharacterTrait], character.traits)
                if x.category_name == cat.name and not (cat.value["show_zero"] and x.value == 0)
            ]
            if trait_values:
                embed.add_field(name=cat.name.title(), value="\n".join(trait_values), inline=True)

    if desc_suffix:
        embed.add_field(name="\u200b", value=desc_suffix, inline=False)

    return embed


def __embed2(
    ctx: discord.ApplicationContext,
    character: Character,
    owned_by_user: discord.User | None = None,
    title: str | None = None,
    show_footer: bool = True,
) -> discord.Embed:
    """Builds the second embed of a character sheet. This embed contains the character's bio and custom sections."""
    custom_sections = character.sheet_sections
    modified = arrow.get(character.date_modified).humanize()

    if title is None:
        title = f"{character.full_name} - Page 2"

    embed = discord.Embed(title=title, description="", color=EmbedColor.INFO.value)

    if show_footer:
        footer = f"Owned by: {owned_by_user.display_name} • " if owned_by_user else ""
        footer += f"Last updated: {modified}"
        embed.set_footer(text=footer)

    if character.bio:
        embed.add_field(name="**BIOGRAPHY**", value=character.bio, inline=False)

    if len(custom_sections) > 0:
        embed.add_field(name="\u200b", value="**CUSTOM SECTIONS**", inline=False)
        for section in custom_sections:
            embed.add_field(
                name=f"__**{section.title.title()}**__", value=section.content, inline=True
            )

    # # stats = Statistics(ctx, character=character)
    # embed.add_field(
    #     name="\u200b", value=f"**ROLL STATISTICS**{stats.get_text(with_title=False)}", inline=False
    # )

    return embed


def __image_embed(
    character: Character,
    image_key: str,
    owned_by_user: discord.User | None = None,
    title: str | None = None,
    show_footer: bool = True,
) -> discord.Embed:
    """Builds the second embed of a character sheet. This embed contains the character's bio and custom sections."""
    modified = arrow.get(character.date_modified).humanize()

    if title is None:
        title = f"{character.full_name} - Images"

    embed = discord.Embed(title=title, description="", color=0x7777FF)

    if show_footer:
        footer = f"Owned by: {owned_by_user.display_name} • " if owned_by_user else ""
        footer += f"Last updated: {modified}"
        embed.set_footer(text=footer)

    aws_svc = AWSService()
    image_url = aws_svc.get_url(image_key)
    embed.set_image(url=image_url)

    return embed


async def show_sheet(
    ctx: discord.ApplicationContext,
    character: Character,
    ephemeral: Any = False,
    show_footer: bool = True,
) -> Any:
    """Show a character sheet."""
    owned_by_user = discord.utils.get(ctx.bot.users, id=character.user_owner.id)  # type: ignore [attr-defined] # it exists

    embeds = []
    embeds.extend(
        [
            __embed1(ctx, character, owned_by_user, show_footer=show_footer),
            __embed2(ctx, character, owned_by_user, show_footer=show_footer),
        ]
    )

    if character.images:
        embeds.extend(
            [
                __image_embed(character, image_key, owned_by_user, show_footer=show_footer)
                for image_key in character.images
            ]
        )

    paginator = pages.Paginator(pages=embeds)  # type: ignore [arg-type]
    paginator.remove_button("first")
    paginator.remove_button("last")
    await paginator.respond(ctx.interaction, ephemeral=ephemeral)


async def sheet_embed(
    ctx: discord.ApplicationContext,
    character: Character,
    owned_by_user: discord.User | None = None,
    title: str | None = None,
    desc_prefix: str | None = None,
    desc_suffix: str | None = None,
    show_footer: bool = True,
) -> discord.Embed:
    """Return the first page of the sheet as an embed."""
    owned_by_user = discord.utils.get(ctx.bot.users, id=character.user_owner.id)  # type: ignore [attr-defined] # it exists
    return __embed1(
        ctx,
        character,
        owned_by_user=owned_by_user,
        title=title,
        desc_prefix=desc_prefix,
        desc_suffix=desc_suffix,
        show_footer=show_footer,
    )

# mypy: disable-error-code="valid-type"
"""Miscellaneous commands."""
import random

import arrow
import discord
import inflect
import semver
from discord.commands import Option
from discord.ext import commands

from valentina.constants import DiceType, EmbedColor, RollResultType
from valentina.models import Probability, Statistics
from valentina.models.bot import Valentina, ValentinaContext
from valentina.models.mongo_collections import Character, Guild, User
from valentina.utils.changelog_parser import ChangelogParser
from valentina.utils.converters import ValidImageURL
from valentina.utils.helpers import fetch_random_name
from valentina.utils.options import (
    select_changelog_version_1,
    select_changelog_version_2,
    select_country,
)
from valentina.views import confirm_action

p = inflect.engine()


class Misc(commands.Cog):
    """Miscellaneous commands."""

    def __init__(self, bot: Valentina) -> None:
        self.bot: Valentina = bot

    @commands.slash_command(name="server_info", description="View information about the server")
    async def server_info(
        self,
        ctx: ValentinaContext,
        hidden: Option(
            bool,
            description="Make the probability only visible to you (default False)",
            default=False,
        ),
    ) -> None:
        """View information about the server."""
        # Load db objects
        guild = await Guild.get(ctx.guild.id)

        # Compute data
        created_on = arrow.get(ctx.guild.created_at)
        player_characters = await Character.find(
            Character.guild == ctx.guild.id,
            Character.type_player == True,  # noqa: E712
        ).count()
        storyteller_characters = await Character.find(
            Character.guild == ctx.guild.id,
            Character.type_storyteller == True,  # noqa: E712
        ).count()
        num_campaigns = len(guild.campaigns)
        active_campaign = await ctx.fetch_active_campaign(raise_error=False)
        roll_stats = Statistics(ctx)

        # Build the Embed
        embed = discord.Embed(
            description=f"## {ctx.guild.name} Information", color=EmbedColor.INFO.value
        )
        embed.add_field(
            name="",
            value=f"""\
```scala
Created: {created_on.humanize()} ({created_on.format('YYYY-MM-DD')})
Owner  : {ctx.guild.owner.display_name}
Members: {ctx.guild.member_count}
Roles  : {', '.join([f'@{x.name}' if not x.name.startswith('@') else x.name for x in ctx.guild.roles if not x.is_bot_managed() and not x.is_integration() and not x.is_default()][::-1])}
```
""",
            inline=False,
        )

        embed.add_field(
            name="Campaigns",
            value=f"""\
```scala
Total Campaigns: {num_campaigns}
Active Campaign: {active_campaign.name if active_campaign else 'None'}
```
""",
            inline=True,
        )

        embed.add_field(
            name="Characters",
            value=f"""\
```scala
Total Characters      : {player_characters + storyteller_characters}
Player Characters     : {player_characters}
Storyteller Characters: {storyteller_characters}
```
""",
            inline=True,
        )

        embed.add_field(
            name="Roll Statistics",
            value=await roll_stats.guild_statistics(
                as_embed=False, with_title=False, with_help=True  # type: ignore [arg-type]
            ),
            inline=False,
        )
        embed.set_footer(
            text=f"Requested by {ctx.author}",
            icon_url=ctx.author.display_avatar.url,
        )
        await ctx.respond(embed=embed, ephemeral=hidden)

    @commands.slash_command(description="View roll statistics")
    async def statistics(
        self,
        ctx: ValentinaContext,
        member: Option(discord.Member, required=False),
        hidden: Option(
            bool,
            description="Make the statistics only visible to you (default true).",
            default=True,
        ),
    ) -> None:
        """Display roll statistics for the guild or a specific user."""
        stats = Statistics(ctx)
        if member:
            embed = await stats.user_statistics(member, as_embed=True)
        else:
            embed = await stats.guild_statistics(as_embed=True)

        await ctx.respond(embed=embed, ephemeral=hidden)

    @commands.slash_command(name="probability", description="Calculate the probability of a roll")
    async def probability(
        self,
        ctx: ValentinaContext,
        pool: discord.Option(int, "The number of dice to roll", required=True),
        difficulty: Option(
            int,
            "The difficulty of the roll",
            required=True,
        ),
        hidden: Option(
            bool,
            description="Make the probability only visible to you (default False)",
            default=False,
        ),
    ) -> None:
        """Roll the dice.

        Args:
            hidden (bool, optional): Make the statistics only visible to you (default true). Defaults to True.
            ctx (ValentinaContext): The context of the command
            difficulty (int): The difficulty of the roll
            pool (int): The number of dice to roll
        """
        probabilities = Probability(
            ctx, pool=pool, difficulty=difficulty, dice_size=DiceType.D10.value
        )
        embed = await probabilities.get_embed()
        await ctx.respond(embed=embed, ephemeral=hidden)

    @commands.slash_command(name="user_info", description="View information about a user")
    async def user_info(
        self,
        ctx: ValentinaContext,
        user: Option(
            discord.User,
            description="The user to view information for",
            required=False,
        ),
        hidden: Option(
            bool,
            description="Make the response only visible to you (default False).",
            default=False,
        ),
    ) -> None:
        """View information about a user."""
        target = user or ctx.author
        db_user = await User.get(target.id, fetch_links=True)
        active_campaign = await ctx.fetch_active_campaign(raise_error=False)
        # Variables for embed
        num_characters = len([x for x in db_user.characters if x.type_player])
        num_macros = len(db_user.macros)

        roles = (
            ", ".join(
                f"@{r.name}" if not r.name.startswith("@") else r.name
                for r in target.roles[::-1][:-1]
                if not r.is_integration()
            )
            or "No roles"
        )
        stats_engine = Statistics(ctx)
        campaign_xp, campaign_total_xp, campaign_cp = db_user.fetch_campaign_xp(active_campaign)
        lifetime_xp = db_user.lifetime_experience
        lifetime_cp = db_user.lifetime_cool_points

        # Build the Embed
        embed = discord.Embed(
            title="",
            description=f"# {target.display_name}",
            color=EmbedColor.INFO.value,
        )
        embed.add_field(
            name="",
            value=f"""\
```scala
Account Created: {arrow.get(target.created_at).humanize()} ({arrow.get(target.created_at).format('YYYY-MM-DD')})
Joined Server  : {arrow.get(target.joined_at).humanize()} ({arrow.get(target.joined_at).format('YYYY-MM-DD')})
Roles: {roles}
```
""",
            inline=False,
        )
        embed.add_field(
            name="Experience",
            value=f"""\
```scala
Lifetime Experience : {lifetime_xp}
Lifetime Cool Points: {lifetime_cp}

"{active_campaign.name}" (active campaign)
Available Experience: {campaign_xp}
Total Earned        : {campaign_total_xp}
Cool Points         : {campaign_cp}
```
""",
            inline=False,
        )
        embed.add_field(
            name="Gameplay",
            value=f"""\
```scala
Player Characters: {num_characters}
Roll Macros      : {num_macros}
```
""",
            inline=False,
        )
        embed.add_field(
            name="Roll Statistics",
            value=await stats_engine.user_statistics(  # type: ignore [arg-type]
                target, as_embed=False, with_title=False, with_help=False
            ),
            inline=False,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(
            text=f"Requested by {ctx.author}",
            icon_url=ctx.author.display_avatar.url,
        )
        embed.timestamp = discord.utils.utcnow()

        # Send the embed
        await ctx.respond(embed=embed, ephemeral=hidden)

    @commands.slash_command(name="changelog", description="Display the bot's changelog")
    async def post_changelog(
        self,
        ctx: ValentinaContext,
        oldest_version: Option(str, autocomplete=select_changelog_version_1, required=True),
        newest_version: Option(str, autocomplete=select_changelog_version_2, required=True),
        hidden: Option(
            bool,
            description="Make the response only visible to you (default true).",
            default=True,
        ),
    ) -> None:
        """Post the changelog."""
        if semver.compare(oldest_version, newest_version) > 0:
            msg = (
                f"Oldest version `{oldest_version}` is newer than newest version `{newest_version}`"
            )
            raise commands.BadArgument(msg)

        changelog = ChangelogParser(self.bot, oldest_version, newest_version)
        embed = changelog.get_embed()
        await ctx.respond(embed=embed, ephemeral=hidden)

    @commands.slash_command(name="coinflip", help="Flip a coin")
    async def coinflip(self, ctx: ValentinaContext) -> None:
        """Coinflip!"""
        coin_sides = ["Heads", "Tails"]
        await ctx.respond(
            f"**{ctx.author.name}** flipped a coin and got **{random.choice(coin_sides)}**!"
        )

    @commands.slash_command(name="name_generator", help="Generate a random name")
    async def name_gen(
        self,
        ctx: ValentinaContext,
        gender: Option(
            str,
            name="gender",
            description="The character's gender",
            choices=["male", "female"],
            required=True,
        ),
        country: Option(
            str,
            name="country",
            description="The country for the character's name (default 'US')",
            autocomplete=select_country,
            default="en-GB,en-US",
        ),
        number: Option(
            int, name="number", description="The number of names to generate (default 5)", default=5
        ),
    ) -> None:
        """Generate a random name."""
        # import re

        # from faker import Faker

        # locale = country.split(",")

        # fake = Faker(locale)

        # name_list = []
        # for _i in range(number):
        #     if gender == "male":
        #         if "zh-CN" in locale or "ja-JP" in locale:
        #             name = fake.romanized_name()
        #         else:
        #             name = fake.name_male()

        #     if gender == "female":
        #         if "zh-CN" in locale or "ja-JP" in locale:
        #             name = fake.romanized_name()
        #         else:
        #             name = fake.name_female()

        #     splitname = name.split(" ")
        #     if len(splitname) > 2 and re.match(
        #         r"^(mr|ms|mrs|dr|sr|sir|miss|herr|Univ\.Prof\.|ing\.|Prof\.|dipl\.|lic\.|sig\.|dott\.|Fru)",
        #         splitname[0],
        #         re.I,
        #     ):
        #         first, last = splitname[1], splitname[2]
        #     elif (
        #         len(splitname) > 2
        #         and re.match(r"^(du|le|de)", splitname[1], re.I)
        #         and "fr-FR" in locale
        #     ):
        #         name, last = splitname[0], f"{splitname[1]} {splitname[2]}"
        #     else:
        #         first, last = splitname[0], splitname[1]
        #     name_list.append(f"- {first.title()} {last.title()}\n")

        name_list = [
            f"- {name[0].title()} {name[1].title()}\n"
            for name in await fetch_random_name(gender=gender, country=country, results=number)
        ]

        await ctx.respond(
            embed=discord.Embed(
                title="Random Name Generator",
                description=f"Here are some random names for you, {ctx.author.mention}!\n{''.join(name_list)}",
                color=EmbedColor.INFO.value,
            ),
            ephemeral=True,
        )

    @commands.slash_command(
        name="add_roll_result_image", description="Add images to roll result embeds"
    )
    async def upload_thumbnail(
        self,
        ctx: ValentinaContext,
        roll_type: Option(
            str,
            description="Type of roll to add the image to",
            required=True,
            choices=[roll_type.name.title() for roll_type in RollResultType],
        ),
        url: Option(ValidImageURL, description="URL to the image", required=True),
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Add a roll result thumbnail to the bot."""
        title = f"Add roll result image for {roll_type.title()}\n{url}"
        is_confirmed, confirmation_response_msg = await confirm_action(
            ctx, title, hidden=hidden, image=url
        )

        if not is_confirmed:
            return

        guild = await Guild.get(ctx.guild.id, fetch_links=True)
        await guild.add_roll_result_thumbnail(ctx, RollResultType[roll_type.upper()], url)

        await ctx.post_to_audit_log(title)
        await confirmation_response_msg


def setup(bot: Valentina) -> None:
    """Add the cog to the bot."""
    bot.add_cog(Misc(bot))

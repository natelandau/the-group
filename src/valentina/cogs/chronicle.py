# mypy: disable-error-code="valid-type"
"""Cog for the Chronicle commands."""

import discord
from discord.commands import Option
from discord.ext import commands, pages
from loguru import logger

from valentina.models.bot import Valentina
from valentina.models.constants import MAX_FIELD_COUNT, MAX_PAGE_CHARACTER_COUNT, EmbedColor
from valentina.utils.converters import ValidChronicle, ValidYYYYMMDD
from valentina.utils.options import select_chapter, select_chronicle, select_note, select_npc
from valentina.views import ChapterModal, ConfirmCancelButtons, NoteModal, NPCModal, present_embed


class Chronicle(commands.Cog):
    """Commands used for updating chronicles."""

    # TODO: Add paginator to long embeds (e.g. chronicle list, chronicle chapters, etc.)

    def __init__(self, bot: Valentina) -> None:
        self.bot = bot

    chronicle = discord.SlashCommandGroup("chronicle", "Manage chronicles")
    chapter = chronicle.create_subgroup(name="chapter", description="Manage chronicle chapters")
    npc = chronicle.create_subgroup(name="npc", description="Manage chronicle NPCs")
    notes = chronicle.create_subgroup(name="notes", description="Manage chronicle notes")

    ### CHRONICLE COMMANDS ####################################################################

    @chronicle.command(name="create", description="Create a new chronicle")
    @commands.has_permissions(administrator=True)
    async def create_chronicle(
        self,
        ctx: discord.ApplicationContext,
        name: Option(str, description="Name of the chronicle", required=True),
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Create a new chronicle."""
        # TODO: Migrate to modal to allow setting chronicle description
        view = ConfirmCancelButtons(ctx.author)
        msg = await present_embed(
            ctx,
            title=f"Create new chronicle named: `{name}`?",
            view=view,
            ephemeral=hidden,
        )
        await view.wait()
        if not view.confirmed:
            embed = discord.Embed(
                title="Cancelled creating chronicle",
                color=EmbedColor.WARNING.value,
            )
            await msg.edit_original_response(embed=embed, view=None)
            return

        chronicle = self.bot.chron_svc.create_chronicle(ctx, name=name)

        await self.bot.guild_svc.send_to_audit_log(ctx, f"Create new chronicle: {chronicle.name}")
        await msg.edit_original_response(
            embed=discord.Embed(
                title=f"Create new chronicle: {chronicle.name}",
                description="",
                color=EmbedColor.SUCCESS.value,
            ),
            view=None,
        )

    @chronicle.command(name="current_date", description="Set the current date of a campaign")
    async def current_date(
        self,
        ctx: discord.ApplicationContext,
        date: Option(ValidYYYYMMDD, description="DOB in the format of YYYY-MM-DD", required=True),
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Set current date of a campaign."""
        chronicle = self.bot.chron_svc.fetch_active(ctx)

        self.bot.chron_svc.update_chronicle(ctx, chronicle, current_date=date)
        await self.bot.guild_svc.send_to_audit_log(
            ctx, f"Set date of chronicle `{chronicle.name}` to `{date:%Y-%m-%d}`"
        )
        await present_embed(
            ctx,
            title=f"Set date of chronicle `{chronicle.name}` to `{date:%Y-%m-%d}`",
            level="success",
            ephemeral=hidden,
        )

    @chronicle.command(name="delete", description="Delete a chronicle")
    @commands.has_permissions(administrator=True)
    async def delete_chronicle(
        self,
        ctx: discord.ApplicationContext,
        chronicle: Option(
            ValidChronicle,
            description="Name of the chronicle",
            required=True,
            autocomplete=select_chronicle,
        ),
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Delete a chronicle."""
        view = ConfirmCancelButtons(ctx.author)
        msg = await present_embed(
            ctx,
            title=f"Delete chronicle `{chronicle.name}` and all associated data (NPCs, notes, chapters)?",
            view=view,
            ephemeral=hidden,
        )
        await view.wait()
        if not view.confirmed:
            embed = discord.Embed(
                title="Cancelled deleting chronicle",
                color=EmbedColor.WARNING.value,
            )
            await msg.edit_original_response(embed=embed, view=None)
            return

        self.bot.chron_svc.delete_chronicle(ctx, chronicle)
        await self.bot.guild_svc.send_to_audit_log(ctx, f"Delete chronicle: {chronicle.name}")
        await msg.edit_original_response(
            embed=discord.Embed(
                title=f"Deleted chronicle: {chronicle.name}",
                description="",
                color=EmbedColor.SUCCESS.value,
            ),
            view=None,
        )

    @chronicle.command(name="view", description="View a chronicle")
    async def view_chronicle(self, ctx: discord.ApplicationContext) -> None:
        """View a chronicle."""
        # TODO: Allow viewing any chronicle

        chronicle = self.bot.chron_svc.fetch_active(ctx)
        npcs = self.bot.chron_svc.fetch_all_npcs(chronicle)
        chapters = self.bot.chron_svc.fetch_all_chapters(chronicle)
        notes = self.bot.chron_svc.fetch_all_notes(chronicle)

        chapter_list = sorted([c for c in chapters], key=lambda c: c.chapter)
        npc_list = sorted([n for n in npcs], key=lambda n: n.name)
        note_list = sorted([n for n in notes], key=lambda n: n.name)

        chapter_listing = "\n".join([f"{c.chapter}. {c.name}" for c in chapter_list])

        intro = f"""
\u200b\n**__{chronicle.name.upper()}__**
An overview of {chronicle.name}.

**{len(chapters)} Chapters**
{chapter_listing}

**{len(npcs)} NPCs**
{', '.join([f"{n.name}" for n in npc_list])}

**{len(notes)} Notes**
{', '.join([f"{n.name}" for n in note_list])}
            """

        ### CHAPTERS ###
        chapter_pages = []
        current_string = ""
        for chapter in chapter_list:
            if len(current_string) + len(chapter.chronicle_display()) > MAX_PAGE_CHARACTER_COUNT:
                chapter_pages.append(f"\u200b\nChapters in **{chronicle.name}**" + current_string)
                current_string = ""
            current_string += f"\n\n{chapter.chronicle_display()}"

        if current_string:
            chapter_pages.append(f"\u200b\nChapters in **{chronicle.name}**" + current_string)

        ## NPCS ##
        npc_pages = []
        current_string = ""
        for npc in npc_list:
            if len(current_string) + len(npc.chronicle_display()) > MAX_PAGE_CHARACTER_COUNT:
                npc_pages.append(f"\u200b\nNPCs in **{chronicle.name}**" + current_string)
                current_string = ""
            current_string += f"\n\n{npc.chronicle_display()}"

        if current_string:
            npc_pages.append(f"\u200b\nNPCs in **{chronicle.name}**" + current_string)

        ## NOTES ##
        note_pages = []
        current_string = ""
        for note in note_list:
            if len(current_string) + len(note.chronicle_display()) > MAX_PAGE_CHARACTER_COUNT:
                note_pages.append(f"\u200b\nNotes in **{chronicle.name}**" + current_string)
                current_string = ""
            current_string += f"\n\n{note.chronicle_display()}"

        if current_string:
            note_pages.append(f"\u200b\nNotes in **{chronicle.name}**" + current_string)

        # Create a paginator with the intro page
        paginator = pages.Paginator(pages=[intro, *chapter_pages, *npc_pages, *note_pages])
        paginator.remove_button("first")
        paginator.remove_button("last")

        # Send the paginator as a dm to the user
        await paginator.respond(
            ctx.interaction,
            target=ctx.author,
            ephemeral=True,
            target_message=f"Please check your DMs! The chronicle **{chronicle.name}** has been sent to you.",
        )

    @chronicle.command(name="set_active", description="Set a chronicle as active")
    @commands.has_permissions(administrator=True)
    async def chronicle_set_active(
        self,
        ctx: discord.ApplicationContext,
        chronicle: Option(
            ValidChronicle,
            description="Name of the chronicle",
            required=True,
            autocomplete=select_chronicle,
        ),
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Set a chronicle as active."""
        view = ConfirmCancelButtons(ctx.author)
        msg = await present_embed(
            ctx,
            title=f"Set chronicle `{chronicle.name}` as active?",
            view=view,
            ephemeral=hidden,
        )
        await view.wait()
        if not view.confirmed:
            embed = discord.Embed(
                title="Cancelled setting chronicle as active",
                color=EmbedColor.WARNING.value,
            )
            await msg.edit_original_response(embed=embed, view=None)
            return

        self.bot.chron_svc.set_active(ctx, chronicle)
        await self.bot.guild_svc.send_to_audit_log(
            ctx, f"Set chronicle as active: {chronicle.name}"
        )
        await msg.edit_original_response(
            embed=discord.Embed(
                title=f"Set chronicle as active: {chronicle.name}",
                color=EmbedColor.SUCCESS.value,
            ),
            view=None,
        )

    @chronicle.command(name="set_inactive", description="Set a chronicle as inactive")
    @commands.has_permissions(administrator=True)
    async def chronicle_set_inactive(
        self,
        ctx: discord.ApplicationContext,
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Set the active chronicle as inactive."""
        chronicle = self.bot.chron_svc.fetch_active(ctx)
        view = ConfirmCancelButtons(ctx.author)
        msg = await present_embed(
            ctx,
            title=f"Set chronicle **{chronicle.name}** as inactive",
            view=view,
            ephemeral=hidden,
        )
        await view.wait()
        if not view.confirmed:
            embed = discord.Embed(
                title="Cancelled",
                description="Cancelled setting chronicle as inactive",
                color=EmbedColor.WARNING.value,
            )
            await msg.edit_original_response(embed=embed, view=None)
            return

        self.bot.chron_svc.set_inactive(ctx)

        await self.bot.guild_svc.send_to_audit_log(
            ctx, f"Set chronicle as inactive: {chronicle.name}"
        )
        await msg.edit_original_response(
            embed=discord.Embed(
                title=f"Set chronicle as inactive: {chronicle.name}",
                color=EmbedColor.SUCCESS.value,
            ),
            view=None,
        )

    @chronicle.command(name="list", description="List all chronicles")
    async def chronicle_list(
        self,
        ctx: discord.ApplicationContext,
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """List all chronicles."""
        chronicles = self.bot.chron_svc.fetch_all(ctx)
        if len(chronicles) == 0:
            await present_embed(
                ctx,
                title="No chronicles",
                description="There are no chronicles\nCreate one with `/chronicle create`",
                level="info",
                ephemeral=hidden,
            )
            return

        fields = []
        for c in sorted(chronicles, key=lambda x: x.name):
            fields.append((f"**{c.name}** (Active)" if c.is_active else f"**{c.name}**", ""))

        await present_embed(ctx, title="Chronicles", fields=fields, level="info")
        logger.debug("CHRONICLE: List all chronicles")

    ### NPC COMMANDS ####################################################################

    @npc.command(name="create", description="Create a new NPC")
    async def create_npc(
        self,
        ctx: discord.ApplicationContext,
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Create a new NPC."""
        chronicle = self.bot.chron_svc.fetch_active(ctx)

        modal = NPCModal(title="Create new NPC")
        await ctx.send_modal(modal)
        await modal.wait()
        if not modal.confirmed:
            return

        name = modal.name.strip().title()
        npc_class = modal.npc_class.strip().title()
        description = modal.description.strip()

        self.bot.chron_svc.create_npc(
            ctx, chronicle=chronicle, name=name, npc_class=npc_class, description=description
        )

        await self.bot.guild_svc.send_to_audit_log(
            ctx, f"Create NPC: `{name}` in `{chronicle.name}`"
        )
        await present_embed(
            ctx,
            title=f"Create NPC: `{name}` in `{chronicle.name}`",
            level="success",
            fields=[
                ("Class", npc_class),
                (
                    "Description",
                    (description[:MAX_FIELD_COUNT] + " ...")
                    if len(description) > MAX_FIELD_COUNT
                    else description,
                ),
            ],
            ephemeral=hidden,
            inline_fields=True,
        )

    @npc.command(name="list", description="List all NPCs")
    async def list_npcs(
        self,
        ctx: discord.ApplicationContext,
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """List all NPCs."""
        chronicle = self.bot.chron_svc.fetch_active(ctx)
        npcs = self.bot.chron_svc.fetch_all_npcs(chronicle)
        if len(npcs) == 0:
            await present_embed(
                ctx,
                title="No NPCs",
                description="There are no NPCs\nCreate one with `/chronicle create_npc`",
                level="info",
                ephemeral=hidden,
            )
            return

        fields = []
        for npc in sorted(npcs, key=lambda x: x.name):
            fields.append(
                (
                    f"**__{npc.name}__**",
                    f"**Class:** {npc.npc_class}\n**Description:** {npc.description}",
                )
            )

        await present_embed(ctx, title="NPCs", fields=fields, level="info", ephemeral=hidden)

    @npc.command(name="edit", description="Edit an NPC")
    async def edit_npc(
        self,
        ctx: discord.ApplicationContext,
        npc: Option(str, description="NPC to edit", required=True, autocomplete=select_npc),
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Edit an NPC."""
        chronicle = self.bot.chron_svc.fetch_active(ctx)
        npc = self.bot.chron_svc.fetch_npc_by_name(ctx, chronicle, npc)

        modal = NPCModal(title="Edit NPC", npc=npc)
        await ctx.send_modal(modal)
        await modal.wait()
        if not modal.confirmed:
            return

        updates = {
            "name": modal.name.strip().title(),
            "npc_class": modal.npc_class.strip().title(),
            "description": modal.description.strip(),
        }
        self.bot.chron_svc.update_npc(ctx, npc, **updates)

        await self.bot.guild_svc.send_to_audit_log(
            ctx, f"Update NPC: `{updates['name']}` in `{chronicle.name}`"
        )
        await present_embed(
            ctx,
            title=f"Update NPC: `{updates['name']}` in `{chronicle.name}`",
            level="success",
            fields=[
                ("Class", updates["npc_class"]),
                (
                    "Description",
                    (modal.description.strip()[:MAX_FIELD_COUNT] + " ...")
                    if len(modal.description.strip()) > MAX_FIELD_COUNT
                    else modal.description.strip(),
                ),
            ],
            ephemeral=hidden,
            inline_fields=True,
        )

    @npc.command(name="delete", description="Delete an NPC")
    @commands.has_permissions(administrator=True)
    async def delete_npc(
        self,
        ctx: discord.ApplicationContext,
        npc: Option(str, description="NPC to edit", required=True, autocomplete=select_npc),
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Delete an NPC."""
        chronicle = self.bot.chron_svc.fetch_active(ctx)
        npc = self.bot.chron_svc.fetch_npc_by_name(ctx, chronicle, npc)

        view = ConfirmCancelButtons(ctx.author)
        msg = await present_embed(
            ctx,
            title=f"Delete NPC `{npc.name}`?",
            view=view,
            ephemeral=hidden,
        )
        await view.wait()
        if not view.confirmed:
            embed = discord.Embed(
                title="Cancelled deleting NPC",
                color=EmbedColor.WARNING.value,
            )
            await msg.edit_original_response(embed=embed, view=None)
            return

        self.bot.chron_svc.delete_npc(ctx, npc)

        await self.bot.guild_svc.send_to_audit_log(
            ctx, f"Delete NPC: `{npc.name}` in `{chronicle.name}`"
        )
        await msg.edit_original_response(
            embed=discord.Embed(
                title=f"Delete NPC: `{npc.name}` in `{chronicle.name}`",
                color=EmbedColor.SUCCESS.value,
            ),
            view=None,
        )

    ### CHAPTER COMMANDS ####################################################################

    @chapter.command(name="create", description="Create a new chapter")
    async def create_chapter(
        self,
        ctx: discord.ApplicationContext,
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Create a new chapter."""
        chronicle = self.bot.chron_svc.fetch_active(ctx)

        modal = ChapterModal(title="Create new chapter")
        await ctx.send_modal(modal)
        await modal.wait()
        if not modal.confirmed:
            return

        name = modal.name.strip().title()
        short_description = modal.short_description.strip()
        description = modal.description.strip()

        chapter = self.bot.chron_svc.create_chapter(
            ctx,
            chronicle=chronicle,
            name=name,
            short_description=short_description,
            description=description,
        )

        await self.bot.guild_svc.send_to_audit_log(
            ctx,
            f"Create chapter: `{chapter.chapter}. {chapter.name}` in `{chronicle.name}`",
        )
        await present_embed(
            ctx,
            f"Create chapter: `{chapter.chapter}. {chapter.name}` in `{chronicle.name}`",
            level="success",
            description=short_description,
            ephemeral=hidden,
        )

    @chapter.command(name="list", description="List all chapters")
    async def list_chapters(
        self,
        ctx: discord.ApplicationContext,
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """List all chapters."""
        chronicle = self.bot.chron_svc.fetch_active(ctx)
        chapters = self.bot.chron_svc.fetch_all_chapters(chronicle)
        if len(chapters) == 0:
            await present_embed(
                ctx,
                title="No Chapters",
                description="There are no chapters\nCreate one with `/chronicle create_chapter`",
                level="info",
                ephemeral=hidden,
            )
            return

        fields = []
        for chapter in sorted(chapters, key=lambda x: x.chapter):
            fields.append(
                (
                    f"**{chapter.chapter}.** **__{chapter.name}__**",
                    f"{chapter.short_description}",
                )
            )

        await present_embed(ctx, title="Chapters", fields=fields, level="info")

    @chapter.command(name="edit", description="Edit a chapter")
    @logger.catch
    async def edit_chapter(
        self,
        ctx: discord.ApplicationContext,
        chapter_select: Option(
            str,
            name="chapter",
            description="Chapter to edit",
            required=True,
            autocomplete=select_chapter,
        ),
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Edit a chapter."""
        chronicle = self.bot.chron_svc.fetch_active(ctx)
        chapter = self.bot.chron_svc.fetch_chapter_by_name(chronicle, chapter_select.split(":")[1])

        modal = ChapterModal(title="Edit chapter", chapter=chapter)
        await ctx.send_modal(modal)
        await modal.wait()
        if not modal.confirmed:
            return

        updates = {
            "name": modal.name.strip().title(),
            "short_description": modal.short_description.strip(),
            "description": modal.description.strip(),
        }
        self.bot.chron_svc.update_chapter(ctx, chapter, **updates)

        await self.bot.guild_svc.send_to_audit_log(
            ctx, f"Update chapter: `{updates['name']}` in `{chronicle.name}`"
        )

        await present_embed(
            ctx,
            title=f"Update chapter: `{updates['name']}` in `{chronicle.name}`",
            level="success",
            description=updates["short_description"],
            ephemeral=hidden,
        )

    @chapter.command(name="delete", description="Delete a chapter")
    @commands.has_permissions(administrator=True)
    async def delete_chapter(
        self,
        ctx: discord.ApplicationContext,
        chapter_select: Option(
            str,
            name="chapter",
            description="Chapter to edit",
            required=True,
            autocomplete=select_chapter,
        ),
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Delete a chapter."""
        chronicle = self.bot.chron_svc.fetch_active(ctx)
        chapter = self.bot.chron_svc.fetch_chapter_by_name(chronicle, chapter_select.split(":")[1])

        view = ConfirmCancelButtons(ctx.author)
        msg = await present_embed(
            ctx,
            title=f"Delete Chapter `{chapter.chapter}. {chapter.name}` from `{chronicle.name}`",
            view=view,
            ephemeral=hidden,
        )
        await view.wait()
        if not view.confirmed:
            embed = discord.Embed(
                title="Cancelled deleting chapter",
                color=EmbedColor.WARNING.value,
            )
            await msg.edit_original_response(embed=embed, view=None)
            return

        self.bot.chron_svc.delete_chapter(ctx, chapter)

        await self.bot.guild_svc.send_to_audit_log(
            ctx, f"Delete chapter: `{chapter.chapter}. {chapter.name}` in `{chronicle.name}`"
        )
        await msg.edit_original_response(
            embed=discord.Embed(
                title=f"Delete chapter: `{chapter.chapter}. {chapter.name}` in `{chronicle.name}`",
                color=EmbedColor.SUCCESS.value,
            ),
            view=None,
        )

    ### NOTE COMMANDS ####################################################################

    @notes.command(name="create", description="Create a new note")
    async def create_note(
        self,
        ctx: discord.ApplicationContext,
        chapter_select: Option(
            str,
            name="chapter",
            description="Chapter to edit",
            required=False,
            autocomplete=select_chapter,
            default=None,
        ),
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Create a new note."""
        chronicle = self.bot.chron_svc.fetch_active(ctx)
        chapter = (
            self.bot.chron_svc.fetch_chapter_by_name(chronicle, chapter_select.split(":")[1])
            if chapter_select
            else None
        )

        modal = NoteModal(title="Create new note")
        await ctx.send_modal(modal)
        await modal.wait()
        if not modal.confirmed:
            return

        name = modal.name.strip().title()
        description = modal.description.strip()

        self.bot.chron_svc.create_note(
            ctx,
            chronicle=chronicle,
            name=name,
            description=description,
            chapter=chapter,
        )

        await self.bot.guild_svc.send_to_audit_log(
            ctx, f"Create note: `{name}` in `{chronicle.name}`"
        )

        await present_embed(
            ctx,
            title=f"Create note: `{name}` in `{chronicle.name}`",
            level="success",
            description=(description[:MAX_FIELD_COUNT] + " ...")
            if len(description) > MAX_FIELD_COUNT
            else description,
            ephemeral=hidden,
        )

    @notes.command(name="list", description="List all notes")
    async def list_notes(
        self,
        ctx: discord.ApplicationContext,
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """List all notes."""
        chronicle = self.bot.chron_svc.fetch_active(ctx)
        notes = self.bot.chron_svc.fetch_all_notes(chronicle)
        if len(notes) == 0:
            await present_embed(
                ctx,
                title="No Notes",
                description="There are no notes\nCreate one with `/chronicle create_note`",
                level="info",
                ephemeral=hidden,
            )
            return

        fields = []
        for note in sorted(notes, key=lambda x: x.name):
            fields.append(
                (
                    f"**__{note.name}__**",
                    f"**Chapter:** {note.chapter.chapter}\n{note.description}"
                    if note.chapter
                    else f"{note.description}",
                )
            )

        await present_embed(
            ctx, title=f"Notes for **{chronicle.name}**", fields=fields, level="info"
        )

    @notes.command(name="edit", description="Edit a note")
    async def edit_note(
        self,
        ctx: discord.ApplicationContext,
        note_select: Option(
            str,
            name="note",
            description="Note to edit",
            required=True,
            autocomplete=select_note,
        ),
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Edit a note."""
        chronicle = self.bot.chron_svc.fetch_active(ctx)
        note = self.bot.chron_svc.fetch_note_by_id(note_select.split(":")[0])

        modal = NoteModal(title="Edit note", note=note)
        await ctx.send_modal(modal)
        await modal.wait()
        if not modal.confirmed:
            return

        updates = {
            "name": modal.name.strip().title(),
            "description": modal.description.strip(),
        }
        self.bot.chron_svc.update_note(ctx, note, **updates)

        await self.bot.guild_svc.send_to_audit_log(
            ctx, f"Update note: `{updates['name']}` in `{chronicle.name}`"
        )

        await present_embed(
            ctx,
            title=f"Update note: `{updates['name']}` in `{chronicle.name}`",
            level="success",
            description=(modal.description.strip()[:MAX_FIELD_COUNT] + " ...")
            if len(modal.description.strip()) > MAX_FIELD_COUNT
            else modal.description.strip(),
            ephemeral=hidden,
        )

    @notes.command(name="delete", description="Delete a note")
    async def delete_note(
        self,
        ctx: discord.ApplicationContext,
        note_select: Option(
            str,
            name="note",
            description="Note to edit",
            required=True,
            autocomplete=select_note,
        ),
        hidden: Option(
            bool,
            description="Make the response visible only to you (default true).",
            default=True,
        ),
    ) -> None:
        """Delete a note."""
        chronicle = self.bot.chron_svc.fetch_active(ctx)
        note = self.bot.chron_svc.fetch_note_by_id(note_select.split(":")[0])

        view = ConfirmCancelButtons(ctx.author)
        msg = await present_embed(
            ctx,
            title=f"Delete note `{note.name}` from `{chronicle.name}`?",
            view=view,
            ephemeral=hidden,
        )
        await view.wait()
        if not view.confirmed:
            embed = discord.Embed(
                title="Cancelled deleting note",
                color=EmbedColor.WARNING.value,
            )
            await msg.edit_original_response(embed=embed, view=None)
            return

        self.bot.chron_svc.delete_note(ctx, note)

        await self.bot.guild_svc.send_to_audit_log(
            ctx, f"Delete note: `{note.name}` in `{chronicle.name}`"
        )

        await msg.edit_original_response(
            embed=discord.Embed(
                title=f"Delete note: `{note.name}` in `{chronicle.name}`",
                color=EmbedColor.SUCCESS.value,
            ),
            view=None,
        )


def setup(bot: Valentina) -> None:
    """Add the cog to the bot."""
    bot.add_cog(Chronicle(bot))

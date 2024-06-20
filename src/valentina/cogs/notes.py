# mypy: disable-error-code="valid-type"
"""Cog for adding notes to campaigns, books, and characters."""

from typing import Annotated

import discord
from discord.commands import Option
from discord.ext import commands

from valentina.constants import MAX_FIELD_COUNT, EmbedColor
from valentina.models import Note as DbNote
from valentina.models.bot import Valentina, ValentinaContext
from valentina.utils.autocomplete import select_note
from valentina.utils.converters import ValidNote
from valentina.utils.discord_utils import determine_channel_type
from valentina.views import NoteModal, auto_paginate, confirm_action, present_embed


class Note(commands.Cog):
    """Miscellaneous commands."""

    def __init__(self, bot: Valentina) -> None:
        self.bot: Valentina = bot

    note = discord.SlashCommandGroup("note", "Add, remove, edit, or view notes")

    @note.command(name="add", description="Add a note to a book or character")
    async def add_note(
        self,
        ctx: ValentinaContext,
        note: Annotated[str, Option(name="note", description="The note to add", required=True)],
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
            ),
        ] = True,
    ) -> None:
        """Add a note."""
        # determine channel type
        _, book, character = await determine_channel_type(ctx, raise_error=False)

        added_to = f"book: `{book.name}`" if book else f"`{character.name}`" if character else ""
        if not added_to:
            await present_embed(
                ctx,
                title="Add note",
                description="Notes can only be added to books and characters.",
                ephemeral=hidden,
                level="error",
            )
            return

        title = f"Add note to {added_to}"
        description = f"```\n{note.strip().capitalize()}\n```"
        is_confirmed, interaction, confirmation_embed = await confirm_action(
            ctx, title, description=description, hidden=hidden, audit=True
        )

        if not is_confirmed:
            return

        if book:
            note = await DbNote(
                created_by=ctx.author.id, text=note.strip().capitalize(), parent_id=str(book.id)
            ).insert()
            book.notes.append(note)
            await book.save()

        elif character:
            note = await DbNote(
                created_by=ctx.author.id,
                text=note.strip().capitalize(),
                parent_id=str(character.id),
            ).insert()
            character.notes.append(note)
            await character.save()

        else:
            await interaction.edit_original_response(
                embed=discord.Embed(
                    title=title,
                    description="Notes can only be added to books and characters within their respective channels.",
                    color=EmbedColor.WARNING.value,
                ),
                view=None,
            )
            return

        await interaction.edit_original_response(embed=confirmation_embed, view=None)

    @note.command(name="view", description="View notes for a book or character")
    async def view_notes(
        self,
        ctx: ValentinaContext,
        hidden: Annotated[
            bool,
            Option(
                name="hidden",
                description="Make the response visible only to you (default true).",
                required=False,
            ),
        ] = True,
    ) -> None:
        """View notes."""
        # determine channel type
        _, book, character = await determine_channel_type(ctx, raise_error=False)
        if book:
            name = book.name
            notes = [await x.display(ctx) for x in book.notes]  # type: ignore [attr-defined]
        elif character:
            name = character.name
            notes = [await x.display(ctx) for x in character.notes]  # type: ignore [attr-defined]
        else:
            await present_embed(
                ctx,
                title="View notes",
                description="Notes can only be viewed for books and characters.",
                ephemeral=hidden,
                level="error",
            )
            return

        await auto_paginate(
            ctx=ctx,
            title=f"Notes for `{name}`",
            text="\n".join(f"{i}. {n}" for i, n in enumerate(notes, start=1))
            if notes
            else "No notes found.",
            hidden=hidden,
        )

    @note.command(name="edit", description="Edit a note for a book or character")
    async def edit_note(
        self,
        ctx: ValentinaContext,
        note: Option(
            ValidNote,
            name="note",
            description="The note to edit",
            required=True,
            autocomplete=select_note,
        ),
        hidden: Option(
            bool,
            name="hidden",
            description="Make the response visible only to you (default true).",
            required=False,
            default=True,
        ),
    ) -> None:
        """Edit a note."""
        modal = NoteModal(title="Edit note", note=note)
        await ctx.send_modal(modal)
        await modal.wait()
        if not modal.confirmed:
            return

        note.text = modal.note_text.strip().capitalize()
        await note.save()

        await ctx.post_to_audit_log(f"Update note: `{note.id}`")

        await present_embed(
            ctx,
            title="Update note",
            level="success",
            description=(note.text[:MAX_FIELD_COUNT] + " ...")
            if len(note.text) > MAX_FIELD_COUNT
            else note.text,
            ephemeral=hidden,
        )

    @note.command(name="delete", description="delete a note for a book or character")
    async def delete_note(
        self,
        ctx: ValentinaContext,
        note_to_delete: Option(
            ValidNote,
            name="note",
            description="The note to edit",
            required=True,
            autocomplete=select_note,
        ),
        hidden: Option(
            bool,
            name="hidden",
            description="Make the response visible only to you (default true).",
            required=False,
            default=True,
        ),
    ) -> None:
        """Delete a note."""
        _, book, character = await determine_channel_type(ctx, raise_error=False)

        deleted_from = (
            f"book: `{book.name}`" if book else f"`{character.name}`" if character else ""
        )
        if not deleted_from:
            await present_embed(
                ctx,
                title="Add note",
                description="Notes can only be added to books and characters.",
                ephemeral=hidden,
                level="error",
            )
            return

        title = f"Delete note from {deleted_from}"
        description = f"```\n{note_to_delete.text}\n```"
        is_confirmed, interaction, confirmation_embed = await confirm_action(
            ctx,
            title,
            description=description,
            hidden=hidden,
            audit=True,
            footer="Careful, this action is irreversible.",
        )

        if not is_confirmed:
            return

        if book:
            book.notes.remove(note_to_delete)
            await book.save()

        if character:
            character.notes.remove(note_to_delete)
            await character.save()

        await note_to_delete.delete()

        await interaction.edit_original_response(embed=confirmation_embed, view=None)


def setup(bot: Valentina) -> None:
    """Add the cog to the bot."""
    bot.add_cog(Note(bot))

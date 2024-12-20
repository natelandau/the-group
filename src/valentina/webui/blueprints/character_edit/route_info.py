"""Route for editing character info such as notes and custom sheet sections."""

from typing import ClassVar, assert_never
from uuid import UUID

from flask_discord import requires_authorization
from quart import abort, request, url_for
from quart.views import MethodView
from quart_wtf import QuartForm
from wtforms import (
    HiddenField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length

from valentina.controllers import delete_character
from valentina.models import Character, CharacterSheetSection
from valentina.webui import catalog
from valentina.webui.constants import CharacterEditableInfo
from valentina.webui.utils import create_toast, fetch_active_character
from valentina.webui.utils.discord import post_to_audit_log


class CustomSectionForm(QuartForm):
    """Form for a custom section."""

    title = StringField(
        "Title", validators=[DataRequired(), Length(min=3, message="Must be at least 3 characters")]
    )
    content = TextAreaField(
        "Content",
        validators=[DataRequired(), Length(min=3, message="Must be at least 3 characters")],
    )

    uuid = HiddenField()
    submit = SubmitField("Submit")


class DeleteCharacterForm(QuartForm):
    """Form for deleting a character."""

    submit = SubmitField("Delete", description="Confirm character deletion")


class EditCharacterInfo(MethodView):
    """Edit the character's info."""

    decorators: ClassVar = [requires_authorization]

    def __init__(self, edit_type: CharacterEditableInfo) -> None:
        self.edit_type = edit_type

    async def _build_form(self, character: Character) -> QuartForm:
        """Build the form and populate with existing data if available."""
        data = {}

        match self.edit_type:
            case CharacterEditableInfo.CUSTOM_SECTION:
                if request.args.get("uuid", None):
                    uuid = UUID(request.args.get("uuid"))
                    for section in character.sheet_sections:
                        if section.uuid == uuid:
                            data["title"] = str(section.title)
                            data["content"] = str(section.content)
                            data["uuid"] = str(section.uuid)
                            break

                return await CustomSectionForm().create_form(data=data)

            case CharacterEditableInfo.DELETE:
                return await DeleteCharacterForm().create_form()

            case _:
                assert_never(self.edit_type)

    async def _delete_custom_section(self, character: Character) -> str:
        """Delete the custom section."""
        uuid = request.args.get("uuid", None)
        if not uuid:
            abort(400)

        for section in character.sheet_sections:
            if section.uuid == UUID(uuid):
                character.sheet_sections.remove(section)
                break

        await post_to_audit_log(
            msg=f"Character {character.name} section `{section.title}` deleted",
            view=self.__class__.__name__,
        )
        await character.save()

        return "Custom section deleted"

    async def _post_custom_section(self, character: Character) -> tuple[bool, str, QuartForm]:
        """Process the custom section form."""
        form = await self._build_form(character)
        if await form.validate_on_submit():
            form_data = {
                k: v if v else None
                for k, v in form.data.items()
                if k not in {"submit", "character_id", "csrf_token"}
            }

            section_title = form_data["title"].strip().title()
            section_content = form_data["content"].strip()

            updated_existing = False
            if form_data.get("uuid"):
                uuid = UUID(form_data["uuid"])
                for section in character.sheet_sections:
                    if section.uuid == uuid:
                        section.title = section_title
                        section.content = section_content
                        updated_existing = True
                        msg = "Custom section updated"
                        break

            if not updated_existing:
                character.sheet_sections.append(
                    CharacterSheetSection(title=section_title, content=section_content)
                )
                msg = "Custom section added"

            await post_to_audit_log(
                msg=f"{msg} to {character.name}",
                view=self.__class__.__name__,
            )
            await character.save()

            return True, msg, form

        return False, "", form

    async def _post_delete_character(self, character: Character) -> tuple[bool, str, QuartForm]:
        """Process the delete character form."""
        form = await self._build_form(character)

        if await form.validate_on_submit():
            await post_to_audit_log(
                msg=f"Character {character.name} deleted",
                view=self.__class__.__name__,
            )
            await delete_character(character)

            return True, "Character deleted", None
        return False, "", form

    async def get(self, character_id: str) -> str:
        """Render the form."""
        character = await fetch_active_character(character_id, fetch_links=False)

        return catalog.render(
            "character_edit.FormPartial",
            character=character,
            form=await self._build_form(character),
            join_label=False,
            floating_label=True,
            post_url=url_for(self.edit_type.value.route, character_id=character_id),
            tab=self.edit_type.value.tab,
            hx_target=f"#{self.edit_type.value.div_id}",
        )

    async def post(self, character_id: str) -> str:
        """Process the form."""
        character = await fetch_active_character(character_id, fetch_links=False)

        match self.edit_type:
            case CharacterEditableInfo.CUSTOM_SECTION:
                form_is_processed, msg, form = await self._post_custom_section(character)

            case CharacterEditableInfo.DELETE:
                form_is_processed, msg, form = await self._post_delete_character(character)
                # If the form is processed, redirect to the homepage with a success message b/c the character is deleted.
                url = url_for("homepage.homepage", success_msg=msg)
                return f'<script>window.location.href="{url}"</script>'

            case _:
                assert_never(self.edit_type)

        if form_is_processed:
            url = url_for("character_view.view", character_id=character_id, success_msg=msg)
            return f'<script>window.location.href="{url}"</script>'

        # If POST request does not validate, return errors
        return catalog.render(
            "character_edit.FormPartial",
            character=character,
            form=form,
            join_label=False,
            floating_label=True,
            post_url=url_for(self.edit_type.value.route, character_id=character_id),
            tab=self.edit_type.value.tab,
            hx_target=f"#{self.edit_type.value.div_id}",
        )

    async def delete(self, character_id: str) -> str:
        """Delete the item."""
        character = await fetch_active_character(character_id, fetch_links=False)

        match self.edit_type:
            case CharacterEditableInfo.CUSTOM_SECTION:
                msg = await self._delete_custom_section(character)
            case CharacterEditableInfo.DELETE:
                pass  # Not implemented
            case _:
                assert_never(self.edit_type)

        return create_toast(msg, level="SUCCESS")

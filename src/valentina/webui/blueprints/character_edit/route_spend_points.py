"""Route for spending freebie points."""

from enum import Enum
from typing import ClassVar, assert_never

from flask_discord import requires_authorization
from quart import Response, abort, redirect, request, session, url_for
from quart.views import MethodView

from valentina.constants import HTTPStatus
from valentina.controllers import CharacterSheetBuilder, TraitModifier
from valentina.models import Campaign, Character, CharacterTrait, User
from valentina.utils import errors
from valentina.utils.helpers import get_max_trait_value
from valentina.webui import catalog
from valentina.webui.utils.discord import post_to_audit_log
from valentina.webui.utils.forms import ValentinaForm
from valentina.webui.utils.helpers import fetch_active_character, fetch_user, is_storyteller


class SpendPointsType(Enum):
    """The type of point to spend."""

    FREEBIE = "freebie"
    EXPERIENCE = "experience"
    STORYTELLER = "storyteller"


class SpendPoints(MethodView):
    """View to manage freebie point spending. This page uses HTMX to validate each trait as it is changed."""

    decorators: ClassVar = [requires_authorization]

    def __init__(self, spend_type: SpendPointsType) -> None:
        self.form = ValentinaForm(
            hx_validate=False,
            join_labels=True,
            title="Character Traits",
            description="Enter the traits for your character.",
        )
        self.spend_type = spend_type

    async def _parse_form_data(
        self, character: Character, form: dict
    ) -> tuple[CharacterTrait, int]:
        """Parse the form data to determine the trait to modify and the target value. If the CharacterTrait object is not alreadfy in the database, create a new one.

        Args:
            character (Character): The character to modify the trait for.
            form (dict): The form data.

        Returns:
            tuple[CharacterTrait, int]: A tuple containing the trait to modify and the target value.
        """
        form_key = str(next(iter(form.keys())))

        # Because we have a mix of existing traits and new traits, we need to create new traits if they don't exist
        if form_key.lower().startswith("new_"):
            target_value = int(next(iter(form.values())))
            name, category, max_value = form_key.split("_")[1:]

            trait = CharacterTrait(
                name=name,
                category_name=category,
                max_value=int(max_value),
                value=0,
                is_custom=False,
                character=str(character.id),
            )

        elif form_key.lower().startswith("custom_"):
            custom_trait_name = next(iter(form.values()))
            target_value = 1
            category = form_key.split("_")[1]

            trait = CharacterTrait(
                name=custom_trait_name,
                category_name=category,
                max_value=get_max_trait_value(custom_trait_name, category),
                value=0,
                is_custom=True,
                character=str(character.id),
            )

        else:
            target_value = int(next(iter(form.values())))
            trait = await CharacterTrait.get(form_key)

        return trait, target_value

    async def _upgrade_trait(
        self, character: Character, trait: CharacterTrait, new_value: int
    ) -> str:
        """Upgrade a trait to a new value.

        Args:
            character (Character): The character to upgrade the trait for.
            trait (CharacterTrait): The trait to upgrade.
            new_value (int): The new value for the trait.

        Returns:
            str: The success message.
        """
        user = await fetch_user()
        trait_modifier = TraitModifier(character, user)
        difference = new_value - trait.value
        cost = trait_modifier.cost_to_upgrade(trait, difference)

        match self.spend_type:
            case SpendPointsType.FREEBIE:
                updated_trait = await trait_modifier.upgrade_with_freebie(trait, difference)
            case SpendPointsType.EXPERIENCE:
                campaign = await Campaign.get(character.campaign)
                updated_trait = await trait_modifier.upgrade_with_xp(trait, campaign, difference)
            case SpendPointsType.STORYTELLER:
                # TODO: Add storyteller trait upgrading
                pass
            case _:
                assert_never()

        await post_to_audit_log(
            msg=f"Upgraded {character.name}'s {trait.name} to {updated_trait.value} costing {cost} {self.spend_type.value} points"
        )
        return f"Upgraded {trait.name} to {updated_trait.value} for {cost} {self.spend_type.value} points"

    async def _downgrade_trait(
        self, character: Character, trait: CharacterTrait, new_value: int
    ) -> str:
        """Downgrade a trait to a new value.

        Args:
            character (Character): The character to upgrade the trait for.
            trait (CharacterTrait): The trait to upgrade.
            new_value (int): The new value for the trait.

        Returns:
            str: The success message.
        """
        user = await fetch_user()
        trait_modifier = TraitModifier(character, user)
        difference = trait.value - new_value
        savings = trait_modifier.savings_from_downgrade(trait, difference)

        match self.spend_type:
            case SpendPointsType.FREEBIE:
                downgraded_trait = await trait_modifier.downgrade_with_freebie(trait, difference)
            case SpendPointsType.EXPERIENCE:
                campaign = await Campaign.get(character.campaign)
                downgraded_trait = await trait_modifier.downgrade_with_xp(
                    trait, campaign, difference
                )
            case SpendPointsType.STORYTELLER:
                # TODO: Add storyteller trait downgrading
                pass
            case _:
                assert_never()

        await post_to_audit_log(
            msg=f"Downgraded {character.name}'s {trait.name} to {downgraded_trait.value} recouping {savings} {self.spend_type.value} points"
        )
        return f"Downgraded {trait.name} to {downgraded_trait.value} for {savings} {self.spend_type.value} points"

    async def _get_campaign_experience(
        self, character: "Character", character_owner: User = None
    ) -> int:
        """Get the experience points for the character's campaign.

        Args:
            character (Character): The character to check.
            character_owner (User, optional): The character's owner. Defaults to None.

        Returns:
            int: The experience points for the character's campaign.
        """
        if not character_owner:
            character_owner = await User.get(character.user_owner, fetch_links=False)

        campaign = await Campaign.get(character.campaign)
        campaign_experience, _, _ = character_owner.fetch_campaign_xp(campaign)
        return campaign_experience

    async def get(self, character_id: str = "") -> str | Response:
        """Manage GET requests."""
        character = await fetch_active_character(character_id, fetch_links=True)
        if not character:
            abort(HTTPStatus.BAD_REQUEST.value)

        character_owner = await User.get(character.user_owner, fetch_links=False)
        if not is_storyteller and character_owner.id != session.get("USER_ID"):
            return redirect(  # type: ignore [return-value]
                url_for(
                    "character_view.view",
                    character_id=character_id,
                    error_msg="You do not have permission to edit this character",
                )
            )

        campaign_experience = (
            await self._get_campaign_experience(character)
            if self.spend_type == SpendPointsType.EXPERIENCE
            else 0
        )

        trait_builder = CharacterSheetBuilder(character)
        all_traits = trait_builder.fetch_character_plus_all_class_traits()

        return catalog.render(
            "character_edit.SpendPoints",
            spend_type=self.spend_type,
            character=character,
            campaign_experience=campaign_experience,
            form=self.form,
            traits=all_traits,
            post_url=url_for(f"character_edit.{self.spend_type.value}", character_id=character_id),
            error_msg=request.args.get("error_msg", ""),
            success_msg=request.args.get("success_msg", ""),
        )

    async def post(self, character_id: str = "") -> Response:
        """Manage POST requests."""
        character = await fetch_active_character(character_id, fetch_links=True)
        if not character:
            abort(HTTPStatus.BAD_REQUEST.value)

        form = await request.form
        trait, target_value = await self._parse_form_data(character, form)

        success_msg = ""
        try:
            if trait.value < target_value:
                success_msg = await self._upgrade_trait(character, trait, target_value)
            elif trait.value > target_value:
                success_msg = await self._downgrade_trait(character, trait, target_value)
        except errors.TraitAtMaxValueError:
            return Response(
                headers={
                    "HX-Redirect": url_for(
                        "character_edit.freebie",
                        character_id=str(character.id),
                        error_msg=f"{trait.name} is already at max value",
                    )
                }
            )
        except errors.NotEnoughFreebiePointsError:
            return Response(
                headers={
                    "HX-Redirect": url_for(
                        "character_edit.freebie",
                        character_id=str(character.id),
                        error_msg=f"Not enough freebie points to upgrade {trait.name} to {target_value}",
                    )
                }
            )
        except errors.TraitExistsError:
            return Response(
                headers={
                    "HX-Redirect": url_for(
                        "character_edit.freebie",
                        character_id=str(character.id),
                        error_msg=f'Trait <span class="font-monospace fw-bold">{trait.name}</span> already exists in <span class="font-monospace fw-bold">{trait.category.name.title()}</span>',
                    )
                }
            )
        except errors.NotEnoughExperienceError:
            return Response(
                headers={
                    "HX-Redirect": url_for(
                        "character_edit.experience",
                        character_id=str(character.id),
                        error_msg=f"Not enough experience points to upgrade {trait.name} to {target_value}",
                    )
                }
            )
        except errors.TraitAtMinValueError:
            return Response(
                headers={
                    "HX-Redirect": url_for(
                        "character_edit.experience",
                        character_id=str(character.id),
                        error_msg=f"{trait.name} can not be lowered below 0",
                    )
                }
            )

        return Response(
            headers={
                "HX-Redirect": url_for(
                    f"character_edit.{self.spend_type.value}",
                    character_id=character_id,
                    success_msg=success_msg,
                )
            }
        )
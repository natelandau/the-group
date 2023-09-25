# type: ignore
"""Test the CharacterService class."""

from random import randint
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import discord
import pytest
from dirty_equals import IsList, IsPartialDict

from valentina.models import CharacterService
from valentina.models.db_tables import (
    Character,
    CustomTrait,
    GuildUser,
    Trait,
    TraitCategory,
    TraitValue,
    VampireClan,
)
from valentina.utils import errors


@pytest.mark.usefixtures("mock_db")
class TestCharacterModel:
    """Test the character database model."""

    def test_character_add_custom_trait(self) -> None:
        """Test the add_custom_trait method.

        GIVEN: A Character object and a TraitCategory object.
        WHEN: The add_custom_trait method is called.
        THEN: The custom trait should be added correctly.
        """
        # GIVEN: A Character object and a TraitCategory object
        test_character = Character.create(
            data={
                "first_name": "add_custom_trait",
                "last_name": "character",
                "nickname": "testy",
                "storyteller_character": False,
                "player_character": True,
            },
            char_class=1,
            guild=1,
            created_by=1,
            clan=1,
        )
        assert len(test_character.custom_traits) == 0
        test_category = TraitCategory.get_by_id(1)

        # WHEN: The add_custom_trait method is called
        test_character.add_custom_trait("new_trait", "new description", test_category, 1, 5)

        # THEN: Check the custom trait is added correctly
        assert len(test_character.custom_traits) == 1
        custom_trait = test_character.custom_traits[0]
        assert custom_trait.name == "new_trait"
        assert custom_trait.description == "new description"
        assert custom_trait.category == test_category
        assert custom_trait.value == 1
        assert custom_trait.max_value == 5

        # WHEN: The add_custom_trait method is called again with the same name
        # THEN: Raise a validation error
        with pytest.raises(errors.ValidationError):
            test_character.add_custom_trait("new_trait", "new description", test_category, 1, 5)

    def test_character_all_trait_values(self) -> None:
        """Test the all_trait_values method of the Character class.

        GIVEN: A Character object with traits.
        WHEN: The all_trait_values method is called.
        THEN: All trait values should be returned as a dictionary containing the appropriate tuple values.
        """
        # GIVEN: A Character object with traits
        # (Assuming that the Character with id=1 has the traits as described in the test)

        # WHEN: The all_trait_values method is called
        trait_values = Character.get_by_id(1).all_trait_values

        # THEN: All trait values should be returned as expected
        assert "Physical" in trait_values
        assert "Skills" in trait_values

        assert trait_values["Physical"] == [
            ("Strength", 1, 5, "●○○○○"),
            ("Dexterity", 2, 5, "●●○○○"),
            ("Stamina", 3, 5, "●●●○○"),
        ]

        assert trait_values["Skills"] == [("Test_Trait", 2, 5, "●●○○○")]

    def test_character_custom_traits(self) -> None:
        """Test the custom_traits method of the Character class.

        GIVEN: A Character object with custom traits.
        WHEN: The custom_traits method is called.
        THEN: All custom traits should be returned as expected.
        """
        # GIVEN: A Character object with custom traits
        # (Assuming that the Character with id=1 has the custom traits as described in the test)

        # WHEN: The custom_traits method is called
        custom_traits = Character.get_by_id(1).custom_traits

        # THEN: All custom traits should be returned as expected
        assert custom_traits is not None, "Custom traits should not be None"
        assert len(custom_traits) == 1, "There should be exactly one custom trait"

        first_trait = custom_traits[0]
        assert (
            first_trait.name == "Test_Trait"
        ), "The name of the first custom trait should be 'Test_Trait'"

    def test_character_get_trait_value(self, mock_ctx):
        """Test character.get_trait_value() method.

        This test verifies that the method correctly returns the value of a given trait or custom trait.
        It also checks that the method returns 0 for a trait that does not exist for the character.
        """
        # GIVEN a character with a custom trait and a trait value
        character = Character.create(
            data={
                "first_name": str(uuid4()).split("-")[0],
                "last_name": "character",
                "nickname": "testy",
                "storyteller_character": False,
            },
            char_class=1,
            guild=mock_ctx.guild.id,
            created_by=mock_ctx.author.id,
            clan=1,
        )
        custom_trait = CustomTrait.create(
            name="test_trait",
            description="test_description",
            category=1,
            value=4,
            max_value=5,
            character=character,
        )
        trait = Trait.get_by_id(1)
        TraitValue.create(character=character, trait=trait, value=2)

        # WHEN the get_trait_value method is called with a CustomTrait
        # THEN check the trait value is returned correctly
        assert character.get_trait_value(custom_trait) == 4, "Custom trait value should be 4"

        # WHEN the get_trait_value method is called with a Trait
        # THEN check the trait value is returned correctly
        assert character.get_trait_value(trait) == 2, "Trait value should be 2"

        # WHEN the get_trait_value method is called with a TraitValue that does not exist
        # THEN return 0 for the value
        non_existent_trait_value = TraitValue(trait=Trait.get_by_id(2))
        assert (
            character.get_trait_value(non_existent_trait_value) == 0
        ), "Non-existent trait value should be 0"

    def test_set_custom_trait_value(self, mock_ctx):
        """Test setting a value for a custom trait using character.set_trait_value()."""
        # GIVEN a character with a custom trait
        character = Character.create(
            data={
                "first_name": str(uuid4()).split("-")[0],
                "last_name": "character",
                "nickname": "testy",
                "storyteller_character": False,
                "player_character": True,
            },
            char_class=1,
            guild=mock_ctx.guild.id,
            created_by=mock_ctx.author.id,
            clan=1,
        )
        custom_trait = CustomTrait.create(
            name="test_trait",
            description="test_description",
            category=1,
            value=0,
            max_value=5,
            character=character,
        )

        # WHEN the set_trait_value method is called with a CustomTrait
        character.set_trait_value(custom_trait, 3)

        # THEN check the trait value is updated correctly
        assert custom_trait.value == 3

    def test_create_new_trait_value(self, mock_ctx):
        """Test creating a new trait value using character.set_trait_value()."""
        # GIVEN a character without a standard trait value
        character = Character.create(
            data={
                "first_name": str(uuid4()).split("-")[0],
                "last_name": "character",
                "nickname": "testy",
                "storyteller_character": False,
                "player_character": True,
            },
            char_class=1,
            guild=mock_ctx.guild.id,
            created_by=mock_ctx.author.id,
            clan=1,
        )
        trait = Trait.get_by_id(1)

        # WHEN the set_trait_value method is called with a Trait
        character.set_trait_value(trait, 3)

        # THEN check the trait value is created correctly
        assert (
            TraitValue.select()
            .where((TraitValue.trait == trait) & (TraitValue.character == character))
            .get()
            .value
            == 3
        )

    def test_update_existing_trait_value(self, mock_ctx):
        """Test updating an existing trait value using character.set_trait_value()."""
        # GIVEN a character with an existing standard trait value
        character = Character.create(
            data={
                "first_name": str(uuid4()).split("-")[0],
                "last_name": "character",
                "nickname": "testy",
                "storyteller_character": False,
                "player_character": True,
            },
            char_class=1,
            guild=mock_ctx.guild.id,
            created_by=mock_ctx.author.id,
            clan=1,
        )
        trait = Trait.get_by_id(1)
        TraitValue.create(character=character, trait=trait, value=3)

        # WHEN the set_trait_value method is called with a Trait
        character.set_trait_value(trait, 1)

        # THEN check the trait value is updated correctly
        assert (
            TraitValue.select()
            .where((TraitValue.trait == trait) & (TraitValue.character == character))
            .get()
            .value
            == 1
        )

    def test_character_traits_dict(self):
        """Test character.traits_dict.

        Given a character with traits
        When character.traits_dict is called
        Then all traits associated with that character are returned as a dictionary
        """
        returned = Character.get_by_id(1).traits_dict

        assert returned == {
            "Physical": [Trait.get_by_id(1), Trait.get_by_id(2), Trait.get_by_id(3)],
            "Skills": [CustomTrait.get_by_id(1)],
        }

    def test_character_traits_list(self):
        """Test character.traits_list.

        Given a character with traits
        When character.all_traits_list is called as a flat list
        Then all traits associated with that character are returned as a list
        """
        returned = Character.get_by_id(1).traits_list
        assert returned == [
            Trait.get_by_id(2),
            Trait.get_by_id(3),
            Trait.get_by_id(1),
            CustomTrait.get_by_id(1),
        ]


@pytest.mark.usefixtures("mock_db")
class TestCharacterService:
    """Test the character service."""

    char_svc = CharacterService()

    def test_custom_section_update_or_add(self, mock_ctx):
        """Test if custom_section_update_or_add() correctly adds or updates a custom section.

        This test covers two scenarios:
        1. Adding a new custom section to an empty list of custom sections.
        2. Updating an existing custom section.

        Args:
            mock_ctx (Mock): Mocked context for the service function call.
        """
        # GIVEN a character object with no custom sections
        character = Character.create(
            data={
                "first_name": "add_custom_section",
                "last_name": "character",
                "nickname": "testy",
                "storyteller_character": False,
                "player_character": True,
            },
            char_class=1,
            guild=1,
            created_by=1,
            clan=1,
        )
        assert character.custom_sections == [], "Initial custom sections should be empty"

        # WHEN the custom_section_update_or_add method is called for the first time
        result1 = self.char_svc.custom_section_update_or_add(
            mock_ctx, character, "new", "new description"
        )

        # THEN check that the custom section is added correctly
        assert character.custom_sections == IsList(length=1), "One custom section should be added"
        assert result1.title == "new", "The title should match the initial input"
        assert (
            result1.description == "new description"
        ), "The description should match the initial input"

        # WHEN the custom_section_update_or_add method is called a second time with different details
        result2 = self.char_svc.custom_section_update_or_add(
            mock_ctx, character, "new2", "new description2"
        )

        # THEN check that the existing custom section is updated correctly
        assert character.custom_sections == IsList(
            length=1
        ), "Should still be only one custom section after update"
        assert result2.title == "new2", "The title should be updated to 'new2'"
        assert (
            result2.description == "new description2"
        ), "The description should be updated to 'new description2'"

    def test_fetch_all_player_characters(self, mocker, mock_member, mock_member2):
        """Test fetch_all_player_characters()."""
        # GIVEN characters for a guild

        local_mock_guild = mocker.MagicMock()
        local_mock_guild.id = randint(1000, 99999)
        local_mock_guild.__class__ = discord.Guild
        local_mock_ctx = mocker.MagicMock()
        local_mock_ctx.guild = local_mock_guild
        local_mock_ctx.__class__ = discord.ApplicationContext

        character1 = Character.create(
            data={
                "first_name": str(uuid4()).split("-")[0],
                "last_name": "character1",
                "storyteller_character": False,
                "player_character": True,
            },
            char_class=1,
            guild=local_mock_ctx.guild.id,
            created_by=mock_member.id,
            owned_by=mock_member.id,
            clan=1,
        )
        character2 = Character.create(
            data={
                "first_name": str(uuid4()).split("-")[0],
                "last_name": "character2",
                "storyteller_character": False,
                "player_character": True,
            },
            char_class=1,
            guild=local_mock_ctx.guild.id,
            created_by=mock_member.id,
            owned_by=mock_member.id,
            clan=1,
        )
        # Created by a second user
        character3 = Character.create(
            data={
                "first_name": str(uuid4()).split("-")[0],
                "last_name": "character3",
                "storyteller_character": False,
                "player_character": True,
            },
            char_class=1,
            guild=local_mock_ctx.guild.id,
            created_by=mock_member2.id,
            owned_by=mock_member2.id,
            clan=1,
        )
        # not a player character
        Character.create(
            data={
                "first_name": str(uuid4()).split("-")[0],
                "last_name": "character4",
                "storyteller_character": True,
            },
            char_class=1,
            guild=local_mock_ctx.guild.id,
            created_by=mock_member.id,
            owned_by=mock_member.id,
            clan=1,
        )
        # not in the guild
        Character.create(
            data={
                "first_name": str(uuid4()).split("-")[0],
                "last_name": "character5",
                "player_character": True,
            },
            char_class=1,
            guild=local_mock_ctx.guild.id + 5,
            created_by=mock_member.id,
            owned_by=mock_member.id,
            clan=1,
        )

        # WHEN the fetch_all_player_characters method is called
        result = self.char_svc.fetch_all_player_characters(local_mock_ctx)

        # THEN check the method returns the correct characters database and updates the default values
        assert result == [character1, character2, character3]
        assert result[0].data["experience"] == 0  # Check default value

        # WHEN the fetch_all_player_characters method is called with a user
        result = self.char_svc.fetch_all_player_characters(local_mock_ctx, owned_by=mock_member)
        assert result == [character1, character2]

    def test_fetch_all_storyteller_characters(self, mocker):
        """Test fetch_all_storyteller_characters()."""
        # GIVEN characters for a guild
        local_mock_guild = mocker.MagicMock()
        local_mock_guild.id = randint(1000, 99999)
        local_mock_guild.__class__ = discord.Guild
        local_mock_ctx = mocker.MagicMock()
        local_mock_ctx.guild = local_mock_guild
        local_mock_ctx.__class__ = discord.ApplicationContext

        character1 = Character.create(
            data={
                "first_name": str(uuid4()).split("-")[0],
                "last_name": "character",
                "storyteller_character": True,
            },
            char_class=1,
            guild=local_mock_ctx.guild.id,
            created_by=1,
            clan=1,
        )
        character2 = Character.create(
            data={
                "first_name": str(uuid4()).split("-")[0],
                "last_name": "character",
                "storyteller_character": True,
            },
            char_class=1,
            guild=local_mock_ctx.guild.id,
            created_by=1,
            clan=1,
        )
        # not a storyteller character
        Character.create(
            data={
                "first_name": str(uuid4()).split("-")[0],
                "last_name": "character",
                "player_character": True,
            },
            char_class=1,
            guild=local_mock_ctx.guild.id,
            created_by=1,
            clan=1,
        )
        # not in the guild
        Character.create(
            data={
                "first_name": str(uuid4()).split("-")[0],
                "last_name": "character",
                "storyteller_character": True,
            },
            char_class=1,
            guild=local_mock_ctx.guild.id + 5,
            created_by=1,
            clan=1,
        )

        # WHEN the fetch_all_storyteller_characters method is called
        result = self.char_svc.fetch_all_storyteller_characters(local_mock_ctx)

        # THEN check the method returns the correct characters database and updates the default values
        assert result == [character1, character2]
        assert result[0].data["experience"] == 0  # Check default value

    @pytest.mark.asyncio()
    async def test_update_or_add_one(self, mock_ctx):
        """Test update_character()."""
        # GIVEN a character object
        user, _ = GuildUser.get_or_create(user=mock_ctx.author.id, guild=mock_ctx.guild.id)

        character = Character.create(
            data={
                "first_name": str(uuid4()).split("-")[0],
                "last_name": "character",
                "nickname": "testy",
                "storyteller_character": False,
                "player_character": True,
            },
            char_class=1,
            guild=mock_ctx.guild.id,
            created_by=user,
            clan=1,
        )

        # WHEN the update_or_add method is called
        updates = {"first_name": "updated", "last_name": "updated", "nickname": "updated"}
        result = await self.char_svc.update_or_add(mock_ctx, character=character, data=updates)

        # THEN check the character is updated correctly
        assert result.data == IsPartialDict(
            first_name="updated",
            last_name="updated",
            nickname="updated",
            storyteller_character=False,
        )

    @pytest.mark.asyncio()
    async def test_update_or_add_two(self, mock_ctx):
        """Test update_or_add()."""
        user, _ = GuildUser.get_or_create(user=mock_ctx.author.id, guild=mock_ctx.guild.id)

        # GIVEN a storyteller character object
        character = Character.create(
            data={
                "first_name": str(uuid4()).split("-")[0],
                "last_name": "character",
                "nickname": "testy",
                "storyteller_character": True,
                "player_character": False,
            },
            char_class=1,
            guild=mock_ctx.guild.id,
            created_by=user,
            clan=1,
        )

        # WHEN the update_or_add method is called
        updates = {"first_name": "updated", "last_name": "updated", "nickname": "updated"}
        result = await self.char_svc.update_or_add(
            mock_ctx, character=character, data=updates, clan=2
        )

        # THEN check the character is updated correctly
        assert result.data == IsPartialDict(
            first_name="updated",
            last_name="updated",
            nickname="updated",
            storyteller_character=True,
        )
        assert result.clan == VampireClan.get_by_id(2)

    @pytest.mark.asyncio()
    @pytest.mark.skip("Can't get async mock to work for call to user_svc.fetch_user")
    async def test_update_or_add_three(self, mocker, mock_ctx):
        """Test update_or_add()."""
        # GIVEN a character that is not created
        name = str(uuid4()).split("-")[0]
        data = {
            "first_name": name,
            "new_key": "new_value",
        }
        user, _ = GuildUser.get_or_create(user=mock_ctx.author.id, guild=mock_ctx.guild.id)

        async def helper(value):
            return value

        mocked_fetch_user = AsyncMock(return_value=user)
        mocker.patch(
            "valentina.models.users.UserService.fetch_user",
            new=mocked_fetch_user,
        )

        # WHEN the update_or_add method is called
        result = await self.char_svc.update_or_add(mock_ctx, data=data, char_class=1, clan=1)

        # THEN check the character is created correctly with default values
        assert result.data == IsPartialDict(
            first_name=name,
            storyteller_character=False,
            experience=0,
            experience_total=0,
            new_key="new_value",
        )
        assert not result.data["last_name"]
        assert not result.data["nickname"]

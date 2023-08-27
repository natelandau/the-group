# type: ignore
"""Test the CharacterService class."""

from uuid import uuid4

import pytest
from dirty_equals import IsList, IsPartialDict

from valentina.models import CharacterService
from valentina.models.db_tables import (
    Character,
    CustomTrait,
    Trait,
    TraitCategory,
    TraitValue,
    VampireClan,
)
from valentina.utils import errors


@pytest.mark.usefixtures("mock_db")
class TestCharacterModel:
    """Test the character database model."""

    def test_character_add_custom_trait(self):
        """Test add_custom_trait()."""
        # GIVEN a Character object and a TraitCategory object
        character = Character.create(
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
        assert len(character.custom_traits) == 0
        category = TraitCategory.get_by_id(1)

        # WHEN the add_custom_trait method is called
        character.add_custom_trait("new_trait", "new description", category, 1, 5)

        # THEN check the custom trait is added correctly
        assert len(character.custom_traits) == 1
        assert character.custom_traits[0].name == "new_trait"
        assert character.custom_traits[0].description == "new description"
        assert character.custom_traits[0].category == category
        assert character.custom_traits[0].value == 1
        assert character.custom_traits[0].max_value == 5

        # WHEN the add_custom_trait method is called again with the same name
        # THEN raise a validation error
        with pytest.raises(errors.ValidationError):
            character.add_custom_trait("new_trait", "new description", category, 1, 5)

    def test_character_all_trait_values(self):
        """Test character.all_trait_values.

        Given a character with traits
        When character.all_trait_values is called
        Then all trait values are returned as a dictionary containing the appropriate tuple values
        """
        returned = Character.get_by_id(1).all_trait_values

        assert returned["Physical"] == [
            ("Strength", 1, 5, "●○○○○"),
            ("Dexterity", 2, 5, "●●○○○"),
            ("Stamina", 3, 5, "●●●○○"),
        ]
        assert returned["Skills"] == [("Test_Trait", 2, 5, "●●○○○")]

    def test_character_custom_traits(self):
        """Test character.custom_traits.

        Given a character with custom traits
        When character.custom_traits is called
        Then all custom traits are returned
        """
        returned = Character.get_by_id(1).custom_traits
        assert len(returned) == 1
        assert returned[0].name == "Test_Trait"

    def test_character_get_trait_value(self, mock_ctx):
        """Test character.get_trait_value()."""
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
        assert character.get_trait_value(custom_trait) == 4

        # WHEN the get_trait_value method is called with a Trait
        # THEN check the trait value is returned correctly
        assert character.get_trait_value(trait) == 2

        # WHEN the get_trait_value method is called with a TraitValue that does not exist
        # THEN return 0 for the value
        assert character.get_trait_value(TraitValue(trait=Trait.get_by_id(2))) == 0

    def test_character_set_trait_value(self, mock_ctx):
        """Test character.set_trait_value()."""
        # GIVEN a character with custom traits
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
        trait = Trait.get_by_id(1)

        # WHEN the set_trait_value method is called with a CustomTrait
        character.set_trait_value(custom_trait, 3)

        # THEN check the trait value is updated correctly
        assert custom_trait.value == 3

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

    def test_character_service_init(self):
        """test_character_service_init.

        GIVEN a CharacterService instance.
        WHEN the __init__ method is called
        THEN check the dictionaries are initialized correctly.
        """
        # Check that the dictionaries are initialized as empty dictionaries
        assert self.char_svc.character_cache == {}
        assert self.char_svc.storyteller_character_cache == {}

    def test_get_char_key(self):
        """Test get_char_key()."""
        # GIVEN a guild ID and a character ID
        guild_id = 123
        char_id = 456

        # WHEN the __get_char_key method is called
        # THEN check the correct key is generated
        assert (
            self.char_svc._CharacterService__get_char_key(guild_id, char_id)
            == f"{guild_id}_{char_id}"
        )

    def test_custom_section_update_or_add(self, mock_ctx):
        """Test custom_section_update_or_add()."""
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
        assert character.custom_sections == []

        # WHEN the custom_section_update_or_add method is called
        result = self.char_svc.custom_section_update_or_add(
            mock_ctx, character, "new", "new description"
        )

        # THEN check the custom section is added correctly
        assert character.custom_sections == IsList(length=1)
        assert result.title == "new"
        assert result.description == "new description"

        # WHEN the custom_section_update_or_add method is called again
        result = self.char_svc.custom_section_update_or_add(
            mock_ctx, character, "new2", "new description2"
        )

        # THEN check the custom section is updated correctly
        assert character.custom_sections == IsList(length=1)
        assert result.title == "new2"
        assert result.description == "new description2"

    def test_fetch_all_player_characters(self, caplog):
        """Test fetch_all_player_characters()."""
        # GIVEN two characters for a guild, with one in the cache
        guild_id = 123321
        character1 = Character.create(
            data={
                "first_name": str(uuid4()).split("-")[0],
                "last_name": "character",
                "nickname": "testy",
                "storyteller_character": False,
                "player_character": True,
            },
            char_class=1,
            guild=guild_id,
            created_by=1,
            clan=1,
        )
        character2 = Character.create(
            data={
                "first_name": str(uuid4()).split("-")[0],
                "last_name": "character",
                "nickname": "testy",
                "storyteller_character": False,
                "player_character": True,
            },
            char_class=1,
            guild=guild_id,
            created_by=1,
            clan=1,
        )
        self.char_svc.character_cache[f"{guild_id}_{character1.id}"] = character1

        # WHEN the fetch_all_player_characters method is called
        result = self.char_svc.fetch_all_player_characters(guild_id)
        returned = caplog.text

        # THEN check the method returns the correct characters from the cache and the database and updates the cache
        assert len(result) == 2
        assert result[0] == character1
        assert result[1] == character2
        assert "CACHE: Fetch 1 characters" in returned
        assert "DATABASE: Fetch 1 characters" in returned
        assert [
            character
            for key, character in self.char_svc.character_cache.items()
            if key.startswith(str(guild_id) + "_")
        ] == [character1, character2]

    def test_fetch_all_storyteller_characters(self, caplog):
        """Test fetch_all_storyteller_characters()."""
        # GIVEN two storyteller characters for a guild, with one in the cache
        guild_id = 123321
        character1 = Character.create(
            data={
                "first_name": str(uuid4()).split("-")[0],
                "last_name": "storyteller",
                "nickname": "1",
                "storyteller_character": True,
                "player_character": False,
            },
            char_class=1,
            guild=guild_id,
            created_by=1,
            clan=1,
        )
        character2 = Character.create(
            data={
                "first_name": str(uuid4()).split("-")[0],
                "last_name": "storyteller",
                "nickname": "2",
                "storyteller_character": True,
            },
            char_class=1,
            guild=guild_id,
            created_by=1,
            clan=1,
        )
        self.char_svc.storyteller_character_cache[guild_id] = [character1]

        # WHEN the fetch_all_storyteller_characters method is called
        result = self.char_svc.fetch_all_storyteller_characters(guild_id=guild_id)
        returned = caplog.text

        # THEN check the method returns the correct characters from the cache and the database and updates the cache
        assert result == [character1, character2]
        assert "CACHE: Fetch 1 StoryTeller characters" in returned
        assert "DATABASE: Fetch 1 StoryTeller characters" in returned
        assert self.char_svc.storyteller_character_cache[guild_id] == [character1, character2]

    def test_is_cached_character(self):
        """Test is_cached_character()."""
        # GIVEN a guild ID and a character ID
        guild_id = 123
        char_id = 456

        # WHEN the is_cached_character method is called
        # THEN check the method returns False
        assert self.char_svc.is_cached_character(guild_id, char_id) is False

        # GIVEN a guild ID, a character ID, and a character in the cache
        self.char_svc.character_cache[f"{guild_id}_{char_id}"] = "test"

        # WHEN the is_cached_character method is called with a guild ID and character ID
        # THEN check the method returns True
        assert self.char_svc.is_cached_character(guild_id, char_id) is True

        # WHEN the is_cached_character method is called with a character_key
        # THEN check the method returns True
        assert self.char_svc.is_cached_character(key=f"{guild_id}_{char_id}") is True

    def test_purge_cache(self, mock_ctx):
        """Test purge_cache()."""
        self.char_svc.character_cache = {}
        self.char_svc.storyteller_character_cache = {}

        # GIVEN a guild ID, a character ID, and a character in the cache
        for i in [1, 2]:
            self.char_svc.character_cache[f"{i}_{i}"] = "test"
            self.char_svc.storyteller_character_cache[i] = ["test1", "test2"]

        # WHEN the purge_cache method is called with a context object
        self.char_svc.purge_cache(mock_ctx)

        # THEN all caches are purged for the matching guild ID
        assert self.char_svc.character_cache == {"2_2": "test"}
        assert self.char_svc.storyteller_character_cache == {2: ["test1", "test2"]}

        # WHEN the purge_cache method is called without a context object
        self.char_svc.purge_cache()

        # THEN all caches are purged
        assert self.char_svc.character_cache == {}
        assert self.char_svc.storyteller_character_cache == {}

    def test_update_or_add_one(self, mock_ctx):
        """Test update_character()."""
        # GIVEN a character object that is in the cache
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
        self.char_svc.character_cache[f"{mock_ctx.guild.id}_{character.id}"] = character

        # WHEN the update_or_add method is called
        updates = {"first_name": "updated", "last_name": "updated", "nickname": "updated"}
        result = self.char_svc.update_or_add(mock_ctx, character=character, data=updates)

        # THEN check the character is updated correctly
        assert result.data == IsPartialDict(
            first_name="updated",
            last_name="updated",
            nickname="updated",
            storyteller_character=False,
        )
        assert f"{mock_ctx.guild.id}_{character.id}" not in self.char_svc.character_cache

    def test_update_or_add_two(self, mock_ctx):
        """Test update_or_add()."""
        # GIVEN a storyteller character object that is in the cache
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
            created_by=mock_ctx.author.id,
            clan=1,
        )
        self.char_svc.storyteller_character_cache[mock_ctx.guild.id] = [character]

        # WHEN the update_or_add method is called
        updates = {"first_name": "updated", "last_name": "updated", "nickname": "updated"}
        result = self.char_svc.update_or_add(mock_ctx, character=character, data=updates, clan=2)

        # THEN check the character is updated correctly
        assert result.data == IsPartialDict(
            first_name="updated",
            last_name="updated",
            nickname="updated",
            storyteller_character=True,
        )
        assert result.clan == VampireClan.get_by_id(2)
        assert mock_ctx.guild.id not in self.char_svc.storyteller_character_cache

    def test_update_or_add_three(self, mock_ctx):
        """Test update_or_add()."""
        # GIVEN a character that is not created and items in the cache
        self.char_svc.character_cache[f"{mock_ctx.guild.id}_999"] = "test"
        name = str(uuid4()).split("-")[0]
        data = {
            "first_name": name,
            "new_key": "new_value",
        }

        # WHEN the update_or_add method is called
        result = self.char_svc.update_or_add(mock_ctx, data=data, char_class=1, clan=1)

        # THEN check the character is created correctly with default values and the cache is cleared
        assert self.char_svc.character_cache == {}
        assert result.data == IsPartialDict(
            first_name=name,
            storyteller_character=False,
            experience=0,
            experience_total=0,
            new_key="new_value",
        )
        assert not result.data["last_name"]
        assert not result.data["nickname"]

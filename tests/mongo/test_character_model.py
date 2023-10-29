# type: ignore
"""Test the mongodb character model."""

import pytest
from rich import print

from valentina.constants import CharacterConcept, CharClass, HunterCreed, TraitCategory, VampireClan
from valentina.models.mongo_collections import Character, CharacterTrait
from valentina.utils import errors


async def test_create_new(create_user):
    """Test creating a new character."""
    # GIVEN a user
    user = await create_user()

    # WHEN creating a user
    character = Character(
        name_first="John",
        name_last="Doe",
        guild=1234567890,
        char_class_name="MORTAL",
        concept_name="SOLDIER",
        type_player=True,
        user_creator=user.id,
        user_owner=user.id,
        clan_name="BRUJAH",
        creed_name="AVENGER",
    )
    await character.insert()

    # THEN default values are set
    assert character.name_first == "John"
    assert character.traits == []
    assert character.sheet_sections == []
    assert character.images == []
    assert character.freebie_points == 0
    assert not character.type_storyteller

    # AND the computed properties are correct
    assert character.name == "John Doe"
    assert character.full_name == "John Doe"
    assert character.char_class == CharClass.MORTAL
    assert character.concept == CharacterConcept.SOLDIER
    assert character.clan == VampireClan.BRUJAH
    assert character.creed == HunterCreed.AVENGER


async def test_custom_enum_names(create_user):
    """Test creating a character with custom enum names."""
    # GIVEN a user
    user = await create_user()

    # WHEN creating a user
    character = Character(
        name_first="John",
        name_last="Doe",
        guild=1234567890,
        char_class_name="not a mortal",
        concept_name="not a concept",
        type_player=True,
        user_creator=user.id,
        user_owner=user.id,
        clan_name="not a clan",
        creed_name="not a creed",
    )
    await character.insert()

    # THEN don't return enum values when calling enum properties
    assert character.concept is None
    assert character.clan is None
    assert character.creed is None
    with pytest.raises(errors.NoCharacterClassError):
        assert character.char_class


async def test_full_name(create_user):
    """Test the full_name computed property."""
    # GIVEN a character
    user = await create_user()
    character = Character(
        name_first="John",
        name_last="Doe",
        guild=1234567890,
        char_class_name="MORTAL",
        user_creator=user.id,
        user_owner=user.id,
    )
    await character.insert()

    # WHEN the full_name property is accessed with no nickname
    # THEN the correct value is returned
    assert character.full_name == "John Doe"

    # WHEN the full_name property is accessed with a nickname
    character.name_nick = "JD"
    await character.save()

    # THEN the correct value is returned
    assert character.full_name == "John 'JD' Doe"


async def test_fetch_owner(create_character):
    """Test the fetch_owner method."""
    # GIVEN a character
    character = await create_character()

    # WHEN fetching the owner
    owner = await character.fetch_owner()

    # THEN the correct user is returned
    assert owner.id == character.user_owner


async def test_add_custom_trait(create_character):
    """Test the add_trait method."""
    # GIVEN a character
    character = await create_character(no_traits=True)

    # WHEN adding a trait
    trait = await character.add_trait(TraitCategory.BACKGROUNDS, "Something", 3, 5)

    # THEN the trait is added to the character
    assert len(character.traits) == 1
    assert character.traits[0] == trait

    # AND the trait is saved to the database
    all_traits = await CharacterTrait.find_all().to_list()
    assert len(all_traits) == 1
    assert all_traits[0].name == "Something"
    assert all_traits[0].value == 3
    assert all_traits[0].max_value == 5
    assert all_traits[0].category_name == TraitCategory.BACKGROUNDS.name
    assert all_traits[0].character == str(character.id)
    assert all_traits[0].is_custom


async def test_add_trait(create_character):
    """Test the add_trait method."""
    # GIVEN a character
    character = await create_character(no_traits=True)

    # WHEN adding a trait that exists in TraitCategory enum
    trait = await character.add_trait(TraitCategory.PHYSICAL, "Strength", 2, 10)

    # THEN the trait is added to the character
    assert len(character.traits) == 1
    assert character.traits[0] == trait

    # AND the trait is saved to the database
    # With the max_value reset to the enum defaults
    all_traits = await CharacterTrait.find_all().to_list()
    assert len(all_traits) == 1
    assert all_traits[0].name == "Strength"
    assert all_traits[0].value == 2
    assert all_traits[0].max_value == 5
    assert all_traits[0].category_name == TraitCategory.PHYSICAL.name
    assert all_traits[0].character == str(character.id)
    assert not all_traits[0].is_custom


async def test_add_trait_already_exists(create_character):
    """Test the add_trait method."""
    # GIVEN a character
    character = await create_character()

    # WHEN adding a trait that already exists on the character
    # THEN a TraitExistsError is raised
    with pytest.raises(errors.TraitExistsError):
        await character.add_trait(TraitCategory.PHYSICAL, "Strength", 2, 10)
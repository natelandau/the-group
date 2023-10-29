"""Trait database models and services.

Note, due to ForeignKey constraints, the trait database models are defined in database.py.
"""

from itertools import chain

import discord
from loguru import logger
from peewee import DoesNotExist, fn

from valentina.constants import CharClass, TraitCategory
from valentina.utils import errors

from .sqlite_models import Character, CharacterClass, CustomTrait, Trait, TraitCategory, TraitClass


class TraitService:
    """Manage traits and custom traits and maintain an in-memory cache."""

    def __init__(self) -> None:
        self.class_traits: dict[str, list[Trait]] = {}  # {class: [traits]}

    @staticmethod
    def fetch_all_traits(
        guild_id: int, flat_list: bool = False
    ) -> dict[str, list[str]] | list[str]:
        """Retrieve all traits for a given guild, both common and custom.

        Use the 'guild_id' to identify the guild for which to fetch traits. If 'flat_list'
        is True, return a flat list of traits instead of a categorized dictionary.

        Args:
            guild_id (int): Specify the guild for which to fetch traits.
            flat_list (bool, optional): If True, return a flat list of traits. Defaults to False.

        Returns:
            dict[str, list[str]] | list[str]: Return a dictionary of categories with associated traits or a flat list of traits if 'flat_list' is True.
        """
        # Prefetch traits for categories
        categories = TraitCategory.select().order_by(TraitCategory.name.asc()).prefetch(Trait)
        all_traits: dict[str, list[str]] = {
            category.name: sorted(trait.name for trait in category.traits)
            for category in categories
        }

        custom_traits = CustomTrait.select().join(Character).where(Character.guild_id == guild_id)
        for custom_trait in custom_traits:
            category = custom_trait.category.name
            all_traits.setdefault(category, [])
            all_traits[category].append(custom_trait.name)

        if flat_list:
            # Flatten the dictionary into a list using itertools.chain
            return sorted(set(chain.from_iterable(all_traits.values())))

        return all_traits

    def fetch_all_class_traits(self, char_class: CharClass) -> list[Trait]:
        """Fetch all traits for a specified character class.

        Checks if the traits for the character class are already cached.
        If they are, it logs this and returns the cached traits.
        If the traits are not cached, it logs this, retrieves the traits from the database,
        sorts them by the `TraitCategory[].value["order"]`, caches them, and then returns the traits.

        Args:
            char_class (CharClass): Name of the character class to fetch traits for.

        Returns:
            list[Trait]: List of traits for the specified character class, sorted by `TraitCategory[].value["order"]`.
        """
        # Guard clause: return cached traits if they exist
        if char_class.name in self.class_traits:
            logger.debug(f"CACHE: Return traits for `{char_class.name}`")
            return self.class_traits[char_class.name]

        logger.debug(f"DATABASE: Fetch all traits for `{char_class.name}`")

        traits = (
            Trait.select()
            .join(TraitClass)
            .join(CharacterClass)
            .where(CharacterClass.name == char_class.name)
        )

        self.class_traits[char_class.name] = sorted(
            traits, key=lambda x: TraitCategory[x.category.name].value["order"]
        )

        return self.class_traits[char_class.name]

    @staticmethod
    def fetch_trait_id_from_name(trait_name: str) -> int:
        """Fetch the ID of a trait from the database using the trait's name.

        Use case-insensitive search to find the trait by its name.
        If the trait is found, the trait's ID is returned.

        Args:
            trait_name (str): Name of the trait to fetch the ID for.

        Returns:
            int: The ID of the trait if found.

        Raises:
            NoMatchingItemsError: If the trait with the given name does not exist.
        """
        logger.debug(f"DATABASE: Fetch trait ID for `{trait_name}`")

        try:
            trait = Trait.get(fn.lower(Trait.name) == trait_name.lower())
        except DoesNotExist as e:
            msg = f"Trait `{trait_name}` not found"
            raise errors.NoMatchingItemsError(msg) from e
        else:
            return trait.id

    @staticmethod
    def fetch_trait_from_name(trait_name: str) -> Trait:
        """Retrieve a trait from the database based on the provided trait name.

        Perform a case-insensitive search for the trait using its name.
        If the trait is found, return the corresponding trait object.

        Args:
            trait_name (str): The name of the trait to retrieve.

        Returns:
            Trait: The trait object corresponding to the provided name.

        Raises:
            NoMatchingItemsError: If a trait with the given name does not exist in the database.
        """
        logger.debug(f"DATABASE: Fetch trait `{trait_name}`")

        try:
            return Trait.get(fn.lower(Trait.name) == trait_name.lower())
        except DoesNotExist as e:
            msg = f"Trait `{trait_name}` not found"
            raise errors.NoMatchingItemsError(msg) from e

    def purge_cache(self, ctx: discord.ApplicationContext | None = None) -> None:  # noqa: ARG002
        """Purge the cache."""
        logger.debug("CACHE: Purge traits cache")
        self.class_traits = {}

"""Helper functions for managing the database."""
from datetime import datetime, timezone

from loguru import logger

from valentina import DATABASE
from valentina.models import (
    Character,
    CharacterClass,
    CustomTrait,
    Guild,
    GuildUser,
    User,
    UserCharacter,
)
from valentina.models.constants import CharClass


def create_tables() -> None:
    """Create the database instance and tables."""
    with DATABASE:
        DATABASE.create_tables(
            [Guild, CharacterClass, Character, CustomTrait, User, GuildUser, UserCharacter]
        )

    logger.info("DATABASE: Create Tables")
    populate_enum_tables()


def populate_enum_tables() -> None:
    """Populate the database with enums."""
    for char_class in CharClass:
        CharacterClass.get_or_create(name=char_class.value)
    logger.info("DATABASE: Populate Enums")


def update_guild_last_connected(guild_id: int, guild_name: str) -> None:
    """Update the last connected timestamp for a guild."""
    db_id, is_created = Guild.get_or_create(
        id=guild_id,
        defaults={
            "id": guild_id,
            "name": guild_name,
            "first_seen": datetime.now(timezone.utc).replace(microsecond=0),
            "last_connected": datetime.now(timezone.utc).replace(microsecond=0),
        },
    )
    if is_created:
        logger.info(f"DATABASE: Create guild {db_id.name}")
    if not is_created:
        Guild.set_by_id(
            db_id, {"last_connected": datetime.now(timezone.utc).replace(microsecond=0)}
        )
        logger.info(f"DATABASE: Update '{db_id.name}'")

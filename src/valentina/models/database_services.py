"""Models for maintaining in-memory caches of database queries."""

import re

import discord
from loguru import logger
from peewee import DoesNotExist, ModelSelect, SqliteDatabase
from semver import Version

from valentina.__version__ import __version__
from valentina.models.constants import CharClass
from valentina.models.database import (
    Character,
    CharacterClass,
    CustomTrait,
    DatabaseVersion,
    DiceBinding,
    Guild,
    GuildUser,
    User,
    UserCharacter,
    time_now,
)
from valentina.utils.errors import (
    CharacterClaimedError,
    CharacterNotFoundError,
    NoClaimError,
    UserHasClaimError,
)
from valentina.utils.helpers import normalize_row


class CharacterService:
    """A service for managing the Character Manager cache/in-memory database."""

    def __init__(self) -> None:
        """Initialize the CharacterService."""
        # Caches to avoid database queries
        ##################################
        self.characters: dict[str, Character] = {}  # {char_key: Character, ...}
        self.claims: dict[str, str] = {}  # {claim_key: char_key}

    @staticmethod
    def __get_char_key(guild_id: int, char_id: int) -> str:
        """Generate a key for the character cache.

        Args:
            guild_id (int): The guild to get the ID for.
            char_id (int): The character database ID

        Returns:
            str: The guild and character IDs joined by an underscore.
        """
        return f"{guild_id}_{char_id}"

    @staticmethod
    def __get_claim_key(guild_id: int, user_id: int) -> str:
        """Generate a key for the claim cache.

        Args:
            guild_id (int): The guild ID
            user_id (int): The user database ID

        Returns:
            str: The guild and user IDs joined by an underscore.
        """
        return f"{guild_id}_{user_id}"

    def purge_all(self) -> None:
        """Purge all caches."""
        logger.debug("CACHE: Purging all character caches")
        self.characters = {}
        self.claims = {}

    def purge_by_id(self, guild_id: int = None, char_id: int = None, key: str = None) -> None:
        """Purge a single character from the cache by ID."""
        key = self.__get_char_key(guild_id, char_id) if key is None else key
        logger.debug(f"CACHE: Purge character {key} from cache")
        self.characters.pop(key, None)

    def is_cached_char(self, guild_id: int = None, char_id: int = None, key: str = None) -> bool:
        """Check if the user is in the cache."""
        key = self.__get_char_key(guild_id, char_id) if key is None else key
        return key in self.characters

    def fetch_all(self, guild_id: int) -> ModelSelect:
        """Returns all characters for a specific guild. Checks the cache first and then the database. If characters are found in the database, they are added to the cache.

        Args:
            guild_id (int): The discord guild id to fetch characters for.

        Returns:
            ModelSelect: A peewee ModelSelect object representing all the characters for the guild.
        """
        cached_ids = []
        chars_to_return = []
        for key, character in self.characters.items():
            if key.startswith(str(guild_id)):
                cached_ids.append(character.id)
                chars_to_return.append(character)
        logger.debug(f"CACHE: Fetch {len(chars_to_return)} characters")

        characters = Character.select().where(
            (Character.guild_id == guild_id)  # grab only characters for the guild
            & ~(Character.id.in_(cached_ids))  # grab only characters not in cache
        )
        if len(characters) > 0:
            logger.info(f"DATABASE: Fetch {len(characters)} characters")
        else:
            logger.debug("DATABASE: No characters to fetch")

        for character in characters:
            self.characters[self.__get_char_key(guild_id, character.id)] = character
            chars_to_return.append(character)

        return chars_to_return

    def fetch_by_id(self, guild_id: int, char_id: int) -> Character:
        """Fetch a character by database id.

        Args:
            char_id (int): The database id of the character.
            guild_id (int): The discord guild id to fetch characters for.

        Returns:
            Character: The character object.
        """
        key = self.__get_char_key(guild_id, char_id)
        if self.is_cached_char(key=key):
            logger.debug(f"CACHE: Fetched character {char_id}")
            return self.characters[key]

        character = Character.get_by_id(char_id)

        self.characters[key] = character
        logger.info(f"DATABASE: Fetched character: {character.first_name}")
        return character

    def add_claim(self, guild_id: int, char_id: int, user_id: int) -> bool:
        """Claim a character for a user."""
        char_key = self.__get_char_key(guild_id, char_id)
        claim_key = self.__get_claim_key(guild_id, user_id)

        if claim_key in self.claims:
            if self.claims[claim_key] == char_key:
                return True

            logger.debug(f"CLAIM: User {user_id} already has a claim")
            raise UserHasClaimError(f"User {user_id} already has a claim")

        if any(char_key == claim for claim in self.claims.values()):
            logger.debug(f"CLAIM: Character {char_id} is already claimed")
            raise CharacterClaimedError(f"Character {char_id} is already claimed")

        self.claims[claim_key] = char_key
        return True

    def remove_claim(self, guild_id: int, user_id: int) -> bool:
        """Remove a claim from a user."""
        claim_key = self.__get_claim_key(guild_id, user_id)
        if claim_key in self.claims:
            logger.debug(f"CLAIM: Removing claim for user {user_id}")
            del self.claims[claim_key]
            return True
        return False

    def user_has_claim(self, guild_id: int, user_id: int) -> bool:
        """Check if a user has a claim."""
        claim_key = self.__get_claim_key(guild_id, user_id)
        return claim_key in self.claims

    def is_char_claimed(self, guild_id: int, char_id: int) -> bool:
        """Check if a character is claimed by any user."""
        char_key = self.__get_char_key(guild_id, char_id)
        return any(char_key == claim for claim in self.claims.values())

    def get_user_of_character(self, guild_id: int, char_id: int) -> int:
        """Returns the user id of the user who claimed a character."""
        if self.is_char_claimed(guild_id, char_id):
            char_key = self.__get_char_key(guild_id, char_id)
            for claim_key, claim in self.claims.items():
                if claim == char_key:
                    user_id = re.sub(r"\d\w+_", "", claim_key)
                    return int(user_id)
            return None
        return None

    def fetch_claim(self, guild_id: int, user_id: int) -> Character:
        """Fetch the character claimed by a user."""
        claim_key = self.__get_claim_key(guild_id, user_id)
        if claim_key in self.claims:
            char_key = self.claims[claim_key]

            if self.is_cached_char(key=char_key):
                logger.debug(f"CACHE: Fetched character {char_key}")
                return self.characters[char_key]

            char_id = re.sub(r"\d\w+_", "", char_key)
            character = self.fetch_by_id(guild_id, int(char_id))
            return character

        raise NoClaimError(f"User {user_id} has no claim")

    def update_char(self, guild_id: int, char_id: int, **kwargs: str | int) -> Character:
        """Update a character in the cache and database."""
        key = self.__get_char_key(guild_id, char_id)

        # Normalize kwargs keys to database column names
        kws = {normalize_row(k): v for k, v in kwargs.items()}

        if key in self.characters:
            character = self.characters[key]
            self.purge_by_id(key=key)
        else:
            try:
                character = Character.get_by_id(char_id)
            except DoesNotExist as e:
                raise CharacterNotFoundError(f"Character {char_id} was not found") from e

        Character.update(modified=time_now(), **kws).where(Character.id == character.id).execute()

        logger.debug(f"DATABASE: Update character: {char_id}")
        return character


class UserService:
    """User manager and in-memory cache."""

    def __init__(self) -> None:
        """Initialize the UserService."""
        self.users: dict[str, User] = {}  # {user_key: User, ...}

    @staticmethod
    def __get_key(guild_id: int, user_id: int) -> str:
        """Get the guild and user IDs.

        Args:
            guild_id (discord.Guild | int): The guild to get the ID for.
            user_id (discord.User | int): The user to get the ID for.

        Returns:
            str: The guild and user IDs joined by an underscore.
        """
        return f"{guild_id}_{user_id}"

    def purge(self) -> None:
        """Purge cache of all users."""
        self.users = {}

    def is_cached(self, guild_id: int, user_id: int) -> bool:
        """Check if the user is in the cache."""
        key = self.__get_key(guild_id, user_id)

        if key in self.users:
            return True

        return False

    def is_in_db(self, guild_id: int, user_id: int) -> bool:
        """Check if the user is in the database."""
        in_user_table = False
        in_guild_user_table = False

        if User.select().where(User.id == user_id).exists():
            in_user_table = True

        if (
            GuildUser.select()
            .where((GuildUser.guild_id == guild_id) & (GuildUser.user_id == user_id))
            .exists()
        ):
            in_guild_user_table = True

        if in_user_table and in_guild_user_table:
            return True

        return False

    def fetch(self, guild_id: int, user_id: int) -> User:
        """Fetch a user object from the cache or database."""
        key = self.__get_key(guild_id, user_id)

        if self.is_cached(guild_id, user_id):
            logger.info(f"CACHE: Returning user {key} from cache")
            return self.users[key]

        if self.is_in_db(guild_id, user_id):
            user = User.get_by_id(user_id)
            user.last_seen = time_now()
            user.save()
            self.users[key] = user
            logger.info(f"CACHE: Returning user {key} from the database and caching")
            return user

        logger.error(f"DATABASE: User {key} does not exist in database or the cache.")
        raise ValueError(f"User {key} does not exist in database or the cache.")

    def create(self, guild_id: int, user: discord.User | discord.Member) -> User:
        """Create a new user in the database and cache."""
        print(f"Creating user {user.id}-{user.name}")
        existing_user = User.get_or_none(id=user.id)
        if existing_user is None:
            logger.info(f"DATABASE: Created user {user.id} in database")
            new_user = User.create(id=user.id, username=user.name)
        else:
            new_user = User.get_by_id(user.id)

        existing_guild_user = GuildUser.get_or_none(guild_id=guild_id, user_id=user.id)
        if existing_guild_user is None:
            logger.info(f"DATABASE: Create guild_user lookup for user:{user.id} guild:{guild_id}")
            GuildUser.create(guild_id=guild_id, user_id=user.id)

        key = self.__get_key(guild_id, user.id)
        self.users[key] = new_user

        return new_user


class GuildService:
    """Manage guilds in the database. Guilds are created a bot_connect,."""

    def __init__(self) -> None:
        """Initialize the GuildService."""
        self.guilds: dict[int, Guild] = {}

    @staticmethod
    def is_in_db(guild_id: int) -> bool:
        """Check if the guild is in the database."""
        return Guild.select().where(Guild.id == guild_id).exists()

    @staticmethod
    def update_or_add(guild_id: int, guild_name: str) -> None:
        """Add a guild to the database or update it if it already exists."""
        db_id, is_created = Guild.get_or_create(
            id=guild_id,
            defaults={
                "id": guild_id,
                "name": guild_name,
                "first_seen": time_now(),
                "last_connected": time_now(),
            },
        )
        if is_created:
            logger.info(f"DATABASE: Create guild {db_id.name}")
        if not is_created:
            Guild.set_by_id(db_id, {"last_connected": time_now()})
            logger.info(f"DATABASE: Update '{db_id.name}'")


class DatabaseService:
    """Representation of the database."""

    def __init__(self, database: SqliteDatabase) -> None:
        """Initialize the DatabaseService."""
        self.db = database

    def create_new_db(self) -> None:
        """Create all tables in the database."""
        with self.db:
            self.db.create_tables(
                [
                    Guild,
                    CharacterClass,
                    Character,
                    CustomTrait,
                    User,
                    GuildUser,
                    UserCharacter,
                    DiceBinding,
                    DatabaseVersion,
                ]
            )
        logger.info("DATABASE: Create Tables")
        logger.debug(f"DATABASE: {self.get_tables()}")

        # Populate default values
        for char_class in CharClass:
            CharacterClass.get_or_create(name=char_class.value)
        logger.info("DATABASE: Populate Enums")

        # Log version number
        DatabaseVersion.create(version=__version__)

    def get_tables(self) -> list[str]:
        """Get all tables in the Database."""
        with self.db:
            cursor = self.db.execute_sql("SELECT name FROM sqlite_master WHERE type='table';")
            return [row[0] for row in cursor.fetchall()]

    def requires_migration(self) -> bool:
        """Determine if the database requires a migration."""
        bot_version = Version.parse(__version__)
        db_version = Version.parse(DatabaseVersion.get().version)
        if bot_version > db_version:
            logger.warning(f"DATABASE: Database version {db_version} is outdated.")
            return True

        logger.debug(f"DATABASE: Database version {db_version} is up to date.")
        return True

"""When a new database is created, this file is used to populate it with the initial data.

IMPORTANT notes about Populating the Database:
    - Adding new data should be fine in an existing database
    - Updating existing data must be handled in the MigrateDatabase class
    - Deleting data must be handled in the MigrateDatabase class
"""

import json

from loguru import logger
from peewee import IntegrityError, TextField
from playhouse.migrate import SqliteMigrator, migrate
from playhouse.sqlite_ext import CSqliteExtDatabase, JSONField
from semver import Version

from valentina.constants import CharClassType, TraitCategories, VampireClanType
from valentina.models.db_tables import (
    Campaign,
    CampaignNote,
    Character,
    CharacterClass,
    CustomSection,
    CustomTrait,
    Guild,
    GuildUser,
    Macro,
    RollStatistic,
    RollThumbnail,
    Trait,
    TraitCategory,
    TraitCategoryClass,
    TraitClass,
    TraitValue,
    VampireClan,
)


class MigrateDatabase:
    """A class that handles migrating an existing database."""

    def __init__(self, db: CSqliteExtDatabase, bot_version: str, db_version: str) -> None:
        self.db = db
        self.bot_version = bot_version
        self.db_version = db_version

    def migrate(self) -> None:
        """Migrate the database to the latest version.

        Checks the current database version and applies migration functions
        to update it to the latest version.

        Returns:
            None
        """
        logger.debug("DATABASE: Migration check")

        # Define a mapping of version numbers to migration functions
        migrations = {
            "0.8.2": self.__0_8_2,
            "0.12.0": self.__0_12_0,
            "1.0.2": self.__1_0_2,
            "1.0.3": self.__1_0_3,
            "1.1.0": self.__1_1_0,
            "1.1.5": self.__1_1_5,
            "1.3.0": self.__1_3_0,
            "1.4.1": self.__1_4_1,
            "1.5.0": self.__1_5_0,
            "1.8.0": self.__1_8_0,
            "1.11.0": self.__1_11_0,
        }

        current_version = Version.parse(self.db_version)

        for version, migration_func in migrations.items():
            if current_version <= Version.parse(version):
                logger.warning(f"DATABASE: Migrate database from v{version}")
                migration_func()

    def _column_exists(self, table: str, column: str) -> bool:
        """Check if a column exists in a table.

        Args:
            table (str): The table to check.
            column (str): The column to check.

        Returns:
            bool: Whether the column exists in the table.
        """
        db = self.db
        cursor = db.execute_sql(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        return column in columns

    def _drop_and_recreate(self, table_name: str, db_model: type) -> None:
        """Migrate a specific table.

        Args:
            table_name: The name of the table to migrate.
            db_model: The Peewee model class for the table.
        """
        logger.debug(f"DATABASE: drop and recreate `{table_name}` table")
        self.db.execute_sql("PRAGMA foreign_keys=OFF;")
        self.db.execute_sql(f"DROP TABLE {table_name};")
        self.db.execute_sql("PRAGMA foreign_keys=ON;")
        self.db.create_tables([db_model])

    def get_tables(self) -> list[str]:
        """Get all tables in the Database."""
        with self.db:
            cursor = self.db.execute_sql("SELECT name FROM sqlite_master WHERE type='table';")
            return [row[0] for row in cursor.fetchall()]

    def __0_8_2(self) -> None:
        """Migrate from database from v0.8.2."""
        logger.info("DATABASE: Migrate database to v0.8.2")
        self.db.execute_sql("ALTER TABLE characters ADD COLUMN security INTEGER DEFAULT 0;")

    def __0_12_0(self) -> None:  # noqa: C901, PLR0912
        """Migration from db v0.12.0."""
        logger.info("DATABASE: Migrate database from v0.12.0")

        # Update Trait values
        if "character_traits" in self.get_tables():
            logger.debug("DATABASE: Migrate trait values")
            tvs = {}
            for row in TraitValue.select():
                tvs[row.id] = {
                    "char": row.character_id,
                    "trait": row.trait_id,
                    "value": row.value,
                    "modified": row.modified,
                }
                row.delete_instance()

            for key, value in tvs.items():
                old_name = self.db.execute_sql(
                    "SELECT name FROM character_traits WHERE id =  ?;", (value["trait"],)
                ).fetchone()[0]

                if old_name.lower() == "larceny":
                    tvs[key]["new_id"] = "DROP"
                    continue

                new_trait = Trait.get_or_none(name=old_name)
                if not new_trait:
                    logger.debug(f"Trait {old_name} no longer exists. Dropping.")
                    tvs[key]["new_id"] = "DROP"
                    continue

                tvs[key]["new_id"] = new_trait.id

            self.db.execute_sql("DROP TABLE character_traits;")
            self.db.execute_sql("DROP TABLE trait_values;")

            # Now we can create the new table and insert the values
            with self.db:
                self.db.create_tables([TraitValue])

            for value in sorted(tvs.values(), key=lambda x: x["char"]):
                if value["new_id"] == "DROP":
                    continue

                character_class = Character.get(id=value["char"]).char_class
                if (
                    not TraitClass.get_or_none(
                        trait_id=value["new_id"], character_class=character_class
                    )
                    and value["value"] == 0
                ):
                    continue

                if not TraitValue.get_or_none(
                    character=value["char"], trait=value["new_id"], value=value["value"]
                ):
                    TraitValue.create(
                        character=value["char"],
                        trait=value["new_id"],
                        value=value["value"],
                        modified=value["modified"],
                    )
                else:
                    logger.debug(
                        f"Skip duplicate trait value for {Trait.get(id=value['new_id']).name} on {Character.get(id=value['char']).name}"
                    )

        # Update Custom Sections
        if self._column_exists("custom_sections", "guild_id"):
            logger.debug("DATABASE: Migrate custom sections")

            cursor = self.db.execute_sql("SELECT * FROM custom_sections;").fetchall()

            self.db.execute_sql("DROP TABLE custom_sections;")

            with self.db:
                self.db.create_tables([CustomSection])

            for _id, char, created, modified, description, _guild, title in cursor:
                CustomSection.create(
                    character=Character.get(id=char),
                    created=created,
                    modified=modified,
                    description=description,
                    title=title,
                )

        # Update Custom Traits
        if self._column_exists("custom_traits", "category"):
            logger.debug("DATABASE: Migrate custom traits")

            cursor = self.db.execute_sql("SELECT * FROM custom_traits;").fetchall()

            self.db.execute_sql("DROP TABLE custom_traits;")
            with self.db:
                self.db.create_tables([CustomTrait])

            for (
                _id,
                char,
                created,
                modified,
                description,
                _guild,
                name,
                category,
                value,
                max_value,
            ) in cursor:
                CustomTrait.create(
                    character=Character.get(id=char),
                    created=created,
                    modified=modified,
                    description=description,
                    name=name,
                    category=TraitCategory.get(name=category),
                    value=value,
                    max_value=max_value,
                )

        if self._column_exists("macros", "trait_one"):
            logger.debug("DATABASE: Migrate macros")
            self.db.execute_sql("DROP TABLE macros;")
            with self.db:
                self.db.create_tables([Macro])

    def __1_0_2(self) -> None:
        """Migrate from version 1.0.2."""
        if not self._column_exists(Character._meta.table_name, "generation"):
            logger.info("DATABASE: Migrate database from v1.0.2")
            migrator = SqliteMigrator(self.db)

            # Fields to add
            generation = TextField(null=True)
            sire = TextField(null=True)
            breed = TextField(null=True)
            tribe = TextField(null=True)
            auspice = TextField(null=True)
            essence = TextField(null=True)
            tradition = TextField(null=True)

            migrate(
                migrator.add_column(Character._meta.table_name, "generation", generation),
                migrator.add_column(Character._meta.table_name, "sire", sire),
                migrator.add_column(Character._meta.table_name, "breed", breed),
                migrator.add_column(Character._meta.table_name, "tribe", tribe),
                migrator.add_column(Character._meta.table_name, "auspice", auspice),
                migrator.add_column(Character._meta.table_name, "essence", essence),
                migrator.add_column(Character._meta.table_name, "tradition", tradition),
            )

    def __1_0_3(self) -> None:
        """Migrate from version 1.0.3."""
        if not self._column_exists(
            Guild._meta.table_name,
            "trait_permissions",
        ) or not self._column_exists(
            Guild._meta.table_name,
            "xp_permissions",
        ):
            logger.info("DATABASE: Migrate database from v1.0.3")

        if not self._column_exists(Guild._meta.table_name, "trait_permissions"):
            logger.debug("DATABASE: Add trait_permissions column")
            self.db.execute_sql(
                "ALTER TABLE guilds ADD COLUMN trait_permissions INTEGER DEFAULT 0;"
            )

        if not self._column_exists(Guild._meta.table_name, "xp_permissions"):
            logger.debug("DATABASE: Add xp_permissions column")
            self.db.execute_sql("ALTER TABLE guilds ADD COLUMN xp_permissions INTEGER DEFAULT 0;")

    def __1_1_0(self) -> None:
        """Migrate from version 1.1.0."""
        if not self._column_exists(Character._meta.table_name, "date_of_birth"):
            logger.info("DATABASE: Migrate database from v1.1.0")

            self.db.execute_sql(
                "ALTER TABLE characters ADD COLUMN date_of_birth DATETIME DEFAULT NULL;"
            )

            self.db.execute_sql(
                "ALTER TABLE chronicles ADD COLUMN current_date DATETIME DEFAULT NULL;"
            )

    def __1_1_5(self) -> None:
        """Migrate from version 1.1.5."""
        if not self._column_exists(Character._meta.table_name, "storyteller_character"):
            logger.debug("DATABASE: create characters:storyteller_character column")
            self.db.execute_sql(
                f"ALTER TABLE {Character._meta.table_name} ADD COLUMN storyteller_character INTEGER DEFAULT 0;"
            )

        if not self._column_exists(Guild._meta.table_name, "data"):
            # Grab the old data and add it to a dictionary to be migrated
            cursor = self.db.execute_sql("SELECT * FROM guilds;").fetchall()
            migration_data = {}

            for (
                guild_id,
                _name,
                _created,
                modified,
                log_channel_id,
                use_audit_log,
                trait_permissions,
                xp_permissions,
            ) in cursor:
                migration_data[guild_id] = {
                    "modified": str(modified),
                    "log_channel_id": log_channel_id,
                    "use_audit_log": use_audit_log,
                    "trait_permissions": trait_permissions,
                    "xp_permissions": xp_permissions,
                    "use_storyteller_channel": 0,
                    "storyteller_channel_id": None,
                }
            logger.debug("DATABASE: grab old Guild data")

            # Disable foreign keys
            self.db.execute_sql("PRAGMA foreign_keys=OFF;")

            # Create new table
            self.db.execute_sql(
                """
                CREATE TABLE new_guilds (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    created DATETIME NOT NULL
                );
            """
            )

            # Copy data from old table to new table
            self.db.execute_sql(
                """
                INSERT INTO new_guilds (id, name, created)
                SELECT id, name, created
                FROM guilds;
            """
            )

            # Drop old table
            self.db.execute_sql("DROP TABLE guilds;")

            # Rename new table to old table name
            self.db.execute_sql("ALTER TABLE new_guilds RENAME TO guilds;")

            # Re-enable foreign keys
            self.db.execute_sql("PRAGMA foreign_keys=ON;")

            logger.debug("DATABASE: complete initial Guild migration")

            # Add the data column
            self.db.execute_sql(f"ALTER TABLE {Guild._meta.table_name} ADD COLUMN data JSON;")
            logger.debug("DATABASE: add Guild data column")

            for guild, data in migration_data.items():
                json_object = json.dumps(data)
                self.db.execute_sql(
                    "UPDATE guilds SET data = ? WHERE id = ?;", (json_object, guild)
                )
            logger.debug("DATABASE: complete Guild data migration")

    def __1_3_0(self) -> None:
        """Migrate from version 1.3.0."""
        if not self._column_exists(Character._meta.table_name, "data"):
            logger.info("DATABASE: Migrate Character class data to JSON")

            # Grab the old data and add it to a dictionary to be migrated
            logger.debug("DATABASE: Grab old Character data")
            saved_data = self.db.execute_sql("SELECT * FROM characters;").fetchall()

            migration_dict: dict = {}
            for c in saved_data:
                migration_dict[c[0]] = {}
                migration_dict[c[0]]["first_name"] = c[1]
                migration_dict[c[0]]["last_name"] = c[2]
                migration_dict[c[0]]["nickname"] = c[3]
                migration_dict[c[0]]["modified"] = str(c[5])
                migration_dict[c[0]]["alive"] = bool(c[12])
                migration_dict[c[0]]["age"] = c[13]
                migration_dict[c[0]]["bio"] = c[15]
                migration_dict[c[0]]["cool_points_total"] = c[17]
                migration_dict[c[0]]["demeanor"] = c[19]
                migration_dict[c[0]]["experience"] = c[20]
                migration_dict[c[0]]["experience_total"] = c[21]
                migration_dict[c[0]]["nature"] = c[23]
                migration_dict[c[0]]["generation"] = c[24]
                migration_dict[c[0]]["sire"] = c[25]
                migration_dict[c[0]]["breed"] = c[26]
                migration_dict[c[0]]["tribe"] = c[27]
                migration_dict[c[0]]["auspice"] = c[28]
                migration_dict[c[0]]["essence"] = c[29]
                migration_dict[c[0]]["tradition"] = c[30]
                migration_dict[c[0]]["date_of_birth"] = c[31]
                migration_dict[c[0]]["storyteller_character"] = bool(c[32])

            # Disable foreign keys
            self.db.execute_sql("PRAGMA foreign_keys=OFF;")

            #### Perform Migration ####
            migrator = SqliteMigrator(self.db)

            # Create the new column
            logger.debug("DATABASE: Add new data column and drop old columns")
            data_column = JSONField(null=True)
            migrate(
                migrator.add_column("characters", "data", data_column),
                migrator.drop_column("characters", "first_name"),
                migrator.drop_column("characters", "last_name"),
                migrator.drop_column("characters", "nickname"),
                migrator.drop_column("characters", "modified"),
                migrator.drop_column("characters", "storyteller_character"),
                migrator.drop_column("characters", "alive"),
                migrator.drop_column("characters", "age"),
                migrator.drop_column("characters", "archived"),
                migrator.drop_column("characters", "bio"),
                migrator.drop_column("characters", "concept"),
                migrator.drop_column("characters", "cool_points"),
                migrator.drop_column("characters", "cool_points_total"),
                migrator.drop_column("characters", "experience"),
                migrator.drop_column("characters", "experience_total"),
                migrator.drop_column("characters", "nature"),
                migrator.drop_column("characters", "demeanor"),
                migrator.drop_column("characters", "generation"),
                migrator.drop_column("characters", "sire"),
                migrator.drop_column("characters", "breed"),
                migrator.drop_column("characters", "tribe"),
                migrator.drop_column("characters", "auspice"),
                migrator.drop_column("characters", "essence"),
                migrator.drop_column("characters", "tradition"),
                migrator.drop_column("characters", "date_of_birth"),
                migrator.drop_column("characters", "gender"),
            )

            # Add saved data into the JSON column
            logger.debug("DATABASE: Add saved data to new column")
            for character, data in migration_dict.items():
                json_object = json.dumps(data)
                self.db.execute_sql(
                    "UPDATE characters SET data = ? WHERE id = ?;", (json_object, character)
                )

            #### End Migration ####

            # Re-enable foreign keys
            self.db.execute_sql("PRAGMA foreign_keys=ON;")

    def __1_4_1(self) -> None:  # noqa: C901
        """Migrate from version 1.4.1."""
        # Micrate roll result thumbnails
        logger.debug("DATABASE: Roll result thumbs to RollResultType enum name")
        for thumb in RollThumbnail.select():
            if thumb.roll_type.lower() == "botch":
                thumb.roll_type = "BOTCH"
            elif thumb.roll_type.lower() == "failure":
                thumb.roll_type = "FAILURE"
            elif thumb.roll_type.lower() == "success":
                thumb.roll_type = "SUCCESS"
            elif thumb.roll_type.lower() == "critical success":
                thumb.roll_type = "CRITICAL"
            elif thumb.roll_type.lower() in ["other", "n/a"]:
                thumb.roll_type = "OTHER"

            thumb.save()

        # Rename "chronicle" to "campaign"
        if "chronicles" in self.get_tables():
            logger.info("DATABASE: Migrate `Chronicles` to `Campaigns`")

            # Collect data to migrate
            saved_chronicles = self.db.execute_sql("SELECT * FROM chronicles;").fetchall()
            saved_npcs = self.db.execute_sql("SELECT * FROM chronicle_npcs;").fetchall()
            saved_notes = self.db.execute_sql("SELECT * FROM chronicle_notes;").fetchall()
            saved_chapters = self.db.execute_sql("SELECT * FROM chronicle_chapters;").fetchall()

            # MIGRATE DATA
            # #################

            # Create new tables
            from valentina.models.db_tables import (
                Campaign,
                CampaignChapter,
                CampaignNote,
                CampaignNPC,
            )

            logger.debug("DATABASE: Create campaign tables")
            self.db.create_tables([Campaign, CampaignChapter, CampaignNote, CampaignNPC])

            logger.debug("DATABASE: Migrate campaign data")
            for c in saved_chronicles:
                Campaign.create(
                    name=c[1],
                    description=c[2],
                    created=c[3],
                    modified=c[4],
                    guild=c[5],
                    is_active=c[6],
                    current_date=c[7],
                )

            logger.debug("DATABASE: Migrate chapter data")
            for c in saved_chapters:
                CampaignChapter.create(
                    chapter_number=c[1],
                    name=c[2],
                    short_description=c[4],
                    description=c[5],
                    created=c[6],
                    modified=c[7],
                    campaign=c[8],
                )

            logger.debug("DATABASE: Migrate NPC data")
            for n in saved_npcs:
                CampaignNPC.create(
                    name=n[1],
                    description=n[2],
                    npc_class=n[3],
                    created=n[5],
                    modified=n[6],
                    campaign=n[7],
                )

            logger.debug("DATABASE: Migrate note data")
            for n in saved_notes:
                CampaignNote.create(
                    name=n[1],
                    description=n[2],
                    created=n[3],
                    modified=n[4],
                    campaign=n[5],
                    user=n[6],
                    chapter=n[7],
                )

            logger.debug("DATABASE: Drop old tables")
            # Disable foreign keys
            self.db.execute_sql("PRAGMA foreign_keys=OFF;")

            # Drop old tables
            self.db.execute_sql("DROP TABLE chronicles;")
            self.db.execute_sql("DROP TABLE chronicle_npcs;")
            self.db.execute_sql("DROP TABLE chronicle_notes;")
            self.db.execute_sql("DROP TABLE chronicle_chapters;")

            # Re-enable foreign keys
            self.db.execute_sql("PRAGMA foreign_keys=ON;")

    def __1_5_0(self) -> None:
        """Migrate from version 1.5.0."""
        # Pre-populate characters "owned_by" with "created_by"
        logger.debug("DATABASE: Pre-populate characters 'owned_by' with 'created_by'")
        for character in Character.select():
            if not character.owned_by:
                character.owned_by = character.created_by
                character.save()

        if self._column_exists(Character._meta.table_name, "claimed_by_id"):
            logger.debug("DATABASE: Drop `claimed_by_id` column from `characters` table")
            self.db.execute_sql("PRAGMA foreign_keys=OFF;")

            # Create new table
            self.db.execute_sql(
                """
                CREATE TABLE new_characters (
                    id INTEGER PRIMARY KEY,
                    created DATETIME NOT NULL,
                    char_class_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    created_by_id INTEGER NOT NULL,
                    owned_by_id INTEGER,
                    clan_id INTEGER,
                    data JSON
                );
            """
            )

            # Copy data from old table to new table
            self.db.execute_sql(
                """
                INSERT INTO new_characters (id, created, char_class_id, guild_id, created_by_id, owned_by_id, clan_id, data)
                SELECT id, created, char_class_id, guild_id, created_by_id, owned_by_id, clan_id, data
                FROM characters;
            """
            )
            self.db.execute_sql("DROP TABLE characters;")
            self.db.execute_sql("ALTER TABLE new_characters RENAME TO characters;")

            self.db.execute_sql("PRAGMA foreign_keys=ON;")

    @staticmethod
    def __1_8_0() -> None:
        """Migrate from version 1.8.0."""
        # Remove unused settings from guilds

        for guild in Guild.select():
            if guild.data.get("changelog_posted_version", None) is not None:
                logger.debug(f"MIGRAGE: Remove data.`changelog_posted_version` on {guild.name}")
                del guild.data["changelog_posted_version"]
                guild.save()

            if guild.data.get("use_error_log_channel", None) is not None:
                logger.debug(f"MIGRAGE: Remove data.`use_error_log_channel` on {guild.name}")
                del guild.data["use_error_log_channel"]
                guild.save()

            if guild.data.get("log_channel_id", None) is not None:
                logger.debug(
                    f"MIGRAGE: Migrate from `log_channel_id` to `audit_log_channel_id` on {guild.name}"
                )
                guild.data["audit_log_channel_id"] = guild.data["log_channel_id"]
                del guild.data["log_channel_id"]
                guild.save()

            if guild.data.get("use_audit_log", None) is not None:
                logger.debug(f"MIGRAGE: Remove data.`use_audit_log` on {guild.name}")
                del guild.data["use_audit_log"]
                guild.save()

            if guild.data.get("use_storyteller_channel", None) is not None:
                logger.debug(f"MIGRAGE: Remove data.`use_storyteller_channel` on {guild.name}")
                del guild.data["use_storyteller_channel"]
                guild.save()

    def __1_11_0(self) -> None:  # noqa: PLR0915, C901
        """Migrate from version 1.11.0."""
        if not self._column_exists(GuildUser._meta.table_name, "data"):
            logger.info("DATABASE: Migrate from User to GuildUser")

            logger.debug("DATABASE: Create GuildUser table")
            # Drop and recreate the GuildUser Table
            users = self.db.execute_sql("SELECT * FROM guilduser;").fetchall()
            self._drop_and_recreate("guilduser", GuildUser)

            for user in users:
                guild = Guild.get_by_id(user[1])
                GuildUser.create(user=user[2], guild=guild)

            for guild_user in GuildUser.select():
                guild_user.set_default_data_values()

            # Migrate foreign keys which referenced the User table

            # Characters Table
            characters = self.db.execute_sql("SELECT * FROM characters;").fetchall()
            self._drop_and_recreate("characters", Character)
            for character in characters:
                Character.create(
                    id=character[0],
                    created=character[1],
                    char_class=character[2],
                    guild=character[3],
                    created_by=GuildUser.get_or_none(user=character[4], guild=character[3]),
                    owned_by=GuildUser.get_or_none(user=character[4], guild=character[3]),
                    clan=character[6],
                    data=json.loads(character[7]),
                )

            # Macros Table
            macros = self.db.execute_sql("SELECT * FROM macros;").fetchall()
            self._drop_and_recreate("macros", Macro)
            for macro in macros:
                Macro.create(
                    id=macro[0],
                    name=macro[1],
                    abbreviation=macro[2],
                    description=macro[3],
                    created=macro[4],
                    modified=macro[5],
                    guild=macro[6],
                    user=GuildUser.get_or_none(user=macro[7], guild=macro[6]),
                )

            # Campaign Notes Table
            notes = self.db.execute_sql("SELECT * FROM campaign_notes;").fetchall()
            self._drop_and_recreate("campaign_notes", CampaignNote)
            for note in notes:
                CampaignNote.create(
                    id=note[0],
                    campaign=note[1],
                    chapter=note[2],
                    user=GuildUser.get_or_none(
                        user=note[3], guild=Campaign.get_by_id(note[1]).guild
                    ),
                    created=note[4],
                    modified=note[5],
                    name=note[6],
                    description=note[7],
                    data={},
                )

            # Migrate roll thumbnails table
            thumbs = self.db.execute_sql("SELECT * FROM roll_thumbnails;").fetchall()
            self._drop_and_recreate("roll_thumbnails", RollThumbnail)
            for thumb in thumbs:
                RollThumbnail.create(
                    id=thumb[0],
                    url=thumb[1],
                    roll_type=thumb[2],
                    created=thumb[3],
                    guild=thumb[4],
                    user=GuildUser.get_or_none(user=thumb[5], guild=thumb[4]),
                )

            # Migrate roll statistics table
            stats = self.db.execute_sql("SELECT * FROM rollstatistic;").fetchall()
            self._drop_and_recreate("rollstatistic", RollStatistic)
            for stat in stats:
                RollStatistic.create(
                    id=stat[0],
                    user=GuildUser.get_or_none(user=stat[1], guild=stat[2]),
                    guild=stat[2],
                    character=stat[3],
                    result=stat[4],
                    pool=stat[5],
                    difficulty=stat[6],
                    date_rolled=stat[7],
                )

            # Finally drop the user table
            if "users" in self.get_tables():
                logger.debug("DATABASE: Drop user table")
                self.db.execute_sql("DROP TABLE users;")

            # Migrate all experience from characters to GuildUsers
            logger.debug("DATABASE: Migrate experience from characters to GuildUsers")
            for character in Character.select():
                if "experience" in character.data:
                    campaign = Campaign.get(guild == character.guild, Campaign.is_active).id
                    user = GuildUser.get_by_id(character.owned_by.id)

                    xp_amount = character.data.get("experience", 0)
                    xp_total_amount = character.data.get("experience_total", 0)
                    cp_total_amount = character.data.get("cool_points_total", 0)

                    campaign_xp = user.data.get(f"{campaign}_experience", 0)
                    campaign_total_xp = user.data.get(f"{campaign}_total_experience", 0)
                    campaign_total_cp = user.data.get(f"{campaign}_total_cool_points", 0)
                    lifetime_xp = user.data.get("lifetime_experience", 0)
                    lifetime_cp = user.data.get("lifetime_cool_points", 0)

                    if not user.data:
                        user.data = {}
                    user.data[f"{campaign}_experience"] = campaign_xp + xp_amount
                    user.data[f"{campaign}_total_experience"] = campaign_total_xp + xp_total_amount
                    user.data[f"{campaign}_total_cool_points"] = campaign_total_cp + cp_total_amount
                    user.data["lifetime_experience"] = lifetime_xp + xp_total_amount
                    user.data["lifetime_cool_points"] = lifetime_cp + cp_total_amount
                    user.save()

                    del character.data["cool_points_total"]
                    del character.data["experience"]
                    del character.data["experience_total"]
                    character.save()


class PopulateDatabase:
    """A class that handles the populating data in a database.

    Important:
        - Adding new data should be fine in an existing database
        - Updating existing data must be handled in the MigrateDatabase class
        - Deleting data must be handled in the MigrateDatabase class

    """

    def __init__(self, db: CSqliteExtDatabase) -> None:
        self.db = db

    def populate(self) -> None:
        """Populate the database with initial data."""
        self._character_classes()
        self._vampire_clans()
        self._traits()
        logger.info("DATABASE: Populate initial data")

    def _character_classes(self) -> None:
        """Create the initial character classes."""
        # TODO: This is a migration from 1.13.0. Remove this after a few releases
        if not CharacterClass.get_or_none(name="VAMPIRE"):
            for c in CharacterClass.select():
                try:
                    # Attempt to find the corresponding enum member
                    enum_member = CharClassType[c.name.upper()]
                except KeyError:  # noqa: PERF203
                    logger.warning(f"No matching enum member for {c.name}")
                else:
                    # Update the name and save the record
                    logger.debug(f"Rename {c.name} to {enum_member.name}")
                    c.name = enum_member.name
                    c.save()

        # Ensure all character classes are in the database
        with self.db.atomic():
            for charclass in CharClassType.playable_classes():
                CharacterClass.insert(name=charclass.name).on_conflict_ignore().execute()

        # Remove any character classes that are no longer in the CharacterClasses enum
        with self.db.atomic():
            for db_object in CharacterClass.select():
                if db_object.name not in CharClassType.__members__:
                    try:
                        db_object.delete_instance()
                    except IntegrityError:
                        logger.warning(
                            f"DATABASE: Unable to delete character class: `{db_object.name}`"
                        )

        logger.debug("DATABASE: Populate character classes")

    def _vampire_clans(self) -> None:
        """Create the initial character classes."""
        # TODO: This if statement is a migration from 1.13.0. Remove this after a few releases
        if not VampireClan.get_or_none(name="BRUJAH"):
            for c in VampireClan.select():
                try:
                    # Attempt to find the corresponding enum member
                    enum_member = VampireClanType[c.name.upper().replace(" ", "_")]
                except KeyError:  # noqa: PERF203
                    logger.warning(f"No matching enum member for {c.name}")
                else:
                    # Update the name and save the record
                    logger.debug(f"Rename {c.name} to {enum_member.name}")
                    c.name = enum_member.name
                    c.save()

        # Ensure all clans are in the database
        with self.db.atomic():
            for clan in VampireClanType:
                VampireClan.insert(name=clan.name).on_conflict_ignore().execute()

        # Remove any clans that are no longer in the VampireClanType enum
        with self.db.atomic():
            for db_object in VampireClan.select():
                if db_object.name not in VampireClanType.__members__:
                    try:
                        db_object.delete_instance()
                    except IntegrityError:
                        logger.warning(
                            f"DATABASE: Unable to delete character class: `{db_object.name}`"
                        )

        logger.debug("DATABASE: Populate vampire clans")

    def _traits(self) -> None:  # noqa: C901
        """Populate the database with initial trait categories and associated character classes.

        This method associates predefined character classes to each category. If a category
        is associated with the 'Common' class, it will be linked with all character classes.
        """
        # TODO: This if statement is a migration from 1.13.0. Remove this after a few releases

        old_reputation = Trait.get_or_none(
            name="Reputation", category=TraitCategory.get_or_none(name="OTHER")
        )
        if old_reputation:
            logger.warning("DATABASE: Delete old reputation trait")
            old_reputation.delete_instance(delete_nullable=True, recursive=True)

        # TODO: This if statement is a migration from 1.13.0. Remove this after a few releases
        if not TraitCategory.get_or_none(name="PHYSICAL"):
            for c in TraitCategory.select():
                try:
                    # Attempt to find the corresponding enum member
                    enum_member = TraitCategories[c.name.upper()]
                except KeyError:  # noqa: PERF203
                    logger.warning(f"No matching enum member for {c.name}")
                else:
                    # Update the name and save the record
                    logger.debug(f"Rename {c.name} to {enum_member.name}")
                    c.name = enum_member.name
                    c.save()

        with self.db.atomic():
            for category in TraitCategories:
                db_cat, _ = TraitCategory.get_or_create(name=category.name)

                # trait/category/class lookup table
                # If common, add to all classes
                if CharClassType.COMMON in category.value["classes"]:
                    for c in CharacterClass.select():
                        TraitCategoryClass.insert(
                            character_class=c, category=db_cat
                        ).on_conflict_ignore().execute()
                # Otherwise, add to the specified classes
                else:
                    for c in category.value["classes"]:
                        TraitCategoryClass.insert(
                            character_class=CharacterClass.get(name=c.name), category=db_cat
                        ).on_conflict_ignore().execute()

                # Add traits to the database and associated lookup tables
                for charclass in CharClassType:
                    if charclass.name not in category.value:
                        continue

                    traits_list = category.value[charclass.name]  # type: ignore [literal-required]

                    # Add traits to the database
                    for trait in traits_list:
                        # Ensure trait is in the database
                        db_trait, _ = Trait.get_or_create(name=trait, category=db_cat)

                        if charclass == CharClassType.COMMON:
                            # Add to all classes
                            for c in CharacterClass.select():
                                TraitClass.get_or_create(character_class=c, trait=db_trait)
                        else:
                            # Add to lookup in the database
                            for c in CharacterClass.select():
                                if c.name == charclass.name:
                                    TraitClass.get_or_create(
                                        character_class=c,
                                        trait=db_trait,
                                    )

        logger.debug("DATABASE: Populate trait categories")

# type: ignore
"""Test the UserService class."""

import arrow
import pytest
from discord import ApplicationContext, Role

from valentina.constants import PermissionManageCampaign, PermissionsEditTrait, PermissionsEditXP
from valentina.models import UserService
from valentina.models.db_tables import Character, GuildUser, User
from valentina.utils import errors


@pytest.mark.usefixtures("mock_db")
class TestUserService:
    """Test the user service."""

    user_svc = UserService()

    def test_fetch_user(self, mock_ctx):
        """Test fetching a user.

        Given a context object with a user in the database
        When a user is fetched
        Then the user object is returned and added to the cache
        """
        # Confirm user object is returned
        assert self.user_svc.fetch_user(mock_ctx) == User(id=1, name="Test User")

        # Confirm user object is in the cache
        user_one = User(id=1)
        assert self.user_svc.user_cache["1_1"] == user_one

    def test_fetch_user_two(self, mock_ctx3):
        """Test creating a user that is not in the cache or db.

        Given a context object with a user not in the database
        When that user is fetched
        Then the user is added to the cache and database
        """
        assert self.user_svc.fetch_user(mock_ctx3) == User(id=600, name="Test User 600")

        # Confirm added to cache
        assert "1_600" in self.user_svc.user_cache

        # Confirm added to database
        assert User.get_by_id(600).name == "Test User 600"
        assert GuildUser.get_by_id(2).user.name == "Test User 600"

    def test_purge_all(self):
        """Test purging all users from the cache.

        Given a cache with users
        When the cache is purged
        Then the cache is empty
        """
        self.user_svc.user_cache = {"1_1": "a", "2_2": "b"}
        self.user_svc.active_character_cache = {"1": "a", "2": "b"}
        self.user_svc.purge_cache()
        assert self.user_svc.user_cache == {}
        assert self.user_svc.active_character_cache == {}

    def test_purge_by_id(self, mock_ctx, mock_ctx3):
        """Test purging a user from the cache.

        Given a cache with two users
        When one user is purged
        Then the cache contains only the other user
        """
        # Confirm the caches are populated with data
        assert self.user_svc.fetch_user(mock_ctx) == User(id=1, name="Test User")
        assert self.user_svc.fetch_user(mock_ctx3) == User(id=600, name="Test User 600")
        self.user_svc.user_cache["100_1"] = User(id=1, name="Test User")
        assert len(self.user_svc.user_cache) == 3
        self.user_svc.active_character_cache[1] = "one"
        self.user_svc.active_character_cache[2] = "two"

        # Purge one user
        self.user_svc.purge_cache(mock_ctx)

        # Confirm one user in cache
        assert len(self.user_svc.user_cache) == 1
        assert "1_1" not in self.user_svc.user_cache
        assert "1_600" not in self.user_svc.user_cache
        assert "100_1" in self.user_svc.user_cache
        assert 1 not in self.user_svc.active_character_cache
        assert 2 in self.user_svc.active_character_cache

    @pytest.mark.parametrize(
        ("xp_permissions_value", "is_admin", "is_char_owner", "hours_since_creation", "expected"),
        [
            (PermissionsEditXP.UNRESTRICTED.value, False, True, 38, True),
            (PermissionsEditXP.WITHIN_24_HOURS.value, False, True, 1, True),
            (PermissionsEditXP.WITHIN_24_HOURS.value, False, True, 38, False),
            (PermissionsEditXP.WITHIN_24_HOURS.value, True, True, 38, True),
            (PermissionsEditXP.WITHIN_24_HOURS.value, False, False, 1, False),
            (PermissionsEditXP.CHARACTER_OWNER_ONLY.value, True, False, 38, True),
            (PermissionsEditXP.CHARACTER_OWNER_ONLY.value, False, False, 38, False),
            (PermissionsEditXP.CHARACTER_OWNER_ONLY.value, False, True, 38, True),
            (PermissionsEditXP.STORYTELLER_ONLY.value, False, True, 1, False),
            (PermissionsEditXP.STORYTELLER_ONLY.value, False, False, 1, False),
            (PermissionsEditXP.STORYTELLER_ONLY.value, True, False, 1, True),
        ],
    )
    def test_can_update_xp(
        self, mocker, xp_permissions_value, is_admin, is_char_owner, hours_since_creation, expected
    ):
        """Test checking if a user has xp permissions.

        GIVEN a user and a character
        WHEN the user and character are checked
        THEN the correct result is returned
        """
        # GIVEN a mock ApplicationContext and Character
        mock_role1 = mocker.Mock(spec=Role)
        mock_role1.name = "Player"

        mock_ctx = mocker.Mock(spec=ApplicationContext)
        mock_ctx.author.guild_permissions.administrator = is_admin
        mock_ctx.author.roles = [mock_role1]

        mock_character = mocker.Mock(spec=Character)
        mock_character.created_by.id = 1 if is_char_owner else 2
        mock_character.created = arrow.utcnow().shift(hours=-hours_since_creation).datetime
        mock_ctx.author.id = 1  # the author is the creator of the character

        # Create mock bot and guild_svc and set them on mock_ctx
        mock_bot = mocker.Mock()
        mock_guild_svc = mocker.Mock()

        # Set up the mock fetch_guild_settings function
        mock_settings = {"permissions_edit_xp": xp_permissions_value}
        mock_guild_svc.fetch_guild_settings = mocker.Mock(return_value=mock_settings)

        mock_bot.guild_svc = mock_guild_svc
        mock_ctx.bot = mock_bot

        # WHEN calling the method with the mock context and character
        result = self.user_svc.can_update_xp(mock_ctx, mock_character)

        # THEN return the correct result
        assert result is expected

    @pytest.mark.parametrize(
        (
            "trait_permissions_value",
            "is_admin",
            "is_char_owner",
            "hours_since_creation",
            "expected",
        ),
        [
            (PermissionsEditTrait.UNRESTRICTED.value, False, True, 38, True),
            (PermissionsEditTrait.WITHIN_24_HOURS.value, False, True, 1, True),
            (PermissionsEditTrait.WITHIN_24_HOURS.value, False, True, 38, False),
            (PermissionsEditTrait.WITHIN_24_HOURS.value, True, True, 38, True),
            (PermissionsEditTrait.WITHIN_24_HOURS.value, False, False, 1, False),
            (PermissionsEditTrait.CHARACTER_OWNER_ONLY.value, True, False, 38, True),
            (PermissionsEditTrait.CHARACTER_OWNER_ONLY.value, False, False, 38, False),
            (PermissionsEditTrait.CHARACTER_OWNER_ONLY.value, False, True, 38, True),
            (PermissionsEditTrait.STORYTELLER_ONLY.value, False, True, 1, False),
            (PermissionsEditTrait.STORYTELLER_ONLY.value, False, False, 1, False),
            (PermissionsEditTrait.STORYTELLER_ONLY.value, True, False, 1, True),
        ],
    )
    def test_has_update_trait_permissions(
        self,
        mocker,
        trait_permissions_value,
        is_admin,
        is_char_owner,
        hours_since_creation,
        expected,
    ):
        """Test checking if a user has update trait permissions.

        GIVEN a user and a character
        WHEN the user and character are checked
        THEN the correct result is returned
        """
        # GIVEN a mock ApplicationContext and Character
        mock_role1 = mocker.Mock(spec=Role)
        mock_role1.name = "Player"

        mock_role2 = mocker.Mock(spec=Role)
        mock_role2.name = "@everyone"

        mock_ctx = mocker.Mock(spec=ApplicationContext)
        mock_ctx.author.guild_permissions.administrator = is_admin
        mock_ctx.author.roles = [mock_role1]
        mock_ctx.author.id = 1

        mock_character = mocker.Mock(spec=Character)
        mock_character.created_by.id = 1 if is_char_owner else 2
        mock_character.created = arrow.utcnow().shift(hours=-hours_since_creation).datetime
        # the author is the creator of the character

        # Create mock bot and guild_svc and set them on mock_ctx
        mock_bot = mocker.Mock()
        mock_guild_svc = mocker.Mock()

        # Set up the mock fetch_guild_settings function
        mock_settings = {"permissions_edit_trait": trait_permissions_value}
        mock_guild_svc.fetch_guild_settings = mocker.Mock(return_value=mock_settings)

        mock_bot.guild_svc = mock_guild_svc
        mock_ctx.bot = mock_bot

        # WHEN calling the method with the mock context and character
        result = self.user_svc.can_update_traits(mock_ctx, mock_character)

        # THEN return the correct result
        assert result is expected

    @pytest.mark.parametrize(
        (
            "permission_value",
            "is_admin",
            "is_storyteller",
            "expected",
        ),
        [
            (PermissionManageCampaign.UNRESTRICTED.value, True, False, True),
            (PermissionManageCampaign.UNRESTRICTED.value, False, False, True),
            (PermissionManageCampaign.UNRESTRICTED.value, False, True, True),
            (PermissionManageCampaign.STORYTELLER_ONLY.value, True, False, True),
            (PermissionManageCampaign.STORYTELLER_ONLY.value, False, False, False),
            (PermissionManageCampaign.STORYTELLER_ONLY.value, False, True, True),
        ],
    )
    def test_can_manage_campaigns(
        self, mocker, permission_value, is_admin, is_storyteller, expected
    ):
        """Test checking if a user has campaign management permissions.

        GIVEN a user
        WHEN the user is checked
        THEN the correct result is returned
        """
        # GIVEN mock ApplicationContexts
        mock_role1 = mocker.Mock(spec=Role)
        mock_role1.name = "Player"

        mock_role2 = mocker.Mock(spec=Role)
        mock_role2.name = "Storyteller"

        mock_ctx = mocker.Mock(spec=ApplicationContext)
        mock_ctx.author.guild_permissions.administrator = is_admin

        if is_storyteller:
            mock_ctx.author.roles = [mock_role1, mock_role2]
        else:
            mock_ctx.author.roles = [mock_role1]

        mock_ctx.author.id = 1

        # Create mock bot and guild_svc and set them on mock_ctx
        mock_bot = mocker.Mock()
        mock_guild_svc = mocker.Mock()

        # Set up the mock fetch_guild_settings function
        mock_settings = {"permissions_manage_campaigns": permission_value}
        mock_guild_svc.fetch_guild_settings = mocker.Mock(return_value=mock_settings)

        mock_bot.guild_svc = mock_guild_svc
        mock_ctx.bot = mock_bot

        # WHEN calling the method with the mock context and character
        result = self.user_svc.can_manage_campaign(mock_ctx)

        # THEN return the correct result
        assert result is expected

    def test_fetch_alive_characters(self, mock_ctx) -> None:
        """Test fetching active characters."""
        # GIVEN a character
        character = Character.create(
            data={
                "first_name": "char1",
                "last_name": "character",
                "storyteller_character": False,
                "player_character": True,
                "alive": True,
            },
            char_class=1,
            guild=mock_ctx.guild.id,
            created_by=mock_ctx.author.id,
            owned_by=mock_ctx.author.id,
            clan=1,
        )
        character2 = Character.create(
            data={
                "first_name": "char2",
                "last_name": "character",
                "storyteller_character": False,
                "player_character": True,
                "alive": True,
            },
            char_class=1,
            guild=mock_ctx.guild.id,
            created_by=mock_ctx.author.id,
            owned_by=mock_ctx.author.id,
            clan=1,
        )
        # Do not return dead or non-player characters
        Character.create(
            data={
                "first_name": "char3",
                "last_name": "character",
                "storyteller_character": False,
                "player_character": True,
                "alive": False,
            },
            char_class=1,
            guild=mock_ctx.guild.id,
            created_by=mock_ctx.author.id,
            owned_by=mock_ctx.author.id,
            clan=1,
        )
        Character.create(
            data={
                "first_name": "char4",
                "last_name": "character",
                "storyteller_character": True,
                "player_character": False,
                "alive": True,
            },
            char_class=1,
            guild=mock_ctx.guild.id,
            created_by=mock_ctx.author.id,
            owned_by=mock_ctx.author.id,
            clan=1,
        )
        Character.create(
            data={
                "first_name": "char15",
                "last_name": "character",
                "storyteller_character": False,
                "player_character": True,
                "alive": True,
            },
            char_class=1,
            guild=mock_ctx.guild.id + 1,
            created_by=mock_ctx.author.id,
            owned_by=mock_ctx.author.id,
            clan=1,
        )

        # WHEN fetch_active_characters is called
        result = self.user_svc.fetch_alive_characters(mock_ctx)

        # THEN return the correct result
        assert result == [character, character2]

    def test_fetch_active_character(self, mock_ctx, caplog) -> None:
        """Test fetching an active character."""
        # GIVEN no active characters
        # WHEN fetch_active_character is called
        # THEN raise NoActiveCharacterError
        with pytest.raises(errors.NoActiveCharacterError):
            self.user_svc.fetch_active_character(mock_ctx)

        # GIVEN an active character and an empty cache
        character = Character.get_by_id(2)
        character.data["is_active"] = True
        character.save()
        self.user_svc.character_cache = {}

        # WHEN fetch_active_character is called
        result = self.user_svc.fetch_active_character(mock_ctx)
        logged = caplog.text

        # THEN return the correct result from the database
        assert result == character
        assert "DATABASE: Fetch active character" in logged
        assert "CACHE: Return active character" not in logged

        # WHEN fetch_active_character is called again
        result = self.user_svc.fetch_active_character(mock_ctx)
        logged = caplog.text

        # THEN return the correct result from the cache
        assert result == character
        assert "CACHE: Return active character" in logged

    def test_set_active_character(self, mock_ctx) -> None:
        """Test switching active characters."""
        # GIVEN an active and an inactive character and a cache
        character1 = Character.create(
            data={
                "first_name": "char1",
                "last_name": "character",
                "storyteller_character": False,
                "player_character": True,
                "alive": True,
                "is_active": True,
            },
            char_class=1,
            guild=mock_ctx.guild.id,
            created_by=mock_ctx.author.id,
            owned_by=mock_ctx.author.id,
            clan=1,
        )
        character2 = Character.create(
            data={
                "first_name": "char2",
                "last_name": "character",
                "storyteller_character": False,
                "player_character": True,
                "alive": True,
                "is_active": False,
            },
            char_class=1,
            guild=mock_ctx.guild.id,
            created_by=mock_ctx.author.id,
            owned_by=mock_ctx.author.id,
            clan=1,
        )
        self.user_svc.active_character_cache = {1: character1}

        # WHEN set_active_character is called
        self.user_svc.set_active_character(mock_ctx, character2)

        # THEN the active character is switched
        assert not Character.get_by_id(character1.id).data["is_active"]
        assert Character.get_by_id(character2.id).data["is_active"]
        assert self.user_svc.active_character_cache == {1: character2}

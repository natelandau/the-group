# type: ignore
"""Test the UserService class."""

import arrow
import pytest
from discord import ApplicationContext, Role

from valentina.constants import PermissionsEditXP
from valentina.models import UserService
from valentina.models.db_tables import Character, GuildUser, User


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
        self.user_svc.purge_cache()
        assert self.user_svc.user_cache == {}

    def test_purge_by_id(self, mock_ctx, mock_ctx3):
        """Test purging a user from the cache.

        Given a cache with two users
        When one user is purged
        Then the cache contains only the other user
        """
        # Confirm three users in cache
        assert self.user_svc.fetch_user(mock_ctx) == User(id=1, name="Test User")
        assert self.user_svc.fetch_user(mock_ctx3) == User(id=600, name="Test User 600")
        self.user_svc.user_cache["100_1"] = User(id=1, name="Test User")
        assert len(self.user_svc.user_cache) == 3

        # Purge one user
        self.user_svc.purge_cache(mock_ctx)

        # Confirm one user in cache
        assert len(self.user_svc.user_cache) == 1
        assert "1_1" not in self.user_svc.user_cache
        assert "1_600" not in self.user_svc.user_cache
        assert "100_1" in self.user_svc.user_cache

    @pytest.mark.parametrize(
        ("xp_permissions_value", "is_admin", "is_char_owner", "hours_since_creation", "expected"),
        [
            (PermissionsEditXP.UNRESTRICTED.value, False, True, 38, True),
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
    def test_has_xp_permissions(
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
        mock_settings = {"xp_permissions": xp_permissions_value}
        mock_guild_svc.fetch_guild_settings = mocker.Mock(return_value=mock_settings)

        mock_bot.guild_svc = mock_guild_svc
        mock_ctx.bot = mock_bot

        # WHEN calling the method with the mock context and character
        result = self.user_svc.has_xp_permissions(mock_ctx, mock_character)

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
            (PermissionsEditXP.UNRESTRICTED.value, False, True, 38, True),
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
        mock_settings = {"trait_permissions": trait_permissions_value}
        mock_guild_svc.fetch_guild_settings = mocker.Mock(return_value=mock_settings)

        mock_bot.guild_svc = mock_guild_svc
        mock_ctx.bot = mock_bot

        # WHEN calling the method with the mock context and character
        result = self.user_svc.has_trait_permissions(mock_ctx, mock_character)

        # THEN return the correct result
        assert result is expected

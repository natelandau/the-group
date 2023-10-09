# type: ignore
"""Tests for helper utilities."""
import discord
import pytest
from dirty_equals import IsStr

from valentina.models import Probability
from valentina.models.db_tables import RollProbability


@pytest.mark.usefixtures("mock_db")
class TestProbability:
    """Test the probability helper."""

    @staticmethod
    def test_calculate(mock_ctx):
        """Test the calculate method."""
        # GIVEN an empty RollProbability table
        for i in RollProbability.select():
            i.delete_instance()

        # WHEN calculating the probability of a roll
        pool = 5
        difficulty = 6
        instance = Probability(mock_ctx, pool=pool, difficulty=difficulty, dice_size=10)

        # THEN confirm the probability is correct and the result is saved to the database
        assert instance.probabilities == RollProbability.get_by_id(1).data

        # WHEN calculating the probability of a roll that has already been calculated
        instance = Probability(mock_ctx, pool=pool, difficulty=difficulty, dice_size=10)

        # THEN confirm the result is retrieved from the database
        assert instance.probabilities == RollProbability.get_by_id(1).data
        assert RollProbability.select().count() == 1

    @pytest.mark.asyncio()
    @staticmethod
    async def test_get_embed(mock_ctx):
        """Test the get_embed method."""
        # GIVEN a probability instance
        pool = 5
        difficulty = 6
        instance = Probability(mock_ctx, pool=pool, difficulty=difficulty, dice_size=10)

        # WHEN getting the embed
        embed = await instance.get_embed()

        # THEN confirm the embed is correct
        assert isinstance(embed, discord.Embed)
        result = embed.to_dict()

        assert result["footer"]["text"] == IsStr(regex=r"Requested by .+")
        assert result["description"] == IsStr()
        assert isinstance(result["fields"], list)
"""Models for dice rolls."""

from enum import Enum

import discord
from loguru import logger
from numpy.random import default_rng

from valentina.models.constants import DiceType, EmbedColor, RollResultType
from valentina.models.db_tables import Character, RollStatistic
from valentina.utils import errors
from valentina.utils.helpers import diceroll_thumbnail, pluralize

_rng = default_rng()
_max_pool_size = 100


class ResultType(Enum):
    """Possible result of a roll. Values are used for logging statistics."""

    BOTCH = "botch"
    CRITICAL = "critical"
    SUCCESS = "success"
    FAILURE = "failure"
    OTHER = "n/a"


class DiceRoll:
    """A container class that determines the result of a roll and logs dicerolls to the database.

    Dice rolling mechanics are based on our unique system, which is loosely based on the Storyteller system. The following rules apply only to throws of 10 sided dice.

    * A roll is made up of a pool of dice, which is the total number of dice rolled.
    * The difficulty is the number that must be rolled on the dice to count as a success.
    * The dice type is the type of dice rolled. (Default is a d10.)
    * Ones negate two successes
    * Tens count as two successes
    * Ones and tens cancel each other out
    * A botch occurs when the result of all dice is less than 0
    * A critical occurs when the roll is a success and the number of 10s rolled is greater than half the pool
    * A failure occurs when the number of dice rolled above the difficulty is zero after accounting for cancelling ones and tens
    * A success occurs when the number of dice rolled above the difficulty is greater than zero after accounting for cancelling ones and tens
    * The result of a roll is the number of successes after accounting for botches and cancelling ones and tens

    Attributes:
        botches (int): The number of ones in the dice.
        criticals (int): The number of rolled criticals (Highest number on dice).
        dice_type (DiceType): The type of dice to roll.
        difficulty (int): The difficulty of the roll.
        embed_color (int): The color of the embed.
        failures (int): The number of unsuccessful dice not including botches.
        is_botch (bool): Whether the roll is a botch.
        is_critical (bool): Whether the roll is a critical success.
        is_failure (bool): Whether the roll is a failure.
        is_success (bool): Whether the roll is a success.
        takeaway (str): The roll's main takeaway for printing to the user - i.e. "SUCCESS", "FAILURE", etc.
        takeaway_type (str): The roll's takeaway type for logging statistics
        pool (int): The pool's total size, including hunger.
        result (int): The number of successes after accounting for botches and cancelling ones and tens.
        roll (list[int]): A list of the result all rolled dice.
        successes (int): The number of successful dice not including criticals.
    """

    def __init__(
        self,
        ctx: discord.ApplicationContext,
        pool: int,
        difficulty: int = 6,
        dice_size: int = 10,
        character: Character = None,
        log_roll: bool = True,
    ) -> None:
        """A container class that determines the result of a roll.

        Args:
            ctx (discord.ApplicationContext): The context of the command.
            dice_size (int, optional): The size of the dice. Defaults to 10.
            difficulty (int, optional): The difficulty of the roll. Defaults to 6.
            pool (int): The pool's total size, including hunger
            character (Character, optional): The character to log the roll for. Defaults to None.
            log_roll (bool, optional): Whether to log the roll to the database. Defaults to True.
        """
        self.ctx = ctx
        self.character = character
        self.log_roll = log_roll

        dice_size_values = [member.value for member in DiceType]
        if dice_size not in dice_size_values:
            raise errors.ValidationError(f"Invalid dice size `{dice_size}`.")

        self.dice_type = DiceType(dice_size)

        if difficulty < 0:
            raise errors.ValidationError(f"Difficulty cannot be less than 0. (Got `{difficulty}`.)")
        if difficulty > self.dice_type.value:
            raise errors.ValidationError(
                f"Difficulty cannot exceed the size of the dice. (Got `{difficulty}` for `{self.dice_type.name}`.)"
            )
        if pool < 0:
            raise errors.ValidationError(f"Pool cannot be less than 0. (Got `{pool}`.)")
        if pool > _max_pool_size:
            raise errors.ValidationError(f"Pool cannot exceed {_max_pool_size}. (Got `{pool}`.)")

        self.difficulty = difficulty
        self.pool = pool
        self._roll: list[int] = None
        self._botches: int = None
        self._criticals: int = None
        self._failures: int = None
        self._successes: int = None
        self._result: int = None
        self._result_type: ResultType = None

        # Log the roll to the database
        if self.log_roll:
            self._log_roll()

    def _calculate_result(self) -> ResultType:
        if self.dice_type != DiceType.D10:
            return ResultType.OTHER

        if self.result < 0:
            return ResultType.BOTCH

        if self.result == 0:
            return ResultType.FAILURE

        if self.result > self.pool:
            return ResultType.CRITICAL

        return ResultType.SUCCESS

    def _log_roll(self) -> None:
        """Log the roll to the database."""
        if self.dice_type == DiceType.D10:
            fields_to_log = {
                "guild": self.ctx.guild.id,
                "user": self.ctx.author.id,
                "character": self.character,
                "result": self.takeaway_type,
                "pool": self.pool,
                "difficulty": self.difficulty,
            }
            RollStatistic.create(**fields_to_log)
            logger.debug(f"DATABASE: Log diceroll {fields_to_log}")

    @property
    def result_type(self) -> ResultType:
        """Retrieve the result type of the roll."""
        if not self._result_type:
            self._result_type = self._calculate_result()

        return self._result_type

    @property
    def roll(self) -> list[int]:
        """Roll the dice and return the results."""
        if not self._roll:
            self._roll = list(map(int, _rng.integers(1, self.dice_type.value + 1, self.pool)))

        return self._roll

    @property
    def botches(self) -> int:
        """Retrieve the number of ones in the dice."""
        if not self._botches:
            self._botches = self.roll.count(1)

        return self._botches

    @property
    def criticals(self) -> int:
        """Retrieve the number of rolled criticals (Highest number on dice)."""
        if not self._criticals:
            self._criticals = self.roll.count(self.dice_type.value)
        return self._criticals

    @property
    def failures(self) -> int:
        """Retrieve the number of unsuccessful dice not including botches."""
        if not self._failures:
            count = 0
            for die in self.roll:
                if 2 <= die <= self.difficulty - 1:  # noqa: PLR2004
                    count += 1
            self._failures = count
        return self._failures

    @property
    def successes(self) -> int:
        """Retrieve the total number of dice which beat the difficulty not including criticals."""
        if not self._successes:
            count = 0
            for die in self.roll:
                if self.difficulty <= die <= self.dice_type.value - 1:
                    count += 1
            self._successes = count
        return self._successes

    @property
    def result(self) -> int:
        """Retrieve the number of successes to count."""
        if not self._result:
            if self.dice_type != DiceType.D10:
                self._result = self.successes + self.criticals - self.failures - self.botches
            else:
                botches = self.botches - self.criticals
                botches = botches if botches > 0 else 0
                criticals = self.criticals - self.botches
                criticals = criticals if criticals > 0 else 0

                self._result = self.successes + (criticals * 2) - (botches * 2)

        return self._result

    @property
    def thumbnail_url(self) -> str:  # pragma: no cover
        """Determine the thumbnail to use for the Discord embed."""
        # Create mapping between ResultType and RollResultType Enums
        thumbnail_map = {
            ResultType.OTHER: RollResultType.OTHER,
            ResultType.BOTCH: RollResultType.BOTCH,
            ResultType.CRITICAL: RollResultType.CRITICAL,
            ResultType.SUCCESS: RollResultType.SUCCESS,
            ResultType.FAILURE: RollResultType.FAILURE,
        }
        return diceroll_thumbnail(self.ctx, thumbnail_map[self.result_type])

    @property
    def embed_color(self) -> int:  # pragma: no cover
        """Determine the Discord embed color based on the result of the roll."""
        color_map = {
            ResultType.OTHER: EmbedColor.INFO,
            ResultType.BOTCH: EmbedColor.ERROR,
            ResultType.CRITICAL: EmbedColor.SUCCESS,
            ResultType.SUCCESS: EmbedColor.SUCCESS,
            ResultType.FAILURE: EmbedColor.WARNING,
        }
        return color_map[self.result_type].value

    @property
    def takeaway(self) -> str:  # pragma: no cover
        """The title of the roll response embed."""
        title_map = {
            ResultType.OTHER: "Dice roll",
            ResultType.BOTCH: f"__**BOTCH!**__\n{self.result} {pluralize(self.result, 'Success')}",
            ResultType.CRITICAL: f"__**CRITICAL SUCCESS!**__\n{self.result} {pluralize(self.result, 'Success')}",
            ResultType.SUCCESS: f"{self.result} {pluralize(self.result, 'Success')}",
            ResultType.FAILURE: f"{self.result} {pluralize(self.result, 'Success')}",
        }
        return title_map[self.result_type]

    @property
    def takeaway_type(self) -> str:  # pragma: no cover
        """The roll's takeaway type for logging statistics."""
        return self.result_type.value

"""Models for dice rolls."""

import random

import inflect
from loguru import logger
from numpy.random import default_rng

from valentina.constants import DICEROLL_THUBMS, DiceType, EmbedColor, RollResultType
from valentina.models.bot import ValentinaContext
from valentina.models.mongo_collections import Character, Guild, RollStatistic
from valentina.utils import errors

p = inflect.engine()
_rng = default_rng()
_max_pool_size = 100


async def diceroll_thumbnail(ctx: ValentinaContext, result: RollResultType) -> str:
    """Take a string and return a random gif url.

    Args:
        ctx (): The application context.
        result (RollResultType): The roll result type.

    Returns:
    Optional[str]: The thumbnail URL, or None if no thumbnail is found.
    """
    # Get the list of default thumbnails for the result type
    thumb_list = DICEROLL_THUBMS.get(result.name, [])

    # Find the matching category in the database thumbnails (case insensitive)
    guild = await Guild.get(ctx.guild.id)
    thumb_list.extend([x.url for x in guild.roll_result_thumbnails if x.roll_type == result])

    # If there are no thumbnails, return None
    if not thumb_list:
        return None

    # Return a random thumbnail
    return random.choice(thumb_list)


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
        embed_title (str): The title of the roll response embed.
        embed_description (str): The description of the roll response embed.
        pool (int): The pool's total size, including hunger.
        result (int): The number of successes after accounting for botches and cancelling ones and tens.
        result_type(RollResultType): The result type of the roll.
        roll (list[int]): A list of the result all rolled dice.
        successes (int): The number of successful dice not including criticals.
    """

    def __init__(
        self,
        ctx: ValentinaContext,
        pool: int,
        difficulty: int = 6,
        dice_size: int = 10,
        character: Character = None,
    ) -> None:
        """A container class that determines the result of a roll.

        Args:
            ctx (ValentinaContext): The context of the command.
            dice_size (int, optional): The size of the dice. Defaults to 10.
            difficulty (int, optional): The difficulty of the roll. Defaults to 6.
            pool (int): The pool's total size, including hunger
            character (Character, optional): The character to log the roll for. Defaults to None.
        """
        self.ctx = ctx
        self.character = character

        dice_size_values = [member.value for member in DiceType]
        if dice_size not in dice_size_values:
            msg = f"Invalid dice size `{dice_size}`."
            raise errors.ValidationError(msg)

        self.dice_type = DiceType(dice_size)

        if difficulty < 0:
            msg = f"Difficulty cannot be less than 0. (Got `{difficulty}`.)"
            raise errors.ValidationError(msg)
        if difficulty > self.dice_type.value:
            msg = f"Difficulty cannot exceed the size of the dice. (Got `{difficulty}` for `{self.dice_type.name}`.)"
            raise errors.ValidationError(msg)
        if pool < 0:
            msg = f"Pool cannot be less than 0. (Got `{pool}`.)"
            raise errors.ValidationError(msg)
        if pool > _max_pool_size:
            msg = f"Pool cannot exceed {_max_pool_size}. (Got `{pool}`.)"
            raise errors.ValidationError(msg)

        self.difficulty = difficulty
        self.pool = pool
        self._roll: list[int] = None
        self._botches: int = None
        self._criticals: int = None
        self._failures: int = None
        self._successes: int = None
        self._result: int = None
        self._result_type: RollResultType = None

    def _calculate_result(self) -> RollResultType:
        if self.dice_type != DiceType.D10:
            return RollResultType.OTHER

        if self.result < 0:
            return RollResultType.BOTCH

        if self.result == 0:
            return RollResultType.FAILURE

        if self.result > self.pool:
            return RollResultType.CRITICAL

        return RollResultType.SUCCESS

    async def log_roll(self, traits: list[str] = []) -> None:
        """Log the roll to the database.

        Args:
            traits (list[str], optional): The traits to log the roll for. Defaults to [].

        """
        # Ensure the user in the database to avoid foreign key errors

        # Log the roll to the database
        if self.dice_type == DiceType.D10:
            stat = RollStatistic(
                guild=self.ctx.guild.id,
                user=self.ctx.author.id,
                character=str(self.character.id) if self.character else None,
                result=self.result_type,
                pool=self.pool,
                difficulty=self.difficulty,
                traits=traits,
            )
            await stat.insert()

            logger.debug(
                f"DICEROLL: {self.ctx.author.display_name} rolled {self.roll} for {self.result_type.name}"
            )

    @property
    def result_type(self) -> RollResultType:
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

    async def thumbnail_url(self) -> str:  # pragma: no cover
        """Determine the thumbnail to use for the Discord embed."""
        return await diceroll_thumbnail(self.ctx, self.result_type)

    @property
    def embed_color(self) -> int:  # pragma: no cover
        """Determine the Discord embed color based on the result of the roll."""
        color_map = {
            RollResultType.OTHER: EmbedColor.INFO,
            RollResultType.BOTCH: EmbedColor.ERROR,
            RollResultType.CRITICAL: EmbedColor.SUCCESS,
            RollResultType.SUCCESS: EmbedColor.SUCCESS,
            RollResultType.FAILURE: EmbedColor.WARNING,
        }
        return color_map[self.result_type].value

    @property
    def embed_title(self) -> str:  # pragma: no cover
        """The title of the roll response embed."""
        title_map = {
            RollResultType.OTHER: "Dice roll",
            RollResultType.BOTCH: "__**BOTCH!**__",
            RollResultType.CRITICAL: "__**CRITICAL SUCCESS!**__",
            RollResultType.SUCCESS: f"**{self.result} {p.plural_noun('SUCCESS', self.result)}**",
            RollResultType.FAILURE: f"**{self.result} {p.plural_noun('SUCCESS', self.result)}**",
        }
        return title_map[self.result_type]

    @property
    def embed_description(self) -> str:
        """The description of the roll response embed."""
        title_map = {
            RollResultType.OTHER: "",
            RollResultType.BOTCH: f"{self.result} {p.plural_noun('Success', self.result)}",
            RollResultType.CRITICAL: f"{self.result} {p.plural_noun('Success', self.result)}",
            RollResultType.SUCCESS: "",
            RollResultType.FAILURE: "",
        }
        return title_map[self.result_type]

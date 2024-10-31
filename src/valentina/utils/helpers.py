"""Helper functions for Valentina."""

import io
import random
from datetime import UTC, datetime
from urllib.parse import urlencode

from aiohttp import ClientSession
from numpy.random import default_rng

from valentina.constants import MaxTraitValue, XPMultiplier, XPNew
from valentina.utils import errors

_rng = default_rng()


def convert_int_to_emoji(num: int, markdown: bool = False, images: bool = False) -> str:
    """Convert an integer to an emoji or a string.

    This method converts an integer to its corresponding emoji representation if it is between 0 and 10.
    For integers outside this range, it returns the number as a string. Optionally, it can wrap numbers
    larger than emojis within in markdown <pre> markers.

    Args:
        num (int): The integer to convert.
        markdown (bool, optional): Whether to wrap numbers larger than emojis in markdown code. Defaults to False.
        images (bool, optional): Whether to use images instead of Discord emoji codes. Defaults to False.

    Returns:
        str: The emoji corresponding to the integer, or the integer as a string.
    """
    if 0 <= num <= 10:  # noqa: PLR2004
        if images:
            return (
                str(num)
                .replace("10", "🔟")
                .replace("0", "0️⃣")
                .replace("1", "1️⃣")
                .replace("2", "2️⃣")
                .replace("3", "3️⃣")
                .replace("4", "4️⃣")
                .replace("5", "5️⃣")
                .replace("6", "6️⃣")
                .replace("7", "7️⃣")
                .replace("8", "8️⃣")
                .replace("9", "9️⃣")
            )

        return (
            str(num)
            .replace("10", ":keycap_ten:")
            .replace("0", ":zero:")
            .replace("1", ":one:")
            .replace("2", ":two:")
            .replace("3", ":three:")
            .replace("4", ":four:")
            .replace("5", ":five:")
            .replace("6", ":six:")
            .replace("7", ":seven:")
            .replace("8", ":eight:")
            .replace("9", ":nine:")
        )

    if markdown:
        return f"`{num}`"

    return str(num)


def random_num(ceiling: int = 100) -> int:
    """Generate a random integer within a specified range.

    Generate and return a random integer between 1 and the given ceiling (inclusive).

    Args:
        ceiling (int, optional): The upper limit for the random number. Defaults to 100.

    Returns:
        int: A random integer between 1 and the ceiling.

    Raises:
        ValueError: If ceiling is less than 1.
    """
    return _rng.integers(1, ceiling + 1)


async def fetch_random_name(
    gender: str | None = None, country: str = "us", results: int = 1
) -> list[tuple[str, str]] | tuple[str, str]:  # pragma: no cover
    """Fetch a random name from the randomuser.me API.

    Retrieve one or more random names from the randomuser.me API based on specified criteria.

    Args:
        gender (str | None): The gender of the name to fetch. If None, a random gender is chosen.
        country (str): The country code to fetch the name from. Defaults to "us".
        results (int): The number of results to fetch. Defaults to 1.

    Returns:
        list[tuple[str, str]] | tuple[str, str]: If results > 1, returns a list of tuples containing
        (first_name, last_name). If results == 1, returns a single tuple (first_name, last_name).
    """
    if not gender:
        gender = random.choice(["male", "female"])

    params = {"gender": gender, "nat": country, "inc": "name", "results": results}
    url = f"https://randomuser.me/api/?{urlencode(params)}"

    async with ClientSession() as session, session.get(url) as res:
        if 300 > res.status >= 200:  # noqa: PLR2004
            data = await res.json()

            result = [
                (result["name"]["first"], result["name"]["last"]) for result in data["results"]
            ]

            if len(result) == 1:
                return result[0]

            return result

    return [("John", "Doe")]


def divide_total_randomly(
    total: int, num: int, max_value: int | None = None, min_value: int = 0
) -> list[int]:
    """Divide a total into random segments with specified constraints.

    Generate a list of random integers that sum up to a given total. The function ensures
    that each segment falls within the specified minimum and maximum values (if provided).
    This can be useful for various applications such as resource allocation, random
    character attribute generation in games, or any scenario requiring a random
    distribution of a total value.

    The algorithm uses an iterative approach to adjust the randomly generated segments
    until they meet all specified constraints. It first generates random values within
    the allowed range, then iteratively adjusts these values to meet the total sum
    requirement while respecting the min and max constraints.

    Args:
        total (int): The total sum to be divided. Must be a positive integer.
        num (int): The number of segments to divide the total into. Must be a positive integer.
        max_value (int | None): The maximum value for any single segment. If None, no upper
            limit is applied beyond the total itself.
        min_value (int): The minimum value for any single segment. Defaults to 0. Must be
            non-negative and less than or equal to max_value (if specified).

    Returns:
        list[int]: A list of integers representing the divided segments. The length of the
            list will be equal to 'num', and the sum of all elements will equal 'total'.

    Raises:
        ValueError: If the total cannot be divided according to the given constraints. This
            can occur if the total is less than num * min_value, if max_value is less than
            min_value, or if num * max_value is less than total.
    """
    if total < num * min_value or (max_value is not None and max_value < min_value):
        msg = "Impossible to divide under given constraints."
        raise ValueError(msg)

    if max_value is not None and num * max_value < total:
        msg = "Impossible to divide under given constraints with max_value."
        raise ValueError(msg)

    # Generate initial random segments
    segments = [random.randint(min_value, max_value or total) for _ in range(num)]
    current_total = sum(segments)

    # Adjust the segments iteratively
    while current_total != total:
        for i in range(num):
            if current_total < total and (max_value is None or segments[i] < max_value):
                increment = min(total - current_total, (max_value or total) - segments[i])
                segments[i] += increment
                current_total += increment
            elif current_total > total and segments[i] > min_value:
                decrement = min(current_total - total, segments[i] - min_value)
                segments[i] -= decrement
                current_total -= decrement

            if current_total == total:
                break

    return segments


def get_max_trait_value(trait: str, category: str) -> int | None:
    """Get the maximum value for a trait by looking up the trait in the XPMultiplier enum.

    Args:
        trait (str): The trait to get the max value for.
        category (str): The category of the trait.
        is_custom_trait (bool, optional): Whether the trait is a custom trait. Defaults to False.

    Returns:
        int | None: The maximum value for the trait or None if the trait is a custom trait and no default for it's parent category exists.
    """
    # Some traits have their own max value. Check for those first.
    if trait.upper() in MaxTraitValue.__members__:
        return MaxTraitValue[trait.upper()].value

    # Try to find the max value by looking up the category of the trait
    if category.upper() in MaxTraitValue.__members__:
        return MaxTraitValue[category.upper()].value

    return MaxTraitValue.DEFAULT.value


def get_trait_multiplier(trait: str, category: str) -> int:
    """Get the experience multiplier associated with a trait for use when upgrading.

    Args:
        trait (str): The trait to get the cost for.
        category (str): The category of the trait.

    Returns:
        int: The multiplier associated with the trait.
    """
    if trait.upper() in XPMultiplier.__members__:
        return XPMultiplier[trait.upper()].value

    if category.upper() in XPMultiplier.__members__:
        return XPMultiplier[category.upper()].value

    return XPMultiplier.DEFAULT.value


def get_trait_new_value(trait: str, category: str) -> int:
    """Get the experience cost of the first dot for a wholly new trait from the XPNew enum.

    Args:
        trait (str): The trait to get the cost for.
        category (str): The category of the trait.

    Returns:
        int: The cost of the first dot of the trait.
    """
    if trait.upper() in XPNew.__members__:
        return XPNew[trait.upper()].value

    if category.upper() in XPNew.__members__:
        return XPNew[category.upper()].value

    return XPNew.DEFAULT.value


async def fetch_data_from_url(url: str) -> io.BytesIO:  # pragma: no cover
    """Fetch data from a URL and return it as a BytesIO object.

    This function retrieves data from a specified URL and returns it as a BytesIO object,
    which can be used for further processing or uploading to services like Amazon S3.

    Args:
        url (str): The URL from which to fetch the data.

    Returns:
        io.BytesIO: A BytesIO object containing the fetched data.

    Raises:
        errors.URLNotAvailableError: If the URL cannot be accessed or returns a non-200 status code.
    """
    async with ClientSession() as session, session.get(url) as resp:
        if resp.status != 200:  # noqa: PLR2004
            msg = f"Could not fetch data from {url}"
            raise errors.URLNotAvailableError(msg)

        return io.BytesIO(await resp.read())


def num_to_circles(num: int = 0, maximum: int = 5) -> str:
    """Return the emoji corresponding to the number. When `num` is greater than `maximum`, the `maximum` is increased to `num`.

    Args:
        num (int, optional): The number to convert. Defaults to 0.
        maximum (int, optional): The maximum number of circles. Defaults to 5.

    Returns:
        str: A string of circles and empty circles. i.e. `●●●○○`
    """
    if num is None:
        num = 0
    if maximum is None:
        maximum = 5
    maximum = max(num, maximum)

    return "●" * num + "○" * (maximum - num)


def truncate_string(text: str, max_length: int = 1000) -> str:
    """Truncate a string to a maximum length.

    Args:
        text (str): The string to truncate.
        max_length (int, optional): The maximum length of the string. Defaults to 1000.

    Returns:
        str: The truncated string.
    """
    if len(text) > max_length:
        return text[: max_length - 4] + "..."
    return text


def time_now() -> datetime:
    """Return the current time in UTC.

    Returns:
        datetime: The current UTC time with microseconds set to 0.
    """
    return datetime.now(UTC).replace(microsecond=0)

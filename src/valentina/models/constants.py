"""Constants for Valentina models."""
from enum import Enum

# maximum number of options in a discord select menu
MAX_OPTION_LIST_SIZE = 25


class MaxTraitValue(Enum):
    """Maximum value for a trait."""

    DEFAULT = 5
    # Specific values
    WILLPOWER = 10
    HUMANITY = 10
    RAGE = 10
    GNOSIS = 10
    ARETE = 10
    BLOOD_POOL = 20
    QUINTESSENCE = 20
    # Category values
    PHYSICAL = 5
    SOCIAL = 5
    MENTAL = 5
    TALENTS = 5
    SKILLS = 5
    KNOWLEDGES = 5
    DISCIPLINES = 5
    SPHERES = 5
    GIFTS = 5
    MERITS = 5
    FLAWS = 5
    BACKGROUNDS = 5
    VIRTUES = 5
    RENOWN = 5


class XPNew(Enum):
    """Experience cost for gaining a wholly new trait. Values are the cost in xp."""

    DEFAULT = 1
    # Category values
    DISCIPLINES = 10
    SPHERES = 10
    BACKGROUNDS = 3
    TALENTS = 3
    SKILLS = 3
    KNOWLEDGES = 3


class XPMultiplier(Enum):
    """Experience costs for raising character traits. Values are the multiplier against current rating."""

    DEFAULT = 2  # TODO: Is this the right value?
    # Attributes
    PHYSICAL = 4
    SOCIAL = 4
    MENTAL = 4
    # Abilities
    TALENTS = 2
    SKILLS = 2
    KNOWLEDGES = 2
    # Other
    VIRTUES = 2
    SPHERES = 7
    CLAN_DISCIPLINE = 5
    OTHER_DISCIPLINE = 7
    DISCIPLINES = 5  # TODO: Remove this and replace with clan/other
    MERITS = 2
    FLAWS = 2
    BACKGROUNDS = 2
    GIFTS = 3
    ## Specific Values #######################
    WILLPOWER = 1
    ARETE = 10
    QUINTESSENCE = 1  # TODO: Get the actual number for this
    RAGE = 1
    GNOSIS = 2
    HUMANITY = 2
    RESONANCE = 2  # TODO: Get the actual number for this
    CONVICTION = 2  # TODO: Get the actual number for this


class EmbedColor(Enum):
    """Enum for colors of embeds."""

    SUCCESS = 0x00FF00
    ERROR = 0xFF0000
    WARNING = 0xFFFF00
    INFO = 0x00FFFF
    DEBUG = 0x0000FF
    DEFAULT = 0x6082B6


class DiceType(Enum):
    """Enum for types of dice."""

    D4 = 4
    D6 = 6
    D8 = 8
    D10 = 10
    D100 = 100


class CharClass(Enum):
    """Enum for types of characters."""

    MORTAL = "Mortal"
    VAMPIRE = "Vampire"
    WEREWOLF = "Werewolf"
    MAGE = "Mage"
    HUNTER = "Hunter"


class TraitCategory(Enum):
    """Enum for categories of traits to be used for categorizing custom traits."""

    # Abilities
    PHYSICAL = "Physical"
    SOCIAL = "Social"
    MENTAL = "Mental"
    # Attributes
    TALENTS = "Talents"
    SKILLS = "Skills"
    KNOWLEDGES = "Knowledges"

    # Other
    VIRTUES = "Virtues"
    BACKGROUNDS = "Backgrounds"
    MERITS = "Merits"
    FLAWS = "Flaws"

    OTHER = "Other"

    # Class Specific
    DISCIPLINES = "Disciplines"  # Vampire
    SPHERES = "Spheres"  # Mage
    GIFTS = "Gifts"  # Werewolf


COMMON_TRAITS = {
    "Physical": ["Strength", "Dexterity", "Stamina"],
    "Social": ["Charisma", "Manipulation", "Appearance"],
    "Mental": ["Perception", "Intelligence", "Wits"],
    "Talents": [
        "Alertness",
        "Athletics",
        "Brawl",
        "Dodge",
        "Empathy",
        "Expression",
        "Intimidation",
        "Leadership",
        "Primal-Urge",
        "Streetwise",
        "Subterfuge",
    ],
    "Skills": [
        "Animal Ken",
        "Crafts",
        "Drive",
        "Etiquette",
        "Firearms",
        "Insight",
        "Larceny",
        "Meditation",
        "Melee",
        "Performance",
        "Persuasion",
        "Repair",
        "Stealth",
        "Survival",
        "Technology",
    ],
    "Knowledges": [
        "Academics",
        "Bureaucracy",
        "Computer",
        "Enigmas",
        "Finance",
        "Investigation",
        "Law",
        "Linguistics",
        "Medicine",
        "Occult",
        "Politics",
        "Rituals",
        "Science",
    ],
    "Virtues": ["Conscience", "Self-Control", "Courage"],
    "Universal": ["Willpower", "Humanity", "Desperation", "Reputation"],
}
MAGE_TRAITS = {
    "Universal": ["Arete", "Quintessence"],
    "Spheres": [
        "Correspondence",
        "Entropy",
        "Forces",
        "Life",
        "Matter",
        "Mind",
        "Prime",
        "Spirit",
        "Time",
    ],
}
VAMPIRE_TRAITS = {
    "Universal": ["Blood Pool"],
    "Disciplines": [
        "Animalism",
        "Auspex",
        "Blood Sorcery",
        "Celerity",
        "Dominate",
        "Fortitude",
        "Obeah",
        "Obfuscate",
        "Oblivion",
        "Potence",
        "Presence",
        "Protean",
        "Vicissitude",
    ],
}
WEREWOLF_TRAITS = {
    "Universal": ["Gnosis", "Rage"],
    "Renown": ["Glory", "Honor", "Wisdom"],
}
HUNTER_TRAITS = {"Universal": ["Conviction"]}

FLAT_COMMON_TRAITS = [trait for trait_list in COMMON_TRAITS.values() for trait in trait_list]

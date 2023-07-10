"""Constants for Valentina models."""
from enum import Enum

# maximum number of options in a discord select menu
MAX_OPTION_LIST_SIZE = 25
MAX_CHARACTER_COUNT = 1990
MAX_FIELD_COUNT = 1010
MAX_PAGE_CHARACTER_COUNT = 1950
MAX_BUTTONS_PER_ROW = 5


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


class RollResultType(Enum):
    """Enum for results of a roll."""

    SUCCESS = "Success"
    FAILURE = "Failure"
    BOTCH = "Botch"
    CRITICAL = "Critical Success"
    OTHER = "Other"


class CharClass(Enum):
    """Enum for types of characters."""

    # NOTE: Anything here must be added to the database CharacterClass table

    MORTAL = "Mortal"
    VAMPIRE = "Vampire"
    WEREWOLF = "Werewolf"
    MAGE = "Mage"
    HUNTER = "Hunter"
    Other = "Other"


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
    PATHS = "Paths"

    OTHER = "Other"

    # Class Specific
    DISCIPLINES = "Disciplines"  # Vampire
    SPHERES = "Spheres"  # Mage
    GIFTS = "Gifts"  # Werewolf


class VampClanList(Enum):
    """Vampire clans."""

    # NOTE: Anything added here must be added to the VampireClan class in models/database.py
    ASSAMITE = "Assamite"
    BRUJAH = "Brujah"
    FOLLOWERS_OF_SET = "Followers of Set"
    GANGREL = "Gangrel"
    GIOVANNI = "Giovanni"
    LASOMBRA = "Lasombra"
    MALKAVIAN = "Malkavian"
    NOSFERATU = "Nosferatu"
    RAVNOS = "Ravnos"
    TOREADOR = "Toreador"
    TREMERE = "Tremere"
    TZIMISCE = "Tzimisce"
    VENTRUE = "Ventrue"


# NOTE: Anything added here must be added to the Character class in models/database.py
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
        "Security",
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
    "Universal": ["Willpower", "Desperation", "Reputation"],
}
MAGE_TRAITS = {
    "Universal": ["Humanity", "Arete", "Quintessence"],
    "Virtues": ["Conscience", "Self-Control", "Courage"],
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
    "Universal": ["Blood Pool", "Humanity"],
    "Virtues": ["Conscience", "Self-Control", "Courage"],
    "Disciplines": [
        "Animalism",
        "Auspex",
        "Blood Sorcery",
        "Celerity",
        "Chimerstry",
        "Dominate",
        "Fortitude",
        "Necromancy",
        "Obeah",
        "Obfuscate",
        "Oblivion",
        "Potence",
        "Presence",
        "Protean",
        "Serpentis",
        "Thaumaturgy",
        "Vicissitude",
    ],
}
WEREWOLF_TRAITS = {
    "Universal": ["Gnosis", "Rage"],
    "Renown": ["Glory", "Honor", "Wisdom"],
}
HUNTER_TRAITS = {
    "Universal": ["Conviction", "Faith", "Humanity"],
    "Virtues": ["Conscience", "Self-Control", "Courage"],
}
MORTAL_TRAITS = {"Universal": ["Humanity"], "Virtues": ["Conscience", "Self-Control", "Courage"]}
CLAN_DISCIPLINES = {
    "Assamite": ["Celerity", "Obfuscate", "Quietus"],
    "Brujah": ["Celerity", "Potence", "Presence"],
    "Followers of Set": ["Obfuscate", "Presence", "Serpentis"],
    "Gangrel": ["Animalism", "Fortitude", "Protean"],
    "Giovanni": ["Dominate", "Necromancy", "Potence"],
    "Lasombra": ["Dominate", "Obfuscate", "Potence"],
    "Malkavian": ["Auspex", "Dominate", "Obfuscate"],
    "Nosferatu": ["Animalism", "Obfuscate", "Potence"],
    "Ravnos": ["Animalism", "Chimerstry", "Fortitude"],
    "Toreador": ["Auspex", "Celerity", "Presence"],
    "Tremere": ["Auspex", "Dominate", "Thaumaturgy"],
    "Tzimisce": ["Animalism", "Auspex", "Vicissitude"],
    "Ventrue": ["Dominate", "Fortitude", "Presence"],
}


FLAT_COMMON_TRAITS = [trait for trait_list in COMMON_TRAITS.values() for trait in trait_list]
DICEROLL_THUBMS = {
    "BOTCH": [
        "https://em-content.zobj.net/source/animated-noto-color-emoji/356/face-vomiting_1f92e.gif",
    ],
    "CRITICAL": [
        "https://em-content.zobj.net/source/animated-noto-color-emoji/356/rocket_1f680.gif",
    ],
    "OTHER": [
        "https://i.giphy.com/media/ygzkZPxmh6HgUzbYFz/giphy.gif",
        "https://em-content.zobj.net/thumbs/240/google/350/game-die_1f3b2.png",
        "https://i.giphy.com/media/ugNDcwUAydqjCPEMR1/giphy.gif",
    ],
    "FAILURE": [
        "https://i.giphy.com/media/aCwWc9CyTisF2/giphy.gif",
        "https://em-content.zobj.net/source/animated-noto-color-emoji/356/crying-face_1f622.gif",
        "https://i.giphy.com/media/xRyIsRCVTN70tBZPP1/giphy.gif",
    ],
    "SUCCESS": [
        "https://em-content.zobj.net/thumbs/240/apple/354/thumbs-up_1f44d.png",
    ],
}

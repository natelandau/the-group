"""Models for the database."""

from loguru import logger
from peewee import BooleanField, DateTimeField, ForeignKeyField, IntegerField, Model, TextField

from valentina import DATABASE
from valentina.utils.helpers import time_now


class BaseModel(Model):
    """Base model for the database."""

    class Meta:
        """Meta class for the database, inherited by all subclasses."""

        database = DATABASE

    def __str__(self) -> str:
        """Return the string representation of the model."""
        return str(self.__dict__)


class Guild(BaseModel):
    """Guild model for the database."""

    guild_id = IntegerField(unique=True)
    name = TextField()
    first_seen = DateTimeField(default=time_now)
    last_connected = DateTimeField(default=time_now)


class CharacterClass(BaseModel):
    """Character Class model for the database."""

    name = TextField(unique=True)


class Character(BaseModel):
    """Character model for the database."""

    # GENERAL ####################################
    first_name = TextField()
    last_name = TextField(null=True)
    nickname = TextField(null=True)
    char_class = ForeignKeyField(CharacterClass, backref="characters")
    guild = ForeignKeyField(Guild, backref="characters")
    created = DateTimeField(default=time_now)
    modified = DateTimeField(default=time_now)
    age = IntegerField(null=True)
    bio = TextField(null=True)
    concept = TextField(null=True)
    cool_points = IntegerField(default=0)
    cool_points_total = IntegerField(default=0)
    experience = IntegerField(default=0)
    experience_total = IntegerField(default=0)
    gender = TextField(null=True)
    player_id = IntegerField(null=True)
    nature = TextField(null=True)
    demeanor = TextField(null=True)
    archived = BooleanField(default=False)
    notes = TextField(null=True)
    # ATTRIBUTES #################################
    strength = IntegerField(default=0)
    dexterity = IntegerField(default=0)
    stamina = IntegerField(default=0)
    charisma = IntegerField(default=0)
    manipulation = IntegerField(default=0)
    appearance = IntegerField(default=0)
    perception = IntegerField(default=0)
    intelligence = IntegerField(default=0)
    wits = IntegerField(default=0)
    # ABILITIES ##################################
    athletics = IntegerField(default=0)
    brawl = IntegerField(default=0)
    dodge = IntegerField(default=0)
    drive = IntegerField(default=0)
    empathy = IntegerField(default=0)
    expression = IntegerField(default=0)
    intimidation = IntegerField(default=0)
    leadership = IntegerField(default=0)
    streetwise = IntegerField(default=0)
    subterfuge = IntegerField(default=0)
    alertness = IntegerField(default=0)
    animal_ken = IntegerField(default=0)
    crafts = IntegerField(default=0)
    drive = IntegerField(default=0)
    etiquette = IntegerField(default=0)
    firearms = IntegerField(default=0)
    larceny = IntegerField(default=0)
    melee = IntegerField(default=0)
    performance = IntegerField(default=0)
    stealth = IntegerField(default=0)
    survival = IntegerField(default=0)
    technology = IntegerField(default=0)
    academics = IntegerField(default=0)
    computer = IntegerField(default=0)
    finance = IntegerField(default=0)
    investigation = IntegerField(default=0)
    law = IntegerField(default=0)
    linguistics = IntegerField(default=0)
    medicine = IntegerField(default=0)
    occult = IntegerField(default=0)
    politics = IntegerField(default=0)
    science = IntegerField(default=0)
    # VIRTUES #################################
    conscience = IntegerField(default=0)
    self_control = IntegerField(default=0)
    courage = IntegerField(default=0)
    # UNIVERSAL ################################
    humanity = IntegerField(default=0)
    willpower = IntegerField(default=0)
    desperation = IntegerField(default=0)
    reputation = IntegerField(default=0)
    # MAGE #####################################
    arete = IntegerField(default=0)
    quintessence = IntegerField(default=0)
    # WEREWOLF #################################
    rage = IntegerField(default=0)
    gnosis = IntegerField(default=0)
    # VAMPIRE ##################################
    blood_pool = IntegerField(default=0)
    # HUNTER ###################################
    conviction = IntegerField(default=0)
    # MAGE_SPHERES #############################
    correspondence = IntegerField(default=0)
    entropy = IntegerField(default=0)
    forces = IntegerField(default=0)
    life = IntegerField(default=0)
    matter = IntegerField(default=0)
    mind = IntegerField(default=0)
    prime = IntegerField(default=0)
    spirit = IntegerField(default=0)
    time = IntegerField(default=0)
    # MAGE_RESONANCE ##########################
    dynamic = IntegerField(default=0)
    static = IntegerField(default=0)
    entropic = IntegerField(default=0)
    # DISCIPLINES #############################
    animalism = IntegerField(default=0)
    auspex = IntegerField(default=0)
    blood_sorcery = IntegerField(default=0)
    celerity = IntegerField(default=0)
    dominate = IntegerField(default=0)
    fortitude = IntegerField(default=0)
    obeah = IntegerField(default=0)
    obfuscate = IntegerField(default=0)
    oblivion = IntegerField(default=0)
    potence = IntegerField(default=0)
    presence = IntegerField(default=0)
    protean = IntegerField(default=0)
    vicissitude = IntegerField(default=0)

    @property
    def name(self) -> str:
        """Return the name of the character."""
        if self.nickname:
            return self.nickname

        if self.last_name:
            return f"{self.first_name} {self.last_name}"

        return self.first_name

    ################################################3

    def __str__(self) -> str:
        """Return the string representation of the model."""
        return f"""Character(
    first_name={self.first_name},
    last_name={self.last_name},
    nickname={self.nickname},
    char_class={self.char_class.name},
    guild={self.guild.name},
    created={self.created},
    modified={self.modified},
    age={self.age},
    bio={self.bio},
    concept={self.concept},
    cool_points={self.cool_points},
    cool_points_total={self.cool_points_total},
    experience={self.experience},
    experience_total={self.experience_total},
    player_id={self.player_id},
    strength={self.strength},
    dexterity={self.dexterity},
    stamina={self.stamina},
    charisma={self.charisma},
    manipulation={self.manipulation},
    appearance={self.appearance},
    perception={self.perception},
    intelligence={self.intelligence},
    wits={self.wits},
        )
        """

    def update_modified(self) -> None:
        """Update the modified field."""
        self.modified = time_now()
        self.save()
        logger.info(f"DATABASE: Character {self.first_name} modified_date updated.")

    def add_experience(self, experience: int) -> None:
        """Update the experience field."""
        self.experience += experience
        self.experience_total += experience
        self.save()
        logger.info(f"DATABASE: Character {self.first_name} experience updated.")

    def spend_experience(self, experience: int) -> None:
        """Update the experience field."""
        if experience > self.experience:
            raise ValueError("Not enough experience to use.")
        self.experience -= experience
        self.save()
        logger.info(f"DATABASE: Character {self.first_name} experience updated.")

    def add_cool_points(self, cool_points: int) -> None:
        """Update the cool_points field."""
        self.cool_points += cool_points
        self.cool_points_total += cool_points
        self.save()
        logger.info(f"DATABASE: Character {self.first_name} cool_points updated.")

    def spend_cool_points(self, cool_points: int) -> None:
        """Update the cool_points field."""
        if cool_points > self.cool_points:
            raise ValueError("Not enough cool_points to use.")
        self.cool_points -= cool_points
        self.save()
        logger.info(f"DATABASE: Character {self.first_name} cool_points updated.")


class CustomTrait(BaseModel):
    """Custom Trait model for the database."""

    name = TextField()
    description = TextField(null=True)
    trait_type = TextField(null=True)
    character = ForeignKeyField(Character, backref="custom_traits")
    value = IntegerField(default=0)
    created = DateTimeField(default=time_now)

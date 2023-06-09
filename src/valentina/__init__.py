"""This module is the entry point of the bot. save version."""

from .bot import Valentina
from .main import CONFIG, DATABASE
from .models.database_services import CharacterService, UserService

char_svc = CharacterService()
user_svc = UserService()

__all__ = ["DATABASE", "Valentina", "CONFIG", "char_svc", "user_svc"]

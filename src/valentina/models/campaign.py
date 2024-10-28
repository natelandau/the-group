"""Campaign models for Valentina."""

from datetime import datetime
from typing import Optional

import discord
from beanie import (
    Document,
    Indexed,
    Insert,
    Link,
    Replace,
    Save,
    SaveChanges,
    Update,
    before_event,
)
from pydantic import BaseModel, Field

from valentina.constants import Emoji
from valentina.utils.helpers import time_now

from .character import Character
from .note import Note


class CampaignChapter(BaseModel):
    """Represents a chapter as a subdocument within Campaign.

    # TODO: Remove after migration
    """

    description_long: str = None
    description_short: str = None
    name: str
    number: int
    date_created: datetime = Field(default_factory=time_now)
    channel: int | None = None


class CampaignNPC(BaseModel):
    """Represents a campaign NPC as a subdocument within Campaign."""

    description: str
    name: str
    npc_class: str

    def campaign_display(self) -> str:
        """Return the display for campaign overview."""
        display = f"**{self.name}**"
        display += f" ({self.npc_class})" if self.npc_class else ""
        display += f"\n{self.description}" if self.description else ""

        return display


class CampaignBookChapter(Document):
    """Represents a chapter as a subdocument within CampaignBook."""

    book: Indexed(str)  # type: ignore [valid-type]
    date_created: datetime = Field(default_factory=time_now)
    description_long: str = None
    description_short: str = None
    name: str
    number: int


class CampaignBook(Document):
    """Represents a book as a sub-document within Campaign."""

    campaign: Indexed(str)  # type: ignore [valid-type]
    channel: int | None = None
    chapters: list[Link[CampaignBookChapter]] = Field(default_factory=list)
    date_created: datetime = Field(default_factory=time_now)
    description_long: str = None
    description_short: str = None
    name: str
    number: int
    notes: list[Link[Note]] = Field(default_factory=list)

    @property
    def channel_name(self) -> str:
        """Channel name for the book."""
        return f"{Emoji.BOOK.value}-{self.number:0>2}-{self.name.lower().replace(' ', '-')}"

    async def fetch_chapters(self) -> list[CampaignBookChapter]:
        """Fetch all chapters in the book.

        This method retrieves and sorts all chapters associated with the book by their number.

        Returns:
            list[CampaignBookChapter]: A sorted list of CampaignBookChapter objects associated with the book.
        """
        return sorted(
            self.chapters,  # type: ignore [arg-type]
            key=lambda x: x.number,
        )

    async def update_channel_id(self, channel: discord.TextChannel) -> None:
        """Update the book's channel ID in the database.

        Args:
            channel (discord.TextChannel): The book's channel.
        """
        if not self.channel or self.channel != channel.id:
            self.channel = channel.id
            await self.save()


class Campaign(Document):
    """Represents a campaign in the database."""

    date_created: datetime = Field(default_factory=time_now)
    date_modified: datetime = Field(default_factory=time_now)
    date_in_game: Optional[datetime] = None
    description: str | None = None
    desperation: int = 0
    danger: int = 0
    guild: int
    name: str
    is_deleted: bool = False  # Campaigns are never deleted from the DB, only marked as deleted
    chapters: list[CampaignChapter] = Field(default_factory=list)
    npcs: list[CampaignNPC] = Field(default_factory=list)
    books: list[Link[CampaignBook]] = Field(default_factory=list)
    notes: list[Link[Note]] = Field(default_factory=list)
    channel_campaign_category: int | None = None
    channel_storyteller: int | None = None
    channel_general: int | None = None

    @before_event(Insert, Replace, Save, Update, SaveChanges)
    async def update_modified_date(self) -> None:
        """Update the date_modified field."""
        self.date_modified = time_now()

    async def fetch_player_characters(self) -> list[Character]:
        """Fetch all player characters in the campaign.

        Retrieve a list of all player characters associated with the current campaign.
        Filter characters to include only those marked as player characters.

        Returns:
            list[Character]: A list of Character objects representing player characters in the campaign.
        """
        return await Character.find(
            Character.campaign == str(self.id),
            Character.type_player == True,  # noqa: E712
        ).to_list()

    async def fetch_storyteller_characters(self) -> list[Character]:
        """Fetch all storyteller characters in the campaign.

        Retrieve a list of all player characters associated with the current campaign.
        Filter characters to include only those marked as player characters.

        Returns:
            list[Character]: A list of Character objects representing player characters in the campaign.
        """
        return await Character.find(
            Character.campaign == str(self.id),
            Character.type_storyteller == True,  # noqa: E712
        ).to_list()

    async def fetch_books(self) -> list[CampaignBook]:
        """Fetch all books in the campaign.

        This method retrieves and sorts a list of all books associated with the campaign by their number.

        Returns:
            list[CampaignBook]: A sorted list of CampaignBook objects associated with the campaign.
        """
        return sorted(
            self.books,  # type: ignore [arg-type]
            key=lambda x: x.number,
        )

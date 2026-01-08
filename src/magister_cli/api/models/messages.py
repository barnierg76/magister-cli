"""Message models for Magister API."""

from datetime import datetime

from pydantic import Field

from magister_cli.api.models.attachments import Bijlage
from magister_cli.api.models.base import MagisterModel


class Afzender(MagisterModel):
    """Message sender or recipient."""

    id: int = Field(alias="id")
    naam: str = Field(alias="naam")
    type: str | None = Field(default=None, alias="type")  # Docent, Leerling, etc.


class Bericht(MagisterModel):
    """Message summary (inbox/sent view)."""

    id: int = Field(alias="id")
    onderwerp: str = Field(alias="onderwerp")
    afzender: Afzender = Field(alias="afzender")
    verzonden_op: datetime = Field(alias="verzondenOp")
    gelezen: bool = Field(alias="isGelezen")
    heeft_bijlagen: bool = Field(default=False, alias="heeftBijlagen")
    prioriteit: str | None = Field(default=None, alias="prioriteit")  # Normaal, Hoog
    heeft_prioriteit: bool = Field(default=False, alias="heeftPrioriteit")

    @property
    def is_unread(self) -> bool:
        """Check if message is unread."""
        return not self.gelezen

    @property
    def sender_name(self) -> str:
        """Get sender name for display."""
        return self.afzender.naam


class BerichtDetail(Bericht):
    """Full message with body and attachments."""

    inhoud: str = Field(alias="inhoud")
    ontvangers: list[Afzender] = Field(default_factory=list, alias="ontvangers")
    bijlagen: list[Bijlage] = Field(default_factory=list, alias="bijlagen")
    cc_ontvangers: list[Afzender] = Field(default_factory=list, alias="ccOntvangers")

    @property
    def recipient_names(self) -> list[str]:
        """Get list of recipient names."""
        return [o.naam for o in self.ontvangers]


class BerichtenResponse(MagisterModel):
    """Response wrapper for messages list."""

    items: list[Bericht] = Field(alias="items")
    total_count: int = Field(default=0, alias="totalCount")

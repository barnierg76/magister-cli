"""Message models for Magister API."""

from datetime import datetime

from pydantic import Field

from magister_cli.api.models.attachments import Bijlage
from magister_cli.api.models.base import MagisterModel


class Afzender(MagisterModel):
    """Message sender or recipient."""

    id: int = Field(alias="Id")
    naam: str = Field(alias="Naam")
    type: str | None = Field(default=None, alias="Type")  # Docent, Leerling, etc.


class Bericht(MagisterModel):
    """Message summary (inbox/sent view)."""

    id: int = Field(alias="Id")
    onderwerp: str = Field(alias="Onderwerp")
    afzender: Afzender = Field(alias="Afzender")
    verzonden_op: datetime = Field(alias="VerzondOp")
    gelezen: bool = Field(alias="IsGelezen")
    heeft_bijlagen: bool = Field(default=False, alias="HeeftBijlagen")
    prioriteit: str | None = Field(default=None, alias="Prioriteit")  # Normaal, Hoog
    heeft_prioriteit: bool = Field(default=False, alias="HeeftPrioriteit")

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

    inhoud: str = Field(alias="Inhoud")
    ontvangers: list[Afzender] = Field(default_factory=list, alias="Ontvangers")
    bijlagen: list[Bijlage] = Field(default_factory=list, alias="Bijlagen")
    cc_ontvangers: list[Afzender] = Field(default_factory=list, alias="CCOntvangers")

    @property
    def recipient_names(self) -> list[str]:
        """Get list of recipient names."""
        return [o.naam for o in self.ontvangers]


class BerichtenResponse(MagisterModel):
    """Response wrapper for messages list."""

    items: list[Bericht] = Field(alias="Items")
    total_count: int = Field(default=0, alias="TotalCount")

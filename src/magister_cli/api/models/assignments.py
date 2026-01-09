"""ELO Assignment (opdracht) models."""

from datetime import datetime

from pydantic import Field

from magister_cli.api.models.attachments import Bijlage
from magister_cli.api.models.base import MagisterModel


class Opdracht(MagisterModel):
    """ELO Assignment that students can submit."""

    id: int = Field(alias="Id")
    titel: str = Field(alias="Titel")
    omschrijving: str | None = Field(default=None, alias="Omschrijving")
    vak: str | None = Field(default=None, alias="Vak")
    inleveren_voor: datetime | None = Field(default=None, alias="InleverenVoor")
    ingeleverd_op: datetime | None = Field(default=None, alias="IngeleverdOp")
    beoordeling: str | None = Field(default=None, alias="Beoordeling")
    beoordeeld_op: datetime | None = Field(default=None, alias="BeoordeeldOp")
    status_laatste_versie: int = Field(default=0, alias="StatusLaatsteOpdrachtVersie")
    laatste_versienummer: int = Field(default=0, alias="LaatsteOpdrachtVersienummer")
    opnieuw_inleveren: bool = Field(default=False, alias="OpnieuwInleveren")
    afgesloten: bool = Field(default=False, alias="Afgesloten")
    mag_inleveren: bool = Field(default=True, alias="MagInleveren")
    bijlagen: list[Bijlage] = Field(default_factory=list, alias="Bijlagen")

    @property
    def is_ingeleverd(self) -> bool:
        """Check if the assignment has been submitted."""
        return self.ingeleverd_op is not None

    @property
    def is_beoordeeld(self) -> bool:
        """Check if the assignment has been graded."""
        return self.beoordeeld_op is not None

    @property
    def is_te_laat(self) -> bool:
        """Check if the deadline has passed without submission."""
        if self.is_ingeleverd:
            return False
        if self.inleveren_voor is None:
            return False
        return datetime.now() > self.inleveren_voor

    @property
    def deadline_tekst(self) -> str:
        """Get a human-readable deadline text."""
        if self.inleveren_voor is None:
            return "Geen deadline"
        return self.inleveren_voor.strftime("%d-%m-%Y %H:%M")

    @property
    def status_tekst(self) -> str:
        """Get a human-readable status text."""
        if self.is_beoordeeld:
            return f"Beoordeeld: {self.beoordeling or 'Geen cijfer'}"
        if self.is_ingeleverd:
            return "Ingeleverd, wacht op beoordeling"
        if self.is_te_laat:
            return "Te laat"
        if self.afgesloten:
            return "Afgesloten"
        return "Open"


class OpdrachtResponse(MagisterModel):
    """Response wrapper for assignments list."""

    items: list[Opdracht] = Field(default_factory=list, alias="Items")
    total_count: int | None = Field(default=None, alias="TotalCount")

    @classmethod
    def from_response(cls, data: dict) -> "OpdrachtResponse":
        """Create from API response, handling both wrapped and unwrapped formats."""
        if "Items" in data:
            return cls.model_validate(data)
        if isinstance(data, list):
            return cls(items=[Opdracht.model_validate(item) for item in data])
        return cls(items=[])

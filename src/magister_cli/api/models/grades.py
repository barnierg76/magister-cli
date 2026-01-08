"""Grade/mark models."""

from datetime import datetime

from pydantic import Field

from magister_cli.api.models.appointments import Vak
from magister_cli.api.models.base import MagisterModel


class CijferKolom(MagisterModel):
    """Grade column metadata."""

    id: int = Field(alias="Id")
    omschrijving: str = Field(default="", alias="Omschrijving")
    weging: float | None = Field(default=None, alias="Weging")
    is_gemiddelde: bool = Field(default=False, alias="IsGemiddelde")


class Cijfer(MagisterModel):
    """Grade/mark model."""

    id: int = Field(alias="CijferId")
    vak: Vak = Field(alias="Vak")
    cijfer_str: str = Field(alias="CijferStr")
    omschrijving: str = Field(default="", alias="Omschrijving")
    datum_ingevoerd: datetime = Field(alias="DatumIngevoerd")
    weging: float | None = Field(default=None, alias="Weging")
    is_voldoende: bool | None = Field(default=None, alias="IsVoldoende")
    kolom: CijferKolom | None = Field(default=None, alias="Kolom")

    @property
    def cijfer_numeriek(self) -> float | None:
        """Parse grade string to numeric value."""
        if not self.cijfer_str:
            return None
        try:
            return float(self.cijfer_str.replace(",", "."))
        except ValueError:
            return None

    @property
    def vak_naam(self) -> str:
        """Get the subject name for this grade."""
        return self.vak.naam


class CijferResponse(MagisterModel):
    """Response wrapper for grades list."""

    items: list[Cijfer] = Field(default_factory=list, alias="Items")

    @classmethod
    def from_response(cls, data: dict | list) -> "CijferResponse":
        """Create from API response, handling both wrapped and unwrapped formats."""
        if isinstance(data, dict) and "Items" in data:
            return cls.model_validate(data)
        if isinstance(data, list):
            return cls(items=[Cijfer.model_validate(item) for item in data])
        return cls(items=[])

"""Grade/mark models."""

from datetime import datetime
from typing import Optional

from pydantic import Field

from magister_cli.api.models.base import MagisterModel


class VakInfo(MagisterModel):
    """Subject info as returned in grade responses."""

    code: str = Field(alias="code")
    omschrijving: str = Field(alias="omschrijving")

    @property
    def naam(self) -> str:
        """Alias for compatibility."""
        return self.omschrijving

    @property
    def afkorting(self) -> str:
        """Alias for compatibility."""
        return self.code


class CijferKolom(MagisterModel):
    """Grade column metadata."""

    id: int = Field(alias="Id")
    omschrijving: str = Field(default="", alias="Omschrijving")
    weging: float | None = Field(default=None, alias="Weging")
    is_gemiddelde: bool = Field(default=False, alias="IsGemiddelde")


class Cijfer(MagisterModel):
    """Grade/mark model.

    Handles both old API format (PascalCase) and new API format (camelCase).
    """

    # Support both old and new API field names
    id: int = Field(alias="kolomId")
    vak: VakInfo = Field(alias="vak")
    cijfer_str: str = Field(alias="waarde")
    omschrijving: str = Field(default="", alias="omschrijving")
    datum_ingevoerd: datetime = Field(alias="ingevoerdOp")
    weging: float | None = Field(default=None, alias="weegfactor")
    is_voldoende: bool | None = Field(default=None, alias="isVoldoende")
    telt_mee: bool = Field(default=True, alias="teltMee")
    moet_inhalen: bool = Field(default=False, alias="moetInhalen")
    heeft_vrijstelling: bool = Field(default=False, alias="heeftVrijstelling")
    behaald_op: Optional[datetime] = Field(default=None, alias="behaaldOp")

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

    items: list[Cijfer] = Field(default_factory=list, alias="items")

    @classmethod
    def from_response(cls, data: dict | list) -> "CijferResponse":
        """Create from API response, handling both wrapped and unwrapped formats."""
        if isinstance(data, dict):
            # Try lowercase first (new API), then uppercase (old API)
            if "items" in data:
                return cls.model_validate(data)
            elif "Items" in data:
                return cls(items=[Cijfer.model_validate(item) for item in data["Items"]])
        if isinstance(data, list):
            return cls(items=[Cijfer.model_validate(item) for item in data])
        return cls(items=[])

"""Attendance/Absence models for Magister."""

from __future__ import annotations

from datetime import datetime
from enum import IntEnum

from pydantic import Field

from magister_cli.api.models.base import MagisterModel


class VerzuimType(IntEnum):
    """Types of absence in Magister."""

    ONBEKEND = 0
    ZIEK = 1
    TE_LAAT = 2
    GEOORLOOFD = 3
    ONGEOORLOOFD = 4
    HUISWERK_NIET_IN_ORDE = 5
    BOEKEN_NIET_IN_ORDE = 6
    VERWIJDERD = 7


class Absentie(MagisterModel):
    """Single absence/attendance record from Magister.

    Note: Field names match the Magister API response (Dutch, PascalCase).
    The API returns Items with these fields.
    """

    id: int = Field(alias="Id")
    start: datetime = Field(alias="Start")
    einde: datetime = Field(alias="Eind")

    # Absence type and status
    afspraak_id: int | None = Field(None, alias="AfspraakId")
    les_uur: int | None = Field(None, alias="Lesuur")

    # Description and reason
    omschrijving: str = Field("", alias="Omschrijving")
    code: str = Field("", alias="Code")

    # Type classification
    type: int = Field(0, alias="Verzuimtype")
    geoorloofd: bool = Field(True, alias="Geoorloofd")

    # Status
    afgehandeld: bool = Field(False, alias="Afgehandeld")

    # Linked lesson info (if available)
    vak: str | None = Field(None, alias="Vak")
    docent: str | None = Field(None, alias="Docent")
    lokaal: str | None = Field(None, alias="Lokaal")

    @property
    def verzuim_type(self) -> VerzuimType:
        """Get the absence type as enum."""
        try:
            return VerzuimType(self.type)
        except ValueError:
            return VerzuimType.ONBEKEND

    @property
    def type_naam(self) -> str:
        """Get human-readable absence type name."""
        type_names = {
            VerzuimType.ONBEKEND: "Onbekend",
            VerzuimType.ZIEK: "Ziek",
            VerzuimType.TE_LAAT: "Te laat",
            VerzuimType.GEOORLOOFD: "Geoorloofd afwezig",
            VerzuimType.ONGEOORLOOFD: "Ongeoorloofd afwezig",
            VerzuimType.HUISWERK_NIET_IN_ORDE: "Huiswerk niet in orde",
            VerzuimType.BOEKEN_NIET_IN_ORDE: "Boeken niet in orde",
            VerzuimType.VERWIJDERD: "Verwijderd uit les",
        }
        return type_names.get(self.verzuim_type, "Onbekend")

    @property
    def datum_str(self) -> str:
        """Get formatted date string."""
        return self.start.strftime("%a %d %b %Y")

    @property
    def tijd_str(self) -> str:
        """Get formatted time range string."""
        start_str = self.start.strftime("%H:%M")
        einde_str = self.einde.strftime("%H:%M")
        return f"{start_str} - {einde_str}"

"""Appointment/schedule models."""

from datetime import datetime

from pydantic import Field

from magister_cli.api.models.attachments import Bijlage
from magister_cli.api.models.base import MagisterModel


class Vak(MagisterModel):
    """Subject/course model."""

    id: int = Field(alias="Id")
    naam: str = Field(alias="Naam")
    afkorting: str | None = Field(default=None, alias="Afkorting")


class Lokaal(MagisterModel):
    """Classroom/location model."""

    naam: str = Field(alias="Naam")


class Docent(MagisterModel):
    """Teacher model."""

    naam: str = Field(alias="Naam")
    afkorting: str | None = Field(default=None, alias="Afkorting")


class Afspraak(MagisterModel):
    """Appointment/lesson with possible homework."""

    id: int = Field(alias="Id")
    start: datetime = Field(alias="Start")
    einde: datetime = Field(alias="Einde")
    omschrijving: str = Field(alias="Omschrijving")
    inhoud: str | None = Field(default=None, alias="Inhoud")
    huiswerk: str | None = Field(default=None, alias="Huiswerk")
    info_type: int = Field(alias="InfoType")
    status: int = Field(default=0, alias="Status")
    vakken: list[Vak] = Field(default_factory=list, alias="Vakken")
    lokalen: list[Lokaal] = Field(default_factory=list, alias="Lokalen")
    docenten: list[Docent] = Field(default_factory=list, alias="Docenten")
    les_uur: int | None = Field(default=None, alias="LesuurVan")
    afgerond: bool = Field(default=False, alias="Afgerond")
    is_toets: bool = Field(default=False, alias="Toets")
    heeft_bijlagen: bool = Field(default=False, alias="HeeftBijlagen")
    bijlagen: list[Bijlage] | None = Field(default=None, alias="Bijlagen")

    def is_test_or_exam(self) -> bool:
        """Check if this appointment is a test/exam using API fields only.

        Relies on:
        - Toets: Boolean flag set by teachers in Magister
        - InfoType: Type indicator (2=Test, 3=Exam, 4=Written quiz, 5=Oral quiz)

        Note: We intentionally do NOT parse description text to avoid false positives
        from homework that mentions future tests (e.g., "prepare for next week's test").
        The Magister UI uses these same API fields for the "Proefwerk" badge.
        """
        # Check explicit API flag
        if self.is_toets:
            return True

        # Check InfoType enum values
        # 2=Test, 3=Exam, 4=Written quiz, 5=Oral quiz
        if self.info_type in {2, 3, 4, 5}:
            return True

        return False

    @property
    def bijlagen_lijst(self) -> list[Bijlage]:
        """Get attachments as a list (never None)."""
        return self.bijlagen or []

    @property
    def heeft_huiswerk(self) -> bool:
        """Check if this appointment has homework."""
        return bool(self.inhoud or self.huiswerk)

    @property
    def huiswerk_tekst(self) -> str:
        """Get the homework text."""
        return self.inhoud or self.huiswerk or ""

    @property
    def vak_naam(self) -> str:
        """Get the primary subject name."""
        return self.vakken[0].naam if self.vakken else self.omschrijving

    @property
    def vak_afkorting(self) -> str | None:
        """Get the primary subject abbreviation."""
        return self.vakken[0].afkorting if self.vakken else None

    @property
    def lokaal_naam(self) -> str | None:
        """Get the primary location name."""
        return self.lokalen[0].naam if self.lokalen else None

    @property
    def docent_naam(self) -> str | None:
        """Get the primary teacher name."""
        return self.docenten[0].naam if self.docenten else None

    @property
    def is_vervallen(self) -> bool:
        """Check if this lesson is cancelled."""
        # Status 4 = cancelled/vervallen in Magister
        return self.status == 4

    @property
    def is_gewijzigd(self) -> bool:
        """Check if this lesson has been modified."""
        # Status 5 = modified/gewijzigd in Magister
        return self.status == 5


class AfspraakResponse(MagisterModel):
    """Response wrapper for appointments list."""

    items: list[Afspraak] = Field(default_factory=list, alias="Items")
    total_count: int | None = Field(default=None, alias="TotalCount")

    @classmethod
    def from_response(cls, data: dict) -> "AfspraakResponse":
        """Create from API response, handling both wrapped and unwrapped formats."""
        if "Items" in data:
            return cls.model_validate(data)
        if isinstance(data, list):
            return cls(items=[Afspraak.model_validate(item) for item in data])
        return cls(items=[])

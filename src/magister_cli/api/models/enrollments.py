"""Enrollment and study year models."""

from datetime import date, datetime

from pydantic import Field

from magister_cli.api.models.base import MagisterModel


class Studie(MagisterModel):
    """Study program information."""

    id: int = Field(alias="Id")
    omschrijving: str = Field(default="", alias="Omschrijving")


class KlasGroep(MagisterModel):
    """Class group information."""

    id: int = Field(alias="Id")
    omschrijving: str = Field(default="", alias="Omschrijving")


class Aanmelding(MagisterModel):
    """Enrollment/registration for a school year.

    Represents a student's enrollment in a specific study program
    for a specific school year.
    """

    id: int = Field(alias="Id")
    studie: Studie = Field(alias="Studie")
    lesperiode: str | None = Field(default=None, alias="Lesperiode")
    groep_obj: KlasGroep | None = Field(default=None, alias="Groep")
    van: datetime | None = Field(default=None, alias="Start")
    tot: datetime | None = Field(default=None, alias="Einde")

    @property
    def studie_naam(self) -> str:
        """Get the study program name."""
        return self.studie.omschrijving

    @property
    def groep(self) -> str | None:
        """Get the class group name."""
        return self.groep_obj.omschrijving if self.groep_obj else None

    @property
    def leerjaar(self) -> int:
        """Extract year from lesperiode (e.g., '2526' -> 25) or studie."""
        if self.lesperiode and len(self.lesperiode) >= 2:
            try:
                return int(self.lesperiode[:2])
            except ValueError:
                pass
        # Fallback: try to extract from studie name
        return 0

    @property
    def is_actief(self) -> bool:
        """Check if this enrollment is currently active."""
        today = date.today()
        if self.van and today < self.van.date():
            return False
        if self.tot and today > self.tot.date():
            return False
        return True

    @property
    def display_name(self) -> str:
        """Get a display name like 'Mavo/Havo klas 8 (Klas a08a)'."""
        name = self.studie_naam
        if self.groep:
            name += f" ({self.groep})"
        return name


class Periode(MagisterModel):
    """Grading period within a school year."""

    id: int = Field(alias="Id")
    naam: str = Field(alias="Naam")  # e.g., "Periode 1", "Trimester 2"
    afkorting: str | None = Field(default=None, alias="Afkorting")
    van: date | None = Field(default=None, alias="VanDatum")
    tot: date | None = Field(default=None, alias="TotDatum")
    is_voortgang_periode: bool = Field(default=False, alias="IsVoortgangPeriode")

    @property
    def is_actief(self) -> bool:
        """Check if this period is currently active."""
        today = date.today()
        if self.van and today < self.van:
            return False
        if self.tot and today > self.tot:
            return False
        return True


class VakCijferOverzicht(MagisterModel):
    """Grade overview for a single subject."""

    vak_id: int = Field(alias="VakId")
    vak_omschrijving: str = Field(alias="VakOmschrijving")
    vak_afkorting: str | None = Field(default=None, alias="VakAfkorting")
    gemiddelde: str | None = Field(default=None, alias="Gemiddelde")
    gemiddelde_afgerond: str | None = Field(default=None, alias="GemiddeldeAfgerond")

    @property
    def gemiddelde_numeriek(self) -> float | None:
        """Parse average to numeric value."""
        val = self.gemiddelde or self.gemiddelde_afgerond
        if not val:
            return None
        try:
            return float(val.replace(",", "."))
        except ValueError:
            return None

    @property
    def is_voldoende(self) -> bool:
        """Check if average is passing (>= 5.5)."""
        avg = self.gemiddelde_numeriek
        return avg is not None and avg >= 5.5


class CijferPeriodeOverzicht(MagisterModel):
    """Grade overview for a period."""

    periode: Periode = Field(alias="Periode")
    cijfers: list["VakCijferOverzicht"] = Field(default_factory=list, alias="Vakken")


class AanmeldingenResponse(MagisterModel):
    """Response wrapper for enrollments list."""

    items: list[Aanmelding] = Field(default_factory=list, alias="Items")

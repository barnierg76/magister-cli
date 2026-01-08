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


class StudieVak(MagisterModel):
    """Subject/course in a study program (from /vakken endpoint)."""

    id: int = Field(alias="id")
    code: str = Field(alias="code")
    omschrijving: str = Field(alias="omschrijving")
    niveau: str | None = Field(default=None, alias="niveau")
    volgnummer: int | None = Field(default=None, alias="volgnummer")
    heeft_cijferstructuur: bool = Field(default=True, alias="heeftCijferstructuur")

    @property
    def naam(self) -> str:
        """Get the subject name."""
        return self.omschrijving

    @property
    def afkorting(self) -> str:
        """Get the subject code/abbreviation."""
        return self.code


class VakDocent(MagisterModel):
    """Teacher assigned to a subject."""

    is_hoofd_docent: bool = Field(default=False, alias="isHoofdDocent")
    code: str = Field(alias="code")
    voorletters: str | None = Field(default=None, alias="voorletters")
    tussenvoegsel: str | None = Field(default=None, alias="tussenvoegsel")
    achternaam: str = Field(alias="achternaam")

    @property
    def naam(self) -> str:
        """Get the full name."""
        parts = []
        if self.voorletters:
            parts.append(self.voorletters)
        if self.tussenvoegsel:
            parts.append(self.tussenvoegsel)
        parts.append(self.achternaam)
        return " ".join(parts)


class VakInschrijving(MagisterModel):
    """Subject enrollment (student registered for a subject in an academic year)."""

    id: int = Field(alias="id")
    begin: date = Field(alias="begin")
    einde: date = Field(alias="einde")
    studievak: StudieVak = Field(alias="studievak")
    docenten: list[VakDocent] | None = Field(default=None, alias="docenten")
    heeft_ontheffing: bool = Field(default=False, alias="heeftOntheffing")
    heeft_vrijstelling: bool = Field(default=False, alias="heeftVrijstelling")
    is_roostertechnisch: bool = Field(default=False, alias="isRoostertechnisch")

    @property
    def vak_naam(self) -> str:
        """Get the subject name."""
        return self.studievak.naam

    @property
    def vak_code(self) -> str:
        """Get the subject code."""
        return self.studievak.code

    @property
    def hoofd_docent(self) -> str | None:
        """Get the main teacher name."""
        if self.docenten:
            for docent in self.docenten:
                if docent.is_hoofd_docent:
                    return docent.naam
            # Fallback to first docent if no main docent
            return self.docenten[0].naam if self.docenten else None
        return None

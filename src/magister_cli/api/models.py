"""Pydantic models for Magister API responses."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Vak(BaseModel):
    """Subject/course model."""

    model_config = ConfigDict(populate_by_name=True)

    id: int = Field(alias="Id")
    naam: str = Field(alias="Naam")
    afkorting: str | None = Field(default=None, alias="Afkorting")


class Lokaal(BaseModel):
    """Classroom/location model."""

    model_config = ConfigDict(populate_by_name=True)

    naam: str = Field(alias="Naam")


class Docent(BaseModel):
    """Teacher model."""

    model_config = ConfigDict(populate_by_name=True)

    naam: str = Field(alias="Naam")
    afkorting: str | None = Field(default=None, alias="Afkorting")


class BijlageLink(BaseModel):
    """Link to attachment content."""

    model_config = ConfigDict(populate_by_name=True)

    rel: str = Field(alias="Rel")
    href: str = Field(alias="Href")


class Bijlage(BaseModel):
    """Attachment model."""

    model_config = ConfigDict(populate_by_name=True)

    id: int = Field(alias="Id")
    naam: str = Field(alias="Naam")
    content_type: str = Field(alias="ContentType")
    grootte: int = Field(default=0, alias="Grootte")
    datum: datetime | None = Field(default=None, alias="Datum")
    links: list[BijlageLink] = Field(default_factory=list, alias="Links")

    @property
    def download_path(self) -> str | None:
        """Get the download path for this attachment."""
        for link in self.links:
            if link.rel == "Contents":
                return link.href
        return None

    @property
    def grootte_leesbaar(self) -> str:
        """Get human-readable file size."""
        if self.grootte < 1024:
            return f"{self.grootte} B"
        elif self.grootte < 1024 * 1024:
            return f"{self.grootte / 1024:.1f} KB"
        else:
            return f"{self.grootte / (1024 * 1024):.1f} MB"


class Afspraak(BaseModel):
    """Appointment/lesson with possible homework."""

    model_config = ConfigDict(populate_by_name=True)

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


class CijferKolom(BaseModel):
    """Grade column metadata."""

    model_config = ConfigDict(populate_by_name=True)

    id: int = Field(alias="Id")
    omschrijving: str = Field(default="", alias="Omschrijving")
    weging: float | None = Field(default=None, alias="Weging")
    is_gemiddelde: bool = Field(default=False, alias="IsGemiddelde")


class Cijfer(BaseModel):
    """Grade/mark model."""

    model_config = ConfigDict(populate_by_name=True)

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


class Persoon(BaseModel):
    """Person/student model."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: int = Field(alias="Id")
    roepnaam: str | None = Field(default=None, alias="Roepnaam")
    voornaam: str | None = Field(default=None, alias="Voornaam")
    achternaam: str | None = Field(default=None, alias="Achternaam")
    tussenvoegsel: str | None = Field(default=None, alias="Tussenvoegsel")

    @property
    def volledige_naam(self) -> str:
        """Get the full name."""
        first_name = self.roepnaam or self.voornaam or ""
        parts = [first_name] if first_name else []
        if self.tussenvoegsel:
            parts.append(self.tussenvoegsel)
        if self.achternaam:
            parts.append(self.achternaam)
        return " ".join(parts) if parts else "Onbekend"


class Kind(BaseModel):
    """Child model for parent accounts."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: int = Field(alias="Id")
    roepnaam: str | None = Field(default=None, alias="Roepnaam")
    voornaam: str | None = Field(default=None, alias="Voornaam")
    achternaam: str | None = Field(default=None, alias="Achternaam")
    tussenvoegsel: str | None = Field(default=None, alias="Tussenvoegsel")

    @property
    def volledige_naam(self) -> str:
        """Get the full name."""
        first_name = self.roepnaam or self.voornaam or ""
        parts = [first_name] if first_name else []
        if self.tussenvoegsel:
            parts.append(self.tussenvoegsel)
        if self.achternaam:
            parts.append(self.achternaam)
        return " ".join(parts) if parts else "Onbekend"


class Groep(BaseModel):
    """Group/role model."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    naam: str = Field(alias="Naam")


class Account(BaseModel):
    """Account info after login."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    persoon: Persoon = Field(alias="Persoon")
    groep: list[Groep] = Field(default_factory=list, alias="Groep")

    @property
    def persoon_id(self) -> int:
        """Get the person ID."""
        return self.persoon.id

    @property
    def naam(self) -> str:
        """Get the person's full name."""
        return self.persoon.volledige_naam

    @property
    def is_parent(self) -> bool:
        """Check if this is a parent account."""
        return any(g.naam == "Ouder" for g in self.groep)


class AfspraakResponse(BaseModel):
    """Response wrapper for appointments list."""

    model_config = ConfigDict(populate_by_name=True)

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


class CijferResponse(BaseModel):
    """Response wrapper for grades list."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[Cijfer] = Field(default_factory=list, alias="Items")

    @classmethod
    def from_response(cls, data: dict | list) -> "CijferResponse":
        """Create from API response, handling both wrapped and unwrapped formats."""
        if isinstance(data, dict) and "Items" in data:
            return cls.model_validate(data)
        if isinstance(data, list):
            return cls(items=[Cijfer.model_validate(item) for item in data])
        return cls(items=[])


class KindResponse(BaseModel):
    """Response wrapper for children list."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[Kind] = Field(default_factory=list, alias="Items")

    @classmethod
    def from_response(cls, data: dict | list) -> "KindResponse":
        """Create from API response, handling both wrapped and unwrapped formats."""
        if isinstance(data, dict) and "Items" in data:
            return cls.model_validate(data)
        if isinstance(data, list):
            return cls(items=[Kind.model_validate(item) for item in data])
        return cls(items=[])

"""Account-related models."""

from pydantic import Field

from magister_cli.api.models.base import MagisterModel


class Persoon(MagisterModel):
    """Person/student model."""

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


class Kind(MagisterModel):
    """Child model for parent accounts."""

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


class Groep(MagisterModel):
    """Group/role model."""

    naam: str = Field(alias="Naam")


class Account(MagisterModel):
    """Account info after login."""

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


class KindResponse(MagisterModel):
    """Response wrapper for children list."""

    items: list[Kind] = Field(default_factory=list, alias="Items")

    @classmethod
    def from_response(cls, data: dict | list) -> "KindResponse":
        """Create from API response, handling both wrapped and unwrapped formats."""
        if isinstance(data, dict) and "Items" in data:
            return cls.model_validate(data)
        if isinstance(data, list):
            return cls(items=[Kind.model_validate(item) for item in data])
        return cls(items=[])

"""Learning materials (lesmateriaal) models."""

from datetime import datetime

from pydantic import Field

from magister_cli.api.models.base import MagisterModel


class LesmateriaalVak(MagisterModel):
    """Subject for learning material."""

    id: int = Field(alias="Id")
    afkorting: str | None = Field(default=None, alias="Afkorting")
    omschrijving: str | None = Field(default=None, alias="Omschrijving")
    volgnr: int = Field(default=0, alias="Volgnr")


class Lesmateriaal(MagisterModel):
    """Digital learning material (textbook, online resource)."""

    id: int = Field(alias="Id")
    titel: str = Field(alias="Titel")
    uitgeverij: str | None = Field(default=None, alias="Uitgeverij")
    ean: str | None = Field(default=None, alias="EAN")
    status: int = Field(default=0, alias="Status")
    materiaal_type: int = Field(default=0, alias="MateriaalType")
    start: datetime | None = Field(default=None, alias="Start")
    eind: datetime | None = Field(default=None, alias="Eind")
    preview_image_url: str | None = Field(default=None, alias="PreviewImageUrl")
    vak: LesmateriaalVak | None = Field(default=None, alias="Vak")

    @property
    def vak_naam(self) -> str | None:
        """Get the subject name."""
        return self.vak.omschrijving if self.vak else None

    @property
    def vak_afkorting(self) -> str | None:
        """Get the subject abbreviation."""
        return self.vak.afkorting if self.vak else None

    @property
    def is_actief(self) -> bool:
        """Check if the material is currently active."""
        now = datetime.now()
        if self.start and now < self.start:
            return False
        if self.eind and now > self.eind:
            return False
        return True


class LesmateriaalResponse(MagisterModel):
    """Response wrapper for learning materials list."""

    items: list[Lesmateriaal] = Field(default_factory=list, alias="Items")
    total_count: int | None = Field(default=None, alias="TotalCount")

    @classmethod
    def from_response(cls, data: dict) -> "LesmateriaalResponse":
        """Create from API response, handling both wrapped and unwrapped formats."""
        if "Items" in data:
            return cls.model_validate(data)
        if isinstance(data, list):
            return cls(items=[Lesmateriaal.model_validate(item) for item in data])
        return cls(items=[])

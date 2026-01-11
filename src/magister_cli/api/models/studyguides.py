"""Study guide (studiewijzer) models."""

from datetime import datetime

from pydantic import Field

from magister_cli.api.models.base import MagisterModel


class StudiewijzerBron(MagisterModel):
    """Resource/attachment in a study guide section."""

    id: int = Field(alias="Id")
    naam: str | None = Field(default=None, alias="Naam")
    uri: str | None = Field(default=None, alias="Uri")
    bron_soort: int | None = Field(default=None, alias="BronSoort")
    content_type: str | None = Field(default=None, alias="ContentType")
    grootte: int | None = Field(default=None, alias="Grootte")


class StudiewijzerOnderdeel(MagisterModel):
    """Section/part of a study guide."""

    id: int = Field(alias="Id")
    titel: str = Field(alias="Titel")
    omschrijving: str | None = Field(default="", alias="Omschrijving")
    van: datetime | None = Field(default=None, alias="Van")
    tot_en_met: datetime | None = Field(default=None, alias="TotEnMet")
    is_zichtbaar: bool = Field(default=True, alias="IsZichtbaar")
    kleur: int = Field(default=0, alias="Kleur")
    volgnummer: int = Field(default=0, alias="Volgnummer")
    bronnen: list[StudiewijzerBron] = Field(default_factory=list, alias="Bronnen")


class StudiewijzerOnderdelenResponse(MagisterModel):
    """Response wrapper for study guide sections."""

    items: list[StudiewijzerOnderdeel] = Field(default_factory=list, alias="Items")
    total_count: int | None = Field(default=None, alias="TotalCount")


class Studiewijzer(MagisterModel):
    """Study guide with sections and resources."""

    id: int = Field(alias="Id")
    titel: str = Field(alias="Titel")
    van: datetime | None = Field(default=None, alias="Van")
    tot_en_met: datetime | None = Field(default=None, alias="TotEnMet")
    is_zichtbaar: bool = Field(default=True, alias="IsZichtbaar")
    in_leerling_archief: bool = Field(default=False, alias="InLeerlingArchief")
    vak_codes: list[str] = Field(default_factory=list, alias="VakCodes")
    onderdelen: StudiewijzerOnderdelenResponse | None = Field(default=None, alias="Onderdelen")

    @property
    def onderdelen_lijst(self) -> list[StudiewijzerOnderdeel]:
        """Get sections as a list (never None)."""
        if self.onderdelen is None:
            return []
        return self.onderdelen.items

    @property
    def aantal_onderdelen(self) -> int:
        """Get the number of sections."""
        return len(self.onderdelen_lijst)

    @property
    def heeft_bronnen(self) -> bool:
        """Check if any section has resources."""
        return any(len(o.bronnen) > 0 for o in self.onderdelen_lijst)


class StudiewijzerResponse(MagisterModel):
    """Response wrapper for study guides list."""

    items: list[Studiewijzer] = Field(default_factory=list, alias="Items")
    total_count: int | None = Field(default=None, alias="TotalCount")

    @classmethod
    def from_response(cls, data: dict) -> "StudiewijzerResponse":
        """Create from API response, handling both wrapped and unwrapped formats."""
        if "Items" in data:
            return cls.model_validate(data)
        if isinstance(data, list):
            return cls(items=[Studiewijzer.model_validate(item) for item in data])
        return cls(items=[])

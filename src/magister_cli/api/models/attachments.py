"""Attachment models."""

from datetime import datetime

from pydantic import Field

from magister_cli.api.models.base import MagisterModel


class BijlageLink(MagisterModel):
    """Link to attachment content."""

    rel: str = Field(alias="Rel")
    href: str = Field(alias="Href")


class Bijlage(MagisterModel):
    """Attachment model."""

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

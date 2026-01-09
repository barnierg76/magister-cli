"""Learning materials (lesmateriaal) resource."""

from __future__ import annotations

from magister_cli.api.base import BaseResource
from magister_cli.api.models import Lesmateriaal


class LearningMaterialsResource(BaseResource):
    """Resource for learning materials (lesmateriaal) API calls."""

    def list(self) -> list[Lesmateriaal]:
        """Get all learning materials for the student.

        Returns:
            List of digital learning materials (textbooks, online resources)
        """
        data = self._get(f"/personen/{self._person_id}/lesmateriaal")
        items = self._extract_items(data)
        return [Lesmateriaal.model_validate(item) for item in items]

    def active(self) -> list[Lesmateriaal]:
        """Get only currently active learning materials.

        Returns:
            List of learning materials that are currently active
        """
        materials = self.list()
        return [m for m in materials if m.is_actief]

    def by_subject(self, vak_afkorting: str) -> list[Lesmateriaal]:
        """Get learning materials for a specific subject.

        Args:
            vak_afkorting: Subject abbreviation (e.g., 'du', 'ne', 'wi')

        Returns:
            List of learning materials for that subject
        """
        materials = self.list()
        return [
            m for m in materials
            if m.vak_afkorting and m.vak_afkorting.lower() == vak_afkorting.lower()
        ]

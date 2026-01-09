"""Study guides (studiewijzers) resource."""

from __future__ import annotations

from magister_cli.api.base import BaseResource
from magister_cli.api.models import Studiewijzer


class StudyGuidesResource(BaseResource):
    """Resource for study guide (studiewijzer) API calls.

    Note: Study guides use the /leerlingen/{id} endpoint pattern,
    not /personen/{id} like most other resources.
    """

    def list(self) -> list[Studiewijzer]:
        """Get all study guides for the student.

        Returns:
            List of study guides (without full details/sections)
        """
        data = self._get(f"/leerlingen/{self._person_id}/studiewijzers")
        items = self._extract_items(data)
        return [Studiewijzer.model_validate(item) for item in items]

    def get(self, studiewijzer_id: int) -> Studiewijzer:
        """Get a single study guide with full details including sections.

        Args:
            studiewijzer_id: The study guide ID

        Returns:
            Full study guide including sections (onderdelen) and resources (bronnen)
        """
        data = self._get(
            f"/leerlingen/{self._person_id}/studiewijzers/{studiewijzer_id}"
        )
        return Studiewijzer.model_validate(data)

    def list_with_details(self) -> list[Studiewijzer]:
        """Get all study guides with full details.

        This fetches each study guide individually to get the full
        section and resource information.

        Returns:
            List of study guides with full details
        """
        guides = self.list()
        return [self.get(g.id) for g in guides]

    def active(self) -> list[Studiewijzer]:
        """Get only currently active study guides.

        Returns:
            List of study guides that are currently visible
        """
        guides = self.list()
        return [g for g in guides if g.is_zichtbaar and not g.in_leerling_archief]

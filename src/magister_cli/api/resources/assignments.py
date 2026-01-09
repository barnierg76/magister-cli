"""ELO Assignments (opdrachten) resource."""

from __future__ import annotations

from magister_cli.api.base import BaseResource
from magister_cli.api.models import Opdracht


class AssignmentsResource(BaseResource):
    """Resource for ELO assignment (opdracht) API calls."""

    def list(self) -> list[Opdracht]:
        """Get all assignments for the student.

        Returns:
            List of ELO assignments
        """
        data = self._get(f"/personen/{self._person_id}/opdrachten")
        items = self._extract_items(data)
        return [Opdracht.model_validate(item) for item in items]

    def get(self, opdracht_id: int) -> Opdracht:
        """Get a single assignment with full details.

        Args:
            opdracht_id: The assignment ID

        Returns:
            Full assignment details
        """
        data = self._get(f"/personen/{self._person_id}/opdrachten/{opdracht_id}")
        return Opdracht.model_validate(data)

    def open(self) -> list[Opdracht]:
        """Get only open (not yet submitted) assignments.

        Returns:
            List of assignments that haven't been submitted yet
        """
        assignments = self.list()
        return [a for a in assignments if not a.is_ingeleverd and not a.afgesloten]

    def pending_review(self) -> list[Opdracht]:
        """Get assignments waiting for review.

        Returns:
            List of assignments that have been submitted but not yet graded
        """
        assignments = self.list()
        return [a for a in assignments if a.is_ingeleverd and not a.is_beoordeeld]

    def overdue(self) -> list[Opdracht]:
        """Get overdue assignments.

        Returns:
            List of assignments past deadline that haven't been submitted
        """
        assignments = self.list()
        return [a for a in assignments if a.is_te_laat]

    def by_subject(self, vak: str) -> list[Opdracht]:
        """Get assignments for a specific subject.

        Args:
            vak: Subject abbreviation (e.g., 'mu', 'ne', 'wi')

        Returns:
            List of assignments for that subject
        """
        assignments = self.list()
        return [
            a for a in assignments
            if a.vak and a.vak.lower() == vak.lower()
        ]

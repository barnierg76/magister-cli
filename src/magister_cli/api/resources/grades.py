"""Grades resource for marks and results."""

from __future__ import annotations

from magister_cli.api.base import BaseResource
from magister_cli.api.models import Aanmelding, Cijfer, Vak


class GradesResource(BaseResource):
    """Resource for grade-related API calls."""

    def recent(self, limit: int = 10) -> list[Cijfer]:
        """Get recent grades.

        Args:
            limit: Maximum number of grades to return

        Returns:
            List of recent grades
        """
        data = self._get(
            f"/personen/{self._person_id}/cijfers/laatste",
            params={"top": limit},
        )
        items = data.get("Items", []) if isinstance(data, dict) else data
        return [Cijfer.model_validate(item) for item in items]

    def enrollments(self) -> list[Aanmelding]:
        """Get all enrollments (school years) for the student.

        Returns:
            List of enrollments, most recent first
        """
        data = self._get(f"/personen/{self._person_id}/aanmeldingen")
        items = data.get("Items", []) if isinstance(data, dict) else data
        enrollments = [Aanmelding.model_validate(item) for item in items]
        # Sort by leerjaar descending (most recent first)
        return sorted(enrollments, key=lambda e: e.leerjaar, reverse=True)

    def current_enrollment(self) -> Aanmelding | None:
        """Get the current/active enrollment.

        Returns:
            The active enrollment or None if not found
        """
        enrollments = self.enrollments()
        for enrollment in enrollments:
            if enrollment.is_actief:
                return enrollment
        # Fall back to most recent if none active
        return enrollments[0] if enrollments else None

    def all_grades(self, enrollment_id: int | None = None) -> list[Cijfer]:
        """Get all grades for an enrollment.

        Args:
            enrollment_id: The enrollment ID. If None, uses current enrollment.

        Returns:
            List of all grades for the enrollment
        """
        if enrollment_id is None:
            enrollment = self.current_enrollment()
            if enrollment is None:
                return []
            enrollment_id = enrollment.id

        data = self._get(
            f"/aanmeldingen/{enrollment_id}/cijfers/cijferoverzichtvooraanmelding",
            params={"actievePerioden": "false", "alleenBerewordeeldePeriwordes": "false"},
        )

        # The response contains a complex structure with grades per subject per period
        # We flatten it to a simple list of grades
        grades = []
        items = data.get("Items", []) if isinstance(data, dict) else []

        for item in items:
            # Each item is a subject with its grades
            cijfer_list = item.get("CijferKolommen", [])
            for kolom in cijfer_list:
                cijfer_items = kolom.get("Cijfers", [])
                for cijfer_data in cijfer_items:
                    try:
                        cijfer = Cijfer.model_validate(cijfer_data)
                        grades.append(cijfer)
                    except Exception:
                        # Skip invalid grade data
                        continue

        return grades

    def subjects(self, enrollment_id: int | None = None) -> list[Vak]:
        """Get subjects for an enrollment.

        Args:
            enrollment_id: The enrollment ID. If None, uses current enrollment.

        Returns:
            List of subjects for the enrollment
        """
        if enrollment_id is None:
            enrollment = self.current_enrollment()
            if enrollment is None:
                return []
            enrollment_id = enrollment.id

        data = self._get(f"/aanmeldingen/{enrollment_id}/vakken")
        items = data.get("Items", []) if isinstance(data, dict) else data
        return [Vak.model_validate(item) for item in items]

    def by_subject(
        self,
        subject: str | None = None,
        enrollment_id: int | None = None,
    ) -> list[Cijfer]:
        """Get grades filtered by subject.

        Args:
            subject: Subject name to filter by (case-insensitive partial match)
            enrollment_id: The enrollment ID. If None, uses current enrollment.

        Returns:
            List of grades for the subject
        """
        grades = self.all_grades(enrollment_id)

        if subject:
            subject_lower = subject.lower()
            grades = [
                g for g in grades
                if subject_lower in g.vak_naam.lower()
                or (g.vak.afkorting and subject_lower in g.vak.afkorting.lower())
            ]

        return grades

    def averages_by_subject(
        self,
        enrollment_id: int | None = None,
    ) -> dict[str, float | None]:
        """Calculate average grades per subject.

        Args:
            enrollment_id: The enrollment ID. If None, uses current enrollment.

        Returns:
            Dictionary mapping subject name to average grade
        """
        grades = self.all_grades(enrollment_id)

        # Group grades by subject
        subject_grades: dict[str, list[float]] = {}
        for grade in grades:
            numeric = grade.cijfer_numeriek
            if numeric is not None:
                subject_name = grade.vak_naam
                if subject_name not in subject_grades:
                    subject_grades[subject_name] = []
                subject_grades[subject_name].append(numeric)

        # Calculate averages
        averages: dict[str, float | None] = {}
        for subject, values in subject_grades.items():
            if values:
                averages[subject] = sum(values) / len(values)
            else:
                averages[subject] = None

        return averages

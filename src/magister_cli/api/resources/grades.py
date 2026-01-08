"""Grades resource for marks and results."""

from __future__ import annotations

import logging

from magister_cli.api.base import BaseResource
from magister_cli.api.models import Aanmelding, Cijfer, VakInschrijving

logger = logging.getLogger(__name__)


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
        logger.debug(f"Recent grades API response type: {type(data)}")
        logger.debug(f"Recent grades API response: {data}")

        # API returns lowercase "items", not "Items"
        if isinstance(data, dict):
            items = data.get("items", data.get("Items", []))
        else:
            items = data
        logger.debug(f"Extracted {len(items)} items from response")

        grades = []
        for item in items:
            try:
                grade = Cijfer.model_validate(item)
                grades.append(grade)
            except Exception as e:
                logger.warning(f"Failed to parse grade item: {e}")
                logger.debug(f"Problematic item: {item}")

        logger.debug(f"Successfully parsed {len(grades)} grades")
        return grades

    def enrollments(self) -> list[Aanmelding]:
        """Get all enrollments (school years) for the student.

        Returns:
            List of enrollments, most recent first
        """
        data = self._get(f"/personen/{self._person_id}/aanmeldingen")
        items = data.get("items", data.get("Items", [])) if isinstance(data, dict) else data
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

        # Get the grades from the correct endpoint
        data = self._get(f"/aanmeldingen/{enrollment_id}/cijfers")
        items = data.get("items", data.get("Items", [])) if isinstance(data, dict) else []

        if not items:
            return []

        # Get subjects to map studievakId to vak info
        subjects = self.subjects(enrollment_id)
        vak_map: dict[int, dict] = {}
        for subject in subjects:
            vak_map[subject.studievak.id] = {
                "code": subject.vak_code,
                "omschrijving": subject.vak_naam,
            }

        # Parse grades and add vak info
        grades = []
        for item in items:
            try:
                kolom = item.get("kolom", {})
                studievak_id = kolom.get("studievakId")
                vak_info = vak_map.get(studievak_id, {"code": "?", "omschrijving": "Onbekend"})

                # Build grade data in the format expected by Cijfer model
                grade_data = {
                    "kolomId": kolom.get("id"),
                    "vak": vak_info,
                    "waarde": item.get("waarde", ""),
                    "omschrijving": kolom.get("omschrijving", ""),
                    "ingevoerdOp": item.get("ingevoerdOp"),
                    "weegfactor": kolom.get("weegfactor"),
                    "isVoldoende": item.get("isVoldoende"),
                    "teltMee": item.get("teltMee", True),
                    "moetInhalen": item.get("moetInhalen", False),
                    "heeftVrijstelling": item.get("heeftVrijstelling", False),
                }

                grade = Cijfer.model_validate(grade_data)
                grades.append(grade)
            except Exception as e:
                logger.debug(f"Failed to parse grade: {e}")
                continue

        return grades

    def subjects(self, enrollment_id: int | None = None) -> list[VakInschrijving]:
        """Get subjects for an enrollment.

        Args:
            enrollment_id: The enrollment ID. If None, uses current enrollment.

        Returns:
            List of subject enrollments for the student
        """
        if enrollment_id is None:
            enrollment = self.current_enrollment()
            if enrollment is None:
                return []
            enrollment_id = enrollment.id

        data = self._get(f"/aanmeldingen/{enrollment_id}/vakken")
        items = data.get("items", data.get("Items", [])) if isinstance(data, dict) else data
        return [VakInschrijving.model_validate(item) for item in items]

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

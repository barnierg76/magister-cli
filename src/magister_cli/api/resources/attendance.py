"""Attendance resource for absence/verzuim data."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from magister_cli.api.base import BaseResource
from magister_cli.api.models import Absentie

logger = logging.getLogger(__name__)


class AttendanceResource(BaseResource):
    """Resource for attendance/absence API calls."""

    def get_absences(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        days: int = 30,
    ) -> list[Absentie]:
        """Get absence records for a date range.

        Args:
            start_date: Start date (defaults to `days` days ago)
            end_date: End date (defaults to today)
            days: Number of days to look back if start_date not specified

        Returns:
            List of absence records
        """
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=days)

        params = {
            "van": start_date.isoformat(),
            "tot": end_date.isoformat(),
        }

        data = self._get(f"/personen/{self._person_id}/absenties", params=params)
        logger.debug(f"Attendance API response: {data}")

        # API returns Items array
        items = data.get("Items", data.get("items", [])) if isinstance(data, dict) else data

        absences = []
        for item in items:
            try:
                absence = Absentie.model_validate(item)
                absences.append(absence)
            except Exception as e:
                logger.warning(f"Failed to parse absence item: {e}")
                logger.debug(f"Problematic item: {item}")

        return absences

    def get_absences_school_year(self) -> list[Absentie]:
        """Get all absences for the current school year.

        Returns:
            List of absence records for the school year
        """
        today = date.today()
        # School year starts August 1
        if today.month >= 8:
            start = date(today.year, 8, 1)
        else:
            start = date(today.year - 1, 8, 1)

        return self.get_absences(start_date=start, end_date=today)

    def get_summary(self, days: int = 365) -> dict:
        """Get attendance summary statistics.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with attendance statistics
        """
        absences = self.get_absences(days=days)

        # Count by type
        totaal = len(absences)
        ziek = sum(1 for a in absences if a.type == 1)
        te_laat = sum(1 for a in absences if a.type == 2)
        geoorloofd = sum(1 for a in absences if a.geoorloofd and a.type not in [1, 2])
        ongeoorloofd = sum(1 for a in absences if not a.geoorloofd)

        return {
            "totaal": totaal,
            "ziek": ziek,
            "te_laat": te_laat,
            "geoorloofd": geoorloofd,
            "ongeoorloofd": ongeoorloofd,
            "periode_dagen": days,
        }

"""Appointments resource for schedule and homework."""

from __future__ import annotations

from datetime import date

from magister_cli.api.base import BaseResource
from magister_cli.api.models import Afspraak


class AppointmentsResource(BaseResource):
    """Resource for appointment-related API calls."""

    def list(self, start: date, end: date) -> list[Afspraak]:
        """Get appointments for a date range.

        Args:
            start: Start date (inclusive)
            end: End date (inclusive)

        Returns:
            List of appointments
        """
        data = self._get(
            f"/personen/{self._person_id}/afspraken",
            params={"van": start.isoformat(), "tot": end.isoformat()},
        )
        items = data.get("items", data.get("Items", [])) if isinstance(data, dict) else data
        return [Afspraak.model_validate(item) for item in items]

    def get(self, afspraak_id: int) -> Afspraak:
        """Get a single appointment with full details.

        Args:
            afspraak_id: The appointment ID

        Returns:
            Full appointment including attachments
        """
        data = self._get(f"/personen/{self._person_id}/afspraken/{afspraak_id}")
        return Afspraak.model_validate(data)

    def with_homework(self, start: date, end: date) -> list[Afspraak]:
        """Get appointments that have homework.

        Args:
            start: Start date (inclusive)
            end: End date (inclusive)

        Returns:
            List of appointments with homework
        """
        appointments = self.list(start, end)
        return [a for a in appointments if a.heeft_huiswerk]

    def with_attachments(self, start: date, end: date) -> list[Afspraak]:
        """Get homework with full attachment details.

        For appointments that have attachments, fetches the full details
        to include the attachment list.

        Args:
            start: Start date (inclusive)
            end: End date (inclusive)

        Returns:
            List of homework items with attachments populated
        """
        appointments = self.with_homework(start, end)
        result = []
        for afspraak in appointments:
            if afspraak.heeft_bijlagen:
                full = self.get(afspraak.id)
                result.append(full)
            else:
                result.append(afspraak)
        return result

    def for_date(self, date_: date) -> list[Afspraak]:
        """Get schedule for a specific date.

        Args:
            date_: The date to get schedule for

        Returns:
            List of appointments for that day
        """
        return self.list(date_, date_)

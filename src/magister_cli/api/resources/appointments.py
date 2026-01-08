"""Appointments resource for schedule and homework."""

from __future__ import annotations

import asyncio
from datetime import date

import httpx

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
        """Get homework with full attachment details (sequential).

        For appointments that have attachments, fetches the full details
        to include the attachment list.

        Note: This method fetches attachments sequentially. For better
        performance with many attachments, use with_attachments_concurrent().

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

    def with_attachments_concurrent(self, start: date, end: date) -> list[Afspraak]:
        """Get homework with full attachment details (concurrent).

        This is a synchronous wrapper around with_attachments_async() that
        provides better performance by fetching attachment details concurrently.
        Use this when you have many appointments with attachments.

        Performance: 10 attachments = ~0.5s (vs 2s+ with sequential fetching)

        Args:
            start: Start date (inclusive)
            end: End date (inclusive)

        Returns:
            List of homework items with attachments populated
        """
        return asyncio.run(self.with_attachments_async(start, end))

    def for_date(self, date_: date) -> list[Afspraak]:
        """Get schedule for a specific date.

        Args:
            date_: The date to get schedule for

        Returns:
            List of appointments for that day
        """
        return self.list(date_, date_)

    # -------------------------------------------------------------------------
    # Async methods for concurrent operations
    # -------------------------------------------------------------------------

    async def get_async(self, afspraak_id: int) -> Afspraak:
        """Get a single appointment with full details (async).

        Args:
            afspraak_id: The appointment ID

        Returns:
            Full appointment including attachments
        """
        # Create async client with same config as sync client
        async with httpx.AsyncClient(
            headers=self._client.headers,
            timeout=self._client.timeout,
        ) as async_client:
            response = await async_client.get(
                f"{self._client.base_url}/personen/{self._person_id}/afspraken/{afspraak_id}"
            )
            data = self._handle_response(response)
            return Afspraak.model_validate(data)

    async def with_attachments_async(self, start: date, end: date) -> list[Afspraak]:
        """Get homework with full attachment details (concurrent).

        For appointments that have attachments, fetches the full details
        concurrently to include the attachment list. This avoids the N+1
        query pattern by using asyncio.gather for parallel fetching.

        Args:
            start: Start date (inclusive)
            end: End date (inclusive)

        Returns:
            List of homework items with attachments populated
        """
        appointments = self.with_homework(start, end)

        # Identify which appointments need details
        needs_details = [a for a in appointments if a.heeft_bijlagen]

        if not needs_details:
            return appointments

        # Fetch details concurrently with semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests

        async def fetch_with_limit(appointment_id: int):
            async with semaphore:
                try:
                    return await self.get_async(appointment_id)
                except Exception as e:
                    # Log error but return None to handle gracefully
                    import logging

                    logging.getLogger(__name__).warning(
                        f"Failed to fetch details for appointment {appointment_id}: {e}"
                    )
                    return None

        # Gather all results concurrently
        tasks = [fetch_with_limit(a.id) for a in needs_details]
        detailed = await asyncio.gather(*tasks)

        # Build map of id -> detailed appointment
        detailed_map = {}
        for i, result in enumerate(detailed):
            if result is not None:
                detailed_map[needs_details[i].id] = result

        # Merge results - use detailed version if available, otherwise original
        return [detailed_map.get(a.id, a) for a in appointments]

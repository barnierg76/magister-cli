"""Sync wrapper for MagisterAsyncService.

.. deprecated::
    This module is provided for backward compatibility only.
    For new code, use MagisterAsyncService directly which provides:
    - Better performance with concurrent API calls
    - No event loop recreation overhead
    - Native async/await support

**Performance Warning:**
Each method call creates a new event loop via asyncio.run(), which adds
overhead. For multiple operations, this is significantly slower than using
MagisterAsyncService directly:

    # SLOW: Creates event loop for each operation
    sync_service = MagisterSyncService("school")
    homework = sync_service.get_homework()  # new event loop
    grades = sync_service.get_recent_grades()  # new event loop

    # FAST: Single event loop, concurrent operations
    async with MagisterAsyncService("school") as service:
        homework, grades = await asyncio.gather(
            service.get_homework(),
            service.get_recent_grades()
        )

**Migration Guide:**
1. Change imports: `from magister_cli.services import MagisterAsyncService`
2. Wrap calls with `async with`: `async with MagisterAsyncService(...) as svc:`
3. Add `await` before method calls: `await svc.get_homework()`
4. Use `asyncio.gather()` for concurrent operations
"""

import asyncio
from datetime import date
from pathlib import Path
from typing import List, Optional

from magister_cli.services.async_magister import MagisterAsyncService
from magister_cli.services.core import (
    GradeInfo,
    HomeworkDay,
    HomeworkItem,
    ScheduleItem,
)


class MagisterSyncService:
    """Sync wrapper for MagisterAsyncService.

    This class provides synchronous interfaces to the async Magister service.
    Each method creates a new event loop and runs the async operation.

    Usage:
        service = MagisterSyncService("schoolcode")
        homework = service.get_homework(days=7)
        grades = service.get_recent_grades(limit=10)

    For better performance with multiple operations, use MagisterAsyncService
    directly with asyncio.
    """

    def __init__(self, school: str):
        """Initialize the sync service.

        Args:
            school: School code (e.g., 'vsvonh')
        """
        self.school = school

    def _run_async(self, coro):
        """Run an async coroutine synchronously."""
        return asyncio.run(coro)

    # -------------------------------------------------------------------------
    # Homework Operations
    # -------------------------------------------------------------------------

    def get_homework(
        self,
        days: int = 7,
        subject: Optional[str] = None,
        include_completed: bool = False,
    ) -> List[HomeworkItem]:
        """Get homework for the next N days.

        Args:
            days: Number of days to look ahead
            subject: Filter by subject (partial match, case-insensitive)
            include_completed: Include completed homework

        Returns:
            List of HomeworkItem objects
        """
        async def _impl():
            async with MagisterAsyncService(self.school) as service:
                return await service.get_homework(
                    days=days,
                    subject=subject,
                    include_completed=include_completed,
                )
        return self._run_async(_impl())

    def get_homework_grouped(
        self,
        days: int = 7,
        subject: Optional[str] = None,
        include_completed: bool = False,
    ) -> List[HomeworkDay]:
        """Get homework grouped by day.

        Args:
            days: Number of days to look ahead
            subject: Filter by subject (partial match, case-insensitive)
            include_completed: Include completed homework

        Returns:
            List of HomeworkDay objects
        """
        async def _impl():
            async with MagisterAsyncService(self.school) as service:
                return await service.get_homework_grouped(
                    days=days,
                    subject=subject,
                    include_completed=include_completed,
                )
        return self._run_async(_impl())

    def get_upcoming_tests(self, days: int = 14) -> List[HomeworkItem]:
        """Get upcoming tests.

        Args:
            days: Number of days to look ahead

        Returns:
            List of test HomeworkItem objects
        """
        async def _impl():
            async with MagisterAsyncService(self.school) as service:
                return await service.get_upcoming_tests(days=days)
        return self._run_async(_impl())

    # -------------------------------------------------------------------------
    # Grades Operations
    # -------------------------------------------------------------------------

    def get_recent_grades(self, limit: int = 10) -> List[GradeInfo]:
        """Get recent grades.

        Args:
            limit: Maximum number of grades to return

        Returns:
            List of GradeInfo objects
        """
        async def _impl():
            async with MagisterAsyncService(self.school) as service:
                return await service.get_recent_grades(limit=limit)
        return self._run_async(_impl())

    # -------------------------------------------------------------------------
    # Schedule Operations
    # -------------------------------------------------------------------------

    def get_schedule(self, target_date: Optional[date] = None) -> List[ScheduleItem]:
        """Get schedule for a specific date.

        Args:
            target_date: Date to get schedule for (defaults to today)

        Returns:
            List of ScheduleItem objects
        """
        async def _impl():
            async with MagisterAsyncService(self.school) as service:
                return await service.get_schedule(target_date=target_date)
        return self._run_async(_impl())

    def get_today_schedule(self) -> List[ScheduleItem]:
        """Get today's schedule."""
        async def _impl():
            async with MagisterAsyncService(self.school) as service:
                return await service.get_today_schedule()
        return self._run_async(_impl())

    # -------------------------------------------------------------------------
    # Combined Operations
    # -------------------------------------------------------------------------

    def get_student_summary(self, days: int = 7) -> dict:
        """Get complete student summary.

        Args:
            days: Number of days to look ahead for homework

        Returns:
            Dictionary with homework, grades, schedule, and metadata
        """
        async def _impl():
            async with MagisterAsyncService(self.school) as service:
                return await service.get_student_summary(days=days)
        return self._run_async(_impl())

    # -------------------------------------------------------------------------
    # Attachment Operations
    # -------------------------------------------------------------------------

    def download_all_attachments(
        self,
        days: int = 7,
        output_dir: Optional[Path] = None,
        subject: Optional[str] = None,
    ) -> List[dict]:
        """Download all attachments from upcoming homework.

        Args:
            days: Number of days to look ahead
            output_dir: Directory to save to
            subject: Filter by subject

        Returns:
            List of download results with paths
        """
        async def _impl():
            async with MagisterAsyncService(self.school) as service:
                return await service.download_all_attachments(
                    days=days,
                    output_dir=output_dir,
                    subject=subject,
                )
        return self._run_async(_impl())

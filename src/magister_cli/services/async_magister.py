"""Async Magister service for efficient concurrent API operations.

This is the primary service implementation using async/await patterns.
Use MagisterSyncService for backward compatibility with sync code.
"""

import asyncio
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

import httpx

from magister_cli.auth import get_current_token
from magister_cli.config import validate_school_code
from magister_cli.services.core import (
    AttachmentInfo,
    GradeInfo,
    HomeworkDay,
    HomeworkItem,
    MagisterCore,
    ScheduleItem,
)


def _sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal.

    Args:
        filename: The filename to sanitize

    Returns:
        Safe filename with dangerous characters removed
    """
    # Remove path separators and parent directory references
    safe_name = filename.replace("/", "_").replace("\\", "_").replace("..", "_")
    # Remove null bytes and other control characters
    safe_name = "".join(c for c in safe_name if c.isprintable())
    # Limit length
    if len(safe_name) > 255:
        safe_name = safe_name[:255]
    return safe_name or "unnamed_file"


class MagisterAsyncService:
    """Async-first Magister service for efficient API operations.

    Usage:
        async with MagisterAsyncService("schoolcode") as service:
            homework = await service.get_homework(days=7)
            grades = await service.get_recent_grades(limit=10)

            # Concurrent operations
            homework, grades = await asyncio.gather(
                service.get_homework(),
                service.get_recent_grades()
            )
    """

    def __init__(self, school: str):
        """Initialize the async service.

        Args:
            school: School code (e.g., 'vsvonh')
        """
        # Validate school code to prevent SSRF
        self.school = validate_school_code(school)
        self.core = MagisterCore()
        self._client: Optional[httpx.AsyncClient] = None
        self._token: Optional[str] = None
        self._person_id: Optional[int] = None
        self._person_name: Optional[str] = None
        self._is_parent: bool = False

    @property
    def base_url(self) -> str:
        """Get the base URL for the school's Magister API."""
        return f"https://{self.school}.magister.net/api"

    async def __aenter__(self) -> "MagisterAsyncService":
        """Initialize async HTTP client and authenticate."""
        token_data = get_current_token(self.school)
        if token_data is None:
            raise RuntimeError(
                f"Not authenticated for school: {self.school}. "
                "Run 'magister login' first."
            )

        self._token = token_data.access_token
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
                "User-Agent": "Magister-CLI/0.1.0",
            },
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            timeout=httpx.Timeout(30.0),
        )

        # Get account info and person ID
        account = await self._get_account()
        self._person_id = account.get("Persoon", {}).get("Id")
        self._person_name = account.get("Persoon", {}).get("Roepnaam")

        # Check if parent account
        groups = account.get("Groep", [])
        self._is_parent = any("Ouder" in g.get("Naam", "") for g in groups)

        if self._is_parent:
            # Get first child's ID for parent accounts
            children = await self._get_children()
            if children:
                self._person_id = children[0].get("Id")
                self._person_name = children[0].get("Roepnaam")

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Cleanup HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure client is initialized."""
        if self._client is None:
            raise RuntimeError(
                "Service not initialized. Use 'async with MagisterAsyncService(...) as service:'"
            )
        return self._client

    async def _get_account(self) -> dict:
        """Get account information."""
        client = self._ensure_client()
        response = await client.get("/account")
        response.raise_for_status()
        return response.json()

    async def _get_children(self) -> List[dict]:
        """Get children for parent account."""
        if self._person_id is None:
            return []

        client = self._ensure_client()
        try:
            response = await client.get(f"/personen/{self._person_id}/kinderen")
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                return data.get("items", data.get("Items", []))
            elif isinstance(data, list):
                return data
            return []
        except httpx.HTTPStatusError:
            return []

    # -------------------------------------------------------------------------
    # Homework Operations
    # -------------------------------------------------------------------------

    async def get_homework(
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
        client = self._ensure_client()
        start = date.today()
        end = start + timedelta(days=days)

        response = await client.get(
            f"/personen/{self._person_id}/afspraken",
            params={
                "van": start.isoformat(),
                "tot": end.isoformat(),
            },
        )
        response.raise_for_status()

        # Parse items with homework content
        data = response.json()
        api_items = data.get("items", data.get("Items", [])) if isinstance(data, dict) else data
        items = []
        for item in api_items:
            if item.get("Inhoud") or item.get("Huiswerk"):
                items.append(self.core.parse_homework_from_api(item))

        # Apply filters
        if not include_completed:
            items = self.core.filter_incomplete(items)
        if subject:
            items = self.core.filter_by_subject(items, subject)

        return items

    async def get_homework_grouped(
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
        items = await self.get_homework(
            days=days,
            subject=subject,
            include_completed=include_completed,
        )
        return self.core.group_by_date(items)

    async def get_upcoming_tests(self, days: int = 14) -> List[HomeworkItem]:
        """Get upcoming tests.

        Args:
            days: Number of days to look ahead

        Returns:
            List of test HomeworkItem objects
        """
        items = await self.get_homework(days=days, include_completed=False)
        return self.core.filter_tests(items)

    # -------------------------------------------------------------------------
    # Grades Operations
    # -------------------------------------------------------------------------

    async def get_recent_grades(self, limit: int = 10) -> List[GradeInfo]:
        """Get recent grades.

        Args:
            limit: Maximum number of grades to return

        Returns:
            List of GradeInfo objects
        """
        client = self._ensure_client()
        response = await client.get(
            f"/personen/{self._person_id}/cijfers/laatste",
            params={"top": limit},
        )
        response.raise_for_status()

        data = response.json()
        api_items = data.get("items", data.get("Items", [])) if isinstance(data, dict) else data
        grades = []
        for item in api_items:
            grades.append(self.core.parse_grade_from_api(item))

        return grades

    # -------------------------------------------------------------------------
    # Schedule Operations
    # -------------------------------------------------------------------------

    async def get_schedule(
        self,
        target_date: Optional[date] = None,
    ) -> List[ScheduleItem]:
        """Get schedule for a specific date.

        Args:
            target_date: Date to get schedule for (defaults to today)

        Returns:
            List of ScheduleItem objects
        """
        client = self._ensure_client()
        target = target_date or date.today()

        response = await client.get(
            f"/personen/{self._person_id}/afspraken",
            params={
                "van": target.isoformat(),
                "tot": target.isoformat(),
            },
        )
        response.raise_for_status()

        data = response.json()
        api_items = data.get("items", data.get("Items", [])) if isinstance(data, dict) else data
        items = []
        for item in api_items:
            items.append(self.core.parse_schedule_from_api(item))

        # Sort by start time
        return sorted(items, key=lambda x: x.start)

    async def get_today_schedule(self) -> List[ScheduleItem]:
        """Get today's schedule."""
        return await self.get_schedule(date.today())

    # -------------------------------------------------------------------------
    # Combined Operations (for MCP tools)
    # -------------------------------------------------------------------------

    async def get_student_summary(self, days: int = 7) -> dict:
        """Get complete student summary with concurrent API calls.

        This is a workflow-optimized method for MCP tools that combines
        multiple API calls into a single operation.

        Args:
            days: Number of days to look ahead for homework

        Returns:
            Dictionary with homework, grades, schedule, and metadata
        """
        # Fetch all data concurrently
        homework, grades, schedule = await asyncio.gather(
            self.get_homework(days=days),
            self.get_recent_grades(limit=5),
            self.get_today_schedule(),
        )

        # Calculate stats
        upcoming_tests = [h for h in homework if h.is_test]
        average = self.core.calculate_average(grades)

        return {
            "student": {
                "name": self._person_name,
                "school": self.school,
                "is_parent_account": self._is_parent,
            },
            "homework": {
                "items": [h.to_dict() for h in homework],
                "total": len(homework),
                "upcoming_tests": len(upcoming_tests),
            },
            "grades": {
                "recent": [g.to_dict() for g in grades],
                "average": average,
            },
            "schedule": {
                "today": [s.to_dict() for s in schedule],
                "lessons_today": len(schedule),
            },
            "summary": (
                f"{self._person_name or 'Student'} has {len(homework)} homework items, "
                f"{len(upcoming_tests)} upcoming tests, and {len(schedule)} lessons today"
            ),
        }

    # -------------------------------------------------------------------------
    # Attachment Operations
    # -------------------------------------------------------------------------

    async def download_attachment(
        self,
        attachment: AttachmentInfo,
        output_dir: Optional[Path] = None,
    ) -> Path:
        """Download a single attachment.

        Args:
            attachment: AttachmentInfo to download
            output_dir: Directory to save to (defaults to current directory)

        Returns:
            Path to downloaded file
        """
        client = self._ensure_client()
        output_dir = output_dir or Path.cwd()
        output_dir.mkdir(parents=True, exist_ok=True)

        # Determine download URL
        if attachment.download_url:
            url = attachment.download_url
        else:
            # Fallback URL pattern
            url = f"/personen/{self._person_id}/bijlagen/{attachment.id}"

        # Download file
        response = await client.get(url)
        response.raise_for_status()

        # Sanitize filename to prevent path traversal
        safe_filename = _sanitize_filename(attachment.name)
        output_path = (output_dir / safe_filename).resolve()

        # Validate path is within output_dir (prevent path traversal)
        if not str(output_path).startswith(str(output_dir.resolve())):
            raise RuntimeError(f"Invalid filename: {attachment.name}")

        # Handle duplicate filenames
        counter = 1
        while output_path.exists():
            stem = output_path.stem
            suffix = output_path.suffix
            output_path = output_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        output_path.write_bytes(response.content)
        return output_path

    async def download_all_attachments(
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
        output_dir = output_dir or Path.cwd() / "magister_materials"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get homework with attachments
        homework = await self.get_homework(days=days, subject=subject)

        # Collect all attachments
        downloads = []
        for item in homework:
            for att in item.attachments:
                # Create subject subdirectory
                subject_dir = output_dir / item.subject.replace("/", "-")
                subject_dir.mkdir(parents=True, exist_ok=True)

                try:
                    path = await self.download_attachment(att, subject_dir)
                    downloads.append({
                        "name": att.name,
                        "path": str(path),
                        "subject": item.subject,
                        "success": True,
                    })
                except Exception as e:
                    downloads.append({
                        "name": att.name,
                        "subject": item.subject,
                        "success": False,
                        "error": str(e),
                    })

        return downloads

"""Async Magister service for efficient concurrent API operations.

This is the primary service implementation using async/await patterns.
Use MagisterSyncService for backward compatibility with sync code.
"""

import asyncio
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

import httpx

from magister_cli.auth import get_current_token, auto_refresh_if_needed
from magister_cli.config import validate_school_code

logger = logging.getLogger(__name__)

from magister_cli.services.core import (
    AttachmentInfo,
    GradeInfo,
    HomeworkDay,
    HomeworkItem,
    MagisterCore,
    ScheduleItem,
)
from magister_cli.utils.files import sanitize_filename


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
        """Initialize async HTTP client and authenticate.

        Automatically refreshes the token if it's expiring within 15 minutes
        and a refresh token is available.
        """
        # Try to auto-refresh if token is expiring soon
        refreshed_token = await auto_refresh_if_needed(self.school, minutes_threshold=15)
        if refreshed_token:
            logger.info(f"Token auto-refreshed for {self.school}")

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
        safe_filename = sanitize_filename(attachment.name)
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
        max_concurrent: int = 5,
    ) -> List[dict]:
        """Download all attachments from upcoming homework concurrently.

        Args:
            days: Number of days to look ahead
            output_dir: Directory to save to
            subject: Filter by subject
            max_concurrent: Maximum concurrent downloads (default 5)

        Returns:
            List of download results with paths
        """
        output_dir = output_dir or Path.cwd() / "magister_materials"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get homework with attachments
        homework = await self.get_homework(days=days, subject=subject)

        # Semaphore to limit concurrent downloads
        semaphore = asyncio.Semaphore(max_concurrent)

        async def download_with_limit(
            attachment: AttachmentInfo,
            subject_dir: Path,
            subject_name: str,
        ) -> dict:
            """Download a single attachment with semaphore limit."""
            async with semaphore:
                try:
                    path = await self.download_attachment(attachment, subject_dir)
                    return {
                        "name": attachment.name,
                        "path": str(path),
                        "subject": subject_name,
                        "success": True,
                    }
                except Exception as e:
                    return {
                        "name": attachment.name,
                        "subject": subject_name,
                        "success": False,
                        "error": str(e),
                    }

        # Collect all download tasks
        tasks = []
        for item in homework:
            # Create subject subdirectory
            subject_dir = output_dir / item.subject.replace("/", "-")
            subject_dir.mkdir(parents=True, exist_ok=True)

            for att in item.attachments:
                tasks.append(download_with_limit(att, subject_dir, item.subject))

        # Execute all downloads concurrently (if any)
        if not tasks:
            return []

        downloads = await asyncio.gather(*tasks, return_exceptions=False)
        return downloads

    # -------------------------------------------------------------------------
    # Message Operations
    # -------------------------------------------------------------------------

    async def get_messages(
        self,
        folder: str = "inbox",
        limit: int = 25,
        unread_only: bool = False,
    ) -> List[dict]:
        """Get messages from the student's mailbox.

        Args:
            folder: Which folder to read - 'inbox', 'sent', or 'deleted'
            limit: Maximum number of messages to return
            unread_only: If True, only return unread messages

        Returns:
            List of message dictionaries
        """
        client = self._ensure_client()

        # Map folder to endpoint
        folder_map = {
            "inbox": "/berichten/postvakin/berichten",
            "sent": "/berichten/verzendenitems/berichten",
            "deleted": "/berichten/verwijderditems/berichten",
        }

        endpoint = folder_map.get(folder)
        if endpoint is None:
            raise ValueError(f"Invalid folder: {folder}. Must be 'inbox', 'sent', or 'deleted'")

        response = await client.get(endpoint, params={"top": limit, "skip": 0})
        response.raise_for_status()

        data = response.json()
        items = data.get("items", data.get("Items", [])) if isinstance(data, dict) else data

        # Convert to simple dicts
        messages = []
        for item in items:
            # Skip read messages if unread_only is True
            if unread_only and item.get("IsGelezen", True):
                continue

            afzender = item.get("Afzender", {})
            messages.append({
                "id": item.get("Id"),
                "subject": item.get("Onderwerp"),
                "sender_name": afzender.get("Naam"),
                "sender_type": afzender.get("Type"),
                "sent_at": item.get("VerzondOp"),
                "is_read": item.get("IsGelezen", False),
                "has_attachments": item.get("HeeftBijlagen", False),
                "priority": item.get("Prioriteit"),
                "has_priority": item.get("HeeftPrioriteit", False),
            })

        return messages

    async def get_message(self, message_id: int) -> dict:
        """Get full message details including body and attachments.

        Args:
            message_id: The ID of the message to read

        Returns:
            Full message dictionary with body, recipients, attachments
        """
        client = self._ensure_client()
        response = await client.get(f"/berichten/{message_id}")
        response.raise_for_status()

        data = response.json()
        afzender = data.get("Afzender", {})

        # Parse recipients
        ontvangers = []
        for o in data.get("Ontvangers", []):
            ontvangers.append({
                "id": o.get("Id"),
                "name": o.get("Naam"),
                "type": o.get("Type"),
            })

        # Parse CC recipients
        cc_ontvangers = []
        for cc in data.get("CCOntvangers", []):
            cc_ontvangers.append({
                "id": cc.get("Id"),
                "name": cc.get("Naam"),
                "type": cc.get("Type"),
            })

        # Parse attachments
        bijlagen = []
        for b in data.get("Bijlagen", []):
            bijlagen.append({
                "id": b.get("Id"),
                "name": b.get("Naam"),
                "mime_type": b.get("ContentType"),
                "size": b.get("Grootte"),
            })

        return {
            "id": data.get("Id"),
            "subject": data.get("Onderwerp"),
            "sender_name": afzender.get("Naam"),
            "sender_type": afzender.get("Type"),
            "sender_id": afzender.get("Id"),
            "sent_at": data.get("VerzondOp"),
            "is_read": data.get("IsGelezen", False),
            "has_attachments": data.get("HeeftBijlagen", False),
            "priority": data.get("Prioriteit"),
            "has_priority": data.get("HeeftPrioriteit", False),
            "body": data.get("Inhoud", ""),
            "recipients": ontvangers,
            "cc_recipients": cc_ontvangers,
            "attachments": bijlagen,
        }

    async def get_unread_message_count(self) -> int:
        """Get count of unread messages in inbox.

        Returns:
            Number of unread messages
        """
        # Get first page and count unread
        messages = await self.get_messages(folder="inbox", limit=100, unread_only=True)
        return len(messages)

    async def mark_message_as_read(self, message_id: int) -> None:
        """Mark a message as read.

        Args:
            message_id: The ID of the message to mark as read
        """
        client = self._ensure_client()
        response = await client.put(f"/berichten/{message_id}/gelezen")
        response.raise_for_status()

    # -------------------------------------------------------------------------
    # Study Guide (Studiewijzer) Operations
    # -------------------------------------------------------------------------

    async def get_study_guides(self) -> List[dict]:
        """Get all study guides for the student.

        Returns:
            List of study guide dictionaries
        """
        client = self._ensure_client()
        response = await client.get(f"/leerlingen/{self._person_id}/studiewijzers")
        response.raise_for_status()

        data = response.json()
        items = data.get("items", data.get("Items", [])) if isinstance(data, dict) else data

        guides = []
        for item in items:
            guides.append({
                "id": item.get("Id"),
                "title": item.get("Titel"),
                "from_date": item.get("Van"),
                "to_date": item.get("TotEnMet"),
                "subject_codes": item.get("VakCodes", []),
                "is_visible": item.get("IsZichtbaar", True),
                "in_archive": item.get("InLeerlingArchief", False),
            })

        return guides

    async def get_study_guide(self, guide_id: int) -> dict:
        """Get full details of a study guide including sections.

        Args:
            guide_id: The study guide ID

        Returns:
            Full study guide with sections and resources
        """
        client = self._ensure_client()
        response = await client.get(
            f"/leerlingen/{self._person_id}/studiewijzers/{guide_id}"
        )
        response.raise_for_status()

        data = response.json()

        # Parse sections (onderdelen)
        onderdelen_data = data.get("Onderdelen", {})
        onderdelen_items = onderdelen_data.get("Items", []) if isinstance(onderdelen_data, dict) else []

        sections = []
        for section in onderdelen_items:
            # Parse resources (bronnen)
            bronnen = []
            for bron in section.get("Bronnen", []):
                bronnen.append({
                    "id": bron.get("Id"),
                    "name": bron.get("Naam"),
                    "uri": bron.get("Uri"),
                    "type": bron.get("BronSoort"),
                    "content_type": bron.get("ContentType"),
                    "size": bron.get("Grootte"),
                })

            sections.append({
                "id": section.get("Id"),
                "title": section.get("Titel"),
                "description": section.get("Omschrijving", ""),
                "from_date": section.get("Van"),
                "to_date": section.get("TotEnMet"),
                "is_visible": section.get("IsZichtbaar", True),
                "color": section.get("Kleur", 0),
                "order": section.get("Volgnummer", 0),
                "resources": bronnen,
            })

        return {
            "id": data.get("Id"),
            "title": data.get("Titel"),
            "from_date": data.get("Van"),
            "to_date": data.get("TotEnMet"),
            "subject_codes": data.get("VakCodes", []),
            "is_visible": data.get("IsZichtbaar", True),
            "in_archive": data.get("InLeerlingArchief", False),
            "sections": sections,
            "section_count": len(sections),
        }

    # -------------------------------------------------------------------------
    # Learning Materials (Lesmateriaal) Operations
    # -------------------------------------------------------------------------

    async def get_learning_materials(self) -> List[dict]:
        """Get all digital learning materials for the student.

        Returns:
            List of learning material dictionaries (textbooks, online resources)
        """
        client = self._ensure_client()
        response = await client.get(f"/personen/{self._person_id}/lesmateriaal")
        response.raise_for_status()

        data = response.json()
        items = data.get("items", data.get("Items", [])) if isinstance(data, dict) else data

        materials = []
        for item in items:
            vak = item.get("Vak", {})
            materials.append({
                "id": item.get("Id"),
                "title": item.get("Titel"),
                "publisher": item.get("Uitgeverij"),
                "ean": item.get("EAN"),
                "status": item.get("Status", 0),
                "material_type": item.get("MateriaalType", 0),
                "start_date": item.get("Start"),
                "end_date": item.get("Eind"),
                "preview_image": item.get("PreviewImageUrl"),
                "subject": {
                    "id": vak.get("Id"),
                    "abbreviation": vak.get("Afkorting"),
                    "name": vak.get("Omschrijving"),
                } if vak else None,
            })

        return materials

    # -------------------------------------------------------------------------
    # Assignment (Opdracht) Operations
    # -------------------------------------------------------------------------

    async def get_assignments(self) -> List[dict]:
        """Get all ELO assignments for the student.

        Returns:
            List of assignment dictionaries
        """
        client = self._ensure_client()
        response = await client.get(f"/personen/{self._person_id}/opdrachten")
        response.raise_for_status()

        data = response.json()
        items = data.get("items", data.get("Items", [])) if isinstance(data, dict) else data

        assignments = []
        for item in items:
            # Parse attachments
            bijlagen = []
            for b in item.get("Bijlagen", []):
                bijlagen.append({
                    "id": b.get("Id"),
                    "name": b.get("Naam"),
                    "mime_type": b.get("ContentType"),
                    "size": b.get("Grootte"),
                })

            assignments.append({
                "id": item.get("Id"),
                "title": item.get("Titel"),
                "description": item.get("Omschrijving", ""),
                "subject": item.get("Vak"),
                "deadline": item.get("InleverenVoor"),
                "submitted_at": item.get("IngeleverdOp"),
                "grade": item.get("Beoordeling"),
                "graded_at": item.get("BeoordeeldOp"),
                "status": item.get("StatusLaatsteOpdrachtVersie", 0),
                "version": item.get("LaatsteOpdrachtVersienummer", 0),
                "can_resubmit": item.get("OpnieuwInleveren", False),
                "is_closed": item.get("Afgesloten", False),
                "can_submit": item.get("MagInleveren", True),
                "attachments": bijlagen,
                "is_submitted": item.get("IngeleverdOp") is not None,
                "is_graded": item.get("BeoordeeldOp") is not None,
            })

        return assignments

    async def get_assignment(self, assignment_id: int) -> dict:
        """Get full details of a single assignment.

        Args:
            assignment_id: The assignment ID

        Returns:
            Full assignment details
        """
        client = self._ensure_client()
        response = await client.get(
            f"/personen/{self._person_id}/opdrachten/{assignment_id}"
        )
        response.raise_for_status()

        item = response.json()

        # Parse attachments
        bijlagen = []
        for b in item.get("Bijlagen", []):
            bijlagen.append({
                "id": b.get("Id"),
                "name": b.get("Naam"),
                "mime_type": b.get("ContentType"),
                "size": b.get("Grootte"),
            })

        return {
            "id": item.get("Id"),
            "title": item.get("Titel"),
            "description": item.get("Omschrijving", ""),
            "subject": item.get("Vak"),
            "deadline": item.get("InleverenVoor"),
            "submitted_at": item.get("IngeleverdOp"),
            "grade": item.get("Beoordeling"),
            "graded_at": item.get("BeoordeeldOp"),
            "status": item.get("StatusLaatsteOpdrachtVersie", 0),
            "version": item.get("LaatsteOpdrachtVersienummer", 0),
            "can_resubmit": item.get("OpnieuwInleveren", False),
            "is_closed": item.get("Afgesloten", False),
            "can_submit": item.get("MagInleveren", True),
            "attachments": bijlagen,
            "is_submitted": item.get("IngeleverdOp") is not None,
            "is_graded": item.get("BeoordeeldOp") is not None,
        }

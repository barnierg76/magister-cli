"""Tests for MagisterAsyncService."""

from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from magister_cli.services.async_magister import MagisterAsyncService
from magister_cli.utils.files import sanitize_filename as _sanitize_filename
from magister_cli.services.core import (
    AttachmentInfo,
    GradeInfo,
    HomeworkDay,
    HomeworkItem,
)


class TestSanitizeFilename:
    """Tests for _sanitize_filename helper function."""

    def test_basic_filename(self):
        """Test normal filename passes through."""
        result = _sanitize_filename("homework.pdf")
        assert result == "homework.pdf"

    def test_removes_path_separators(self):
        """Test path separators are removed."""
        result = _sanitize_filename("../../etc/passwd")
        assert "/" not in result
        assert "\\" not in result
        assert ".." not in result

    def test_removes_null_bytes(self):
        """Test null bytes are removed."""
        result = _sanitize_filename("file\x00.pdf")
        assert "\x00" not in result

    def test_limits_length(self):
        """Test filename is limited to 255 characters."""
        long_name = "a" * 300 + ".pdf"
        result = _sanitize_filename(long_name)
        assert len(result) <= 255

    def test_empty_string_returns_default(self):
        """Test empty string returns default name."""
        result = _sanitize_filename("")
        assert result == "unnamed_file"


class TestMagisterAsyncServiceInit:
    """Tests for MagisterAsyncService initialization."""

    def test_initialization(self):
        """Test service initialization with valid school code."""
        service = MagisterAsyncService("vsvonh")
        assert service.school == "vsvonh"
        assert service.base_url == "https://vsvonh.magister.net/api"

    def test_invalid_school_code(self):
        """Test initialization with invalid school code raises error."""
        with pytest.raises(ValueError):
            MagisterAsyncService("../../../etc/passwd")


@pytest.mark.asyncio
class TestMagisterAsyncServiceContext:
    """Tests for MagisterAsyncService context manager behavior."""

    @patch("magister_cli.services.async_magister.get_current_token")
    async def test_context_manager_not_authenticated(self, mock_token):
        """Test error when not authenticated."""
        mock_token.return_value = None

        service = MagisterAsyncService("vsvonh")

        with pytest.raises(RuntimeError, match="Not authenticated"):
            async with service:
                pass

    @patch("magister_cli.services.async_magister.get_current_token")
    @patch("magister_cli.services.async_magister.httpx.AsyncClient")
    async def test_context_manager_initializes_client(self, mock_client_cls, mock_token):
        """Test that context manager initializes HTTP client."""
        # Mock token
        token_data = MagicMock()
        token_data.access_token = "test_token"
        mock_token.return_value = token_data

        # Mock HTTP client
        mock_client = AsyncMock()
        mock_account_response = MagicMock()
        mock_account_response.json.return_value = {
            "Persoon": {"Id": 12345, "Roepnaam": "Jan"},
            "Groep": [],
        }
        mock_client.get.return_value = mock_account_response
        mock_client_cls.return_value = mock_client

        service = MagisterAsyncService("vsvonh")

        async with service as svc:
            assert svc._client is not None
            assert svc._person_id == 12345
            assert svc._person_name == "Jan"

        # Client should be closed after exit
        mock_client.aclose.assert_called_once()


@pytest.mark.asyncio
class TestMagisterAsyncServiceHomework:
    """Tests for homework-related methods."""

    @pytest.fixture
    def mock_service(self):
        """Create a mock service with initialized client."""
        service = MagisterAsyncService("vsvonh")
        service._token = "test_token"
        service._person_id = 12345
        service._person_name = "Jan"
        service._is_parent = False

        # Mock HTTP client
        mock_client = AsyncMock()
        service._client = mock_client

        return service, mock_client

    async def test_get_homework_returns_list(self, mock_service):
        """Test that get_homework returns a list of homework items."""
        service, mock_client = mock_service

        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Items": [
                {
                    "Id": 1,
                    "Start": "2026-01-10T09:00:00Z",
                    "Vakken": [{"Naam": "Wiskunde", "Afkorting": "WIS"}],
                    "Docenten": [{"Naam": "Dhr. Jansen"}],
                    "Lokalen": [{"Naam": "A101"}],
                    "Inhoud": "Maak opgaven 4.1-4.15",
                    "LesuurVan": 2,
                    "InfoType": 1,
                    "Afgerond": False,
                    "Bijlagen": [],
                },
                {
                    "Id": 2,
                    "Start": "2026-01-11T10:00:00Z",
                    "Vakken": [{"Naam": "Engels"}],
                    "Docenten": [],
                    "Lokalen": [],
                    "Huiswerk": "Lees hoofdstuk 5",
                    "InfoType": 1,
                    "Afgerond": False,
                    "Bijlagen": [],
                },
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        result = await service.get_homework(days=7)

        assert isinstance(result, list)
        assert len(result) == 2
        assert isinstance(result[0], HomeworkItem)
        assert result[0].subject == "Wiskunde"
        assert result[1].subject == "Engels"

    async def test_get_homework_filters_by_subject(self, mock_service):
        """Test homework filtering by subject."""
        service, mock_client = mock_service

        # Mock API response with multiple subjects
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Items": [
                {
                    "Id": 1,
                    "Start": "2026-01-10T09:00:00Z",
                    "Vakken": [{"Naam": "Wiskunde", "Afkorting": "WIS"}],
                    "Docenten": [],
                    "Lokalen": [],
                    "Inhoud": "Math homework",
                    "InfoType": 1,
                    "Afgerond": False,
                    "Bijlagen": [],
                },
                {
                    "Id": 2,
                    "Start": "2026-01-11T10:00:00Z",
                    "Vakken": [{"Naam": "Engels"}],
                    "Docenten": [],
                    "Lokalen": [],
                    "Inhoud": "English homework",
                    "InfoType": 1,
                    "Afgerond": False,
                    "Bijlagen": [],
                },
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        result = await service.get_homework(days=7, subject="wiskunde")

        assert len(result) == 1
        assert result[0].subject == "Wiskunde"

    async def test_get_homework_excludes_completed(self, mock_service):
        """Test that completed homework is excluded by default."""
        service, mock_client = mock_service

        # Mock API response with completed item
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Items": [
                {
                    "Id": 1,
                    "Start": "2026-01-10T09:00:00Z",
                    "Vakken": [{"Naam": "Math"}],
                    "Docenten": [],
                    "Lokalen": [],
                    "Inhoud": "Completed homework",
                    "InfoType": 1,
                    "Afgerond": True,  # Completed
                    "Bijlagen": [],
                },
                {
                    "Id": 2,
                    "Start": "2026-01-11T10:00:00Z",
                    "Vakken": [{"Naam": "Science"}],
                    "Docenten": [],
                    "Lokalen": [],
                    "Inhoud": "Pending homework",
                    "InfoType": 1,
                    "Afgerond": False,
                    "Bijlagen": [],
                },
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        result = await service.get_homework(days=7, include_completed=False)

        assert len(result) == 1
        assert result[0].subject == "Science"

    async def test_get_homework_grouped(self, mock_service):
        """Test homework grouped by day."""
        service, mock_client = mock_service

        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Items": [
                {
                    "Id": 1,
                    "Start": "2026-01-10T09:00:00Z",
                    "Vakken": [{"Naam": "Math"}],
                    "Docenten": [],
                    "Lokalen": [],
                    "Inhoud": "Day 1",
                    "InfoType": 1,
                    "Afgerond": False,
                    "Bijlagen": [],
                },
                {
                    "Id": 2,
                    "Start": "2026-01-11T10:00:00Z",
                    "Vakken": [{"Naam": "Science"}],
                    "Docenten": [],
                    "Lokalen": [],
                    "Inhoud": "Day 2",
                    "InfoType": 1,
                    "Afgerond": False,
                    "Bijlagen": [],
                },
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        result = await service.get_homework_grouped(days=7)

        assert isinstance(result, list)
        assert len(result) == 2
        assert isinstance(result[0], HomeworkDay)

    async def test_get_upcoming_tests(self, mock_service):
        """Test filtering for tests only."""
        service, mock_client = mock_service

        # Mock API response with test and homework
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Items": [
                {
                    "Id": 1,
                    "Start": "2026-01-10T09:00:00Z",
                    "Vakken": [{"Naam": "Math"}],
                    "Docenten": [],
                    "Lokalen": [],
                    "Inhoud": "Regular homework",
                    "InfoType": 1,  # Regular homework
                    "Afgerond": False,
                    "Bijlagen": [],
                },
                {
                    "Id": 2,
                    "Start": "2026-01-15T10:00:00Z",
                    "Vakken": [{"Naam": "Science"}],
                    "Docenten": [],
                    "Lokalen": [],
                    "Inhoud": "Test chapter 5",
                    "InfoType": 2,  # Test
                    "Afgerond": False,
                    "Bijlagen": [],
                },
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        result = await service.get_upcoming_tests(days=14)

        assert len(result) == 1
        assert result[0].is_test is True


@pytest.mark.asyncio
class TestMagisterAsyncServiceGrades:
    """Tests for grades-related methods."""

    @pytest.fixture
    def mock_service(self):
        """Create a mock service with initialized client."""
        service = MagisterAsyncService("vsvonh")
        service._token = "test_token"
        service._person_id = 12345
        service._person_name = "Jan"
        service._is_parent = False
        mock_client = AsyncMock()
        service._client = mock_client
        return service, mock_client

    async def test_get_recent_grades(self, mock_service):
        """Test fetching recent grades."""
        service, mock_client = mock_service

        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Items": [
                {
                    "Vak": {"Omschrijving": "Wiskunde"},
                    "CijferStr": "8,5",
                    "Weging": 2.0,
                    "DatumIngevoerd": "2026-01-08T12:00:00Z",
                    "KolomOmschrijving": "Toets hoofdstuk 4",
                },
                {
                    "Vak": {"Omschrijving": "Engels"},
                    "CijferStr": "7.0",
                    "Weging": 1.0,
                    "DatumIngevoerd": "2026-01-07T12:00:00Z",
                    "KolomOmschrijving": "Essay",
                },
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        result = await service.get_recent_grades(limit=10)

        assert isinstance(result, list)
        assert len(result) == 2
        assert isinstance(result[0], GradeInfo)
        assert result[0].subject == "Wiskunde"
        assert result[0].grade == "8,5"
        assert result[1].subject == "Engels"


@pytest.mark.asyncio
class TestMagisterAsyncServiceSchedule:
    """Tests for schedule-related methods."""

    @pytest.fixture
    def mock_service(self):
        """Create a mock service with initialized client."""
        service = MagisterAsyncService("vsvonh")
        service._token = "test_token"
        service._person_id = 12345
        service._person_name = "Jan"
        service._is_parent = False
        mock_client = AsyncMock()
        service._client = mock_client
        return service, mock_client

    async def test_get_schedule(self, mock_service):
        """Test fetching schedule for a specific date."""
        service, mock_client = mock_service

        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Items": [
                {
                    "Start": "2026-01-08T09:00:00Z",
                    "Einde": "2026-01-08T09:50:00Z",
                    "Vakken": [{"Naam": "Wiskunde"}],
                    "Docenten": [{"Naam": "Dhr. Jansen"}],
                    "Lokalen": [{"Naam": "A101"}],
                    "LesuurVan": 2,
                    "Inhoud": "Lesson content",
                    "Status": 0,
                },
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        result = await service.get_schedule(target_date=date(2026, 1, 8))

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].subject == "Wiskunde"
        assert result[0].location == "A101"

    async def test_get_today_schedule(self, mock_service):
        """Test fetching today's schedule."""
        service, mock_client = mock_service

        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {"Items": []}
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        result = await service.get_today_schedule()

        assert isinstance(result, list)


@pytest.mark.asyncio
class TestMagisterAsyncServiceCombined:
    """Tests for combined workflow operations."""

    @pytest.fixture
    def mock_service(self):
        """Create a mock service with initialized client."""
        service = MagisterAsyncService("vsvonh")
        service._token = "test_token"
        service._person_id = 12345
        service._person_name = "Jan Jansen"
        service._is_parent = False
        mock_client = AsyncMock()
        service._client = mock_client
        return service, mock_client

    async def test_get_student_summary(self, mock_service):
        """Test combined student summary operation."""
        service, mock_client = mock_service

        # Mock all API responses
        def mock_get(url, **kwargs):
            response = MagicMock()
            response.raise_for_status = MagicMock()

            if "afspraken" in url:
                response.json.return_value = {"Items": []}
            elif "cijfers" in url:
                response.json.return_value = {
                    "Items": [
                        {
                            "Vak": {"Omschrijving": "Math"},
                            "CijferStr": "8.0",
                            "Weging": 1.0,
                            "DatumIngevoerd": "2026-01-08T12:00:00Z",
                        }
                    ]
                }
            else:
                response.json.return_value = {"Items": []}

            return response

        mock_client.get.side_effect = mock_get

        result = await service.get_student_summary(days=7)

        assert isinstance(result, dict)
        assert "student" in result
        assert "homework" in result
        assert "grades" in result
        assert "schedule" in result
        assert "summary" in result
        assert result["student"]["name"] == "Jan Jansen"
        assert result["student"]["school"] == "vsvonh"


@pytest.mark.asyncio
class TestMagisterAsyncServiceAttachments:
    """Tests for attachment download operations."""

    @pytest.fixture
    def mock_service(self):
        """Create a mock service with initialized client."""
        service = MagisterAsyncService("vsvonh")
        service._token = "test_token"
        service._person_id = 12345
        service._person_name = "Jan"
        service._is_parent = False
        mock_client = AsyncMock()
        service._client = mock_client
        return service, mock_client

    @pytest.fixture
    def temp_dir(self, tmp_path):
        """Create a temporary directory for downloads."""
        return tmp_path / "downloads"

    async def test_download_attachment(self, mock_service, temp_dir):
        """Test downloading a single attachment."""
        service, mock_client = mock_service

        # Mock file download response
        mock_response = MagicMock()
        mock_response.content = b"PDF content"
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        attachment = AttachmentInfo(
            id=123,
            name="homework.pdf",
            size="1 MB",
            content_type="application/pdf",
            download_url="https://example.com/file.pdf",
        )

        result = await service.download_attachment(attachment, temp_dir)

        assert isinstance(result, Path)
        assert result.name == "homework.pdf"
        assert result.exists()
        assert result.read_bytes() == b"PDF content"

    async def test_download_attachment_sanitizes_filename(self, mock_service, temp_dir):
        """Test that dangerous filenames are sanitized."""
        service, mock_client = mock_service

        # Mock file download response
        mock_response = MagicMock()
        mock_response.content = b"Content"
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        attachment = AttachmentInfo(
            id=123,
            name="../../etc/passwd",
            size="1 KB",
            content_type="text/plain",
        )

        result = await service.download_attachment(attachment, temp_dir)

        # Filename should be sanitized
        assert ".." not in str(result)
        assert "/" not in result.name
        # File should be within temp_dir
        assert temp_dir in result.parents

    async def test_download_attachment_handles_duplicates(self, mock_service, temp_dir):
        """Test that duplicate filenames are handled."""
        service, mock_client = mock_service
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Create existing file
        existing = temp_dir / "homework.pdf"
        existing.write_text("existing")

        # Mock file download response
        mock_response = MagicMock()
        mock_response.content = b"New content"
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        attachment = AttachmentInfo(
            id=123,
            name="homework.pdf",
            size="1 MB",
            content_type="application/pdf",
        )

        result = await service.download_attachment(attachment, temp_dir)

        # Should create a new file with counter
        assert result.name == "homework_1.pdf"
        assert result.read_bytes() == b"New content"
        # Original file should be unchanged
        assert existing.read_text() == "existing"


@pytest.mark.asyncio
class TestMagisterAsyncServiceErrorHandling:
    """Tests for error handling in async service."""

    def test_ensure_client_not_initialized(self):
        """Test error when client is not initialized."""
        service = MagisterAsyncService("vsvonh")

        with pytest.raises(RuntimeError, match="not initialized"):
            service._ensure_client()

    @patch("magister_cli.services.async_magister.get_current_token")
    async def test_http_error_propagates(self, mock_token):
        """Test that HTTP errors are propagated."""
        # Mock token
        token_data = MagicMock()
        token_data.access_token = "test_token"
        mock_token.return_value = token_data

        service = MagisterAsyncService("vsvonh")

        with patch("magister_cli.services.async_magister.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            # Mock 404 error on account fetch
            mock_client.get.side_effect = httpx.HTTPStatusError(
                "Not found", request=MagicMock(), response=MagicMock(status_code=404)
            )
            mock_client_cls.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                async with service:
                    pass

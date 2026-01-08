"""Attachments resource for file downloads."""

from pathlib import Path

import httpx

from magister_cli.api.base import BaseResource
from magister_cli.api.exceptions import MagisterAPIError
from magister_cli.api.models import Bijlage
from magister_cli.utils.files import sanitize_filename


class AttachmentsResource(BaseResource):
    """Resource for attachment downloads."""

    def __init__(
        self,
        client: httpx.Client,
        person_id: int,
        base_url: str,
        token: str,
        timeout: int = 30,
    ):
        """Initialize the attachments resource.

        Args:
            client: HTTP client instance
            person_id: The student's person ID
            base_url: The API base URL
            token: The access token for downloads
            timeout: Timeout for downloads in seconds
        """
        super().__init__(client, person_id)
        self._base_url = base_url
        self._token = token
        self._timeout = timeout

    def download(self, bijlage: Bijlage, output_dir: Path | None = None) -> Path:
        """Download an attachment to the specified directory.

        Args:
            bijlage: The attachment to download
            output_dir: Directory to save to (defaults to current directory)

        Returns:
            Path to the downloaded file

        Raises:
            MagisterAPIError: If download fails
        """
        download_path = bijlage.download_path
        if not download_path:
            raise MagisterAPIError(f"No download path for attachment: {bijlage.naam}")

        # Strip /api prefix if present (API returns full path but base_url ends with /api)
        if download_path.startswith("/api/"):
            download_path = download_path[4:]

        full_url = f"{self._base_url}{download_path}"

        # Use separate client with redirect support for downloads
        with httpx.Client(
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=self._timeout,
            follow_redirects=True,
        ) as download_client:
            response = download_client.get(full_url)

        if response.status_code >= 400:
            raise MagisterAPIError(
                f"Failed to download attachment: {response.status_code}",
                response.status_code,
            )

        # Determine output path
        if output_dir is None:
            output_dir = Path.cwd()
        output_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize filename to prevent path traversal
        safe_filename = sanitize_filename(bijlage.naam)
        output_path = (output_dir / safe_filename).resolve()

        # Validate path is within output_dir (prevent path traversal)
        if not str(output_path).startswith(str(output_dir.resolve())):
            raise MagisterAPIError(f"Invalid filename: {bijlage.naam}", 400)

        # Handle duplicate filenames
        if output_path.exists():
            stem = output_path.stem
            suffix = output_path.suffix
            counter = 1
            while output_path.exists():
                output_path = output_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        output_path.write_bytes(response.content)
        return output_path

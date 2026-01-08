"""Messages resource for Magister API."""

from magister_cli.api.base import BaseResource
from magister_cli.api.models import Bericht, BerichtDetail


class MessagesResource(BaseResource):
    """Resource for messages (berichten) operations.

    Note: Messages API uses different base paths than person-based endpoints.
    """

    def inbox(self, top: int = 25, skip: int = 0) -> list[Bericht]:
        """Get inbox messages.

        Args:
            top: Maximum number of messages to return
            skip: Number of messages to skip (for pagination)

        Returns:
            List of messages in inbox
        """
        data = self._get(
            "/berichten/postvakin/berichten",
            params={"top": top, "skip": skip},
        )
        items = data.get("items", data.get("Items", [])) if isinstance(data, dict) else data
        return [Bericht.model_validate(item) for item in items]

    def sent(self, top: int = 25, skip: int = 0) -> list[Bericht]:
        """Get sent messages.

        Args:
            top: Maximum number of messages to return
            skip: Number of messages to skip (for pagination)

        Returns:
            List of sent messages
        """
        data = self._get(
            "/berichten/verzendenitems/berichten",
            params={"top": top, "skip": skip},
        )
        items = data.get("items", data.get("Items", [])) if isinstance(data, dict) else data
        return [Bericht.model_validate(item) for item in items]

    def deleted(self, top: int = 25, skip: int = 0) -> list[Bericht]:
        """Get deleted messages (trash).

        Args:
            top: Maximum number of messages to return
            skip: Number of messages to skip (for pagination)

        Returns:
            List of deleted messages
        """
        data = self._get(
            "/berichten/verwijderditems/berichten",
            params={"top": top, "skip": skip},
        )
        items = data.get("items", data.get("Items", [])) if isinstance(data, dict) else data
        return [Bericht.model_validate(item) for item in items]

    def get(self, message_id: int) -> BerichtDetail:
        """Get full message details.

        Args:
            message_id: The message ID

        Returns:
            Full message with body and attachments
        """
        data = self._get(f"/berichten/{message_id}")
        return BerichtDetail.model_validate(data)

    def mark_as_read(self, message_id: int) -> None:
        """Mark a message as read.

        Args:
            message_id: The message ID to mark as read
        """
        self._put(f"/berichten/{message_id}/gelezen")

    def delete(self, message_id: int) -> None:
        """Delete a message (move to trash).

        Args:
            message_id: The message ID to delete
        """
        self._delete(f"/berichten/{message_id}")

    def unread_count(self) -> int:
        """Get count of unread messages in inbox.

        Returns:
            Number of unread messages
        """
        # Get first page of inbox and count unread
        messages = self.inbox(top=100)
        return sum(1 for m in messages if m.is_unread)

"""Account resource for user/student information."""

from __future__ import annotations

from magister_cli.api.base import BaseResource
from magister_cli.api.models import Account, Kind


class AccountResource(BaseResource):
    """Resource for account-related API calls."""

    def get_account(self) -> Account:
        """Get account info."""
        data = self._get("/account")
        return Account.model_validate(data)

    def get_children(self, account_id: int) -> list[Kind]:
        """Get children for a parent account.

        Args:
            account_id: The parent account's person ID

        Returns:
            List of children, empty if not a parent account
        """
        data = self._get(f"/personen/{account_id}/kinderen")
        if isinstance(data, dict):
            items = data.get("items", data.get("Items", []))
            return [Kind.model_validate(item) for item in items]
        if isinstance(data, list):
            return [Kind.model_validate(item) for item in data]
        return []

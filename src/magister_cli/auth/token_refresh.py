"""Token refresh service for Magister OAuth tokens.

This module handles refreshing access tokens using the refresh_token
without requiring the user to re-authenticate via browser.
"""

import logging
from datetime import datetime, timedelta

import httpx

from magister_cli.auth.token_manager import TokenData, get_token_manager
from magister_cli.config import validate_school_code

logger = logging.getLogger(__name__)

# Magister OAuth endpoints
TOKEN_ENDPOINT = "https://accounts.magister.net/connect/token"
CLIENT_ID = "M6LOAPP"


async def refresh_access_token(school: str) -> TokenData:
    """Refresh the access token using the stored refresh token.

    Args:
        school: School code (e.g., 'vsvonh')

    Returns:
        Updated TokenData with new access_token and possibly new refresh_token

    Raises:
        RuntimeError: If no refresh token is available or refresh fails
    """
    validated_school = validate_school_code(school)
    token_manager = get_token_manager(validated_school)
    current_token = token_manager.get_token()

    if current_token is None:
        raise RuntimeError("No token stored. Please login first.")

    if not current_token.has_refresh_token():
        raise RuntimeError(
            "No refresh token available. Please login again to get a refresh token."
        )

    refresh_token = current_token.refresh_token

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                TOKEN_ENDPOINT,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": CLIENT_ID,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                error_msg = f"Token refresh failed with status {response.status_code}"
                try:
                    error_data = response.json()
                    if "error_description" in error_data:
                        error_msg = error_data["error_description"]
                    elif "error" in error_data:
                        error_msg = error_data["error"]
                except Exception:
                    pass
                logger.error(f"Token refresh failed: {error_msg}")
                raise RuntimeError(
                    f"Token refresh failed: {error_msg}. Please login again."
                )

            data = response.json()

            # Parse the new token data
            new_access_token = data.get("access_token")
            new_refresh_token = data.get("refresh_token", refresh_token)
            expires_in = data.get("expires_in", 7200)  # Default 2 hours

            if not new_access_token:
                raise RuntimeError("No access_token in refresh response")

            expires_at = datetime.now() + timedelta(seconds=expires_in)

            # Create updated token data, preserving person info
            new_token_data = TokenData(
                access_token=new_access_token,
                school=validated_school,
                person_id=current_token.person_id,
                person_name=current_token.person_name,
                expires_at=expires_at,
                refresh_token=new_refresh_token,
            )

            # Save the new token
            token_manager.save_token(new_token_data)

            logger.info(f"Token refreshed successfully for {validated_school}")
            return new_token_data

        except httpx.RequestError as e:
            logger.error(f"Network error during token refresh: {e}")
            raise RuntimeError(f"Network error during token refresh: {e}")


def refresh_access_token_sync(school: str) -> TokenData:
    """Synchronous version of refresh_access_token.

    Args:
        school: School code (e.g., 'vsvonh')

    Returns:
        Updated TokenData with new access_token and possibly new refresh_token

    Raises:
        RuntimeError: If no refresh token is available or refresh fails
    """
    validated_school = validate_school_code(school)
    token_manager = get_token_manager(validated_school)
    current_token = token_manager.get_token()

    if current_token is None:
        raise RuntimeError("No token stored. Please login first.")

    if not current_token.has_refresh_token():
        raise RuntimeError(
            "No refresh token available. Please login again to get a refresh token."
        )

    refresh_token = current_token.refresh_token

    with httpx.Client() as client:
        try:
            response = client.post(
                TOKEN_ENDPOINT,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": CLIENT_ID,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                error_msg = f"Token refresh failed with status {response.status_code}"
                try:
                    error_data = response.json()
                    if "error_description" in error_data:
                        error_msg = error_data["error_description"]
                    elif "error" in error_data:
                        error_msg = error_data["error"]
                except Exception:
                    pass
                logger.error(f"Token refresh failed: {error_msg}")
                raise RuntimeError(
                    f"Token refresh failed: {error_msg}. Please login again."
                )

            data = response.json()

            # Parse the new token data
            new_access_token = data.get("access_token")
            new_refresh_token = data.get("refresh_token", refresh_token)
            expires_in = data.get("expires_in", 7200)  # Default 2 hours

            if not new_access_token:
                raise RuntimeError("No access_token in refresh response")

            expires_at = datetime.now() + timedelta(seconds=expires_in)

            # Create updated token data, preserving person info
            new_token_data = TokenData(
                access_token=new_access_token,
                school=validated_school,
                person_id=current_token.person_id,
                person_name=current_token.person_name,
                expires_at=expires_at,
                refresh_token=new_refresh_token,
            )

            # Save the new token
            token_manager.save_token(new_token_data)

            logger.info(f"Token refreshed successfully for {validated_school}")
            return new_token_data

        except httpx.RequestError as e:
            logger.error(f"Network error during token refresh: {e}")
            raise RuntimeError(f"Network error during token refresh: {e}")


async def auto_refresh_if_needed(school: str, minutes_threshold: int = 15) -> TokenData | None:
    """Automatically refresh token if it's expiring soon.

    Args:
        school: School code (e.g., 'vsvonh')
        minutes_threshold: Refresh if token expires within this many minutes

    Returns:
        New TokenData if refreshed, None if not needed or no refresh token available
    """
    validated_school = validate_school_code(school)
    token_manager = get_token_manager(validated_school)

    if not token_manager.is_token_expiring_soon(minutes=minutes_threshold):
        return None  # Token is still valid

    if not token_manager.has_refresh_token():
        logger.warning("Token expiring but no refresh token available")
        return None

    try:
        return await refresh_access_token(validated_school)
    except RuntimeError as e:
        logger.warning(f"Auto-refresh failed: {e}")
        return None

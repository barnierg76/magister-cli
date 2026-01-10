"""PKCE OAuth flow for Magister mobile app authentication.

This module implements the OAuth 2.0 Authorization Code Flow with PKCE,
which is used by the Magister mobile app to get refresh tokens.

The web OAuth flow uses implicit grant (response_type=token) which doesn't
return refresh tokens. The mobile app flow uses authorization code + PKCE
which does return refresh tokens.
"""

import base64
import hashlib
import logging
import os
import re
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from magister_cli.auth.token_manager import TokenData
from magister_cli.config import validate_school_code

logger = logging.getLogger(__name__)

# OAuth endpoints
AUTHORIZE_ENDPOINT = "https://accounts.magister.net/connect/authorize"
TOKEN_ENDPOINT = "https://accounts.magister.net/connect/token"

# Mobile app client configuration
# The mobile app uses a different client_id that supports authorization_code flow
MOBILE_CLIENT_ID = "M6LOAPP"
MOBILE_REDIRECT_URI = "m6loapp://oauth2redirect/"

# Scopes that include offline_access for refresh token
MOBILE_SCOPES = [
    "openid",
    "profile",
    "offline_access",  # Required for refresh token
    "magister.ecs.legacy",
    "magister.mdv.broker.read",
    "magister.dnn.roles.read",
]


def generate_code_verifier(length: int = 64) -> str:
    """Generate a cryptographically random code verifier for PKCE.

    Args:
        length: Length of the verifier (43-128 characters)

    Returns:
        URL-safe base64 encoded random string
    """
    # Generate random bytes
    random_bytes = os.urandom(length)
    # Base64 URL encode without padding
    verifier = base64.urlsafe_b64encode(random_bytes).decode('utf-8').rstrip('=')
    # Ensure valid length (43-128 chars)
    return verifier[:128]


def generate_code_challenge(code_verifier: str) -> str:
    """Generate SHA256 code challenge from verifier for PKCE.

    Args:
        code_verifier: The code verifier string

    Returns:
        Base64 URL encoded SHA256 hash of the verifier
    """
    # SHA256 hash of the verifier
    digest = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    # Base64 URL encode without padding
    challenge = base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')
    return challenge


def generate_state() -> str:
    """Generate a random state parameter for CSRF protection."""
    return base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8').rstrip('=')


class PKCEAuthFlow:
    """OAuth 2.0 Authorization Code Flow with PKCE for Magister.

    This flow is used by the Magister mobile app and returns refresh tokens,
    unlike the web implicit grant flow.
    """

    def __init__(self, school: str):
        """Initialize the PKCE auth flow.

        Args:
            school: School code (e.g., 'vsvonh')
        """
        self.school = validate_school_code(school)
        self.code_verifier = generate_code_verifier()
        self.code_challenge = generate_code_challenge(self.code_verifier)
        self.state = generate_state()

    def get_authorization_url(self) -> str:
        """Get the authorization URL for the OAuth flow.

        Returns:
            URL to redirect the user to for authentication
        """
        params = {
            "client_id": MOBILE_CLIENT_ID,
            "redirect_uri": MOBILE_REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(MOBILE_SCOPES),
            "state": self.state,
            "code_challenge": self.code_challenge,
            "code_challenge_method": "S256",
            # Add tenant hint for the school
            "acr_values": f"tenant:{self.school}.magister.net",
        }
        return f"{AUTHORIZE_ENDPOINT}?{urlencode(params)}"

    def extract_code_from_redirect(self, redirect_url: str) -> str:
        """Extract the authorization code from the redirect URL.

        Args:
            redirect_url: The URL the user was redirected to (m6loapp://...)

        Returns:
            The authorization code

        Raises:
            ValueError: If the code cannot be extracted or state doesn't match
        """
        parsed = urlparse(redirect_url)

        # Handle fragment or query parameters
        if parsed.query:
            params = parse_qs(parsed.query)
        elif parsed.fragment:
            params = parse_qs(parsed.fragment)
        else:
            raise ValueError("No parameters found in redirect URL")

        # Check for error
        if "error" in params:
            error = params["error"][0]
            error_desc = params.get("error_description", ["Unknown error"])[0]
            raise ValueError(f"OAuth error: {error} - {error_desc}")

        # Validate state (CSRF protection)
        if "state" in params:
            if params["state"][0] != self.state:
                raise ValueError("State mismatch - possible CSRF attack")

        # Extract code
        if "code" not in params:
            raise ValueError("No authorization code in redirect URL")

        return params["code"][0]

    async def exchange_code_for_tokens(self, code: str) -> TokenData:
        """Exchange the authorization code for access and refresh tokens.

        Args:
            code: The authorization code from the redirect

        Returns:
            TokenData with access_token and refresh_token

        Raises:
            RuntimeError: If token exchange fails
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                TOKEN_ENDPOINT,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": MOBILE_REDIRECT_URI,
                    "client_id": MOBILE_CLIENT_ID,
                    "code_verifier": self.code_verifier,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                error_msg = f"Token exchange failed with status {response.status_code}"
                try:
                    error_data = response.json()
                    if "error_description" in error_data:
                        error_msg = error_data["error_description"]
                    elif "error" in error_data:
                        error_msg = error_data["error"]
                except Exception:
                    pass
                logger.error(f"Token exchange failed: {error_msg}")
                raise RuntimeError(f"Token exchange failed: {error_msg}")

            data = response.json()

            access_token = data.get("access_token")
            refresh_token = data.get("refresh_token")
            expires_in = data.get("expires_in", 3600)

            if not access_token:
                raise RuntimeError("No access_token in token response")

            expires_at = datetime.now() + timedelta(seconds=expires_in)

            logger.info(f"Token exchange successful, refresh_token: {'present' if refresh_token else 'absent'}")

            return TokenData(
                access_token=access_token,
                school=self.school,
                expires_at=expires_at,
                refresh_token=refresh_token,
            )

    def exchange_code_for_tokens_sync(self, code: str) -> TokenData:
        """Synchronous version of exchange_code_for_tokens."""
        with httpx.Client() as client:
            response = client.post(
                TOKEN_ENDPOINT,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": MOBILE_REDIRECT_URI,
                    "client_id": MOBILE_CLIENT_ID,
                    "code_verifier": self.code_verifier,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                error_msg = f"Token exchange failed with status {response.status_code}"
                try:
                    error_data = response.json()
                    if "error_description" in error_data:
                        error_msg = error_data["error_description"]
                    elif "error" in error_data:
                        error_msg = error_data["error"]
                except Exception:
                    pass
                logger.error(f"Token exchange failed: {error_msg}")
                raise RuntimeError(f"Token exchange failed: {error_msg}")

            data = response.json()

            access_token = data.get("access_token")
            refresh_token = data.get("refresh_token")
            expires_in = data.get("expires_in", 3600)

            if not access_token:
                raise RuntimeError("No access_token in token response")

            expires_at = datetime.now() + timedelta(seconds=expires_in)

            logger.info(f"Token exchange successful, refresh_token: {'present' if refresh_token else 'absent'}")

            return TokenData(
                access_token=access_token,
                school=self.school,
                expires_at=expires_at,
                refresh_token=refresh_token,
            )

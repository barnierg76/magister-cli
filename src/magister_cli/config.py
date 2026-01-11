"""Configuration management using Pydantic Settings."""

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

# Config file location
CONFIG_PATH = Path.home() / ".config" / "magister-cli" / "config.yaml"


class YamlConfigSettingsSource(PydanticBaseSettingsSource):
    """Custom settings source that loads from YAML config file."""

    def get_field_value(
        self, field: Any, field_name: str
    ) -> tuple[Any, str, bool]:
        """Get field value from YAML config."""
        config = self._load_config()
        if field_name in config:
            return config[field_name], field_name, False
        return None, field_name, False

    def _load_config(self) -> dict:
        """Load config from YAML file."""
        if not CONFIG_PATH.exists():
            return {}
        try:
            with open(CONFIG_PATH) as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError:
            return {}

    def __call__(self) -> dict[str, Any]:
        """Return all config values."""
        return self._load_config()


def validate_school_code(school: str | None) -> str:
    """Validate school code format to prevent SSRF/phishing.

    Args:
        school: School code to validate

    Returns:
        Normalized (lowercase) school code

    Raises:
        ValueError: If school code is invalid
    """
    if not school:
        raise ValueError("School code cannot be empty")

    # Only allow alphanumeric characters and hyphens
    if not re.match(r"^[a-zA-Z0-9-]+$", school):
        raise ValueError(f"Invalid school code format: {school}")

    # Reasonable length limit
    if len(school) > 50:
        raise ValueError("School code too long (max 50 characters)")

    return school.lower()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="MAGISTER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    school: str | None = Field(
        default=None,
        description="School code (e.g., vsvonh)",
    )
    username: str | None = Field(default=None, description="Username for auto-login hint")
    timeout: int = Field(default=30, ge=5, le=120, description="HTTP timeout in seconds")
    headless: bool = Field(default=True, description="Run browser in headless mode")
    cache_dir: Path = Field(
        default=Path.home() / ".config" / "magister-cli",
        description="Cache directory for tokens and config",
    )
    oauth_callback_port: int = Field(
        default=8080,
        ge=1024,
        le=65535,
        description="Port for OAuth callback server",
    )
    oauth_timeout: int = Field(
        default=300,
        ge=30,
        le=600,
        description="Timeout for OAuth flow in seconds",
    )
    mcp_auth_timeout: int = Field(
        default=300,
        ge=60,
        le=600,
        description="Timeout for MCP browser authentication in seconds",
    )
    mcp_auto_browser_auth: bool = Field(
        default=True,
        description="Allow MCP server to launch browser for authentication",
    )

    @field_validator("cache_dir", mode="after")
    @classmethod
    def ensure_cache_dir_exists(cls, v: Path) -> Path:
        """Create cache directory if it doesn't exist."""
        v.mkdir(parents=True, exist_ok=True)
        return v

    @property
    def token_file(self) -> Path:
        """Path to the token cache file."""
        return self.cache_dir / "token.json"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customize settings sources - priority: env > yaml > defaults."""
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls),
        )


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset settings (useful for testing)."""
    global _settings
    _settings = None


def load_config() -> dict[str, Any]:
    """Load config from YAML file.

    Returns:
        Dictionary of config values, empty dict if file doesn't exist or is invalid.
    """
    if not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError:
        return {}


def save_config(config: dict[str, Any]) -> None:
    """Save config to YAML file.

    Args:
        config: Dictionary of config values to save.
    """
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

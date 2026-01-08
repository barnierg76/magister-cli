"""Base model configuration for all Magister models."""

from pydantic import BaseModel, ConfigDict


class MagisterModel(BaseModel):
    """Base model with common configuration.

    All Magister API models should inherit from this class to get:
    - populate_by_name: Allow both alias and field name in input
    - extra="ignore": Ignore unknown fields from API responses
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
    )

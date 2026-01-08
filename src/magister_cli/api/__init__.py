"""API module for Magister CLI."""

from magister_cli.api.client import (
    MagisterAPIError,
    MagisterClient,
    RateLimitError,
    TokenExpiredError,
)
from magister_cli.api.models import (
    Account,
    Afspraak,
    AfspraakResponse,
    Bijlage,
    Cijfer,
    CijferResponse,
    Kind,
    KindResponse,
    Persoon,
    Vak,
)

__all__ = [
    "MagisterClient",
    "MagisterAPIError",
    "TokenExpiredError",
    "RateLimitError",
    "Account",
    "Afspraak",
    "AfspraakResponse",
    "Bijlage",
    "Cijfer",
    "CijferResponse",
    "Kind",
    "KindResponse",
    "Persoon",
    "Vak",
]

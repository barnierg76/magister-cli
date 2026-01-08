"""API module for Magister CLI."""

from magister_cli.api.client import MagisterClient
from magister_cli.api.exceptions import (
    MagisterAPIError,
    NotAuthenticatedError,
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
    MagisterModel,
    Persoon,
    Vak,
)
from magister_cli.api.resources import (
    AccountResource,
    AppointmentsResource,
    AttachmentsResource,
    GradesResource,
)

__all__ = [
    # Client
    "MagisterClient",
    # Exceptions
    "MagisterAPIError",
    "NotAuthenticatedError",
    "TokenExpiredError",
    "RateLimitError",
    # Base model
    "MagisterModel",
    # Models
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
    # Resources
    "AccountResource",
    "AppointmentsResource",
    "AttachmentsResource",
    "GradesResource",
]

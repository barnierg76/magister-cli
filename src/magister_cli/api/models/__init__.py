"""Re-export all models for backward compatibility."""

from magister_cli.api.models.account import (
    Account,
    Groep,
    Kind,
    KindResponse,
    Persoon,
)
from magister_cli.api.models.appointments import (
    Afspraak,
    AfspraakResponse,
    Docent,
    Lokaal,
    Vak,
)
from magister_cli.api.models.attachments import Bijlage, BijlageLink
from magister_cli.api.models.base import MagisterModel
from magister_cli.api.models.grades import Cijfer, CijferKolom, CijferResponse
from magister_cli.api.models.enrollments import (
    Aanmelding,
    AanmeldingenResponse,
    CijferPeriodeOverzicht,
    Periode,
    Studie,
    VakCijferOverzicht,
)
from magister_cli.api.models.messages import (
    Afzender,
    Bericht,
    BerichtDetail,
    BerichtenResponse,
)

__all__ = [
    # Base
    "MagisterModel",
    # Account
    "Account",
    "Groep",
    "Kind",
    "KindResponse",
    "Persoon",
    # Appointments
    "Afspraak",
    "AfspraakResponse",
    "Docent",
    "Lokaal",
    "Vak",
    # Attachments
    "Bijlage",
    "BijlageLink",
    # Grades
    "Cijfer",
    "CijferKolom",
    "CijferResponse",
    # Enrollments
    "Aanmelding",
    "AanmeldingenResponse",
    "CijferPeriodeOverzicht",
    "Periode",
    "Studie",
    "VakCijferOverzicht",
    # Messages
    "Afzender",
    "Bericht",
    "BerichtDetail",
    "BerichtenResponse",
]

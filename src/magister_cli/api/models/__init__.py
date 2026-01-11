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
from magister_cli.api.models.assignments import (
    Opdracht,
    OpdrachtResponse,
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
    StudieVak,
    VakCijferOverzicht,
    VakDocent,
    VakInschrijving,
)
from magister_cli.api.models.learningmaterials import (
    Lesmateriaal,
    LesmateriaalResponse,
    LesmateriaalVak,
)
from magister_cli.api.models.messages import (
    Afzender,
    Bericht,
    BerichtDetail,
    BerichtenResponse,
)
from magister_cli.api.models.studyguides import (
    Studiewijzer,
    StudiewijzerBron,
    StudiewijzerOnderdeel,
    StudiewijzerOnderdelenResponse,
    StudiewijzerResponse,
)
from magister_cli.api.models.attendance import (
    Absentie,
    VerzuimType,
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
    # Assignments
    "Opdracht",
    "OpdrachtResponse",
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
    "StudieVak",
    "VakCijferOverzicht",
    "VakDocent",
    "VakInschrijving",
    # Learning Materials
    "Lesmateriaal",
    "LesmateriaalResponse",
    "LesmateriaalVak",
    # Messages
    "Afzender",
    "Bericht",
    "BerichtDetail",
    "BerichtenResponse",
    # Study Guides
    "Studiewijzer",
    "StudiewijzerBron",
    "StudiewijzerOnderdeel",
    "StudiewijzerOnderdelenResponse",
    "StudiewijzerResponse",
    # Attendance
    "Absentie",
    "VerzuimType",
]

"""API resources."""

from magister_cli.api.resources.account import AccountResource
from magister_cli.api.resources.appointments import AppointmentsResource
from magister_cli.api.resources.attachments import AttachmentsResource
from magister_cli.api.resources.grades import GradesResource
from magister_cli.api.resources.messages import MessagesResource

__all__ = [
    "AccountResource",
    "AppointmentsResource",
    "AttachmentsResource",
    "GradesResource",
    "MessagesResource",
]

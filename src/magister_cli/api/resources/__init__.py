"""API resources."""

from magister_cli.api.resources.account import AccountResource
from magister_cli.api.resources.appointments import AppointmentsResource
from magister_cli.api.resources.assignments import AssignmentsResource
from magister_cli.api.resources.attachments import AttachmentsResource
from magister_cli.api.resources.grades import GradesResource
from magister_cli.api.resources.learningmaterials import LearningMaterialsResource
from magister_cli.api.resources.messages import MessagesResource
from magister_cli.api.resources.studyguides import StudyGuidesResource

__all__ = [
    "AccountResource",
    "AppointmentsResource",
    "AssignmentsResource",
    "AttachmentsResource",
    "GradesResource",
    "LearningMaterialsResource",
    "MessagesResource",
    "StudyGuidesResource",
]

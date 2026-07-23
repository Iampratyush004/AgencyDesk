from app.models.enums import RoleEnum, ProjectStatusEnum, TaskStatusEnum, TaskPriorityEnum, VisibilityEnum, FileApprovalStatusEnum, InvitationStatusEnum
from app.models.user import User
from app.models.agency import Agency, AgencyMembership
from app.models.client import Client, ClientMembership
from app.models.project import Project, ProjectMembership
from app.models.task import Task
from app.models.comment import Comment
from app.models.time_entry import TimeEntry
from app.models.file import File, FileApproval
from app.models.invitation import Invitation

# This ensures all models are loaded when Base.metadata is accessed
__all__ = [
    "User",
    "Agency",
    "AgencyMembership",
    "Client",
    "ClientMembership",
    "Project",
    "ProjectMembership",
    "Task",
    "Comment",
    "TimeEntry",
    "File",
    "FileApproval",
    "Invitation",
    "RoleEnum",
    "ProjectStatusEnum",
    "TaskStatusEnum",
    "TaskPriorityEnum",
    "VisibilityEnum",
    "FileApprovalStatusEnum",
    "InvitationStatusEnum",
]

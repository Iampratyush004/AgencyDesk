import enum

class RoleEnum(str, enum.Enum):
    agency_admin = 'agency_admin'
    agency_member = 'agency_member'
    client_user = 'client_user'

class ProjectStatusEnum(str, enum.Enum):
    active = 'active'
    archived = 'archived'
    completed = 'completed'

class TaskStatusEnum(str, enum.Enum):
    todo = 'todo'
    in_progress = 'in_progress'
    review = 'review'
    done = 'done'

class TaskPriorityEnum(str, enum.Enum):
    low = 'low'
    medium = 'medium'
    high = 'high'
    urgent = 'urgent'

class VisibilityEnum(str, enum.Enum):
    internal = 'internal'
    client = 'client'

class FileApprovalStatusEnum(str, enum.Enum):
    approved = 'approved'
    needs_changes = 'needs_changes'

class InvitationStatusEnum(str, enum.Enum):
    pending = 'pending'
    accepted = 'accepted'
    expired = 'expired'
    revoked = 'revoked'

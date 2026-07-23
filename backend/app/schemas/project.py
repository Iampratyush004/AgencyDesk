from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from app.models.enums import ProjectStatusEnum

class ProjectCreate(BaseModel):
    name: str
    client_id: UUID
    description: str | None = None
    
    model_config = ConfigDict(extra="forbid")

class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: ProjectStatusEnum | None = None
    
    model_config = ConfigDict(extra="forbid")

class ProjectResponse(BaseModel):
    id: UUID
    client_id: UUID
    name: str
    description: str | None
    status: ProjectStatusEnum
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ProjectMembershipCreate(BaseModel):
    user_id: UUID
    
    model_config = ConfigDict(extra="forbid")

class ProjectMembershipResponse(BaseModel):
    id: UUID
    user_id: UUID
    project_id: UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class DashboardTaskCounts(BaseModel):
    todo: int = 0
    in_progress: int = 0
    review: int = 0
    done: int = 0

class ProjectDashboardClientResponse(BaseModel):
    task_counts: DashboardTaskCounts

class ProjectDashboardStaffResponse(BaseModel):
    task_counts: DashboardTaskCounts
    hours_logged: int

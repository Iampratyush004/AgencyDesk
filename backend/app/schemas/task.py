from uuid import UUID
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import TaskStatusEnum, TaskPriorityEnum, VisibilityEnum

class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    status: TaskStatusEnum = TaskStatusEnum.todo
    priority: TaskPriorityEnum = TaskPriorityEnum.medium
    visibility: VisibilityEnum = VisibilityEnum.internal
    assignee_id: UUID | None = None
    due_date: date | None = None
    
    model_config = ConfigDict(extra="forbid")

class TaskUpdate(BaseModel):
    title: str = Field(default=None)
    description: str | None = Field(default=None)
    status: TaskStatusEnum = Field(default=None)
    priority: TaskPriorityEnum = Field(default=None)
    visibility: VisibilityEnum = Field(default=None)
    assignee_id: UUID | None = Field(default=None)
    due_date: date | None = Field(default=None)
    
    model_config = ConfigDict(extra="forbid")

class TaskResponse(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    description: str | None
    status: TaskStatusEnum
    priority: TaskPriorityEnum
    visibility: VisibilityEnum
    assignee_id: UUID | None
    due_date: date | None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

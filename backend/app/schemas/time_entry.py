from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class TimeEntryCreate(BaseModel):
    duration_minutes: int = Field(gt=0)
    date: date
    note: str | None = None
    
    model_config = ConfigDict(extra="forbid")

class TimeEntryResponse(BaseModel):
    id: UUID
    task_id: UUID
    project_id: UUID
    user_id: UUID
    duration_minutes: int
    date: date
    note: str | None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

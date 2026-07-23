from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import VisibilityEnum

class CommentCreate(BaseModel):
    content: str
    visibility: VisibilityEnum = Field(default=VisibilityEnum.internal)
    
    model_config = ConfigDict(extra="forbid")

class CommentResponse(BaseModel):
    id: UUID
    task_id: UUID
    author_id: UUID
    content: str
    visibility: VisibilityEnum
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

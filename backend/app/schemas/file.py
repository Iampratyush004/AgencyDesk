from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import FileApprovalStatusEnum, VisibilityEnum

class FileApprovalResponse(BaseModel):
    id: UUID
    file_id: UUID
    reviewer_id: UUID
    status: str
    note: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class FileResponse(BaseModel):
    id: UUID
    task_id: UUID
    uploaded_by_id: UUID
    filename: str
    mime_type: str | None
    file_size_bytes: int | None
    visibility: VisibilityEnum
    created_at: datetime
    approvals: list[FileApprovalResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

class FileApprovalCreate(BaseModel):
    status: FileApprovalStatusEnum
    note: str | None = None

    model_config = ConfigDict(extra="forbid")

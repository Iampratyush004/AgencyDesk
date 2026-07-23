from datetime import datetime
from uuid import UUID
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from app.models.enums import RoleEnum

class InvitationCreate(BaseModel):
    email: EmailStr
    role: RoleEnum
    client_id: UUID | None = None
    
    model_config = ConfigDict(extra="forbid")
    
    @field_validator('email', mode='before')
    @classmethod
    def normalize_email(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v

class InvitationAccept(BaseModel):
    token: str
    full_name: str
    password: str
    
    model_config = ConfigDict(extra="forbid")
    
    @field_validator('password')
    @classmethod
    def validate_password_length(cls, v: str) -> str:
        if len(v.encode('utf-8')) > 72:
            raise ValueError('Password cannot exceed 72 bytes')
        return v

class InvitationResponse(BaseModel):
    id: UUID
    agency_id: UUID
    email: str
    role: str
    client_id: UUID | None
    status: str
    invited_by_id: UUID
    expires_at: datetime
    created_at: datetime
    accepted_at: datetime | None
    
    model_config = ConfigDict(from_attributes=True)

class InvitationSendResponse(InvitationResponse):
    raw_token: str

class InvitationAcceptResponse(BaseModel):
    status: Literal["accepted"] = "accepted"

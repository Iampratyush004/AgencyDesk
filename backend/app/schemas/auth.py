from pydantic import BaseModel, EmailStr, field_validator
from typing import Literal
from uuid import UUID

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    agency_id: UUID | None = None

    @field_validator('password')
    @classmethod
    def validate_password_length(cls, v: str) -> str:
        if len(v.encode('utf-8')) > 72:
            raise ValueError('Password cannot exceed 72 bytes')
        return v


class AuthenticatedResponse(BaseModel):
    status: Literal["authenticated"] = "authenticated"
    access_token: str
    token_type: Literal["bearer"] = "bearer"

class AgencySelectionItem(BaseModel):
    id: UUID
    name: str
    role: str

class AgencySelectionResponse(BaseModel):
    status: Literal["agency_selection_required"] = "agency_selection_required"
    agencies: list[AgencySelectionItem]

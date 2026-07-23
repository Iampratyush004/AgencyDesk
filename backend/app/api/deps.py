from dataclasses import dataclass
from uuid import UUID
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings
from app.models.user import User
from app.models.agency import AgencyMembership
from app.models.client import ClientMembership
from app.models.enums import RoleEnum

oauth2_scheme = HTTPBearer()

@dataclass(frozen=True)
class TenantContext:
    user: User
    membership: AgencyMembership
    agency_id: UUID
    role: str
    client_id: UUID | None

async def get_current_tenant_context(
    token: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> TenantContext:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token.credentials, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id_str = payload.get("sub")
        agency_id_str = payload.get("agency_id")
        
        if user_id_str is None or agency_id_str is None:
            raise credentials_exception
            
        user_id = UUID(user_id_str)
        agency_id = UUID(agency_id_str)
    except (jwt.PyJWTError, ValueError):
        raise credentials_exception

    # Query User
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None or not user.is_active:
        raise credentials_exception

    # Query AgencyMembership
    membership_result = await db.execute(
        select(AgencyMembership).where(
            and_(
                AgencyMembership.user_id == user_id,
                AgencyMembership.agency_id == agency_id
            )
        )
    )
    membership = membership_result.scalar_one_or_none()
    
    if membership is None or not membership.is_active:
        raise credentials_exception
        
    role = membership.role
    client_id = None
    
    # Verify ClientMembership if role is client_user
    if role == RoleEnum.client_user.value:
        client_mem_result = await db.execute(
            select(ClientMembership).where(
                and_(
                    ClientMembership.user_id == user_id,
                    ClientMembership.agency_id == agency_id
                )
            )
        )
        client_mem = client_mem_result.scalar_one_or_none()
        
        if client_mem is None:
            raise credentials_exception
            
        client_id = client_mem.client_id
        
    return TenantContext(
        user=user,
        membership=membership,
        agency_id=agency_id,
        role=role,
        client_id=client_id
    )

def require_roles(allowed_roles: list[str]):
    def role_checker(context: TenantContext = Depends(get_current_tenant_context)) -> TenantContext:
        if context.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return context
    return role_checker

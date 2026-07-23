from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database import get_db
from app.schemas.auth import LoginRequest, AuthenticatedResponse, AgencySelectionResponse, AgencySelectionItem
from app.models.user import User
from app.models.agency import Agency, AgencyMembership
from app.models.client import ClientMembership
from app.models.enums import RoleEnum
from app.core.security import verify_password, create_access_token

router = APIRouter()

@router.post("/login", response_model=AuthenticatedResponse | AgencySelectionResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    generic_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password",
    )
    
    # 1. Normalize email
    email = request.email.lower()
    
    # 2. Find User
    user_result = await db.execute(select(User).where(User.email == email))
    user = user_result.scalar_one_or_none()
    
    # 3. Verify password
    if user is None or not verify_password(request.password, user.password_hash):
        raise generic_error
        
    # 4. Require User.is_active
    if not user.is_active:
        raise generic_error

    # 5. Load ACTIVE AgencyMembership rows for the User
    stmt = (
        select(AgencyMembership, Agency)
        .join(Agency, AgencyMembership.agency_id == Agency.id)
        .where(
            and_(
                AgencyMembership.user_id == user.id,
                AgencyMembership.is_active == True
            )
        )
    )
    memberships_result = await db.execute(stmt)
    memberships = memberships_result.all()
    
    if not memberships:
        raise generic_error

    selected_membership = None
    
    # 6. If agency_id was supplied
    if request.agency_id:
        for m, a in memberships:
            if m.agency_id == request.agency_id:
                selected_membership = m
                break
                
        if not selected_membership:
            raise generic_error
            
    # 7. If agency_id omitted
    else:
        if len(memberships) == 1:
            selected_membership = memberships[0][0]
        else:
            # MORE THAN ONE: return status=agency_selection_required
            agencies_list = [
                AgencySelectionItem(id=a.id, name=a.name, role=m.role)
                for m, a in memberships
            ]
            return AgencySelectionResponse(agencies=agencies_list)
            
    # 8. Once membership is selected
    role = selected_membership.role
    client_id = None
    
    # 9. If role == client_user, load ClientMembership
    if role == RoleEnum.client_user.value:
        client_mem_result = await db.execute(
            select(ClientMembership).where(
                and_(
                    ClientMembership.user_id == user.id,
                    ClientMembership.agency_id == selected_membership.agency_id
                )
            )
        )
        client_mem = client_mem_result.scalar_one_or_none()
        if client_mem is None:
            raise generic_error
            
        client_id = client_mem.client_id
        
    # 10. Issue the JWT
    access_token = create_access_token(
        sub=str(user.id),
        agency_id=str(selected_membership.agency_id),
        role=role,
        client_id=str(client_id) if client_id else None
    )
    
    return AuthenticatedResponse(access_token=access_token)

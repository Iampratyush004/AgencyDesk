import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.database import get_db
from app.config import settings
from app.api.deps import TenantContext, get_current_tenant_context, require_roles
from app.models.invitation import Invitation
from app.models.user import User
from app.models.agency import AgencyMembership
from app.models.client import Client, ClientMembership
from app.models.enums import RoleEnum, InvitationStatusEnum
from app.schemas.invitation import (
    InvitationCreate,
    InvitationAccept,
    InvitationResponse,
    InvitationSendResponse,
    InvitationAcceptResponse
)
from app.core.security import get_password_hash

router = APIRouter()

agency_admin_only = Depends(require_roles([RoleEnum.agency_admin.value]))

@router.post("", response_model=InvitationSendResponse, status_code=status.HTTP_201_CREATED, dependencies=[agency_admin_only])
async def send_invitation(
    payload: InvitationCreate,
    context: TenantContext = Depends(get_current_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    if payload.role == RoleEnum.client_user.value:
        if not payload.client_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="client_id is required for client_user")
        
        # Verify client belongs to this agency
        client = (await db.execute(
            select(Client).where(Client.id == payload.client_id, Client.agency_id == context.agency_id)
        )).scalar_one_or_none()
        if not client:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    else:
        if payload.client_id is not None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="client_id must not be provided for non-client roles")

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.INVITATION_EXPIRE_DAYS)

    stmt = insert(Invitation).values(
        agency_id=context.agency_id,
        email=payload.email,
        role=payload.role.value,
        client_id=payload.client_id,
        token_hash=token_hash,
        status=InvitationStatusEnum.pending.value,
        invited_by_id=context.user.id,
        expires_at=expires_at
    ).on_conflict_do_update(
        index_elements=['agency_id', 'email'],
        index_where=text("status = 'pending'"),
        set_={
            "token_hash": token_hash,
            "expires_at": expires_at,
            "invited_by_id": context.user.id,
            "role": payload.role.value,
            "client_id": payload.client_id
        }
    ).returning(Invitation)

    result = await db.execute(stmt)
    await db.commit()
    invitation = result.scalar_one()

    resp_data = InvitationResponse.model_validate(invitation).model_dump()
    resp_data['raw_token'] = raw_token
    return resp_data

@router.post("/{invitation_id}/resend", response_model=InvitationSendResponse, dependencies=[agency_admin_only])
async def resend_invitation(
    invitation_id: UUID,
    context: TenantContext = Depends(get_current_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    invitation = (await db.execute(
        select(Invitation).where(Invitation.id == invitation_id, Invitation.agency_id == context.agency_id)
    )).scalar_one_or_none()

    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    if invitation.status != InvitationStatusEnum.pending.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Can only resend pending invitations")

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.INVITATION_EXPIRE_DAYS)

    stmt = insert(Invitation).values(
        agency_id=context.agency_id,
        email=invitation.email,
        role=invitation.role,
        client_id=invitation.client_id,
        token_hash=token_hash,
        status=InvitationStatusEnum.pending.value,
        invited_by_id=context.user.id,
        expires_at=expires_at
    ).on_conflict_do_update(
        index_elements=['agency_id', 'email'],
        index_where=text("status = 'pending'"),
        set_={
            "token_hash": token_hash,
            "expires_at": expires_at,
            "invited_by_id": context.user.id
        }
    ).returning(Invitation)

    result = await db.execute(stmt)
    await db.commit()
    updated_invitation = result.scalar_one()

    resp_data = InvitationResponse.model_validate(updated_invitation).model_dump()
    resp_data['raw_token'] = raw_token
    return resp_data

@router.post("/accept", response_model=InvitationAcceptResponse)
async def accept_invitation(
    payload: InvitationAccept,
    db: AsyncSession = Depends(get_db)
):
    token_hash = hashlib.sha256(payload.token.encode('utf-8')).hexdigest()
    
    try:
        # 1. Lock the pending invitation
        stmt = select(Invitation).where(
            Invitation.token_hash == token_hash,
            Invitation.status == InvitationStatusEnum.pending.value,
            Invitation.expires_at > func.now()
        ).with_for_update()
        
        invitation = (await db.execute(stmt)).scalar_one_or_none()
        
        if not invitation:
            # 2. Idempotent check
            acc_stmt = select(Invitation).where(
                Invitation.token_hash == token_hash,
                Invitation.status == InvitationStatusEnum.accepted.value
            )
            if (await db.execute(acc_stmt)).scalar_one_or_none():
                return {"status": "accepted"}
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation invalid or expired")

        # 3. Find or Create User
        password_hash = get_password_hash(payload.password)
        u_stmt = insert(User).values(
            email=invitation.email, 
            password_hash=password_hash,
            full_name=payload.full_name
        ).on_conflict_do_nothing().returning(User.id)
        
        user_id = (await db.execute(u_stmt)).scalar()
        if not user_id:
            user_id = (await db.execute(select(User.id).where(User.email == invitation.email))).scalar_one()

        # 4. Create Memberships
        m_stmt = insert(AgencyMembership).values(
            user_id=user_id, agency_id=invitation.agency_id, role=invitation.role
        ).on_conflict_do_nothing()
        await db.execute(m_stmt)
        
        if invitation.role == RoleEnum.client_user.value:
            c_stmt = insert(ClientMembership).values(
                user_id=user_id, client_id=invitation.client_id, agency_id=invitation.agency_id
            ).on_conflict_do_nothing()
            await db.execute(c_stmt)

        # 5. Mark Accepted
        invitation.status = InvitationStatusEnum.accepted.value
        invitation.accepted_at = func.now()
        
        # EXACTLY ONE COMMIT
        await db.commit()
        return {"status": "accepted"}
        
    except Exception:
        # EXPLICIT ROLLBACK ON ANY ERROR
        await db.rollback()
        raise

import pytest
import pytest_asyncio
from httpx import AsyncClient
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import APIRouter, Depends
from uuid import uuid4

from app.main import app
from app.models.user import User
from app.models.agency import Agency, AgencyMembership
from app.models.client import Client, ClientMembership
from app.models.enums import RoleEnum
from app.core.security import get_password_hash, create_access_token
from app.config import settings
from app.api.deps import get_current_tenant_context, require_roles, TenantContext

test_router = APIRouter()

@test_router.get("/test-context")
async def get_test_context(context: TenantContext = Depends(get_current_tenant_context)):
    return {
        "user_id": str(context.user.id),
        "agency_id": str(context.agency_id),
        "role": context.role,
        "client_id": str(context.client_id) if context.client_id else None
    }

@test_router.get("/test-role-admin")
async def get_test_role_admin(context: TenantContext = Depends(require_roles([RoleEnum.agency_admin.value]))):
    return {"status": "ok"}

app.include_router(test_router, tags=["test"])

async def create_user(db_session, is_active=True):
    user = User(email=f"{uuid4()}@test.com", password_hash="hash", full_name="Test User", is_active=is_active)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

async def create_agency(db_session):
    agency = Agency(name="A", slug=str(uuid4())[:8])
    db_session.add(agency)
    await db_session.commit()
    await db_session.refresh(agency)
    return agency

async def create_agency_membership(db_session, user_id, agency_id, role=RoleEnum.agency_member.value, is_active=True):
    mem = AgencyMembership(user_id=user_id, agency_id=agency_id, role=role, is_active=is_active)
    db_session.add(mem)
    await db_session.commit()
    await db_session.refresh(mem)
    return mem

async def create_client(db_session, agency_id):
    client = Client(agency_id=agency_id, name=f"C-{uuid4()}")
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client

async def create_client_membership(db_session, user_id, agency_id, client_id):
    mem = ClientMembership(user_id=user_id, agency_id=agency_id, client_id=client_id)
    db_session.add(mem)
    await db_session.commit()
    await db_session.refresh(mem)
    return mem

@pytest.mark.asyncio
async def test_valid_jwt_resolves_context(async_client: AsyncClient, db_session):
    user = await create_user(db_session)
    agency = await create_agency(db_session)
    await create_agency_membership(db_session, user.id, agency.id, role=RoleEnum.agency_member.value)

    token = create_access_token(str(user.id), str(agency.id), RoleEnum.agency_member.value)
    res = await async_client.get("/test-context", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == str(user.id)
    assert data["agency_id"] == str(agency.id)
    assert data["role"] == RoleEnum.agency_member.value

@pytest.mark.asyncio
async def test_malformed_jwt_denied(async_client: AsyncClient, db_session):
    res = await async_client.get("/test-context", headers={"Authorization": "Bearer not-a-jwt"})
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_expired_jwt_denied(async_client: AsyncClient, db_session):
    user = await create_user(db_session)
    agency = await create_agency(db_session)
    await create_agency_membership(db_session, user.id, agency.id)

    # create manually expired token
    to_encode = {
        "sub": str(user.id),
        "agency_id": str(agency.id),
        "role": RoleEnum.agency_member.value,
        "exp": datetime.now(timezone.utc) - timedelta(minutes=10)
    }
    token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    res = await async_client.get("/test-context", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_user_deactivated_after_issuance(async_client: AsyncClient, db_session):
    user = await create_user(db_session)
    agency = await create_agency(db_session)
    await create_agency_membership(db_session, user.id, agency.id)

    token = create_access_token(str(user.id), str(agency.id), RoleEnum.agency_member.value)
    
    # deactivate user
    user.is_active = False
    await db_session.commit()

    res = await async_client.get("/test-context", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_membership_deactivated_after_issuance(async_client: AsyncClient, db_session):
    user = await create_user(db_session)
    agency = await create_agency(db_session)
    mem = await create_agency_membership(db_session, user.id, agency.id)

    token = create_access_token(str(user.id), str(agency.id), RoleEnum.agency_member.value)
    
    mem.is_active = False
    await db_session.commit()

    res = await async_client.get("/test-context", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_role_changed_after_issuance_uses_db_role(async_client: AsyncClient, db_session):
    user = await create_user(db_session)
    agency = await create_agency(db_session)
    mem = await create_agency_membership(db_session, user.id, agency.id, role=RoleEnum.agency_member.value)

    token = create_access_token(str(user.id), str(agency.id), RoleEnum.agency_member.value)
    
    # change role in DB to admin
    mem.role = RoleEnum.agency_admin.value
    await db_session.commit()

    res = await async_client.get("/test-context", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["role"] == RoleEnum.agency_admin.value

@pytest.mark.asyncio
async def test_client_membership_removed_after_issuance(async_client: AsyncClient, db_session):
    user = await create_user(db_session)
    agency = await create_agency(db_session)
    await create_agency_membership(db_session, user.id, agency.id, role=RoleEnum.client_user.value)
    client = await create_client(db_session, agency.id)
    mem = await create_client_membership(db_session, user.id, agency.id, client.id)

    token = create_access_token(str(user.id), str(agency.id), RoleEnum.client_user.value, str(client.id))
    
    await db_session.delete(mem)
    await db_session.commit()

    res = await async_client.get("/test-context", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_require_roles_permits_allowed(async_client: AsyncClient, db_session):
    user = await create_user(db_session)
    agency = await create_agency(db_session)
    await create_agency_membership(db_session, user.id, agency.id, role=RoleEnum.agency_admin.value)

    token = create_access_token(str(user.id), str(agency.id), RoleEnum.agency_admin.value)
    res = await async_client.get("/test-role-admin", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200

@pytest.mark.asyncio
async def test_require_roles_rejects_disallowed(async_client: AsyncClient, db_session):
    user = await create_user(db_session)
    agency = await create_agency(db_session)
    await create_agency_membership(db_session, user.id, agency.id, role=RoleEnum.agency_member.value)

    token = create_access_token(str(user.id), str(agency.id), RoleEnum.agency_member.value)
    res = await async_client.get("/test-role-admin", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403

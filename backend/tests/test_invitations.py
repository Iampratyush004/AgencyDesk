import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select, func

from app.config import settings
from app.models.user import User
from app.models.invitation import Invitation
from app.models.agency import Agency, AgencyMembership
from app.models.client import Client, ClientMembership
from app.models.enums import RoleEnum, InvitationStatusEnum
from app.core.security import get_password_hash
from app.database import async_session_maker
from app.api.routes.invitations import accept_invitation
from app.schemas.invitation import InvitationAccept

async def create_user(db_session, email, hashed_password, is_active=True):
    user = User(email=email, password_hash=hashed_password, full_name="Test User", is_active=is_active)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

async def create_agency(db_session, name, slug):
    agency = Agency(name=name, slug=slug)
    db_session.add(agency)
    await db_session.commit()
    await db_session.refresh(agency)
    return agency

async def create_agency_membership(db_session, user_id, agency_id, role, is_active=True):
    mem = AgencyMembership(user_id=user_id, agency_id=agency_id, role=role, is_active=is_active)
    db_session.add(mem)
    await db_session.commit()
    await db_session.refresh(mem)
    return mem

async def create_client(db_session, agency_id, name):
    client = Client(agency_id=agency_id, name=name)
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

async def setup_env(db_session, hashed_password):
    admin = await create_user(db_session, "admin@test.com", hashed_password)
    member = await create_user(db_session, "member@test.com", hashed_password)
    client_user = await create_user(db_session, "client@test.com", hashed_password)
    
    agency = await create_agency(db_session, "Agency A", "a")
    
    await create_agency_membership(db_session, admin.id, agency.id, RoleEnum.agency_admin.value)
    await create_agency_membership(db_session, member.id, agency.id, RoleEnum.agency_member.value)
    await create_agency_membership(db_session, client_user.id, agency.id, RoleEnum.client_user.value)
    
    client = await create_client(db_session, agency.id, "Client 1")
    await create_client_membership(db_session, client_user.id, agency.id, client.id)
    
    return {
        "admin": admin, "member": member, "client_user": client_user,
        "agency": agency, "client": client
    }

async def login(async_client: AsyncClient, email: str, password: str, agency_id: str = None) -> str:
    data = {"email": email, "password": password}
    if agency_id:
        data["agency_id"] = agency_id
    response = await async_client.post("/auth/login", json=data)
    return response.json()["access_token"]

@pytest.fixture
def password():
    return "Test1234!"

@pytest.fixture
def hashed_password(password):
    return get_password_hash(password)

@pytest.mark.asyncio
async def test_invitation_send_and_resend(async_client: AsyncClient, db_session, password, hashed_password):
    env = await setup_env(db_session, hashed_password)
    admin_token = await login(async_client, "admin@test.com", password, str(env["agency"].id))
    
    # 1. Send invite
    res1 = await async_client.post(
        "/invitations",
        json={"email": "NEW@test.com", "role": "agency_member"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res1.status_code == 201
    data1 = res1.json()
    assert data1["email"] == "new@test.com"
    raw_token_1 = data1["raw_token"]
    
    # Verify DB
    invites1 = (await db_session.execute(select(Invitation).where(Invitation.email == "new@test.com"))).scalars().all()
    assert len(invites1) == 1
    assert invites1[0].token_hash == hashlib.sha256(raw_token_1.encode('utf-8')).hexdigest()
    assert invites1[0].token_hash != raw_token_1
    
    # 2. Resend invite (Architecture Test 15)
    res2 = await async_client.post(
        f"/invitations/{data1['id']}/resend",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res2.status_code == 200
    data2 = res2.json()
    raw_token_2 = data2["raw_token"]
    assert raw_token_2 != raw_token_1
    
    db_session.expunge_all()
    # Verify DB (assert exactly one pending row)
    invites2 = (await db_session.execute(
        select(Invitation).where(Invitation.agency_id == env["agency"].id, Invitation.email == "new@test.com", Invitation.status == "pending")
    )).scalars().all()
    assert len(invites2) == 1
    assert invites2[0].token_hash == hashlib.sha256(raw_token_2.encode('utf-8')).hexdigest()
    
    # Old raw token is rejected
    res_accept_old = await async_client.post(
        "/invitations/accept",
        json={"token": raw_token_1, "full_name": "Old", "password": "Password123!"}
    )
    assert res_accept_old.status_code == 400

@pytest.mark.asyncio
async def test_invitation_acceptance_idempotency(async_client: AsyncClient, db_session, password, hashed_password):
    env = await setup_env(db_session, hashed_password)
    admin_token = await login(async_client, "admin@test.com", password, str(env["agency"].id))
    
    res1 = await async_client.post(
        "/invitations",
        json={"email": "idempotent@test.com", "role": "client_user", "client_id": str(env["client"].id)},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    raw_token = res1.json()["raw_token"]
    
    # Accept invite
    payload = {"token": raw_token, "full_name": "Idemp User", "password": "Password123!"}
    res2 = await async_client.post("/invitations/accept", json=payload)
    assert res2.status_code == 200
    
    # Verify DB state
    users = (await db_session.execute(select(User).where(User.email == "idempotent@test.com"))).scalars().all()
    assert len(users) == 1
    user_id = users[0].id
    
    mems = (await db_session.execute(select(AgencyMembership).where(AgencyMembership.user_id == user_id))).scalars().all()
    assert len(mems) == 1
    
    cmems = (await db_session.execute(select(ClientMembership).where(ClientMembership.user_id == user_id))).scalars().all()
    assert len(cmems) == 1
    
    inv = (await db_session.execute(select(Invitation).where(Invitation.email == "idempotent@test.com"))).scalar_one()
    assert inv.status == "accepted"
    assert inv.accepted_at is not None
    
    # Architecture Test 16: Re-accept same token
    res3 = await async_client.post("/invitations/accept", json=payload)
    assert res3.status_code == 200
    
    # Verify no duplicate memberships were created
    db_session.expunge_all()
    users_after = (await db_session.execute(select(User).where(User.email == "idempotent@test.com"))).scalars().all()
    assert len(users_after) == 1
    
    mems_after = (await db_session.execute(select(AgencyMembership).where(
        AgencyMembership.user_id == user_id, 
        AgencyMembership.agency_id == env["agency"].id
    ))).scalars().all()
    assert len(mems_after) == 1
    
    cmems_after = (await db_session.execute(select(ClientMembership).where(
        ClientMembership.user_id == user_id,
        ClientMembership.client_id == env["client"].id
    ))).scalars().all()
    assert len(cmems_after) == 1
    
    inv_after = (await db_session.execute(select(Invitation).where(Invitation.email == "idempotent@test.com"))).scalar_one()
    assert inv_after.status == "accepted"
    assert inv_after.accepted_at is not None

async def run_concurrent_accepts(payload: InvitationAccept, test_db_maker):
    async with test_db_maker() as db1, test_db_maker() as db2:
        return await asyncio.wait_for(
            asyncio.gather(
                accept_invitation(payload, db1),
                accept_invitation(payload, db2)
            ),
            timeout=10.0
        )

@pytest.mark.asyncio
async def test_invitation_concurrency(async_client: AsyncClient, db_session, password, hashed_password):
    env = await setup_env(db_session, hashed_password)
    admin_token = await login(async_client, "admin@test.com", password, str(env["agency"].id))
    
    res1 = await async_client.post(
        "/invitations",
        json={"email": "concurrent@test.com", "role": "agency_member"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    raw_token = res1.json()["raw_token"]
    
    payload = InvitationAccept(token=raw_token, full_name="Concurrent User", password="Password123!")
    
    # Architecture Test 17: Real concurrency
    results = await run_concurrent_accepts(payload, async_session_maker)
    
    # Both should have completed successfully
    for r in results:
        assert r == {"status": "accepted"}
        
    # Assert DB correctness
    async with async_session_maker() as verify_db:
        users = (await verify_db.execute(select(User).where(User.email == "concurrent@test.com"))).scalars().all()
        assert len(users) == 1
        user_id = users[0].id
        
        mems = (await verify_db.execute(select(AgencyMembership).where(
            AgencyMembership.user_id == user_id,
            AgencyMembership.agency_id == env["agency"].id
        ))).scalars().all()
        assert len(mems) == 1
        
        cmems = (await verify_db.execute(select(ClientMembership).where(ClientMembership.user_id == user_id))).scalars().all()
        assert len(cmems) == 0 # role is agency_member
        
        invs = (await verify_db.execute(select(Invitation).where(
            Invitation.email == "concurrent@test.com",
            Invitation.agency_id == env["agency"].id
        ))).scalars().all()
        assert len(invs) == 1
        inv = invs[0]
        assert inv.status == "accepted"
        assert inv.accepted_at is not None

@pytest.mark.asyncio
async def test_invitation_validation(async_client: AsyncClient, db_session, password, hashed_password):
    env = await setup_env(db_session, hashed_password)
    admin_token = await login(async_client, "admin@test.com", password, str(env["agency"].id))
    
    # client_user missing client_id -> 422
    res = await async_client.post(
        "/invitations",
        json={"email": "val1@test.com", "role": "client_user"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 422
    
    # client_id on non-client -> 422
    res = await async_client.post(
        "/invitations",
        json={"email": "val2@test.com", "role": "agency_member", "client_id": str(env["client"].id)},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 422
    
    # cross-tenant client_id -> 404
    res = await async_client.post(
        "/invitations",
        json={"email": "val3@test.com", "role": "client_user", "client_id": str(uuid4())},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 404
    
    # member trying to invite -> 403
    member_token = await login(async_client, "member@test.com", password, str(env["agency"].id))
    res = await async_client.post(
        "/invitations",
        json={"email": "val4@test.com", "role": "agency_member"},
        headers={"Authorization": f"Bearer {member_token}"}
    )
    assert res.status_code == 403

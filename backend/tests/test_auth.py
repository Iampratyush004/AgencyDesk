import pytest
import jwt
from uuid import uuid4
from httpx import AsyncClient
from app.models.user import User
from app.models.agency import Agency, AgencyMembership
from app.models.client import Client, ClientMembership
from app.models.enums import RoleEnum
from app.core.security import get_password_hash
from app.config import settings

@pytest.fixture
def password():
    return "ValidPassword123!"

@pytest.fixture
def hashed_password(password):
    return get_password_hash(password)

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

async def create_agency_membership(db_session, user_id, agency_id, role=RoleEnum.agency_member.value, is_active=True):
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

@pytest.mark.asyncio
async def test_valid_single_agency_login(async_client: AsyncClient, db_session, password, hashed_password):
    user = await create_user(db_session, "test@test.com", hashed_password)
    agency = await create_agency(db_session, "A1", "a1")
    await create_agency_membership(db_session, user.id, agency.id)

    res = await async_client.post("/auth/login", json={"email": "test@test.com", "password": password})
    assert res.status_code == 200
    assert "access_token" in res.json()
    assert res.json()["status"] == "authenticated"

@pytest.mark.asyncio
async def test_invalid_email_password(async_client: AsyncClient, db_session, password, hashed_password):
    await create_user(db_session, "test@test.com", hashed_password)
    res = await async_client.post("/auth/login", json={"email": "wrong@test.com", "password": password})
    assert res.status_code == 401
    res2 = await async_client.post("/auth/login", json={"email": "test@test.com", "password": "wrong"})
    assert res2.status_code == 401

@pytest.mark.asyncio
async def test_inactive_user_denied(async_client: AsyncClient, db_session, password, hashed_password):
    user = await create_user(db_session, "test@test.com", hashed_password, is_active=False)
    agency = await create_agency(db_session, "A1", "a1")
    await create_agency_membership(db_session, user.id, agency.id)
    res = await async_client.post("/auth/login", json={"email": "test@test.com", "password": password})
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_zero_active_memberships_denied(async_client: AsyncClient, db_session, password, hashed_password):
    await create_user(db_session, "test@test.com", hashed_password)
    res = await async_client.post("/auth/login", json={"email": "test@test.com", "password": password})
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_multi_agency_login_returns_selection(async_client: AsyncClient, db_session, password, hashed_password):
    user = await create_user(db_session, "test@test.com", hashed_password)
    a1 = await create_agency(db_session, "A1", "a1")
    a2 = await create_agency(db_session, "A2", "a2")
    await create_agency_membership(db_session, user.id, a1.id)
    await create_agency_membership(db_session, user.id, a2.id)

    res = await async_client.post("/auth/login", json={"email": "test@test.com", "password": password})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "agency_selection_required"
    assert len(data["agencies"]) == 2
    ids = [a["id"] for a in data["agencies"]]
    assert str(a1.id) in ids and str(a2.id) in ids

@pytest.mark.asyncio
async def test_multi_agency_response_contains_only_users_agencies(async_client: AsyncClient, db_session, password, hashed_password):
    user = await create_user(db_session, "test@test.com", hashed_password)
    a1 = await create_agency(db_session, "A1", "a1")
    a2 = await create_agency(db_session, "A2", "a2")
    a3 = await create_agency(db_session, "A3", "a3") # Not a member
    await create_agency_membership(db_session, user.id, a1.id)
    await create_agency_membership(db_session, user.id, a2.id)

    res = await async_client.post("/auth/login", json={"email": "test@test.com", "password": password})
    assert res.status_code == 200
    ids = [a["id"] for a in res.json()["agencies"]]
    assert str(a3.id) not in ids

@pytest.mark.asyncio
async def test_valid_explicit_agency_selection_issues_token(async_client: AsyncClient, db_session, password, hashed_password):
    user = await create_user(db_session, "test@test.com", hashed_password)
    a1 = await create_agency(db_session, "A1", "a1")
    a2 = await create_agency(db_session, "A2", "a2")
    await create_agency_membership(db_session, user.id, a1.id)
    await create_agency_membership(db_session, user.id, a2.id)

    res = await async_client.post("/auth/login", json={"email": "test@test.com", "password": password, "agency_id": str(a2.id)})
    assert res.status_code == 200
    assert "access_token" in res.json()

@pytest.mark.asyncio
async def test_foreign_agency_selection_denied(async_client: AsyncClient, db_session, password, hashed_password):
    user = await create_user(db_session, "test@test.com", hashed_password)
    a1 = await create_agency(db_session, "A1", "a1")
    a2 = await create_agency(db_session, "A2", "a2")
    await create_agency_membership(db_session, user.id, a1.id)
    # user not member of a2

    res = await async_client.post("/auth/login", json={"email": "test@test.com", "password": password, "agency_id": str(a2.id)})
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_inactive_agency_membership_denied(async_client: AsyncClient, db_session, password, hashed_password):
    user = await create_user(db_session, "test@test.com", hashed_password)
    a1 = await create_agency(db_session, "A1", "a1")
    await create_agency_membership(db_session, user.id, a1.id, is_active=False)

    res = await async_client.post("/auth/login", json={"email": "test@test.com", "password": password})
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_client_user_with_membership_succeeds(async_client: AsyncClient, db_session, password, hashed_password):
    user = await create_user(db_session, "test@test.com", hashed_password)
    agency = await create_agency(db_session, "A1", "a1")
    await create_agency_membership(db_session, user.id, agency.id, role=RoleEnum.client_user.value)
    client = await create_client(db_session, agency.id, "Client 1")
    await create_client_membership(db_session, user.id, agency.id, client.id)

    res = await async_client.post("/auth/login", json={"email": "test@test.com", "password": password})
    assert res.status_code == 200
    assert "access_token" in res.json()

@pytest.mark.asyncio
async def test_client_user_without_membership_denied(async_client: AsyncClient, db_session, password, hashed_password):
    user = await create_user(db_session, "test@test.com", hashed_password)
    agency = await create_agency(db_session, "A1", "a1")
    await create_agency_membership(db_session, user.id, agency.id, role=RoleEnum.client_user.value)
    # missing client membership

    res = await async_client.post("/auth/login", json={"email": "test@test.com", "password": password})
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_exactly_72_byte_password_behavior(async_client: AsyncClient, db_session):
    pwd = "a" * 72
    hashed = get_password_hash(pwd)
    user = await create_user(db_session, "72@test.com", hashed)
    agency = await create_agency(db_session, "A1", "a1")
    await create_agency_membership(db_session, user.id, agency.id)

    res = await async_client.post("/auth/login", json={"email": "72@test.com", "password": pwd})
    assert res.status_code == 200
    assert "access_token" in res.json()

@pytest.mark.asyncio
async def test_greater_than_72_byte_password_rejection(async_client: AsyncClient, db_session):
    pwd = "a" * 73
    # Schema validation should block it during login
    res = await async_client.post("/auth/login", json={"email": "73@test.com", "password": pwd})
    assert res.status_code == 422
    assert "Password cannot exceed 72 bytes" in str(res.json())

@pytest.mark.asyncio
async def test_multibyte_utf8_password_byte_limit_behavior(async_client: AsyncClient, db_session):
    # 'é' is 2 bytes in UTF-8. 37 * 2 = 74 bytes, length in chars is 37
    pwd = "é" * 37 
    res = await async_client.post("/auth/login", json={"email": "utf8@test.com", "password": pwd})
    assert res.status_code == 422
    assert "Password cannot exceed 72 bytes" in str(res.json())

    # 'é' * 36 = 72 bytes, length in chars is 36
    pwd_valid = "é" * 36
    hashed = get_password_hash(pwd_valid)
    user = await create_user(db_session, "utf8_valid@test.com", hashed)
    agency = await create_agency(db_session, "A1", "a1")
    await create_agency_membership(db_session, user.id, agency.id)

    res2 = await async_client.post("/auth/login", json={"email": "utf8_valid@test.com", "password": pwd_valid})
    assert res2.status_code == 200

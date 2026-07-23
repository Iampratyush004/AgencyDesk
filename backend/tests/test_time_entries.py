import pytest
from httpx import AsyncClient
from uuid import uuid4
from sqlalchemy import text, select
from datetime import date
import asyncio

from app.models.user import User
from app.models.agency import Agency, AgencyMembership
from app.models.client import Client, ClientMembership
from app.models.project import Project, ProjectMembership
from app.models.task import Task
from app.models.time_entry import TimeEntry
from app.models.enums import RoleEnum, VisibilityEnum
from app.core.security import get_password_hash

# --- HELPERS ---
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

async def create_project(db_session, agency_id, client_id, name):
    project = Project(agency_id=agency_id, client_id=client_id, name=name)
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project

async def create_project_membership(db_session, user_id, project_id, agency_id):
    mem = ProjectMembership(user_id=user_id, project_id=project_id, agency_id=agency_id)
    db_session.add(mem)
    await db_session.commit()
    await db_session.refresh(mem)
    return mem

async def create_task(db_session, agency_id, project_id, title, visibility=VisibilityEnum.internal.value, assignee_id=None):
    task = Task(agency_id=agency_id, project_id=project_id, title=title, visibility=visibility, assignee_id=assignee_id)
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task

async def create_time_entry(db_session, agency_id, task_id, project_id, user_id, duration_minutes, entry_date):
    entry = TimeEntry(agency_id=agency_id, task_id=task_id, project_id=project_id, user_id=user_id, duration_minutes=duration_minutes, date=entry_date)
    db_session.add(entry)
    await db_session.commit()
    await db_session.refresh(entry)
    return entry

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

async def setup_env(db_session, hashed_password):
    admin = await create_user(db_session, "admin@test.com", hashed_password)
    member = await create_user(db_session, "member@test.com", hashed_password)
    unassigned = await create_user(db_session, "unassigned@test.com", hashed_password)
    client_user = await create_user(db_session, "client@test.com", hashed_password)
    cross_tenant = await create_user(db_session, "crosstenant@test.com", hashed_password)
    
    agency = await create_agency(db_session, "Agency A", "a")
    agency_b = await create_agency(db_session, "Agency B", "b")
    
    await create_agency_membership(db_session, admin.id, agency.id, RoleEnum.agency_admin.value)
    await create_agency_membership(db_session, member.id, agency.id, RoleEnum.agency_member.value)
    await create_agency_membership(db_session, unassigned.id, agency.id, RoleEnum.agency_member.value)
    await create_agency_membership(db_session, client_user.id, agency.id, RoleEnum.client_user.value)
    
    await create_agency_membership(db_session, cross_tenant.id, agency_b.id, RoleEnum.agency_admin.value)
    
    client = await create_client(db_session, agency.id, "Client 1")
    client_b = await create_client(db_session, agency_b.id, "Client B")
    
    await create_client_membership(db_session, client_user.id, agency.id, client.id)
    
    project = await create_project(db_session, agency.id, client.id, "Project 1")
    other_project = await create_project(db_session, agency.id, client.id, "Project 2") # unassigned for member
    project_b = await create_project(db_session, agency_b.id, client_b.id, "Project B")
    
    # Assign member to project 1
    await create_project_membership(db_session, member.id, project.id, agency.id)
    
    return {
        "admin": admin, "member": member, "unassigned": unassigned, "client_user": client_user, "cross_tenant": cross_tenant,
        "agency": agency, "agency_b": agency_b,
        "client": client, "client_b": client_b,
        "project": project, "other_project": other_project, "project_b": project_b
    }

@pytest.mark.asyncio
async def test_time_entries_listing(async_client: AsyncClient, db_session, password, hashed_password):
    env = await setup_env(db_session, hashed_password)
    
    t_assigned = await create_task(db_session, env["agency"].id, env["project"].id, "Assigned Task")
    t_unassigned = await create_task(db_session, env["agency"].id, env["other_project"].id, "Unassigned Task")
    t_cross = await create_task(db_session, env["agency_b"].id, env["project_b"].id, "Cross Task")
    
    # Admin creates some entries
    e1 = await create_time_entry(db_session, env["agency"].id, t_assigned.id, env["project"].id, env["admin"].id, 30, date(2023, 1, 1))
    e2 = await create_time_entry(db_session, env["agency"].id, t_assigned.id, env["project"].id, env["admin"].id, 60, date(2023, 1, 1))
    # Force created_at to tie exactly
    await db_session.execute(text(f"UPDATE time_entries SET created_at = '2023-01-01 12:00:00+00' WHERE id IN ('{e1.id}', '{e2.id}')"))
    await db_session.commit()
    
    e3 = await create_time_entry(db_session, env["agency"].id, t_assigned.id, env["project"].id, env["admin"].id, 90, date(2023, 1, 2))
    
    admin_token = await login(async_client, "admin@test.com", password, str(env["agency"].id))
    member_token = await login(async_client, "member@test.com", password, str(env["agency"].id))
    client_token = await login(async_client, "client@test.com", password, str(env["agency"].id))
    cross_token = await login(async_client, "crosstenant@test.com", password, str(env["agency_b"].id))
    
    # Admin lists time entries on task
    res = await async_client.get(f"/tasks/{t_assigned.id}/time-entries", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    entries = res.json()
    assert len(entries) == 3
    # Check ordering (date desc, created_at desc, id desc)
    assert entries[0]["id"] == str(e3.id) # Date is 2023-01-02
    
    # For e1 and e2, date and created_at are identical, so ordering falls back to id DESC.
    # UUIDv4 are random, so we compute the expected order lexicographically
    expected_tied_ids = sorted([str(e1.id), str(e2.id)], reverse=True)
    assert entries[1]["id"] == expected_tied_ids[0]
    assert entries[2]["id"] == expected_tied_ids[1]
    
    # Agency member lists time entries on assigned task
    res = await async_client.get(f"/tasks/{t_assigned.id}/time-entries", headers={"Authorization": f"Bearer {member_token}"})
    assert res.status_code == 200
    
    # Agency member attempting to access unassigned task -> 404
    res = await async_client.get(f"/tasks/{t_unassigned.id}/time-entries", headers={"Authorization": f"Bearer {member_token}"})
    assert res.status_code == 404
    
    # Cross-tenant task access -> 404
    res = await async_client.get(f"/tasks/{t_cross.id}/time-entries", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 404
    
    # client_user attempts GET -> 403
    res = await async_client.get(f"/tasks/{t_assigned.id}/time-entries", headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 403

@pytest.mark.asyncio
async def test_time_entries_creation(async_client: AsyncClient, db_session, password, hashed_password):
    env = await setup_env(db_session, hashed_password)
    
    t_assigned = await create_task(db_session, env["agency"].id, env["project"].id, "Assigned Task")
    
    admin_token = await login(async_client, "admin@test.com", password, str(env["agency"].id))
    member_token = await login(async_client, "member@test.com", password, str(env["agency"].id))
    client_token = await login(async_client, "client@test.com", password, str(env["agency"].id))
    
    payload = {"duration_minutes": 120, "date": "2023-01-03", "note": "Worked hard"}
    
    # Admin creates time entry
    res = await async_client.post(f"/tasks/{t_assigned.id}/time-entries", json=payload, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 201
    assert res.json()["user_id"] == str(env["admin"].id)
    assert res.json()["project_id"] == str(env["project"].id)
    
    # Agency member creates time entry
    res = await async_client.post(f"/tasks/{t_assigned.id}/time-entries", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert res.status_code == 201
    assert res.json()["user_id"] == str(env["member"].id)
    assert res.json()["project_id"] == str(env["project"].id)
    
    # Test 11: client_user attempts POST -> 403
    res = await async_client.post(f"/tasks/{t_assigned.id}/time-entries", json=payload, headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 403
    
    # Payload validation: negative/zero duration -> 422
    res = await async_client.post(f"/tasks/{t_assigned.id}/time-entries", json={"duration_minutes": 0, "date": "2023-01-03"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 422
    
    res = await async_client.post(f"/tasks/{t_assigned.id}/time-entries", json={"duration_minutes": -5, "date": "2023-01-03"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 422
    
    # Payload forbid extra fields
    res = await async_client.post(f"/tasks/{t_assigned.id}/time-entries", json={"duration_minutes": 10, "date": "2023-01-03", "user_id": str(env["client_user"].id)}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 422
    
    res = await async_client.post(f"/tasks/{t_assigned.id}/time-entries", json={"duration_minutes": 10, "date": "2023-01-03", "project_id": str(env["other_project"].id)}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 422

@pytest.mark.asyncio
async def test_historical_preservation_structural(db_session, hashed_password):
    # Structural DB constraint test for Architecture Test 20 foundation.
    # Verifying that deleting a ProjectMembership does NOT cascade-delete a TimeEntry.
    env = await setup_env(db_session, hashed_password)
    
    t_assigned = await create_task(db_session, env["agency"].id, env["project"].id, "Task")
    
    # Create time entry for member
    entry = await create_time_entry(db_session, env["agency"].id, t_assigned.id, env["project"].id, env["member"].id, 30, date(2023, 1, 1))
    
    # Locate project membership
    mem = (await db_session.execute(
        select(ProjectMembership).where(
            ProjectMembership.user_id == env["member"].id,
            ProjectMembership.project_id == env["project"].id
        )
    )).scalar_one()
    
    # Delete membership
    await db_session.delete(mem)
    await db_session.commit()
    
    # Assert time entry still exists and belongs to member
    surviving_entry = (await db_session.execute(
        select(TimeEntry).where(TimeEntry.id == entry.id)
    )).scalar_one_or_none()
    
    assert surviving_entry is not None
    assert surviving_entry.user_id == env["member"].id

import pytest
from httpx import AsyncClient
from uuid import uuid4
import os
from pathlib import Path
from sqlalchemy import select

from app.config import settings
from app.models.user import User
from app.models.agency import Agency, AgencyMembership
from app.models.client import Client, ClientMembership
from app.models.project import Project, ProjectMembership
from app.models.task import Task
from app.models.file import File, FileApproval
from app.models.enums import RoleEnum, VisibilityEnum, FileApprovalStatusEnum
from app.core.security import get_password_hash

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

async def create_file_record(db_session, agency_id, task_id, uploaded_by_id, visibility=VisibilityEnum.internal.value, storage_path=None):
    storage_path = storage_path or str(uuid4())
    f = File(
        task_id=task_id,
        agency_id=agency_id,
        uploaded_by_id=uploaded_by_id,
        filename="test.txt",
        storage_path=storage_path,
        mime_type="text/plain",
        file_size_bytes=100,
        visibility=visibility
    )
    db_session.add(f)
    await db_session.commit()
    await db_session.refresh(f)
    
    # Create fake physical file for download tests
    p = Path(settings.FILE_STORAGE_ROOT) / storage_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"test data")
    
    return f

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
    other_client = await create_user(db_session, "otherclient@test.com", hashed_password)
    
    agency = await create_agency(db_session, "Agency A", "a")
    agency_b = await create_agency(db_session, "Agency B", "b")
    
    await create_agency_membership(db_session, admin.id, agency.id, RoleEnum.agency_admin.value)
    await create_agency_membership(db_session, member.id, agency.id, RoleEnum.agency_member.value)
    await create_agency_membership(db_session, unassigned.id, agency.id, RoleEnum.agency_member.value)
    await create_agency_membership(db_session, client_user.id, agency.id, RoleEnum.client_user.value)
    await create_agency_membership(db_session, other_client.id, agency.id, RoleEnum.client_user.value)
    await create_agency_membership(db_session, cross_tenant.id, agency_b.id, RoleEnum.agency_admin.value)
    
    client = await create_client(db_session, agency.id, "Client 1")
    client_b = await create_client(db_session, agency_b.id, "Client B")
    client_other = await create_client(db_session, agency.id, "Client 2")
    
    await create_client_membership(db_session, client_user.id, agency.id, client.id)
    await create_client_membership(db_session, other_client.id, agency.id, client_other.id)
    
    project = await create_project(db_session, agency.id, client.id, "Project 1")
    other_project = await create_project(db_session, agency.id, client_other.id, "Project 2")
    project_b = await create_project(db_session, agency_b.id, client_b.id, "Project B")
    
    await create_project_membership(db_session, member.id, project.id, agency.id)
    
    t_internal = await create_task(db_session, agency.id, project.id, "Internal Task", VisibilityEnum.internal.value)
    t_client = await create_task(db_session, agency.id, project.id, "Client Task", VisibilityEnum.client.value)
    t_other = await create_task(db_session, agency.id, other_project.id, "Other Client Task", VisibilityEnum.client.value)
    t_cross = await create_task(db_session, agency_b.id, project_b.id, "Cross Task", VisibilityEnum.client.value)
    
    return {
        "admin": admin, "member": member, "unassigned": unassigned, "client_user": client_user, "cross_tenant": cross_tenant, "other_client": other_client,
        "agency": agency, "agency_b": agency_b,
        "client": client, "client_other": client_other,
        "project": project, "other_project": other_project,
        "t_internal": t_internal, "t_client": t_client, "t_other": t_other, "t_cross": t_cross
    }

@pytest.mark.asyncio
async def test_file_listing(async_client: AsyncClient, db_session, password, hashed_password):
    env = await setup_env(db_session, hashed_password)
    
    f1 = await create_file_record(db_session, env["agency"].id, env["t_client"].id, env["admin"].id, VisibilityEnum.client.value)
    f2 = await create_file_record(db_session, env["agency"].id, env["t_client"].id, env["admin"].id, VisibilityEnum.internal.value)
    
    admin_token = await login(async_client, "admin@test.com", password, str(env["agency"].id))
    member_token = await login(async_client, "member@test.com", password, str(env["agency"].id))
    unassigned_token = await login(async_client, "unassigned@test.com", password, str(env["agency"].id))
    client_token = await login(async_client, "client@test.com", password, str(env["agency"].id))
    
    # admin/member lists files
    res = await async_client.get(f"/tasks/{env['t_client'].id}/files", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert len(res.json()) == 2
    
    res = await async_client.get(f"/tasks/{env['t_client'].id}/files", headers={"Authorization": f"Bearer {member_token}"})
    assert res.status_code == 200
    assert len(res.json()) == 2
    
    # unassigned member -> 404
    res = await async_client.get(f"/tasks/{env['t_client'].id}/files", headers={"Authorization": f"Bearer {unassigned_token}"})
    assert res.status_code == 404
    
    # cross-tenant -> 404
    cross_token = await login(async_client, "crosstenant@test.com", password, str(env["agency_b"].id))
    res = await async_client.get(f"/tasks/{env['t_client'].id}/files", headers={"Authorization": f"Bearer {cross_token}"})
    assert res.status_code == 404
    
    # client internal-task access -> 404
    res = await async_client.get(f"/tasks/{env['t_internal'].id}/files", headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 404
    
    # Architecture Test 8: client list excludes internal files
    res = await async_client.get(f"/tasks/{env['t_client'].id}/files", headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["id"] == str(f1.id)
    assert "agency_id" not in res.json()[0]
    assert "storage_path" not in res.json()[0]

@pytest.mark.asyncio
async def test_file_upload(async_client: AsyncClient, db_session, password, hashed_password, tmp_path):
    env = await setup_env(db_session, hashed_password)
    admin_token = await login(async_client, "admin@test.com", password, str(env["agency"].id))
    client_token = await login(async_client, "client@test.com", password, str(env["agency"].id))
    
    file_content = b"my uploaded data"
    files = {"file": ("../../../etc/passwd", file_content, "text/plain")}
    
    # admin upload -> 201
    res = await async_client.post(
        f"/tasks/{env['t_internal'].id}/files", 
        files=files, 
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 201
    data = res.json()
    assert data["visibility"] == "internal" # default
    assert data["file_size_bytes"] == len(file_content)
    assert data["filename"] == "../../../etc/passwd"
    
    # storage path is UUID-based and independent of filename, traversal blocked
    f_record = (await db_session.execute(select(File).where(File.id == data["id"]))).scalar_one()
    # verify UUID
    from uuid import UUID
    UUID(hex=f_record.storage_path) # raises if not valid UUID
    
    # physical file exists
    physical_path = Path(settings.FILE_STORAGE_ROOT) / f_record.storage_path
    assert physical_path.exists()
    assert physical_path.read_bytes() == file_content
    
    # invalid visibility -> 422
    res = await async_client.post(
        f"/tasks/{env['t_internal'].id}/files",
        files={"file": ("invalid.txt", b"x")},
        data={"visibility": "public"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 422
    # Verify no file created
    assert len(list(Path(settings.FILE_STORAGE_ROOT).glob("*"))) == 1 # only the first one
    
    # omitted visibility -> internal
    res = await async_client.post(
        f"/tasks/{env['t_internal'].id}/files",
        files={"file": ("omitted.txt", b"x")},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 201
    assert res.json()["visibility"] == "internal"
    
    # explicit client -> succeeds on client-visible task
    res = await async_client.post(
        f"/tasks/{env['t_client'].id}/files",
        files={"file": ("client.txt", b"x")},
        data={"visibility": "client"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 201
    assert res.json()["visibility"] == "client"
    
    # client upload -> 403
    res = await async_client.post(f"/tasks/{env['t_client'].id}/files", files={"file": ("x", b"x")}, headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 403
    
    # client-visible upload on internal task -> 400
    res = await async_client.post(
        f"/tasks/{env['t_internal'].id}/files",
        files={"file": ("a", b"a")},
        data={"visibility": "client"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 400
    assert "internal task" in res.json()["detail"].lower()

@pytest.mark.asyncio
async def test_file_upload_cleanup(async_client: AsyncClient, db_session, password, hashed_password, tmp_path):
    # simulate DB failure to verify cleanup
    env = await setup_env(db_session, hashed_password)
    admin_token = await login(async_client, "admin@test.com", password, str(env["agency"].id))
    
    # Insert a bad task_id into route somehow? Actually we can't easily fail the DB since task exists.
    # We can mock the DB commit to raise an exception.
    # To test this via API, we'd need to mock session.commit. We will just trust the code or monkeypatch it.
    from unittest import mock
    with mock.patch("sqlalchemy.ext.asyncio.AsyncSession.commit", side_effect=Exception("DB Error")):
        try:
            await async_client.post(
                f"/tasks/{env['t_internal'].id}/files", 
                files={"file": ("a.txt", b"test")}, 
                headers={"Authorization": f"Bearer {admin_token}"}
            )
        except Exception:
            pass
        
    # verify directory is empty (file was cleaned up)
    storage = Path(settings.FILE_STORAGE_ROOT)
    if storage.exists():
        assert len(list(storage.iterdir())) == 0

@pytest.mark.asyncio
async def test_file_download(async_client: AsyncClient, db_session, password, hashed_password):
    env = await setup_env(db_session, hashed_password)
    f_client = await create_file_record(db_session, env["agency"].id, env["t_client"].id, env["admin"].id, VisibilityEnum.client.value)
    f_internal = await create_file_record(db_session, env["agency"].id, env["t_client"].id, env["admin"].id, VisibilityEnum.internal.value)
    f_other = await create_file_record(db_session, env["agency"].id, env["t_other"].id, env["admin"].id, VisibilityEnum.client.value)
    
    admin_token = await login(async_client, "admin@test.com", password, str(env["agency"].id))
    client_token = await login(async_client, "client@test.com", password, str(env["agency"].id))
    unassigned_token = await login(async_client, "unassigned@test.com", password, str(env["agency"].id))
    
    # admin download -> 200
    res = await async_client.get(f"/files/{f_client.id}/download", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert res.content == b"test data"
    
    # unassigned member -> 404
    res = await async_client.get(f"/files/{f_client.id}/download", headers={"Authorization": f"Bearer {unassigned_token}"})
    assert res.status_code == 404
    
    # client own client-visible -> 200
    res = await async_client.get(f"/files/{f_client.id}/download", headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 200
    
    # client internal-file download -> 404 (Test 14 foundation)
    res = await async_client.get(f"/files/{f_internal.id}/download", headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 404
    
    # client other-client download -> 404
    res = await async_client.get(f"/files/{f_other.id}/download", headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 404

@pytest.mark.asyncio
async def test_file_approvals(async_client: AsyncClient, db_session, password, hashed_password):
    env = await setup_env(db_session, hashed_password)
    f_client = await create_file_record(db_session, env["agency"].id, env["t_client"].id, env["admin"].id, VisibilityEnum.client.value)
    f_internal = await create_file_record(db_session, env["agency"].id, env["t_client"].id, env["admin"].id, VisibilityEnum.internal.value)
    f_other = await create_file_record(db_session, env["agency"].id, env["t_other"].id, env["admin"].id, VisibilityEnum.client.value)
    
    admin_token = await login(async_client, "admin@test.com", password, str(env["agency"].id))
    client_token = await login(async_client, "client@test.com", password, str(env["agency"].id))
    
    # agency staff approval -> 403
    res = await async_client.post(f"/files/{f_client.id}/approvals", json={"status": "approved"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 403
    
    # Architecture Test 14: internal-file approval -> 404
    res = await async_client.post(f"/files/{f_internal.id}/approvals", json={"status": "approved"}, headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 404
    
    # Architecture Test 13: other-client approval -> 404
    res = await async_client.post(f"/files/{f_other.id}/approvals", json={"status": "approved"}, headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 404
    
    # Client approves own client-visible file
    res = await async_client.post(f"/files/{f_client.id}/approvals", json={"status": "approved"}, headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 200
    app1 = res.json()
    assert app1["status"] == "approved"
    assert "agency_id" not in app1
    
    # Client updates approval (needs_changes) - UPSERT
    res = await async_client.post(f"/files/{f_client.id}/approvals", json={"status": "needs_changes", "note": "fix this"}, headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 200
    app2 = res.json()
    assert app2["id"] == app1["id"] # Same row
    assert app2["status"] == "needs_changes"
    assert app2["note"] == "fix this"
    
    # Invalid status -> 422
    res = await async_client.post(f"/files/{f_client.id}/approvals", json={"status": "whatever"}, headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 422
    
    # Forbidden fields -> 422
    res = await async_client.post(f"/files/{f_client.id}/approvals", json={"status": "approved", "agency_id": str(uuid4())}, headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 422

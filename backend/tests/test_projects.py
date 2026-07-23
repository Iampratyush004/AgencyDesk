import pytest
from httpx import AsyncClient
from uuid import uuid4

from app.models.user import User
from app.models.agency import Agency, AgencyMembership
from app.models.client import Client, ClientMembership
from app.models.project import Project, ProjectMembership
from app.models.enums import RoleEnum
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
async def test_admin_access_same_agency(async_client: AsyncClient, db_session, password, hashed_password):
    user = await create_user(db_session, "admin@test.com", hashed_password)
    agency = await create_agency(db_session, "Agency A", "agency-a")
    await create_agency_membership(db_session, user.id, agency.id, RoleEnum.agency_admin.value)
    client_obj = await create_client(db_session, agency.id, "Client A")
    project = await create_project(db_session, agency.id, client_obj.id, "Project A")
    
    token = await login(async_client, "admin@test.com", password, str(agency.id))
    
    # 1. Agency A admin can access Agency A project.
    res = await async_client.get(f"/projects/{project.id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["name"] == "Project A"
    # 26. ProjectResponse never exposes agency_id.
    assert "agency_id" not in res.json()

@pytest.mark.asyncio
async def test_admin_access_cross_agency(async_client: AsyncClient, db_session, password, hashed_password):
    user = await create_user(db_session, "admin@test.com", hashed_password)
    agency_a = await create_agency(db_session, "Agency A", "agency-a")
    agency_b = await create_agency(db_session, "Agency B", "agency-b")
    await create_agency_membership(db_session, user.id, agency_a.id, RoleEnum.agency_admin.value)
    
    client_b = await create_client(db_session, agency_b.id, "Client B")
    project_b = await create_project(db_session, agency_b.id, client_b.id, "Project B")
    
    token = await login(async_client, "admin@test.com", password, str(agency_a.id))
    
    # 2. Agency A admin gets 404 for Agency B project.
    res = await async_client.get(f"/projects/{project_b.id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 404
    
    # 3. Cross-tenant guessed ID and nonexistent ID have identical 404 behavior.
    res_fake = await async_client.get(f"/projects/{uuid4()}", headers={"Authorization": f"Bearer {token}"})
    assert res_fake.status_code == 404
    assert res.json() == res_fake.json()

@pytest.mark.asyncio
async def test_agency_member_access(async_client: AsyncClient, db_session, password, hashed_password):
    user = await create_user(db_session, "member@test.com", hashed_password)
    agency = await create_agency(db_session, "Agency A", "agency-a")
    await create_agency_membership(db_session, user.id, agency.id, RoleEnum.agency_member.value)
    
    client_obj = await create_client(db_session, agency.id, "Client A")
    assigned_project = await create_project(db_session, agency.id, client_obj.id, "Assigned")
    unassigned_project = await create_project(db_session, agency.id, client_obj.id, "Unassigned")
    
    await create_project_membership(db_session, user.id, assigned_project.id, agency.id)
    
    agency_b = await create_agency(db_session, "Agency B", "agency-b")
    client_b = await create_client(db_session, agency_b.id, "Client B")
    project_b = await create_project(db_session, agency_b.id, client_b.id, "Project B")
    
    token = await login(async_client, "member@test.com", password, str(agency.id))
    
    # 4. agency_member can access assigned project.
    res = await async_client.get(f"/projects/{assigned_project.id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    
    # 5. agency_member gets 404 for unassigned same-agency project.
    res2 = await async_client.get(f"/projects/{unassigned_project.id}", headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 404
    
    # 6. agency_member gets 404 for another-agency project.
    res3 = await async_client.get(f"/projects/{project_b.id}", headers={"Authorization": f"Bearer {token}"})
    assert res3.status_code == 404

@pytest.mark.asyncio
async def test_client_user_access(async_client: AsyncClient, db_session, password, hashed_password):
    user = await create_user(db_session, "client@test.com", hashed_password)
    agency = await create_agency(db_session, "Agency A", "agency-a")
    await create_agency_membership(db_session, user.id, agency.id, RoleEnum.client_user.value)
    
    client_a = await create_client(db_session, agency.id, "Client A")
    await create_client_membership(db_session, user.id, agency.id, client_a.id)
    
    client_other = await create_client(db_session, agency.id, "Client Other")
    
    project_mine = await create_project(db_session, agency.id, client_a.id, "Mine")
    project_other = await create_project(db_session, agency.id, client_other.id, "Other")
    
    agency_b = await create_agency(db_session, "Agency B", "agency-b")
    client_b = await create_client(db_session, agency_b.id, "Client B")
    project_b = await create_project(db_session, agency_b.id, client_b.id, "Project B")
    
    token = await login(async_client, "client@test.com", password, str(agency.id))
    
    # 7. client_user can access their Client's project.
    res = await async_client.get(f"/projects/{project_mine.id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    
    # 8. client_user gets 404 for another Client's project in same agency.
    res2 = await async_client.get(f"/projects/{project_other.id}", headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 404
    
    # 9. client_user gets 404 for another-agency project.
    res3 = await async_client.get(f"/projects/{project_b.id}", headers={"Authorization": f"Bearer {token}"})
    assert res3.status_code == 404

@pytest.mark.asyncio
async def test_list_projects(async_client: AsyncClient, db_session, password, hashed_password):
    user_admin = await create_user(db_session, "admin@test.com", hashed_password)
    user_member = await create_user(db_session, "member@test.com", hashed_password)
    user_client = await create_user(db_session, "client@test.com", hashed_password)
    
    agency = await create_agency(db_session, "Agency A", "agency-a")
    agency_b = await create_agency(db_session, "Agency B", "agency-b")
    
    await create_agency_membership(db_session, user_admin.id, agency.id, RoleEnum.agency_admin.value)
    await create_agency_membership(db_session, user_member.id, agency.id, RoleEnum.agency_member.value)
    await create_agency_membership(db_session, user_client.id, agency.id, RoleEnum.client_user.value)
    
    client_a = await create_client(db_session, agency.id, "Client A")
    client_other = await create_client(db_session, agency.id, "Client Other")
    client_b = await create_client(db_session, agency_b.id, "Client B")
    
    await create_client_membership(db_session, user_client.id, agency.id, client_a.id)
    
    # Projects
    p_mine = await create_project(db_session, agency.id, client_a.id, "Mine")
    p_unassigned = await create_project(db_session, agency.id, client_a.id, "Unassigned")
    p_other = await create_project(db_session, agency.id, client_other.id, "Other")
    p_b = await create_project(db_session, agency_b.id, client_b.id, "Proj B")
    
    await create_project_membership(db_session, user_member.id, p_mine.id, agency.id)
    
    # Tokens
    t_admin = await login(async_client, "admin@test.com", password, str(agency.id))
    t_member = await login(async_client, "member@test.com", password, str(agency.id))
    t_client = await login(async_client, "client@test.com", password, str(agency.id))
    
    # 10. Admin list contains only active-agency projects.
    res_admin = await async_client.get("/projects", headers={"Authorization": f"Bearer {t_admin}"})
    assert res_admin.status_code == 200
    ids_admin = {p["id"] for p in res_admin.json()}
    assert str(p_mine.id) in ids_admin
    assert str(p_unassigned.id) in ids_admin
    assert str(p_other.id) in ids_admin
    assert str(p_b.id) not in ids_admin  # 13. Unauthorized never appear
    
    # 11. Agency-member list contains only assigned projects.
    res_member = await async_client.get("/projects", headers={"Authorization": f"Bearer {t_member}"})
    assert res_member.status_code == 200
    ids_member = {p["id"] for p in res_member.json()}
    assert str(p_mine.id) in ids_member
    assert str(p_unassigned.id) not in ids_member
    assert str(p_other.id) not in ids_member
    
    # 12. Client-user list contains only their Client's projects.
    res_client = await async_client.get("/projects", headers={"Authorization": f"Bearer {t_client}"})
    assert res_client.status_code == 200
    ids_client = {p["id"] for p in res_client.json()}
    assert str(p_mine.id) in ids_client
    assert str(p_unassigned.id) in ids_client
    assert str(p_other.id) not in ids_client
    
    # 14. skip/limit pagination is applied after authorization filtering.
    res_pag = await async_client.get("/projects?limit=1", headers={"Authorization": f"Bearer {t_admin}"})
    assert len(res_pag.json()) == 1
    
    # 15. limit > 100 is rejected.
    res_limit = await async_client.get("/projects?limit=101", headers={"Authorization": f"Bearer {t_admin}"})
    assert res_limit.status_code == 422
    
    # 16. negative skip is rejected.
    res_skip = await async_client.get("/projects?skip=-1", headers={"Authorization": f"Bearer {t_admin}"})
    assert res_skip.status_code == 422

@pytest.mark.asyncio
async def test_create_project(async_client: AsyncClient, db_session, password, hashed_password):
    user_admin = await create_user(db_session, "admin@test.com", hashed_password)
    agency = await create_agency(db_session, "Agency A", "agency-a")
    agency_b = await create_agency(db_session, "Agency B", "agency-b")
    await create_agency_membership(db_session, user_admin.id, agency.id, RoleEnum.agency_admin.value)
    
    client_a = await create_client(db_session, agency.id, "Client A")
    client_b = await create_client(db_session, agency_b.id, "Client B")
    
    token = await login(async_client, "admin@test.com", password, str(agency.id))
    
    # 17. Admin can create a project for a Client in active agency.
    res = await async_client.post("/projects", json={
        "name": "New Proj",
        "client_id": str(client_a.id)
    }, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 201
    
    # 18. Persisted created Project.agency_id equals TenantContext agency.
    from sqlalchemy import select
    from app.models.project import Project
    persisted_project = (await db_session.execute(select(Project).where(Project.id == res.json()["id"]))).scalar_one()
    assert persisted_project.agency_id == agency.id
    
    # 19. Request supplying agency_id is rejected.
    res_malicious = await async_client.post("/projects", json={
        "name": "Malicious Proj",
        "client_id": str(client_a.id),
        "agency_id": str(agency_b.id)
    }, headers={"Authorization": f"Bearer {token}"})
    assert res_malicious.status_code == 422 # Pydantic extra='forbid'
    
    # 20. Cross-tenant client_id creation returns 404.
    res_cross = await async_client.post("/projects", json={
        "name": "Cross Proj",
        "client_id": str(client_b.id)
    }, headers={"Authorization": f"Bearer {token}"})
    assert res_cross.status_code == 404

@pytest.mark.asyncio
async def test_create_project_unauthorized(async_client: AsyncClient, db_session, password, hashed_password):
    user_member = await create_user(db_session, "member@test.com", hashed_password)
    user_client = await create_user(db_session, "client@test.com", hashed_password)
    agency = await create_agency(db_session, "Agency A", "agency-a")
    
    await create_agency_membership(db_session, user_member.id, agency.id, RoleEnum.agency_member.value)
    await create_agency_membership(db_session, user_client.id, agency.id, RoleEnum.client_user.value)
    
    client_a = await create_client(db_session, agency.id, "Client A")
    await create_client_membership(db_session, user_client.id, agency.id, client_a.id)
    
    t_member = await login(async_client, "member@test.com", password, str(agency.id))
    t_client = await login(async_client, "client@test.com", password, str(agency.id))
    
    # 21. agency_member cannot create project.
    res1 = await async_client.post("/projects", json={"name": "X", "client_id": str(client_a.id)}, headers={"Authorization": f"Bearer {t_member}"})
    assert res1.status_code == 403
    
    # 22. client_user cannot create project.
    res2 = await async_client.post("/projects", json={"name": "Y", "client_id": str(client_a.id)}, headers={"Authorization": f"Bearer {t_client}"})
    assert res2.status_code == 403

@pytest.mark.asyncio
async def test_update_project(async_client: AsyncClient, db_session, password, hashed_password):
    user = await create_user(db_session, "admin@test.com", hashed_password)
    agency = await create_agency(db_session, "Agency A", "agency-a")
    agency_b = await create_agency(db_session, "Agency B", "agency-b")
    await create_agency_membership(db_session, user.id, agency.id, RoleEnum.agency_admin.value)
    client_obj = await create_client(db_session, agency.id, "Client A")
    client_b = await create_client(db_session, agency_b.id, "Client B")
    project = await create_project(db_session, agency.id, client_obj.id, "Project A")
    
    token = await login(async_client, "admin@test.com", password, str(agency.id))
    
    # 23, 24, 25. Admin can update name/description/status.
    res = await async_client.patch(f"/projects/{project.id}", json={
        "name": "Updated",
        "description": "Desc",
        "status": "completed"
    }, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["name"] == "Updated"
    assert res.json()["description"] == "Desc"
    assert res.json()["status"] == "completed"
    
    # 24. PATCH cannot change client_id.
    res2 = await async_client.patch(f"/projects/{project.id}", json={
        "client_id": str(client_b.id)
    }, headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 422 # Pydantic extra='forbid'
    
    # 25. PATCH cannot change agency_id.
    res3 = await async_client.patch(f"/projects/{project.id}", json={
        "agency_id": str(agency_b.id)
    }, headers={"Authorization": f"Bearer {token}"})
    assert res3.status_code == 422

@pytest.mark.asyncio
async def test_project_memberships(async_client: AsyncClient, db_session, password, hashed_password):
    admin = await create_user(db_session, "admin@test.com", hashed_password)
    member = await create_user(db_session, "member@test.com", hashed_password)
    member_inactive = await create_user(db_session, "inactive@test.com", hashed_password)
    client_u = await create_user(db_session, "client@test.com", hashed_password)
    other_member = await create_user(db_session, "other@test.com", hashed_password)
    
    agency = await create_agency(db_session, "Agency A", "a")
    agency_b = await create_agency(db_session, "Agency B", "b")
    
    await create_agency_membership(db_session, admin.id, agency.id, RoleEnum.agency_admin.value)
    await create_agency_membership(db_session, member.id, agency.id, RoleEnum.agency_member.value)
    await create_agency_membership(db_session, member_inactive.id, agency.id, RoleEnum.agency_member.value, is_active=False)
    await create_agency_membership(db_session, client_u.id, agency.id, RoleEnum.client_user.value)
    
    await create_agency_membership(db_session, other_member.id, agency_b.id, RoleEnum.agency_member.value)
    
    client_obj = await create_client(db_session, agency.id, "Client")
    project = await create_project(db_session, agency.id, client_obj.id, "Proj")
    
    token = await login(async_client, "admin@test.com", password, str(agency.id))
    
    # 27. Admin can assign an active agency_member to project.
    res = await async_client.post(f"/projects/{project.id}/members", json={"user_id": str(member.id)}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 201
    
    # 33. Membership response does not expose agency_id.
    assert "agency_id" not in res.json()
    
    # 32. Duplicate ProjectMembership request is idempotent.
    res_dup = await async_client.post(f"/projects/{project.id}/members", json={"user_id": str(member.id)}, headers={"Authorization": f"Bearer {token}"})
    assert res_dup.status_code == 201
    assert res.json()["id"] == res_dup.json()["id"]
    
    # 28. Cannot assign user from another agency.
    res_other = await async_client.post(f"/projects/{project.id}/members", json={"user_id": str(other_member.id)}, headers={"Authorization": f"Bearer {token}"})
    assert res_other.status_code == 404
    
    # 29. Cannot assign inactive AgencyMembership.
    res_inactive = await async_client.post(f"/projects/{project.id}/members", json={"user_id": str(member_inactive.id)}, headers={"Authorization": f"Bearer {token}"})
    assert res_inactive.status_code == 404
    
    # 30. Cannot assign client_user.
    res_client = await async_client.post(f"/projects/{project.id}/members", json={"user_id": str(client_u.id)}, headers={"Authorization": f"Bearer {token}"})
    assert res_client.status_code == 404
    
    # 31. Can assign agency_admin.
    res_admin = await async_client.post(f"/projects/{project.id}/members", json={"user_id": str(admin.id)}, headers={"Authorization": f"Bearer {token}"})
    assert res_admin.status_code == 201

@pytest.mark.asyncio
async def test_project_membership_deactivated(async_client: AsyncClient, db_session, password, hashed_password):
    user = await create_user(db_session, "member@test.com", hashed_password)
    agency = await create_agency(db_session, "Agency A", "agency-a")
    membership = await create_agency_membership(db_session, user.id, agency.id, RoleEnum.agency_member.value)
    
    token = await login(async_client, "member@test.com", password, str(agency.id))
    
    # 3. Confirm GET /projects succeeds.
    res_success = await async_client.get("/projects", headers={"Authorization": f"Bearer {token}"})
    assert res_success.status_code == 200
    
    # 4. Deactivate that AgencyMembership in PostgreSQL AFTER token issuance.
    membership.is_active = False
    await db_session.commit()
    
    # 7. Call GET /projects again with SAME JWT.
    res_fail = await async_client.get("/projects", headers={"Authorization": f"Bearer {token}"})
    
    # 8. Assert 401 Unauthorized. (TenantContext revalidation fails)
    assert res_fail.status_code == 401



import pytest
from httpx import AsyncClient
from uuid import uuid4
from sqlalchemy import text, select
import sqlalchemy.exc

from app.models.user import User
from app.models.agency import Agency, AgencyMembership
from app.models.client import Client, ClientMembership
from app.models.project import Project, ProjectMembership
from app.models.task import Task
from app.models.comment import Comment
from app.models.file import File
from app.models.enums import RoleEnum, TaskStatusEnum, TaskPriorityEnum, VisibilityEnum
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

async def create_task(db_session, agency_id, project_id, title, visibility=VisibilityEnum.internal.value, assignee_id=None, description="Test description"):
    task = Task(agency_id=agency_id, project_id=project_id, title=title, visibility=visibility, assignee_id=assignee_id, description=description)
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task

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
    other_client_user = await create_user(db_session, "other_client@test.com", hashed_password)
    cross_tenant = await create_user(db_session, "crosstenant@test.com", hashed_password)
    
    agency = await create_agency(db_session, "Agency A", "a")
    agency_b = await create_agency(db_session, "Agency B", "b")
    
    await create_agency_membership(db_session, admin.id, agency.id, RoleEnum.agency_admin.value)
    await create_agency_membership(db_session, member.id, agency.id, RoleEnum.agency_member.value)
    await create_agency_membership(db_session, unassigned.id, agency.id, RoleEnum.agency_member.value)
    await create_agency_membership(db_session, client_user.id, agency.id, RoleEnum.client_user.value)
    await create_agency_membership(db_session, other_client_user.id, agency.id, RoleEnum.client_user.value)
    
    await create_agency_membership(db_session, cross_tenant.id, agency_b.id, RoleEnum.agency_admin.value)
    
    client = await create_client(db_session, agency.id, "Client 1")
    other_client = await create_client(db_session, agency.id, "Client 2")
    client_b = await create_client(db_session, agency_b.id, "Client B")
    
    await create_client_membership(db_session, client_user.id, agency.id, client.id)
    await create_client_membership(db_session, other_client_user.id, agency.id, other_client.id)
    
    project = await create_project(db_session, agency.id, client.id, "Project 1")
    other_project = await create_project(db_session, agency.id, other_client.id, "Project 2")
    project_b = await create_project(db_session, agency_b.id, client_b.id, "Project B")
    
    await create_project_membership(db_session, member.id, project.id, agency.id)
    
    return {
        "admin": admin, "member": member, "unassigned": unassigned, "client_user": client_user, 
        "other_client_user": other_client_user, "cross_tenant": cross_tenant,
        "agency": agency, "agency_b": agency_b,
        "client": client, "other_client": other_client, "client_b": client_b,
        "project": project, "other_project": other_project, "project_b": project_b
    }

@pytest.mark.asyncio
async def test_authorization(async_client: AsyncClient, db_session, password, hashed_password):
    env = await setup_env(db_session, hashed_password)
    
    t_internal = await create_task(db_session, env["agency"].id, env["project"].id, "T1", VisibilityEnum.internal.value)
    t_client = await create_task(db_session, env["agency"].id, env["project"].id, "T2", VisibilityEnum.client.value)
    t_other = await create_task(db_session, env["agency"].id, env["other_project"].id, "T3", VisibilityEnum.internal.value)
    t_cross = await create_task(db_session, env["agency_b"].id, env["project_b"].id, "T4", VisibilityEnum.internal.value)
    
    admin_token = await login(async_client, "admin@test.com", password, str(env["agency"].id))
    member_token = await login(async_client, "member@test.com", password, str(env["agency"].id))
    unassigned_token = await login(async_client, "unassigned@test.com", password, str(env["agency"].id))
    client_token = await login(async_client, "client@test.com", password, str(env["agency"].id))
    other_client_token = await login(async_client, "other_client@test.com", password, str(env["agency"].id))
    cross_token = await login(async_client, "crosstenant@test.com", password, str(env["agency_b"].id))
    
    # 1. admin can list tasks in same-agency project
    # 2. admin with NO ProjectMembership can still access/list tasks
    res = await async_client.get(f"/projects/{env['project'].id}/tasks", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert len(res.json()) == 2
    
    # 3. cross-tenant project list -> 404
    res = await async_client.get(f"/projects/{env['project'].id}/tasks", headers={"Authorization": f"Bearer {cross_token}"})
    assert res.status_code == 404
    
    # 4. agency_member can list assigned project tasks
    res = await async_client.get(f"/projects/{env['project'].id}/tasks", headers={"Authorization": f"Bearer {member_token}"})
    assert res.status_code == 200
    assert len(res.json()) == 2
    
    # 5. agency_member cannot list unassigned project tasks
    res = await async_client.get(f"/projects/{env['project'].id}/tasks", headers={"Authorization": f"Bearer {unassigned_token}"})
    assert res.status_code == 404
    
    # 6. client_user sees client-visible own-client task
    # 7. client_user list excludes internal task
    res = await async_client.get(f"/projects/{env['project'].id}/tasks", headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["visibility"] == "client"
    
    # 8. client_user cannot access another client's project/tasks
    res = await async_client.get(f"/projects/{env['other_project'].id}/tasks", headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 404
    
    # 9. GET /tasks/{cross_tenant_task} -> 404
    res = await async_client.get(f"/tasks/{t_cross.id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 404
    
    # 10. GET internal task as client_user -> 404
    res = await async_client.get(f"/tasks/{t_internal.id}", headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 404
    
    # 11. inaccessible and nonexistent task produce same safe status/response behavior
    res_fake = await async_client.get(f"/tasks/{uuid4()}", headers={"Authorization": f"Bearer {client_token}"})
    assert res_fake.status_code == 404
    assert res_fake.json() == res.json()

@pytest.mark.asyncio
async def test_search(async_client: AsyncClient, db_session, password, hashed_password):
    env = await setup_env(db_session, hashed_password)
    admin_token = await login(async_client, "admin@test.com", password, str(env["agency"].id))
    client_token = await login(async_client, "client@test.com", password, str(env["agency"].id))
    
    await create_task(db_session, env["agency"].id, env["project"].id, "Secret keyword internal", VisibilityEnum.internal.value, description="No")
    await create_task(db_session, env["agency"].id, env["project"].id, "Visible keyword task", VisibilityEnum.client.value, description="Yes")
    await create_task(db_session, env["agency"].id, env["other_project"].id, "Inaccessible keyword task", VisibilityEnum.internal.value)
    
    for _ in range(5):
         await create_task(db_session, env["agency"].id, env["project"].id, "filler keyword", VisibilityEnum.internal.value)
    
    # 12. agency staff search finds accessible matching task
    res = await async_client.get(f"/projects/{env['project'].id}/tasks?search=keyword", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert len(res.json()) == 7
    
    # 13. client search finds matching client-visible task
    res = await async_client.get(f"/projects/{env['project'].id}/tasks?search=visible", headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 200
    assert len(res.json()) == 1
    
    # 14. client search for keyword existing only in internal task returns []
    res = await async_client.get(f"/projects/{env['project'].id}/tasks?search=secret", headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 200
    assert len(res.json()) == 0
    
    # 15. search cannot expose task from inaccessible project
    res = await async_client.get(f"/projects/{env['other_project'].id}/tasks?search=inaccessible", headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 404
    
    # 16. pagination is applied after authorization + visibility + search
    res = await async_client.get(f"/projects/{env['project'].id}/tasks?search=keyword&limit=2", headers={"Authorization": f"Bearer {admin_token}"})
    assert len(res.json()) == 2
    
    # 17. skip < 0 -> 422
    res = await async_client.get(f"/projects/{env['project'].id}/tasks?skip=-1", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 422
    
    # 18. limit > 100 -> 422
    res = await async_client.get(f"/projects/{env['project'].id}/tasks?limit=101", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 422

@pytest.mark.asyncio
async def test_create(async_client: AsyncClient, db_session, password, hashed_password):
    env = await setup_env(db_session, hashed_password)
    admin_token = await login(async_client, "admin@test.com", password, str(env["agency"].id))
    member_token = await login(async_client, "member@test.com", password, str(env["agency"].id))
    unassigned_token = await login(async_client, "unassigned@test.com", password, str(env["agency"].id))
    client_token = await login(async_client, "client@test.com", password, str(env["agency"].id))
    
    # 19. admin can create task
    # 23. persisted task agency_id == TenantContext agency
    # 24. persisted task project_id == authorized path project
    # 27. omitted visibility persists/returns internal
    # 28. omitted status -> todo
    # 29. omitted priority -> medium
    res = await async_client.post(f"/projects/{env['project'].id}/tasks", json={"title": "Admin task"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 201
    assert res.json()["title"] == "Admin task"
    assert res.json()["project_id"] == str(env["project"].id)
    assert res.json()["visibility"] == "internal"
    assert res.json()["status"] == "todo"
    assert res.json()["priority"] == "medium"
    assert "agency_id" not in res.json()
    
    # 20. assigned agency_member can create task
    res = await async_client.post(f"/projects/{env['project'].id}/tasks", json={"title": "Member task"}, headers={"Authorization": f"Bearer {member_token}"})
    assert res.status_code == 201
    
    # 21. unassigned agency_member cannot create in project
    res = await async_client.post(f"/projects/{env['project'].id}/tasks", json={"title": "Unassigned task"}, headers={"Authorization": f"Bearer {unassigned_token}"})
    assert res.status_code == 404
    
    # 22. client_user create -> 403
    res = await async_client.post(f"/projects/{env['project'].id}/tasks", json={"title": "Client task"}, headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 403
    
    # 25. JSON agency_id rejected
    res = await async_client.post(f"/projects/{env['project'].id}/tasks", json={"title": "T", "agency_id": str(env["agency_b"].id)}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 422
    
    # 26. JSON project_id rejected
    res = await async_client.post(f"/projects/{env['project'].id}/tasks", json={"title": "T", "project_id": str(env["project"].id)}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 422
    
    # 30. explicit client visibility works for agency staff
    res = await async_client.post(f"/projects/{env['project'].id}/tasks", json={"title": "Client visible", "visibility": "client"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 201
    assert res.json()["visibility"] == "client"

@pytest.mark.asyncio
async def test_assignment(async_client: AsyncClient, db_session, password, hashed_password):
    env = await setup_env(db_session, hashed_password)
    admin_token = await login(async_client, "admin@test.com", password, str(env["agency"].id))
    
    # Create inactive member
    inactive_u = await create_user(db_session, "inactive@test.com", hashed_password)
    await create_agency_membership(db_session, inactive_u.id, env["agency"].id, RoleEnum.agency_member.value, is_active=False)
    await create_project_membership(db_session, inactive_u.id, env["project"].id, env["agency"].id)
    
    # Create admin with membership
    admin_mem_u = await create_user(db_session, "admin_mem@test.com", hashed_password)
    await create_agency_membership(db_session, admin_mem_u.id, env["agency"].id, RoleEnum.agency_admin.value)
    await create_project_membership(db_session, admin_mem_u.id, env["project"].id, env["agency"].id)
    
    # 31. active same-agency agency_member WITH ProjectMembership accepted
    res = await async_client.post(f"/projects/{env['project'].id}/tasks", json={"title": "T", "assignee_id": str(env["member"].id)}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 201
    
    # 32. agency_member WITHOUT ProjectMembership rejected
    res = await async_client.post(f"/projects/{env['project'].id}/tasks", json={"title": "T", "assignee_id": str(env["unassigned"].id)}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 400
    assert res.json()["detail"] == "Invalid task assignee"
    
    # 33. inactive AgencyMembership rejected
    res = await async_client.post(f"/projects/{env['project'].id}/tasks", json={"title": "T", "assignee_id": str(inactive_u.id)}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 400
    
    # 34. cross-agency user rejected
    res = await async_client.post(f"/projects/{env['project'].id}/tasks", json={"title": "T", "assignee_id": str(env["cross_tenant"].id)}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 400
    
    # 35. client_user rejected
    res = await async_client.post(f"/projects/{env['project'].id}/tasks", json={"title": "T", "assignee_id": str(env["client_user"].id)}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 400
    
    # 36. agency_admin WITHOUT ProjectMembership rejected
    res = await async_client.post(f"/projects/{env['project'].id}/tasks", json={"title": "T", "assignee_id": str(env["admin"].id)}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 400
    
    # 37. agency_admin WITH ProjectMembership accepted
    res = await async_client.post(f"/projects/{env['project'].id}/tasks", json={"title": "T", "assignee_id": str(admin_mem_u.id)}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 201

@pytest.mark.asyncio
async def test_patch(async_client: AsyncClient, db_session, password, hashed_password):
    env = await setup_env(db_session, hashed_password)
    admin_token = await login(async_client, "admin@test.com", password, str(env["agency"].id))
    member_token = await login(async_client, "member@test.com", password, str(env["agency"].id))
    unassigned_token = await login(async_client, "unassigned@test.com", password, str(env["agency"].id))
    client_token = await login(async_client, "client@test.com", password, str(env["agency"].id))
    
    admin_mem_u = await create_user(db_session, "admin_mem2@test.com", hashed_password)
    await create_agency_membership(db_session, admin_mem_u.id, env["agency"].id, RoleEnum.agency_admin.value)
    await create_project_membership(db_session, admin_mem_u.id, env["project"].id, env["agency"].id)
    
    t = await create_task(db_session, env["agency"].id, env["project"].id, "Task to patch", assignee_id=admin_mem_u.id)
    t2 = await create_task(db_session, env["agency"].id, env["project"].id, "Client task", visibility=VisibilityEnum.client.value)
    
    # 38. admin can update task
    res = await async_client.patch(f"/tasks/{t.id}", json={"title": "Admin patch"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert res.json()["title"] == "Admin patch"
    
    # 39. assigned agency_member can update task
    res = await async_client.patch(f"/tasks/{t.id}", json={"title": "Member patch"}, headers={"Authorization": f"Bearer {member_token}"})
    assert res.status_code == 200
    
    # 40. unassigned agency_member cannot update task
    res = await async_client.patch(f"/tasks/{t.id}", json={"title": "Fail patch"}, headers={"Authorization": f"Bearer {unassigned_token}"})
    assert res.status_code == 404
    
    # 41. client_user PATCH -> 403
    res = await async_client.patch(f"/tasks/{t2.id}", json={"title": "Fail patch"}, headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 403
    
    # 42. omitted assignee_id leaves assignment unchanged
    res = await async_client.patch(f"/tasks/{t.id}", json={"title": "Just title"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert res.json()["assignee_id"] == str(admin_mem_u.id)
    
    # 43. assignee_id=null unassigns
    res = await async_client.patch(f"/tasks/{t.id}", json={"assignee_id": None}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert res.json()["assignee_id"] is None
    
    # 44. valid new assignee works
    res = await async_client.patch(f"/tasks/{t.id}", json={"assignee_id": str(env["member"].id)}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert res.json()["assignee_id"] == str(env["member"].id)
    
    # 45. invalid new assignee rejected
    res = await async_client.patch(f"/tasks/{t.id}", json={"assignee_id": str(env["client_user"].id)}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 400
    
    # 46. project_id in PATCH rejected
    res = await async_client.patch(f"/tasks/{t.id}", json={"project_id": str(env["project"].id)}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 422
    
    # 47. agency_id in PATCH rejected
    res = await async_client.patch(f"/tasks/{t.id}", json={"agency_id": str(env["agency"].id)}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 422
    
    # Nullability checks for non-nullable fields -> 422
    res = await async_client.patch(f"/tasks/{t.id}", json={"title": None}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 422
    res = await async_client.patch(f"/tasks/{t.id}", json={"status": None}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 422
    res = await async_client.patch(f"/tasks/{t.id}", json={"priority": None}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 422
    res = await async_client.patch(f"/tasks/{t.id}", json={"visibility": None}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 422
    
    # Nullability checks for nullable fields -> 200 and clears field
    res = await async_client.patch(f"/tasks/{t.id}", json={"description": None}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert res.json()["description"] is None
    
    res = await async_client.patch(f"/tasks/{t.id}", json={"due_date": None}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert res.json()["due_date"] is None

@pytest.mark.asyncio
async def test_visibility_invariant(async_client: AsyncClient, db_session, password, hashed_password):
    env = await setup_env(db_session, hashed_password)
    admin_token = await login(async_client, "admin@test.com", password, str(env["agency"].id))
    
    # 1. internal -> client succeeds and does not fail due to blocker logic
    t_int = await create_task(db_session, env["agency"].id, env["project"].id, "Int Task", VisibilityEnum.internal.value)
    db_session.add(Comment(task_id=t_int.id, agency_id=env["agency"].id, author_id=env["admin"].id, content="C", visibility="client"))
    await db_session.commit()
    res = await async_client.patch(f"/tasks/{t_int.id}", json={"visibility": "client"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert res.json()["visibility"] == "client"
    
    # 2. client -> client succeeds
    t_client_stay = await create_task(db_session, env["agency"].id, env["project"].id, "Client Stay", VisibilityEnum.client.value)
    db_session.add(Comment(task_id=t_client_stay.id, agency_id=env["agency"].id, author_id=env["admin"].id, content="C", visibility="client"))
    await db_session.commit()
    res = await async_client.patch(f"/tasks/{t_client_stay.id}", json={"visibility": "client"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert res.json()["visibility"] == "client"
    
    # 3. PATCH of another field while visibility is omitted succeeds normally
    res = await async_client.patch(f"/tasks/{t_client_stay.id}", json={"title": "Client Stay Updated"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert res.json()["title"] == "Client Stay Updated"
    
    # 48. (7) client -> internal succeeds with no visible children
    t_clean = await create_task(db_session, env["agency"].id, env["project"].id, "Clean", VisibilityEnum.client.value)
    res = await async_client.patch(f"/tasks/{t_clean.id}", json={"visibility": "internal"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert res.json()["visibility"] == "internal"
    
    # 49. (4) client -> internal blocked by client-visible Comment
    t_comm = await create_task(db_session, env["agency"].id, env["project"].id, "Comm", VisibilityEnum.client.value)
    db_session.add(Comment(task_id=t_comm.id, agency_id=env["agency"].id, author_id=env["admin"].id, content="C", visibility="client"))
    await db_session.commit()
    res = await async_client.patch(f"/tasks/{t_comm.id}", json={"visibility": "internal"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 400
    assert res.json()["detail"]["blockers"] == ["comments"]
    
    # 50. client -> internal blocked by client-visible File
    t_file = await create_task(db_session, env["agency"].id, env["project"].id, "File", VisibilityEnum.client.value)
    db_session.add(File(task_id=t_file.id, agency_id=env["agency"].id, uploaded_by_id=env["admin"].id, filename="a.txt", storage_path="path", visibility="client"))
    await db_session.commit()
    res = await async_client.patch(f"/tasks/{t_file.id}", json={"visibility": "internal"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 400
    assert res.json()["detail"]["blockers"] == ["files"]
    
    # 51. blocked by both returns blockers exactly: ["comments", "files"]
    t_both = await create_task(db_session, env["agency"].id, env["project"].id, "Both", VisibilityEnum.client.value)
    db_session.add(Comment(task_id=t_both.id, agency_id=env["agency"].id, author_id=env["admin"].id, content="C", visibility="client"))
    db_session.add(File(task_id=t_both.id, agency_id=env["agency"].id, uploaded_by_id=env["admin"].id, filename="a.txt", storage_path="path", visibility="client"))
    await db_session.commit()
    res = await async_client.patch(f"/tasks/{t_both.id}", json={"visibility": "internal"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 400
    assert res.json()["detail"]["blockers"] == ["comments", "files"]
    
    # 52. internal comments do NOT block transition
    # 53. internal files do NOT block transition
    t_internal_children = await create_task(db_session, env["agency"].id, env["project"].id, "InternalC", VisibilityEnum.client.value)
    db_session.add(Comment(task_id=t_internal_children.id, agency_id=env["agency"].id, author_id=env["admin"].id, content="C", visibility="internal"))
    db_session.add(File(task_id=t_internal_children.id, agency_id=env["agency"].id, uploaded_by_id=env["admin"].id, filename="a.txt", storage_path="path", visibility="internal"))
    await db_session.commit()
    res = await async_client.patch(f"/tasks/{t_internal_children.id}", json={"visibility": "internal"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200

@pytest.mark.asyncio
async def test_auth_revalidation(async_client: AsyncClient, db_session, password, hashed_password):
    env = await setup_env(db_session, hashed_password)
    admin_token = await login(async_client, "admin@test.com", password, str(env["agency"].id))
    
    # 54. issue token, deactivate AgencyMembership, reuse same token -> 401
    mem = (await db_session.execute(select(AgencyMembership).where(AgencyMembership.user_id == env["admin"].id))).scalar_one()
    mem.is_active = False
    await db_session.commit()
    res = await async_client.get(f"/projects/{env['project'].id}/tasks", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 401
    
    mem.is_active = True
    await db_session.commit()
    
    # 55. issue token, deactivate User, reuse same token -> 401
    user = (await db_session.execute(select(User).where(User.id == env["admin"].id))).scalar_one()
    user.is_active = False
    await db_session.commit()
    res = await async_client.get(f"/projects/{env['project'].id}/tasks", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_project_membership_correction(async_client: AsyncClient, db_session, password, hashed_password):
    env = await setup_env(db_session, hashed_password)
    admin_token = await login(async_client, "admin@test.com", password, str(env["agency"].id))
    
    admin2 = await create_user(db_session, "admin2@test.com", hashed_password)
    await create_agency_membership(db_session, admin2.id, env["agency"].id, RoleEnum.agency_admin.value)
    
    # 56. project membership endpoint accepts active same-agency agency_admin
    res = await async_client.post(f"/projects/{env['project'].id}/members", json={"user_id": str(admin2.id)}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 201
    
    # 57. project membership endpoint still rejects client_user
    res = await async_client.post(f"/projects/{env['project'].id}/members", json={"user_id": str(env["client_user"].id)}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 404

@pytest.mark.asyncio
async def test_schema_level_security(async_client: AsyncClient, db_session, password, hashed_password):
    env = await setup_env(db_session, hashed_password)
    
    # Section 20 Test 24 requires: Insert task with agency_id = Agency A, project_id = Agency B project -> database error
    task = Task(agency_id=env["agency"].id, project_id=env["project_b"].id, title="Schema bypass attempt")
    db_session.add(task)
    
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await db_session.commit()
        
    await db_session.rollback()

import pytest
from httpx import AsyncClient
from uuid import uuid4
from sqlalchemy import text, select
import sqlalchemy.exc
import asyncio

from app.models.user import User
from app.models.agency import Agency, AgencyMembership
from app.models.client import Client, ClientMembership
from app.models.project import Project, ProjectMembership
from app.models.task import Task
from app.models.comment import Comment
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

async def create_comment(db_session, agency_id, task_id, author_id, content, visibility=VisibilityEnum.internal.value):
    comment = Comment(agency_id=agency_id, task_id=task_id, author_id=author_id, content=content, visibility=visibility)
    db_session.add(comment)
    await db_session.commit()
    await db_session.refresh(comment)
    return comment

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
    
    await create_project_membership(db_session, member.id, project.id, agency.id)
    
    return {
        "admin": admin, "member": member, "unassigned": unassigned, "client_user": client_user, "cross_tenant": cross_tenant,
        "agency": agency, "agency_b": agency_b,
        "client": client, "client_b": client_b,
        "project": project, "other_project": other_project, "project_b": project_b
    }

@pytest.mark.asyncio
async def test_list_comments(async_client: AsyncClient, db_session, password, hashed_password):
    env = await setup_env(db_session, hashed_password)
    
    t_internal = await create_task(db_session, env["agency"].id, env["project"].id, "Internal Task", VisibilityEnum.internal.value)
    t_client = await create_task(db_session, env["agency"].id, env["project"].id, "Client Task", VisibilityEnum.client.value)
    t_unassigned = await create_task(db_session, env["agency"].id, env["other_project"].id, "Unassigned Task", VisibilityEnum.internal.value)
    t_cross = await create_task(db_session, env["agency_b"].id, env["project_b"].id, "Cross Task", VisibilityEnum.internal.value)
    
    # 8. Client visibility filtering occurs BEFORE pagination
    for i in range(5):
        await create_comment(db_session, env["agency"].id, t_client.id, env["admin"].id, f"internal {i}", VisibilityEnum.internal.value)
        # Sleep slightly to ensure created_at ordering
        await asyncio.sleep(0.01)
    
    c_vis = await create_comment(db_session, env["agency"].id, t_client.id, env["admin"].id, "visible", VisibilityEnum.client.value)
    
    admin_token = await login(async_client, "admin@test.com", password, str(env["agency"].id))
    member_token = await login(async_client, "member@test.com", password, str(env["agency"].id))
    unassigned_token = await login(async_client, "unassigned@test.com", password, str(env["agency"].id))
    client_token = await login(async_client, "client@test.com", password, str(env["agency"].id))
    cross_token = await login(async_client, "crosstenant@test.com", password, str(env["agency_b"].id))
    
    # 1. Admin lists comments on accessible task
    res = await async_client.get(f"/tasks/{t_client.id}/comments", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert len(res.json()) == 6
    
    # 2. Agency member lists comments on assigned-project task
    res = await async_client.get(f"/tasks/{t_client.id}/comments", headers={"Authorization": f"Bearer {member_token}"})
    assert res.status_code == 200
    
    # 3. Agency member receives 404 for task in unassigned project
    res = await async_client.get(f"/tasks/{t_unassigned.id}/comments", headers={"Authorization": f"Bearer {member_token}"})
    assert res.status_code == 404
    
    # 4. Cross-tenant task access returns 404
    res = await async_client.get(f"/tasks/{t_cross.id}/comments", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 404
    
    # 5. client_user list includes client-visible comments
    # 6. client_user list excludes internal comments
    # 8. Client visibility filtering occurs BEFORE pagination
    # 27. Arch Test 7: never returns internal comments
    res = await async_client.get(f"/tasks/{t_client.id}/comments?limit=2", headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["id"] == str(c_vis.id)
    
    # 7. client_user receives 404 for internal parent task
    res = await async_client.get(f"/tasks/{t_internal.id}/comments", headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 404
    
    # 9. Negative skip -> 422
    res = await async_client.get(f"/tasks/{t_client.id}/comments?skip=-1", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 422
    
    # 10. limit > 100 -> 422
    res = await async_client.get(f"/tasks/{t_client.id}/comments?limit=101", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 422

@pytest.mark.asyncio
async def test_create_comments(async_client: AsyncClient, db_session, password, hashed_password):
    env = await setup_env(db_session, hashed_password)
    
    t_internal = await create_task(db_session, env["agency"].id, env["project"].id, "Internal Task", VisibilityEnum.internal.value)
    t_client = await create_task(db_session, env["agency"].id, env["project"].id, "Client Task", VisibilityEnum.client.value)
    
    admin_token = await login(async_client, "admin@test.com", password, str(env["agency"].id))
    member_token = await login(async_client, "member@test.com", password, str(env["agency"].id))
    client_token = await login(async_client, "client@test.com", password, str(env["agency"].id))
    
    # 11. Admin create without visibility persists internal
    # 29. Arch Test 28: agency staff comment without visibility -> internal
    res = await async_client.post(f"/tasks/{t_client.id}/comments", json={"content": "c"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 201
    assert res.json()["visibility"] == "internal"
    
    # 12. Agency member create without visibility persists internal
    res = await async_client.post(f"/tasks/{t_client.id}/comments", json={"content": "c"}, headers={"Authorization": f"Bearer {member_token}"})
    assert res.status_code == 201
    assert res.json()["visibility"] == "internal"
    
    # Cascade boundary: internal task + internal staff comment -> allowed
    res = await async_client.post(f"/tasks/{t_internal.id}/comments", json={"content": "c", "visibility": "internal"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 201
    
    # 13. Staff can create client comment on client-visible task
    # Cascade boundary: client task + client staff comment -> allowed
    res = await async_client.post(f"/tasks/{t_client.id}/comments", json={"content": "c", "visibility": "client"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 201
    
    # 14. Staff cannot create client comment on internal task -> 400
    # Cascade boundary: internal task + client staff comment -> 400
    res = await async_client.post(f"/tasks/{t_internal.id}/comments", json={"content": "c", "visibility": "client"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 400
    
    # 15. client_user create on client-visible task persists visibility='client'
    res = await async_client.post(f"/tasks/{t_client.id}/comments", json={"content": "c"}, headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 201
    assert res.json()["visibility"] == "client"
    
    # 16. client_user explicitly sends visibility='internal' and persisted visibility is still 'client'
    # 28. Arch Test 27: forced visibility
    res = await async_client.post(f"/tasks/{t_client.id}/comments", json={"content": "c", "visibility": "internal"}, headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 201
    assert res.json()["visibility"] == "client"
    
    # 17. client_user cannot create on internal task -> 404
    res = await async_client.post(f"/tasks/{t_internal.id}/comments", json={"content": "c"}, headers={"Authorization": f"Bearer {client_token}"})
    assert res.status_code == 404
    
    # 18. Persisted author_id equals authenticated context.user.id
    # 19. Persisted agency_id equals authenticated context.agency_id using a direct DB assertion
    comment_id = res.json()["id"] if res.status_code == 201 else res.json().get("id") # from previous success
    # Need to fetch a definitely created one
    res_c = await async_client.post(f"/tasks/{t_client.id}/comments", json={"content": "admin made this"}, headers={"Authorization": f"Bearer {admin_token}"})
    c_id = res_c.json()["id"]
    
    db_comment = (await db_session.execute(select(Comment).where(Comment.id == c_id))).scalar_one()
    assert db_comment.author_id == env["admin"].id
    assert db_comment.agency_id == env["agency"].id
    
    # 20. Supplying author_id in body -> 422
    res = await async_client.post(f"/tasks/{t_client.id}/comments", json={"content": "c", "author_id": str(env["client_user"].id)}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 422
    
    # 21. Supplying agency_id in body -> 422
    res = await async_client.post(f"/tasks/{t_client.id}/comments", json={"content": "c", "agency_id": str(env["agency_b"].id)}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 422
    
    # 22. Supplying task_id in body -> 422
    res = await async_client.post(f"/tasks/{t_client.id}/comments", json={"content": "c", "task_id": str(t_internal.id)}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 422
    
    # 23. CommentResponse does not expose agency_id
    res = await async_client.get(f"/tasks/{t_client.id}/comments", headers={"Authorization": f"Bearer {admin_token}"})
    assert "agency_id" not in res.json()[0]

@pytest.mark.asyncio
async def test_auth_revalidation(async_client: AsyncClient, db_session, password, hashed_password):
    env = await setup_env(db_session, hashed_password)
    t_client = await create_task(db_session, env["agency"].id, env["project"].id, "Client Task", VisibilityEnum.client.value)
    
    admin_token = await login(async_client, "admin@test.com", password, str(env["agency"].id))
    
    # 24. Existing JWT fails with 401 after AgencyMembership deactivation
    mem = (await db_session.execute(select(AgencyMembership).where(AgencyMembership.user_id == env["admin"].id))).scalar_one()
    mem.is_active = False
    await db_session.commit()
    res = await async_client.get(f"/tasks/{t_client.id}/comments", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 401
    
    mem.is_active = True
    await db_session.commit()
    
    # 25. Existing JWT fails with 401 after User deactivation
    user = (await db_session.execute(select(User).where(User.id == env["admin"].id))).scalar_one()
    user.is_active = False
    await db_session.commit()
    res = await async_client.get(f"/tasks/{t_client.id}/comments", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_schema_level_security(async_client: AsyncClient, db_session, password, hashed_password):
    env = await setup_env(db_session, hashed_password)
    
    # 26. Direct DB insertion of a comment with agency_id=A and task_id belonging to Agency B fails with IntegrityError
    comment = Comment(
        task_id=env["project_b"].id, # Wait, I need a task belonging to project_b. Let's make one.
        agency_id=env["agency"].id, 
        author_id=env["admin"].id, 
        content="Cross"
    )
    
    task_b = await create_task(db_session, env["agency_b"].id, env["project_b"].id, "B Task")
    
    comment2 = Comment(
        task_id=task_b.id,
        agency_id=env["agency"].id, 
        author_id=env["admin"].id, 
        content="Cross"
    )
    
    db_session.add(comment2)
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await db_session.commit()
        
    await db_session.rollback()

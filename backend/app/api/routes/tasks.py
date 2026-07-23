from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import TenantContext, get_current_tenant_context, require_roles
from app.api.project_access import get_authorized_project
from app.api.task_access import get_authorized_task, validate_task_assignee
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse
from app.models.task import Task
from app.models.enums import RoleEnum, VisibilityEnum
from app.models.comment import Comment
from app.models.file import File

router = APIRouter()

@router.get("/projects/{project_id}/tasks", response_model=list[TaskResponse])
async def list_tasks(
    project_id: UUID,
    search: str | None = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    context: TenantContext = Depends(get_current_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    project = await get_authorized_project(project_id, context, db)
    
    stmt = select(Task).where(
        and_(
            Task.project_id == project.id,
            Task.agency_id == context.agency_id
        )
    )
    
    if context.role == RoleEnum.client_user.value:
        stmt = stmt.where(Task.visibility == VisibilityEnum.client.value)
        
    if search:
        stmt = stmt.where(
            or_(
                Task.title.ilike(f"%{search}%"),
                Task.description.ilike(f"%{search}%")
            )
        )
        
    stmt = stmt.order_by(Task.created_at.desc(), Task.id.desc()).offset(skip).limit(limit)
    
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    return list(tasks)

@router.post("/projects/{project_id}/tasks", response_model=TaskResponse, status_code=201)
async def create_task(
    project_id: UUID,
    payload: TaskCreate,
    context: TenantContext = Depends(require_roles([RoleEnum.agency_admin.value, RoleEnum.agency_member.value])),
    db: AsyncSession = Depends(get_db)
):
    project = await get_authorized_project(project_id, context, db)
    
    if payload.assignee_id is not None:
        await validate_task_assignee(payload.assignee_id, project.id, context, db)
        
    task = Task(
        agency_id=context.agency_id,
        project_id=project.id,
        title=payload.title,
        description=payload.description,
        status=payload.status.value,
        priority=payload.priority.value,
        visibility=payload.visibility.value,
        assignee_id=payload.assignee_id,
        due_date=payload.due_date
    )
    
    db.add(task)
    await db.commit()
    await db.refresh(task)
    
    return task

@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: UUID,
    context: TenantContext = Depends(get_current_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    task = await get_authorized_task(task_id, context, db)
    return task

@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    payload: TaskUpdate,
    context: TenantContext = Depends(require_roles([RoleEnum.agency_admin.value, RoleEnum.agency_member.value])),
    db: AsyncSession = Depends(get_db)
):
    task = await get_authorized_task(task_id, context, db)
    
    update_data = payload.model_dump(exclude_unset=True)
    
    if "assignee_id" in update_data:
        assignee_id = update_data["assignee_id"]
        if assignee_id is not None:
            await validate_task_assignee(assignee_id, task.project_id, context, db)
            
    # Check visibility transition
    if "visibility" in update_data:
        req_vis = update_data["visibility"]
        req_vis_val = req_vis.value if hasattr(req_vis, "value") else req_vis
        if task.visibility == VisibilityEnum.client.value and req_vis_val == VisibilityEnum.internal.value:
            blockers = []
            
            comment_stmt = select(Comment).where(
                and_(
                    Comment.task_id == task.id,
                    Comment.agency_id == context.agency_id,
                    Comment.visibility == VisibilityEnum.client.value
                )
            ).limit(1)
            comment_exists = (await db.execute(comment_stmt)).scalar_one_or_none()
            if comment_exists:
                blockers.append("comments")
                
            file_stmt = select(File).where(
                and_(
                    File.task_id == task.id,
                    File.agency_id == context.agency_id,
                    File.visibility == VisibilityEnum.client.value
                )
            ).limit(1)
            file_exists = (await db.execute(file_stmt)).scalar_one_or_none()
            if file_exists:
                blockers.append("files")
                
            if blockers:
                raise HTTPException(
                    status_code=400, 
                    detail={"error": "Visibility transition blocked", "blockers": blockers}
                )
            
    for key, value in update_data.items():
        if hasattr(value, "value"): # Unpack enums
            setattr(task, key, value.value)
        else:
            setattr(task, key, value)
            
    await db.commit()
    await db.refresh(task)
    
    return task

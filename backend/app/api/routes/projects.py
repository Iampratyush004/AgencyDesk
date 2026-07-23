from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, and_, delete, update, func
from sqlalchemy.ext.asyncio import AsyncSession
import sqlalchemy.exc

from app.database import get_db
from app.api.deps import TenantContext, get_current_tenant_context, require_roles
from app.api.project_access import get_authorized_project
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse,
    ProjectMembershipCreate, ProjectMembershipResponse,
    ProjectDashboardStaffResponse, ProjectDashboardClientResponse, DashboardTaskCounts
)
from app.models.project import Project, ProjectMembership
from app.models.client import Client
from app.models.agency import AgencyMembership
from app.models.task import Task
from app.models.time_entry import TimeEntry
from app.models.enums import RoleEnum, TaskStatusEnum, VisibilityEnum

router = APIRouter()

@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    context: TenantContext = Depends(get_current_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Project).where(Project.agency_id == context.agency_id)

    if context.role == RoleEnum.agency_member.value:
        stmt = stmt.join(
            ProjectMembership,
            and_(
                ProjectMembership.project_id == Project.id,
                ProjectMembership.user_id == context.user.id
            )
        )
    elif context.role == RoleEnum.client_user.value:
        stmt = stmt.where(Project.client_id == context.client_id)

    stmt = stmt.order_by(Project.created_at.desc(), Project.id.desc()).offset(skip).limit(limit)

    result = await db.execute(stmt)
    projects = result.scalars().all()

    return list(projects)

@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    payload: ProjectCreate,
    context: TenantContext = Depends(require_roles([RoleEnum.agency_admin.value])),
    db: AsyncSession = Depends(get_db)
):
    # Validate the client BEFORE creating the project
    client_result = await db.execute(
        select(Client).where(
            and_(
                Client.id == payload.client_id,
                Client.agency_id == context.agency_id
            )
        )
    )
    client = client_result.scalar_one_or_none()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    project = Project(
        agency_id=context.agency_id,
        client_id=payload.client_id,
        name=payload.name,
        description=payload.description
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    return project

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    context: TenantContext = Depends(get_current_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    project = await get_authorized_project(project_id, context, db)
    return project

@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    context: TenantContext = Depends(require_roles([RoleEnum.agency_admin.value])),
    db: AsyncSession = Depends(get_db)
):
    project = await get_authorized_project(project_id, context, db)

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(project, key, value)

    await db.commit()
    await db.refresh(project)

    return project

@router.post("/{project_id}/members", response_model=ProjectMembershipResponse, status_code=201)
async def create_project_membership(
    project_id: UUID,
    payload: ProjectMembershipCreate,
    context: TenantContext = Depends(require_roles([RoleEnum.agency_admin.value])),
    db: AsyncSession = Depends(get_db)
):
    # Ensure project exists and belongs to the agency
    project = await get_authorized_project(project_id, context, db)

    # Check for existing membership (idempotency)
    existing_result = await db.execute(
        select(ProjectMembership).where(
            and_(
                ProjectMembership.project_id == project.id,
                ProjectMembership.user_id == payload.user_id
            )
        )
    )
    existing_membership = existing_result.scalar_one_or_none()

    if existing_membership:
        return existing_membership

    # Validate target user is an active agency staff member in the same agency
    membership_result = await db.execute(
        select(AgencyMembership).where(
            and_(
                AgencyMembership.user_id == payload.user_id,
                AgencyMembership.agency_id == context.agency_id,
                AgencyMembership.is_active == True,
                AgencyMembership.role.in_([RoleEnum.agency_admin.value, RoleEnum.agency_member.value])
            )
        )
    )
    target_membership = membership_result.scalar_one_or_none()

    if not target_membership:
        raise HTTPException(status_code=404, detail="Eligible agency staff member not found")

    project_membership = ProjectMembership(
        user_id=payload.user_id,
        project_id=project.id,
        agency_id=context.agency_id
    )
    try:
        db.add(project_membership)
        await db.commit()
        await db.refresh(project_membership)
        return project_membership
    except sqlalchemy.exc.IntegrityError:
        await db.rollback()

        # Re-query for the membership to see if it was the unique constraint race
        race_result = await db.execute(
            select(ProjectMembership).where(
                and_(
                    ProjectMembership.project_id == project.id,
                    ProjectMembership.user_id == payload.user_id
                )
            )
        )
        race_membership = race_result.scalar_one_or_none()

        if race_membership:
            return race_membership

        # If it wasn't a duplicate race, something else failed; re-raise
        raise

@router.delete("/{project_id}/members/{user_id}", status_code=204)
async def remove_project_member(
    project_id: UUID,
    user_id: UUID,
    context: TenantContext = Depends(require_roles([RoleEnum.agency_admin.value])),
    db: AsyncSession = Depends(get_db)
):
    # Ensure project exists and belongs to the agency
    project = await get_authorized_project(project_id, context, db)

    # Check for existing membership
    existing_result = await db.execute(
        select(ProjectMembership).where(
            and_(
                ProjectMembership.project_id == project.id,
                ProjectMembership.user_id == user_id,
                ProjectMembership.agency_id == context.agency_id
            )
        )
    )
    existing_membership = existing_result.scalar_one_or_none()

    if not existing_membership:
        raise HTTPException(status_code=404, detail="Project membership not found")

    try:
        # 1. Unassign tasks
        update_stmt = (
            update(Task)
            .where(
                and_(
                    Task.project_id == project.id,
                    Task.agency_id == context.agency_id,
                    Task.assignee_id == user_id
                )
            )
            .values(assignee_id=None, updated_at=func.now())
        )
        await db.execute(update_stmt)

        # 2. Delete project membership
        delete_stmt = (
            delete(ProjectMembership)
            .where(
                and_(
                    ProjectMembership.project_id == project.id,
                    ProjectMembership.user_id == user_id,
                    ProjectMembership.agency_id == context.agency_id
                )
            )
        )
        await db.execute(delete_stmt)

        await db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception:
        await db.rollback()
        raise

@router.get("/{project_id}/dashboard", response_model=ProjectDashboardStaffResponse | ProjectDashboardClientResponse)
async def get_project_dashboard(
    project_id: UUID,
    context: TenantContext = Depends(get_current_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    project = await get_authorized_project(project_id, context, db)

    stmt = (
        select(Task.status, func.count(Task.id))
        .where(
            and_(
                Task.project_id == project.id,
                Task.agency_id == context.agency_id
            )
        )
    )
    if context.role == RoleEnum.client_user.value:
        stmt = stmt.where(Task.visibility == VisibilityEnum.client.value)

    stmt = stmt.group_by(Task.status)
    result = await db.execute(stmt)
    status_counts = dict(result.all())

    task_counts = DashboardTaskCounts(
        todo=status_counts.get(TaskStatusEnum.todo.value, 0),
        in_progress=status_counts.get(TaskStatusEnum.in_progress.value, 0),
        review=status_counts.get(TaskStatusEnum.review.value, 0),
        done=status_counts.get(TaskStatusEnum.done.value, 0)
    )

    if context.role == RoleEnum.client_user.value:
        return ProjectDashboardClientResponse(task_counts=task_counts)

    time_stmt = select(func.coalesce(func.sum(TimeEntry.duration_minutes), 0)).where(
        and_(
            TimeEntry.project_id == project.id,
            TimeEntry.agency_id == context.agency_id
        )
    )
    time_result = await db.execute(time_stmt)
    hours_logged = time_result.scalar_one()

    return ProjectDashboardStaffResponse(
        task_counts=task_counts,
        hours_logged=hours_logged
    )

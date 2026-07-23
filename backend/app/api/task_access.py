from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.task import Task
from app.models.project import Project, ProjectMembership
from app.models.agency import AgencyMembership
from app.models.enums import RoleEnum, VisibilityEnum
from app.api.deps import TenantContext

async def get_authorized_task(task_id: UUID, context: TenantContext, db: AsyncSession) -> Task:
    stmt = (
        select(Task)
        .join(Project, and_(Task.project_id == Project.id, Task.agency_id == Project.agency_id))
        .where(
            and_(
                Task.id == task_id,
                Task.agency_id == context.agency_id,
                Project.agency_id == context.agency_id
            )
        )
    )

    if context.role == RoleEnum.agency_member.value:
        stmt = stmt.join(
            ProjectMembership,
            and_(
                ProjectMembership.project_id == Project.id,
                ProjectMembership.user_id == context.user.id,
                ProjectMembership.agency_id == context.agency_id
            )
        )
    elif context.role == RoleEnum.client_user.value:
        stmt = stmt.where(
            and_(
                Project.client_id == context.client_id,
                Task.visibility == VisibilityEnum.client.value
            )
        )

    result = await db.execute(stmt)
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task

async def validate_task_assignee(assignee_id: UUID, project_id: UUID, context: TenantContext, db: AsyncSession):
    # AgencyMembership must exist, active, role in (agency_admin, agency_member)
    # ProjectMembership must exist
    stmt = (
        select(AgencyMembership)
        .join(
            ProjectMembership,
            and_(
                ProjectMembership.user_id == AgencyMembership.user_id,
                ProjectMembership.agency_id == AgencyMembership.agency_id
            )
        )
        .where(
            and_(
                AgencyMembership.user_id == assignee_id,
                AgencyMembership.agency_id == context.agency_id,
                AgencyMembership.is_active == True,
                AgencyMembership.role.in_([RoleEnum.agency_admin.value, RoleEnum.agency_member.value]),
                ProjectMembership.project_id == project_id
            )
        )
    )
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=400, detail="Invalid task assignee")

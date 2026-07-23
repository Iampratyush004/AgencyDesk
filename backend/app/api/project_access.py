from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, ProjectMembership
from app.models.enums import RoleEnum
from app.api.deps import TenantContext

async def get_authorized_project(project_id: UUID, context: TenantContext, db: AsyncSession) -> Project:
    stmt = select(Project).where(
        and_(
            Project.id == project_id,
            Project.agency_id == context.agency_id
        )
    )

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
        
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    return project

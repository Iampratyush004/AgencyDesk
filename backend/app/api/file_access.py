from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.deps import TenantContext
from app.models.file import File
from app.models.task import Task
from app.models.project import Project, ProjectMembership
from app.models.enums import RoleEnum, VisibilityEnum

async def get_authorized_file(file_id: UUID, context: TenantContext, db: AsyncSession) -> File:
    stmt = (
        select(File)
        .options(joinedload(File.task).joinedload(Task.project))
        .where(
            and_(
                File.id == file_id,
                File.agency_id == context.agency_id
            )
        )
    )
    result = await db.execute(stmt)
    file = result.scalar_one_or_none()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
        
    task = file.task
    project = task.project
    
    if context.role == RoleEnum.agency_admin.value:
        return file
        
    if context.role == RoleEnum.agency_member.value:
        mem_stmt = select(ProjectMembership).where(
            and_(
                ProjectMembership.user_id == context.user.id,
                ProjectMembership.project_id == project.id,
                ProjectMembership.agency_id == context.agency_id
            )
        )
        mem = (await db.execute(mem_stmt)).scalar_one_or_none()
        if not mem:
            raise HTTPException(status_code=404, detail="File not found")
        return file
        
    if context.role == RoleEnum.client_user.value:
        if file.visibility != VisibilityEnum.client.value:
            raise HTTPException(status_code=404, detail="File not found")
        if project.client_id != context.client_id:
            raise HTTPException(status_code=404, detail="File not found")
        return file
        
    raise HTTPException(status_code=404, detail="File not found")

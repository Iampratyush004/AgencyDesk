from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import TenantContext, get_current_tenant_context, require_roles
from app.api.task_access import get_authorized_task
from app.schemas.time_entry import TimeEntryCreate, TimeEntryResponse
from app.models.time_entry import TimeEntry
from app.models.enums import RoleEnum

router = APIRouter()

# Dependency enforcing that only agency_admin and agency_member can access time entries
agency_staff_only = Depends(require_roles([RoleEnum.agency_admin.value, RoleEnum.agency_member.value]))

@router.get("/tasks/{task_id}/time-entries", response_model=list[TimeEntryResponse], dependencies=[agency_staff_only])
async def list_time_entries(
    task_id: UUID,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    context: TenantContext = Depends(get_current_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    task = await get_authorized_task(task_id, context, db)
    
    stmt = (
        select(TimeEntry)
        .where(
            and_(
                TimeEntry.task_id == task.id,
                TimeEntry.agency_id == context.agency_id
            )
        )
        .order_by(TimeEntry.date.desc(), TimeEntry.created_at.desc(), TimeEntry.id.desc())
        .offset(skip)
        .limit(limit)
    )
    
    result = await db.execute(stmt)
    entries = result.scalars().all()
    return list(entries)

@router.post("/tasks/{task_id}/time-entries", response_model=TimeEntryResponse, status_code=201, dependencies=[agency_staff_only])
async def create_time_entry(
    task_id: UUID,
    payload: TimeEntryCreate,
    context: TenantContext = Depends(get_current_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    task = await get_authorized_task(task_id, context, db)
    
    time_entry = TimeEntry(
        task_id=task.id,
        project_id=task.project_id,
        agency_id=context.agency_id,
        user_id=context.user.id,
        duration_minutes=payload.duration_minutes,
        date=payload.date,
        note=payload.note
    )
    
    db.add(time_entry)
    await db.commit()
    await db.refresh(time_entry)
    
    return time_entry

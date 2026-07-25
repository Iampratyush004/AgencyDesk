import os
import uuid
from typing import Annotated
from uuid import UUID
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File as FastAPIFile, Form
from fastapi.responses import FileResponse as FastAPIFileResponse
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.database import get_db
from app.config import settings
from app.api.deps import TenantContext, get_current_tenant_context, require_roles
from app.api.task_access import get_authorized_task
from app.api.file_access import get_authorized_file
from app.schemas.file import FileResponse, FileApprovalResponse, FileApprovalCreate
from app.models.file import File, FileApproval
from app.models.enums import RoleEnum, VisibilityEnum

router = APIRouter()

agency_staff_only = Depends(require_roles([RoleEnum.agency_admin.value, RoleEnum.agency_member.value]))
client_only = Depends(require_roles([RoleEnum.client_user.value]))

@router.get("/tasks/{task_id}/files", response_model=list[FileResponse])
async def list_files(
    task_id: UUID,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    context: TenantContext = Depends(get_current_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    task = await get_authorized_task(task_id, context, db)
    
    stmt = select(File).where(
        and_(
            File.task_id == task.id,
            File.agency_id == context.agency_id
        )
    ).options(selectinload(File.approvals))
    
    if context.role == RoleEnum.client_user.value:
        stmt = stmt.where(File.visibility == VisibilityEnum.client.value)
        
    stmt = (
        stmt.order_by(File.created_at.desc(), File.id.desc())
        .offset(skip)
        .limit(limit)
    )
    
    result = await db.execute(stmt)
    entries = result.scalars().all()
    return list(entries)

@router.post("/tasks/{task_id}/files", response_model=FileResponse, status_code=201, dependencies=[agency_staff_only])
async def upload_file(
    task_id: UUID,
    file: UploadFile = FastAPIFile(...),
    visibility: VisibilityEnum = Form(VisibilityEnum.internal),
    context: TenantContext = Depends(get_current_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    task = await get_authorized_task(task_id, context, db)
    visibility_value = visibility.value
    
    if visibility_value == VisibilityEnum.client.value and task.visibility == VisibilityEnum.internal.value:
        raise HTTPException(status_code=400, detail="Cannot upload client-visible file to internal task")
        
    storage_path = str(uuid.uuid4())
    storage_root = Path(settings.FILE_STORAGE_ROOT).resolve()
    os.makedirs(storage_root, exist_ok=True)
    
    physical_path = storage_root / storage_path
    file_size_bytes = 0
    
    try:
        with open(physical_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                f.write(chunk)
                file_size_bytes += len(chunk)
                
        file_record = File(
            task_id=task.id,
            agency_id=context.agency_id,
            uploaded_by_id=context.user.id,
            filename=file.filename or "unknown",
            storage_path=storage_path,
            mime_type=file.content_type,
            file_size_bytes=file_size_bytes,
            visibility=visibility_value
        )

        db.add(file_record)
        await db.commit()

        stmt = select(File).where(File.id == file_record.id).options(selectinload(File.approvals))
        result = await db.execute(stmt)
        return result.scalar_one()
    except Exception:
        physical_path.unlink(missing_ok=True)
        raise

@router.get("/files/{file_id}/download")
async def download_file(
    file_id: UUID,
    context: TenantContext = Depends(get_current_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    file = await get_authorized_file(file_id, context, db)
    
    storage_root = Path(settings.FILE_STORAGE_ROOT).resolve()
    resolved_path = (storage_root / file.storage_path).resolve()
    
    if not resolved_path.is_relative_to(storage_root):
        raise HTTPException(status_code=404, detail="File not found")
        
    if not resolved_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
        
    return FastAPIFileResponse(
        path=str(resolved_path),
        filename=file.filename,
        media_type=file.mime_type or "application/octet-stream"
    )

@router.post("/files/{file_id}/approvals", response_model=FileApprovalResponse, dependencies=[client_only])
async def approve_file(
    file_id: UUID,
    payload: FileApprovalCreate,
    context: TenantContext = Depends(get_current_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    file = await get_authorized_file(file_id, context, db)
    
    stmt = insert(FileApproval).values(
        file_id=file.id,
        agency_id=context.agency_id,
        reviewer_id=context.user.id,
        status=payload.status,
        note=payload.note
    ).on_conflict_do_update(
        index_elements=['file_id', 'reviewer_id'],
        set_={"status": payload.status, "note": payload.note}
    ).returning(FileApproval)
    
    result = await db.execute(stmt)
    await db.commit()
    approval = result.scalar_one()
    
    return approval

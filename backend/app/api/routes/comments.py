from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import TenantContext, get_current_tenant_context
from app.api.task_access import get_authorized_task
from app.schemas.comment import CommentCreate, CommentResponse
from app.models.comment import Comment
from app.models.enums import RoleEnum, VisibilityEnum

router = APIRouter()

@router.get("/tasks/{task_id}/comments", response_model=list[CommentResponse])
async def list_comments(
    task_id: UUID,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    context: TenantContext = Depends(get_current_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    task = await get_authorized_task(task_id, context, db)
    
    stmt = select(Comment).where(
        and_(
            Comment.task_id == task.id,
            Comment.agency_id == context.agency_id
        )
    )
    
    if context.role == RoleEnum.client_user.value:
        stmt = stmt.where(Comment.visibility == VisibilityEnum.client.value)
        
    stmt = stmt.order_by(Comment.created_at.asc(), Comment.id.asc()).offset(skip).limit(limit)
    
    result = await db.execute(stmt)
    comments = result.scalars().all()
    return list(comments)

@router.post("/tasks/{task_id}/comments", response_model=CommentResponse, status_code=201)
async def create_comment(
    task_id: UUID,
    payload: CommentCreate,
    context: TenantContext = Depends(get_current_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    task = await get_authorized_task(task_id, context, db)
    
    visibility = payload.visibility.value if hasattr(payload.visibility, "value") else payload.visibility
    
    if context.role == RoleEnum.client_user.value:
        visibility = VisibilityEnum.client.value
    else:
        if visibility == VisibilityEnum.client.value and task.visibility == VisibilityEnum.internal.value:
            raise HTTPException(
                status_code=400, 
                detail="Cannot create a client-visible comment on an internal task"
            )
            
    comment = Comment(
        task_id=task.id,
        agency_id=context.agency_id,
        author_id=context.user.id,
        content=payload.content,
        visibility=visibility
    )
    
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    
    return comment

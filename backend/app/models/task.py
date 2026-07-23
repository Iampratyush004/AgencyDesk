import uuid
from datetime import datetime, date
from sqlalchemy import String, Text, Date, DateTime, ForeignKey, ForeignKeyConstraint, func, text, UniqueConstraint, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import TaskStatusEnum, TaskPriorityEnum, VisibilityEnum

class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("id", "agency_id", name="uq_tasks_id_agency"), # For composite FKs
        ForeignKeyConstraint(
            ["project_id", "agency_id"],
            ["projects.id", "projects.agency_id"],
            name="fk_tasks_project_agency",
            ondelete="CASCADE"
        ),
        CheckConstraint("status IN ('todo', 'in_progress', 'review', 'done')", name="chk_tasks_status"),
        CheckConstraint("priority IN ('low', 'medium', 'high', 'urgent')", name="chk_tasks_priority"),
        CheckConstraint("visibility IN ('internal', 'client')", name="chk_tasks_visibility"),
        Index("ix_tasks_agency_project_visibility", "agency_id", "project_id", "visibility"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    agency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="todo", server_default=text("'todo'"))
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="medium", server_default=text("'medium'"))
    visibility: Mapped[str] = mapped_column(String(10), nullable=False, default="internal", server_default=text("'internal'"))
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True,
        index=True
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=func.now(), 
        onupdate=func.now()
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="tasks")
    assignee: Mapped["User"] = relationship("User")
    comments: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="task", cascade="all, delete-orphan"
    )
    files: Mapped[list["File"]] = relationship(
        "File", back_populates="task", cascade="all, delete-orphan"
    )
    time_entries: Mapped[list["TimeEntry"]] = relationship(
        "TimeEntry", back_populates="task", cascade="all, delete-orphan"
    )

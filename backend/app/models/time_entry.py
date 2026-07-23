import uuid
from datetime import datetime, date
from sqlalchemy import String, Text, Date, Integer, DateTime, ForeignKey, ForeignKeyConstraint, func, text, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

class TimeEntry(Base):
    __tablename__ = "time_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id", "agency_id"],
            ["tasks.id", "tasks.agency_id"],
            name="fk_time_entries_task_agency",
            ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["project_id", "agency_id"],
            ["projects.id", "projects.agency_id"],
            name="fk_time_entries_project_agency"
            # Explicitly not adding CASCADE here because the architecture 
            # specifies time_entries cascade from tasks, not projects directly.
        ),
        CheckConstraint("duration_minutes > 0", name="chk_time_entries_duration"),
        Index("ix_time_entries_agency_project", "agency_id", "project_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=text("gen_random_uuid()")
    )
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    agency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="RESTRICT"), 
        nullable=False,
        index=True
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=func.now()
    )

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="time_entries")
    project: Mapped["Project"] = relationship("Project")
    user: Mapped["User"] = relationship("User")

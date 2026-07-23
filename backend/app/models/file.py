import uuid
from datetime import datetime
from sqlalchemy import String, BigInteger, Text, DateTime, ForeignKey, ForeignKeyConstraint, func, text, UniqueConstraint, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import VisibilityEnum, FileApprovalStatusEnum

class File(Base):
    __tablename__ = "files"
    __table_args__ = (
        UniqueConstraint("id", "agency_id", name="uq_files_id_agency"), # For composite FKs
        ForeignKeyConstraint(
            ["task_id", "agency_id"],
            ["tasks.id", "tasks.agency_id"],
            name="fk_files_task_agency",
            ondelete="CASCADE"
        ),
        CheckConstraint("visibility IN ('internal', 'client')", name="chk_files_visibility"),
        Index("ix_files_task_visibility", "task_id", "visibility"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=text("gen_random_uuid()")
    )
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    agency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="RESTRICT"), 
        nullable=False
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    visibility: Mapped[str] = mapped_column(String(10), nullable=False, default="internal", server_default=text("'internal'"))
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=func.now()
    )

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="files")
    uploaded_by: Mapped["User"] = relationship("User")
    approvals: Mapped[list["FileApproval"]] = relationship(
        "FileApproval", back_populates="file", cascade="all, delete-orphan"
    )

class FileApproval(Base):
    __tablename__ = "file_approvals"
    __table_args__ = (
        UniqueConstraint("file_id", "reviewer_id", name="uq_file_approvals_file_reviewer"),
        ForeignKeyConstraint(
            ["file_id", "agency_id"],
            ["files.id", "files.agency_id"],
            name="fk_file_approvals_file_agency",
            ondelete="CASCADE"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=text("gen_random_uuid()")
    )
    file_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    agency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="RESTRICT"), 
        nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=func.now()
    )

    # Relationships
    file: Mapped["File"] = relationship("File", back_populates="approvals")
    reviewer: Mapped["User"] = relationship("User")

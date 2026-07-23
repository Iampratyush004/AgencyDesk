import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, ForeignKeyConstraint, func, text, UniqueConstraint, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ProjectStatusEnum

class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("id", "agency_id", name="uq_projects_id_agency"), # For composite FKs
        UniqueConstraint("agency_id", "client_id", "name", name="uq_projects_agency_client_name"),
        ForeignKeyConstraint(
            ["client_id", "agency_id"],
            ["clients.id", "clients.agency_id"],
            name="fk_projects_client_agency",
            ondelete="RESTRICT"
        ),
        CheckConstraint("status IN ('active', 'archived', 'completed')", name="chk_projects_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=text("gen_random_uuid()")
    )
    agency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default=text("'active'"))
    
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
    client: Mapped["Client"] = relationship("Client", back_populates="projects")
    memberships: Mapped[list["ProjectMembership"]] = relationship(
        "ProjectMembership", back_populates="project", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["Task"]] = relationship(
        "Task", back_populates="project", cascade="all, delete-orphan"
    )

class ProjectMembership(Base):
    __tablename__ = "project_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "project_id", name="uq_project_memberships_user_project"),
        ForeignKeyConstraint(
            ["project_id", "agency_id"],
            ["projects.id", "projects.agency_id"],
            name="fk_project_memberships_project_agency",
            ondelete="CASCADE"
        ),
        Index("ix_project_memberships_agency_project", "agency_id", "project_id")
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="RESTRICT"), 
        nullable=False,
        index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    agency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="project_memberships")
    project: Mapped["Project"] = relationship("Project", back_populates="memberships")

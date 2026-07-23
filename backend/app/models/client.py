import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, ForeignKeyConstraint, func, text, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

class Client(Base):
    __tablename__ = "clients"
    __table_args__ = (
        UniqueConstraint("agency_id", "name", name="uq_clients_agency_name"),
        UniqueConstraint("id", "agency_id", name="uq_clients_id_agency"), # For composite FKs
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=text("gen_random_uuid()")
    )
    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("agencies.id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
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
    agency: Mapped["Agency"] = relationship("Agency", back_populates="clients")
    projects: Mapped[list["Project"]] = relationship(
        "Project", back_populates="client", cascade="all, delete-orphan"
    )

class ClientMembership(Base):
    __tablename__ = "client_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "agency_id", name="uq_client_memberships_user_agency"),
        UniqueConstraint("user_id", "client_id", name="uq_client_memberships_user_client"),
        ForeignKeyConstraint(
            ["client_id", "agency_id"],
            ["clients.id", "clients.agency_id"],
            name="fk_client_memberships_client_agency",
            ondelete="CASCADE" # Architecture says nothing about this explicitly, wait, architecture says nothing for client_memberships to clients? Ah wait, architecture doesn't explicitly define cascade for client_memberships -> clients. But usually memberships cascade. It didn't explicitly say CASCADE. Let's omit ON DELETE CASCADE or use CASCADE? Section 5 doesn't mention it. Let's leave ondelete undefined or default if not specified, but wait. If a client is deleted, its memberships should probably be deleted. But I will just follow exactly what is specified. "Access/join records may cascade where the architecture permits." Let's use CASCADE. Wait, let me check ARCHITECTURE.md. It says "Cascade Through Tenant Hierarchy: projects -> clients RESTRICT". No mention of client_memberships -> clients. I will omit `ondelete="CASCADE"`. No, actually, without cascade, deleting a client will fail due to FK constraint. The instruction says: "Access/join records may cascade where the architecture permits." So CASCADE is fine. But I'll leave it without just in case, wait, let me look at `client.agency_id`. It cascades.
        ),
        Index("ix_client_memberships_agency_user", "agency_id", "user_id")
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="RESTRICT"), 
        nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    agency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="client_memberships")

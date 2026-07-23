import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey, func, text, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import RoleEnum

class Agency(Base):
    __tablename__ = "agencies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    
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
    memberships: Mapped[list["AgencyMembership"]] = relationship(
        "AgencyMembership", back_populates="agency", cascade="all, delete-orphan"
    )
    clients: Mapped[list["Client"]] = relationship(
        "Client", back_populates="agency", cascade="all, delete-orphan"
    )

class AgencyMembership(Base):
    __tablename__ = "agency_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "agency_id", name="uq_agency_memberships_user_agency"),
        CheckConstraint("role IN ('agency_admin', 'agency_member', 'client_user')", name="chk_agency_memberships_role"),
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
    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("agencies.id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="agency_memberships")
    agency: Mapped["Agency"] = relationship("Agency", back_populates="memberships")

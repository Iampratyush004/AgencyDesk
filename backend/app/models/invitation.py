import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, ForeignKeyConstraint, func, text, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import RoleEnum, InvitationStatusEnum

class Invitation(Base):
    __tablename__ = "invitations"
    __table_args__ = (
        CheckConstraint("role IN ('agency_admin', 'agency_member', 'client_user')", name="chk_invitations_role"),
        CheckConstraint("status IN ('pending', 'accepted', 'expired', 'revoked')", name="chk_invitations_status"),
        Index("uq_pending_invitation", "agency_id", "email", unique=True, postgresql_where=text("status = 'pending'")),
        ForeignKeyConstraint(
            ["client_id", "agency_id"],
            ["clients.id", "clients.agency_id"],
            name="fk_invitations_client_agency",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=text("gen_random_uuid()")
    )
    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("agencies.id", ondelete="CASCADE"), 
        nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), 
        nullable=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default=text("'pending'"))
    invited_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="RESTRICT"), 
        nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=func.now()
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    agency: Mapped["Agency"] = relationship("Agency")
    client: Mapped["Client"] = relationship("Client")
    invited_by: Mapped["User"] = relationship("User")

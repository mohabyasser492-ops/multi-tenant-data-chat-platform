import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from models.role import Role, UserRole
    from models.tenant import Tenant


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "email",
            name="uq_users_tenant_email",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    full_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    password_hash: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
        server_default="active",
    )
    is_tenant_admin: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    tenant: Mapped["Tenant"] = relationship(
        back_populates="users",
    )
    user_roles: Mapped[list["UserRole"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    roles: Mapped[list["Role"]] = relationship(
        secondary="user_roles",
        viewonly=True,
        overlaps="user_roles,role,users",
    )

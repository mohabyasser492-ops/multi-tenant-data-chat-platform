import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.mixins import TimestampWithoutUpdateMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from models.tenant import Tenant
    from models.user import User


class Role(UUIDPrimaryKeyMixin, TimestampWithoutUpdateMixin, Base):
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "name",
            name="uq_roles_tenant_name",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    tenant: Mapped["Tenant"] = relationship(
        back_populates="roles",
    )
    user_roles: Mapped[list["UserRole"]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
    )
    users: Mapped[list["User"]] = relationship(
        secondary="user_roles",
        viewonly=True,
        overlaps="user_roles,user,roles",
    )


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship(
        back_populates="user_roles",
        overlaps="roles,users",
    )
    role: Mapped["Role"] = relationship(
        back_populates="user_roles",
        overlaps="roles,users",
    )

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from models.role import Role
    from models.user import User


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
        server_default="active",
    )
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    users: Mapped[list["User"]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    roles: Mapped[list["Role"]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

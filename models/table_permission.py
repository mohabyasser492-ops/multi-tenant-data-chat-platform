import uuid
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from db.mixins import TimestampWithoutUpdateMixin, UUIDPrimaryKeyMixin


class TablePermission(
    UUIDPrimaryKeyMixin,
    TimestampWithoutUpdateMixin,
    Base,
):
    __tablename__ = "table_permissions"
    __table_args__ = (
        CheckConstraint(
            """
            (
                role_id IS NOT NULL
                AND user_id IS NULL
            )
            OR
            (
                role_id IS NULL
                AND user_id IS NOT NULL
            )
            """,
            name="permission_subject",
        ),
        UniqueConstraint(
            "role_id",
            "table_id",
            name="uq_table_permissions_role_table",
        ),
        UniqueConstraint(
            "user_id",
            "table_id",
            name="uq_table_permissions_user_table",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "tenants.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    role_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "roles.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "database_connections.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "database_tables.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    can_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    can_insert: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    can_update: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    can_delete: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    row_filter: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )


class ColumnPermission(
    UUIDPrimaryKeyMixin,
    TimestampWithoutUpdateMixin,
    Base,
):
    __tablename__ = "column_permissions"
    __table_args__ = (
        UniqueConstraint(
            "table_permission_id",
            "column_id",
            name="uq_column_permissions_table_permission_column",
        ),
    )

    table_permission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "table_permissions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    column_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "database_columns.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    can_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    can_filter: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    can_aggregate: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    mask_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

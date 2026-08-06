import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class DatabaseConnection(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    __tablename__ = "database_connections"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "name",
            name="uq_database_connections_tenant_name",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    database_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    host: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    port: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    database_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    username: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    encrypted_password: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    encrypted_connection_string: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    ssl_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    ssl_settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    connection_options: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    last_tested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_test_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    schema_sync_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    last_schema_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

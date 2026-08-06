"""use timezone aware connection timestamps

Revision ID: 1b0af03b18c3
Revises: dd14ffb4ba72
Create Date: 2026-08-06 04:54:58.991079

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1b0af03b18c3"
down_revision: str | Sequence[str] | None = "dd14ffb4ba72"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "database_connections",
        "last_tested_at",
        existing_type=sa.DateTime(timezone=False),
        type_=sa.DateTime(timezone=True),
        postgresql_using="last_tested_at AT TIME ZONE 'UTC'",
        existing_nullable=True,
    )
    op.alter_column(
        "database_connections",
        "last_schema_sync_at",
        existing_type=sa.DateTime(timezone=False),
        type_=sa.DateTime(timezone=True),
        postgresql_using="last_schema_sync_at AT TIME ZONE 'UTC'",
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "database_connections",
        "last_schema_sync_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(timezone=False),
        postgresql_using=("last_schema_sync_at AT TIME ZONE 'UTC'"),
        existing_nullable=True,
    )
    op.alter_column(
        "database_connections",
        "last_tested_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(timezone=False),
        postgresql_using="last_tested_at AT TIME ZONE 'UTC'",
        existing_nullable=True,
    )

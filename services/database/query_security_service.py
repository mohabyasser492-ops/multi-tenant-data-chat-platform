import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from core.permissions import AllowedSchema
from models.user import User
from services.database.effective_permission_service import (
    build_permission_filtered_schema,
)
from services.database.query_validator import (
    SQLValidationResult,
    validate_sql,
)
from services.database.row_filter_service import (
    RowFilterError,
    inject_mandatory_row_filters,
)


@dataclass(slots=True)
class SecureQueryResult:
    sql: str
    referenced_tables: list[str]
    referenced_columns: list[str]
    applied_limit: int
    row_filters_applied: bool


class QuerySecurityError(ValueError):
    """Raised when SQL cannot pass the security pipeline."""


def require_valid_result(
    result: SQLValidationResult,
    *,
    stage: str,
) -> None:
    if result.is_valid:
        return

    error_message = result.errors[0] if result.errors else "SQL validation failed."

    raise QuerySecurityError(f"{stage}: {error_message}")


def prepare_validated_sql(
    *,
    sql: str,
    allowed_schema: AllowedSchema,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    dialect: str = "postgres",
    maximum_rows: int = 100,
) -> SecureQueryResult:
    if not allowed_schema.tables:
        raise QuerySecurityError(
            "The authenticated user has no readable database tables."
        )

    initial_validation = validate_sql(
        sql=sql,
        allowed_schema=allowed_schema,
        dialect=dialect,
        maximum_rows=maximum_rows,
    )

    require_valid_result(
        initial_validation,
        stage="Initial SQL validation failed",
    )

    if initial_validation.normalized_sql is None:
        raise QuerySecurityError("Initial SQL validation produced no executable SQL.")

    has_mandatory_filters = any(
        table.row_filters for table in allowed_schema.tables.values()
    )

    try:
        secured_sql = inject_mandatory_row_filters(
            sql=initial_validation.normalized_sql,
            allowed_schema=allowed_schema,
            tenant_id=tenant_id,
            user_id=user_id,
            dialect=dialect,
        )
    except RowFilterError as exc:
        raise QuerySecurityError(
            f"Mandatory row-filter injection failed: {exc}"
        ) from exc

    final_validation = validate_sql(
        sql=secured_sql,
        allowed_schema=allowed_schema,
        dialect=dialect,
        maximum_rows=maximum_rows,
    )

    require_valid_result(
        final_validation,
        stage="Final SQL validation failed",
    )

    if final_validation.normalized_sql is None:
        raise QuerySecurityError("Final SQL validation produced no executable SQL.")

    if final_validation.applied_limit is None:
        raise QuerySecurityError("The secured query has no valid result limit.")

    return SecureQueryResult(
        sql=final_validation.normalized_sql,
        referenced_tables=final_validation.referenced_tables,
        referenced_columns=final_validation.referenced_columns,
        applied_limit=final_validation.applied_limit,
        row_filters_applied=has_mandatory_filters,
    )


async def prepare_secure_query(
    *,
    session: AsyncSession,
    current_user: User,
    connection_id: uuid.UUID,
    sql: str,
) -> SecureQueryResult:
    allowed_schema = await build_permission_filtered_schema(
        session=session,
        current_user=current_user,
        connection_id=connection_id,
    )

    return prepare_validated_sql(
        sql=sql,
        allowed_schema=allowed_schema,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        dialect="postgres",
        maximum_rows=settings.sql_default_row_limit,
    )

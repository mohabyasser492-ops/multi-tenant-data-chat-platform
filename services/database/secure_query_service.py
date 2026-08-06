import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from models.user import User
from services.database.connection_service import (
    get_database_connection,
)
from services.database.effective_permission_service import (
    build_permission_filtered_schema,
)
from services.database.query_executor import (
    QueryExecutionResult,
    execute_secured_query,
)
from services.database.query_security_service import (
    SecureQueryResult,
    prepare_validated_sql,
)


@dataclass(slots=True)
class SecureQueryExecution:
    security: SecureQueryResult
    execution: QueryExecutionResult


async def run_secure_query(
    *,
    session: AsyncSession,
    current_user: User,
    connection_id: uuid.UUID,
    proposed_sql: str,
) -> SecureQueryExecution:
    connection = await get_database_connection(
        session=session,
        current_user=current_user,
        connection_id=connection_id,
    )

    if not connection.is_active:
        raise ValueError("The selected database connection is disabled.")

    if connection.status != "connected":
        raise ValueError(
            "The selected database connection must be tested "
            "successfully before query execution."
        )

    allowed_schema = await build_permission_filtered_schema(
        session=session,
        current_user=current_user,
        connection_id=connection_id,
    )

    security_result = prepare_validated_sql(
        sql=proposed_sql,
        allowed_schema=allowed_schema,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        dialect="postgres",
        maximum_rows=settings.sql_default_row_limit,
    )

    execution_result = await execute_secured_query(
        connection=connection,
        sql=security_result.sql,
        allowed_schema=allowed_schema,
        timeout_seconds=settings.sql_timeout_seconds,
        maximum_result_bytes=settings.sql_max_result_bytes,
    )

    return SecureQueryExecution(
        security=security_result,
        execution=execution_result,
    )

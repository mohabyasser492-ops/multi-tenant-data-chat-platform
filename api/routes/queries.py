import uuid

from fastapi import APIRouter, HTTPException, status

from app.dependencies import CurrentUser, DatabaseSession
from schemas.query import (
    SecureQueryRequest,
    SecureQueryResponse,
)
from services.database.connection_service import (
    DatabaseConnectionNotFoundError,
)
from services.database.query_executor import (
    QueryExecutionError,
    QueryExecutionTimeoutError,
    QueryResultTooLargeError,
)
from services.database.query_security_service import (
    QuerySecurityError,
)
from services.database.secure_query_service import (
    run_secure_query,
)

router = APIRouter(
    prefix="/database-connections",
    tags=["Secure Queries"],
)


@router.post(
    "/{connection_id}/query",
    response_model=SecureQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate and execute a secure read-only query",
)
async def execute_secure_query_endpoint(
    connection_id: uuid.UUID,
    request: SecureQueryRequest,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> SecureQueryResponse:
    try:
        result = await run_secure_query(
            session=session,
            current_user=current_user,
            connection_id=connection_id,
            proposed_sql=request.sql,
        )
    except DatabaseConnectionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Database connection was not found.",
        ) from exc
    except QuerySecurityError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except QueryExecutionTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The secured query execution timed out.",
        ) from exc
    except QueryResultTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=("The query result exceeded the configured size limit."),
        ) from exc
    except QueryExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The secured query could not be executed.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return SecureQueryResponse(
        connection_id=connection_id,
        secured_sql=result.security.sql,
        columns=result.execution.columns,
        rows=result.execution.rows,
        row_count=result.execution.row_count,
        result_size_bytes=(result.execution.result_size_bytes),
        execution_time_ms=(result.execution.execution_time_ms),
        truncated=result.execution.truncated,
        referenced_tables=(result.security.referenced_tables),
        referenced_columns=(result.security.referenced_columns),
        applied_limit=result.security.applied_limit,
        row_filters_applied=(result.security.row_filters_applied),
    )

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import CurrentUser, DatabaseSession
from schemas.audit import (
    AuditLogListResponse,
    AuditLogResponse,
)
from services.audit_service import (
    list_audit_logs,
)
from services.database.connection_service import (
    TenantAdministratorRequiredError,
)

router = APIRouter(
    prefix="/audit-logs",
    tags=["Audit Logs"],
)


@router.get(
    "",
    response_model=AuditLogListResponse,
    status_code=status.HTTP_200_OK,
    summary="List tenant audit events",
)
async def list_audit_logs_endpoint(
    session: DatabaseSession,
    current_user: CurrentUser,
    action: Annotated[
        str | None,
        Query(min_length=1, max_length=100),
    ] = None,
    outcome: Annotated[
        str | None,
        Query(min_length=1, max_length=30),
    ] = None,
    user_id: Annotated[
        uuid.UUID | None,
        Query(),
    ] = None,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 50,
) -> AuditLogListResponse:
    try:
        audit_logs, total = await list_audit_logs(
            session=session,
            current_user=current_user,
            action=action,
            outcome=outcome,
            user_id=user_id,
            offset=offset,
            limit=limit,
        )
    except TenantAdministratorRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant administrator access is required.",
        ) from exc

    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(audit_log) for audit_log in audit_logs],
        total=total,
    )

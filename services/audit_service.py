import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from models.conversation import AuditLog
from models.user import User
from repositories.audit_logs import (
    create_audit_log_record,
    list_audit_log_records,
)
from services.database.connection_service import (
    require_tenant_administrator,
)

SENSITIVE_METADATA_KEYS = {
    "access_token",
    "authorization",
    "connection_string",
    "encrypted_connection_string",
    "encrypted_password",
    "fernet_key",
    "jwt_secret_key",
    "password",
    "password_hash",
    "refresh_token",
    "secret",
    "token",
}


def sanitize_audit_metadata(
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    if not metadata:
        return {}

    sanitized: dict[str, Any] = {}

    for key, value in metadata.items():
        normalized_key = key.lower()

        if normalized_key in SENSITIVE_METADATA_KEYS:
            sanitized[key] = "[REDACTED]"
            continue

        if isinstance(value, dict):
            sanitized[key] = sanitize_audit_metadata(value)
            continue

        if isinstance(value, list):
            sanitized[key] = [
                sanitize_audit_metadata(item) if isinstance(item, dict) else item
                for item in value
            ]
            continue

        sanitized[key] = value

    return sanitized


async def record_audit_event(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID | None,
    outcome: str,
    metadata: dict[str, Any] | None = None,
    request_id: str | None = None,
    client_ip: str | None = None,
    commit: bool = True,
) -> AuditLog:
    audit_log = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        request_id=request_id,
        client_ip=client_ip,
        audit_metadata=sanitize_audit_metadata(metadata),
    )

    return await create_audit_log_record(
        session=session,
        audit_log=audit_log,
        commit=commit,
    )


async def list_audit_logs(
    *,
    session: AsyncSession,
    current_user: User,
    action: str | None,
    outcome: str | None,
    user_id: uuid.UUID | None,
    offset: int,
    limit: int,
) -> tuple[list[AuditLog], int]:
    require_tenant_administrator(current_user)

    return await list_audit_log_records(
        session=session,
        tenant_id=current_user.tenant_id,
        action=action,
        outcome=outcome,
        user_id=user_id,
        offset=offset,
        limit=limit,
    )

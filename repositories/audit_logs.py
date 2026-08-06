import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.conversation import AuditLog


async def create_audit_log_record(
    *,
    session: AsyncSession,
    audit_log: AuditLog,
    commit: bool = True,
) -> AuditLog:
    session.add(audit_log)

    if commit:
        await session.commit()
    else:
        await session.flush()

    await session.refresh(audit_log)

    return audit_log


async def list_audit_log_records(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    action: str | None,
    outcome: str | None,
    user_id: uuid.UUID | None,
    offset: int,
    limit: int,
) -> tuple[list[AuditLog], int]:
    filters = [
        AuditLog.tenant_id == tenant_id,
    ]

    if action is not None:
        filters.append(AuditLog.action == action)

    if outcome is not None:
        filters.append(AuditLog.outcome == outcome)

    if user_id is not None:
        filters.append(AuditLog.user_id == user_id)

    items_result = await session.execute(
        select(AuditLog)
        .where(*filters)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    total_result = await session.execute(
        select(func.count(AuditLog.id)).where(*filters)
    )

    return (
        list(items_result.scalars().all()),
        total_result.scalar_one(),
    )

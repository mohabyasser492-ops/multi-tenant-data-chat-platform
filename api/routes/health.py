import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from db.session import AsyncSessionFactory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Check API health",
)
async def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": "multi-tenant-data-chat-platform",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get(
    "/database",
    status_code=status.HTTP_200_OK,
    summary="Check platform database health",
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Platform database is unavailable",
            "content": {
                "application/json": {
                    "example": {"detail": "Platform database is unavailable."}
                }
            },
        }
    },
)
async def database_health_check() -> dict[str, str]:
    try:
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))

        return {
            "status": "healthy",
            "database": "postgresql",
        }

    except Exception as exc:
        logger.warning(
            "Platform database health check failed: %s",
            type(exc).__name__,
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Platform database is unavailable.",
        ) from exc

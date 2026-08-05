from datetime import UTC, datetime

from fastapi import APIRouter, status

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
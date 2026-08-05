from fastapi import FastAPI

from api.router import api_router
from app.config import settings

app = FastAPI(
    title=settings.app_name,
    description=(
        "Secure backend platform for Text-to-SQL, document chat, "
        "and hybrid conversational queries."
    ),
    version="1.0.0",
    debug=settings.debug,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "environment": settings.app_env,
        "status": "running",
        "documentation": "/docs",
    }

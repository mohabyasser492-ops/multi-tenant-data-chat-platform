from fastapi import FastAPI

from api.router import api_router

app = FastAPI(
    title="Multi-Tenant Data Chat Platform",
    description=(
        "Secure backend platform for Text-to-SQL, document chat, "
        "and hybrid conversational queries."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(api_router, prefix="/api")


@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    return {
        "service": "Multi-Tenant Data Chat Platform",
        "status": "running",
        "documentation": "/docs",
    }
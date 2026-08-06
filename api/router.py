from fastapi import APIRouter

from api.routes.auth import router as auth_router
from api.routes.database_connections import (
    router as database_connections_router,
)
from api.routes.database_schema import (
    router as database_schema_router,
)
from api.routes.health import router as health_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(database_connections_router)
api_router.include_router(database_schema_router)
api_router.include_router(health_router)

from fastapi import APIRouter

from api.routes.auth import router as auth_router
from api.routes.conversations import (
    router as conversations_router,
)
from api.routes.database_chat import (
    router as database_chat_router,
)
from api.routes.database_connections import (
    router as database_connections_router,
)
from api.routes.database_schema import (
    router as database_schema_router,
)
from api.routes.documents import router as documents_router
from api.routes.health import router as health_router
from api.routes.knowledge_bases import (
    router as knowledge_bases_router,
)
from api.routes.messages import router as messages_router
from api.routes.permissions import router as permissions_router
from api.routes.queries import router as queries_router
from api.routes.retrieval import (
    router as retrieval_router,
)

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(database_connections_router)
api_router.include_router(database_schema_router)
api_router.include_router(permissions_router)
api_router.include_router(queries_router)
api_router.include_router(knowledge_bases_router)
api_router.include_router(documents_router)
api_router.include_router(retrieval_router)
api_router.include_router(conversations_router)
api_router.include_router(messages_router)
api_router.include_router(database_chat_router)
api_router.include_router(health_router)

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from app.dependencies import CurrentUser, DatabaseSession
from schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
)
from services.database.connection_service import (
    TenantAdministratorRequiredError,
)
from services.document.knowledge_base_service import (
    DuplicateKnowledgeBaseNameError,
    KnowledgeBaseNotFoundError,
    create_knowledge_base,
    get_knowledge_base,
    list_knowledge_bases,
)

router = APIRouter(
    prefix="/knowledge-bases",
    tags=["Knowledge Bases"],
)


@router.post(
    "",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a knowledge base",
)
async def create_knowledge_base_endpoint(
    request: KnowledgeBaseCreate,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> KnowledgeBaseResponse:
    try:
        knowledge_base = await create_knowledge_base(
            session=session,
            current_user=current_user,
            request=request,
        )
    except TenantAdministratorRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant administrator access is required.",
        ) from exc
    except DuplicateKnowledgeBaseNameError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        await session.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The knowledge base could not be created.",
        ) from exc

    return KnowledgeBaseResponse.model_validate(knowledge_base)


@router.get(
    "",
    response_model=KnowledgeBaseListResponse,
    status_code=status.HTTP_200_OK,
    summary="List knowledge bases for the active tenant",
)
async def list_knowledge_bases_endpoint(
    session: DatabaseSession,
    current_user: CurrentUser,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> KnowledgeBaseListResponse:
    knowledge_bases, total = await list_knowledge_bases(
        session=session,
        current_user=current_user,
        offset=offset,
        limit=limit,
    )

    return KnowledgeBaseListResponse(
        items=[
            KnowledgeBaseResponse.model_validate(knowledge_base)
            for knowledge_base in knowledge_bases
        ],
        total=total,
    )


@router.get(
    "/{knowledge_base_id}",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a knowledge base",
)
async def get_knowledge_base_endpoint(
    knowledge_base_id: uuid.UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> KnowledgeBaseResponse:
    try:
        knowledge_base = await get_knowledge_base(
            session=session,
            current_user=current_user,
            knowledge_base_id=knowledge_base_id,
        )
    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base was not found.",
        ) from exc

    return KnowledgeBaseResponse.model_validate(knowledge_base)

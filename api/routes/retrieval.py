import uuid

from fastapi import APIRouter, HTTPException, status

from app.dependencies import CurrentUser, DatabaseSession
from schemas.retrieval import (
    DocumentCitationResponse,
    KnowledgeBaseSearchRequest,
    KnowledgeBaseSearchResponse,
)
from services.document.knowledge_base_service import (
    KnowledgeBaseNotFoundError,
)
from services.document.retrieval_service import (
    DocumentRetrievalError,
    retrieve_relevant_chunks,
)

router = APIRouter(
    prefix="/knowledge-bases",
    tags=["Document Retrieval"],
)


@router.post(
    "/{knowledge_base_id}/search",
    response_model=KnowledgeBaseSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Search embedded knowledge-base documents",
)
async def search_knowledge_base_endpoint(
    knowledge_base_id: uuid.UUID,
    request: KnowledgeBaseSearchRequest,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> KnowledgeBaseSearchResponse:
    try:
        matches = await retrieve_relevant_chunks(
            session=session,
            current_user=current_user,
            knowledge_base_id=knowledge_base_id,
            query=request.query,
            top_k=request.top_k,
            minimum_similarity=(request.minimum_similarity),
        )
    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base was not found.",
        ) from exc
    except DocumentRetrievalError as exc:
        raise HTTPException(
            status_code=(status.HTTP_422_UNPROCESSABLE_CONTENT),
            detail=str(exc),
        ) from exc

    citations = [
        DocumentCitationResponse(
            document_id=match.document_id,
            document_name=match.document_name,
            chunk_id=match.chunk_id,
            chunk_index=match.chunk_index,
            page_number=match.page_number,
            section_title=match.section_title,
            similarity_score=(match.similarity_score),
            content=match.content,
        )
        for match in matches
    ]

    return KnowledgeBaseSearchResponse(
        knowledge_base_id=knowledge_base_id,
        query=request.query,
        matches=citations,
        total=len(citations),
    )

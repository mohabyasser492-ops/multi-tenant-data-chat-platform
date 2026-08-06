import asyncio
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.config import settings


class EmbeddingGenerationError(RuntimeError):
    """Raised when text embeddings cannot be generated safely."""


@lru_cache(maxsize=2)
def load_embedding_model(
    model_name: str,
) -> SentenceTransformer:
    try:
        return SentenceTransformer(model_name)
    except Exception as exc:
        raise EmbeddingGenerationError(
            "The embedding model could not be loaded."
        ) from exc


def generate_embeddings_sync(
    *,
    texts: list[str],
    model_name: str,
    expected_dimension: int,
) -> list[list[float]]:
    if not texts:
        raise EmbeddingGenerationError("At least one text chunk is required.")

    if any(not text.strip() for text in texts):
        raise EmbeddingGenerationError("Empty text chunks cannot be embedded.")

    try:
        model = load_embedding_model(model_name)

        encoded_embeddings = model.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
    except EmbeddingGenerationError:
        raise
    except Exception as exc:
        raise EmbeddingGenerationError(
            "Document embeddings could not be generated."
        ) from exc

    embeddings = [embedding.astype(float).tolist() for embedding in encoded_embeddings]

    if len(embeddings) != len(texts):
        raise EmbeddingGenerationError(
            "The embedding count does not match the chunk count."
        )

    for embedding in embeddings:
        if len(embedding) != expected_dimension:
            raise EmbeddingGenerationError(
                "The generated embedding dimension is invalid."
            )

    return embeddings


async def generate_embeddings(
    *,
    texts: list[str],
    model_name: str | None = None,
    expected_dimension: int | None = None,
) -> list[list[float]]:
    selected_model = model_name or settings.embedding_model
    selected_dimension = expected_dimension or settings.embedding_dimension

    return await asyncio.to_thread(
        generate_embeddings_sync,
        texts=texts,
        model_name=selected_model,
        expected_dimension=selected_dimension,
    )

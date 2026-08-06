import numpy as np
import pytest

from services.document.embedding_service import (
    EmbeddingGenerationError,
    generate_embeddings_sync,
)


class FakeEmbeddingModel:
    def encode(
        self,
        texts: list[str],
        **_: object,
    ) -> np.ndarray:
        return np.array(
            [[0.1, 0.2, 0.3] for _ in texts],
            dtype=float,
        )


def test_embeddings_match_text_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "services.document.embedding_service.load_embedding_model",
        lambda _: FakeEmbeddingModel(),
    )

    embeddings = generate_embeddings_sync(
        texts=[
            "First chunk",
            "Second chunk",
        ],
        model_name="fake-model",
        expected_dimension=3,
    )

    assert len(embeddings) == 2
    assert all(len(embedding) == 3 for embedding in embeddings)


def test_empty_text_list_is_rejected() -> None:
    with pytest.raises(
        EmbeddingGenerationError,
        match="At least one text chunk",
    ):
        generate_embeddings_sync(
            texts=[],
            model_name="fake-model",
            expected_dimension=3,
        )


def test_empty_chunk_is_rejected() -> None:
    with pytest.raises(
        EmbeddingGenerationError,
        match="Empty text chunks",
    ):
        generate_embeddings_sync(
            texts=["Valid chunk", "   "],
            model_name="fake-model",
            expected_dimension=3,
        )


def test_invalid_dimension_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "services.document.embedding_service.load_embedding_model",
        lambda _: FakeEmbeddingModel(),
    )

    with pytest.raises(
        EmbeddingGenerationError,
        match="embedding dimension is invalid",
    ):
        generate_embeddings_sync(
            texts=["Chunk text"],
            model_name="fake-model",
            expected_dimension=384,
        )

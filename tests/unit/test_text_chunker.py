import pytest

from services.document.text_chunker import (
    TextChunkingError,
    chunk_extracted_document,
    estimate_token_count,
    split_text_with_overlap,
)
from services.document.text_extractor import (
    ExtractedDocument,
    ExtractedSection,
)


def test_short_text_produces_one_chunk() -> None:
    chunks = split_text_with_overlap(
        text="Short company policy.",
        chunk_size=100,
        chunk_overlap=20,
    )

    assert chunks == ["Short company policy."]


def test_long_text_produces_multiple_chunks() -> None:
    text = " ".join(f"word-{index}" for index in range(100))

    chunks = split_text_with_overlap(
        text=text,
        chunk_size=120,
        chunk_overlap=20,
    )

    assert len(chunks) > 1
    assert all(chunks)


def test_chunks_respect_maximum_size() -> None:
    text = "A" * 500

    chunks = split_text_with_overlap(
        text=text,
        chunk_size=100,
        chunk_overlap=20,
    )

    assert all(len(chunk) <= 100 for chunk in chunks)


def test_overlap_preserves_context() -> None:
    text = " ".join(f"token{index}" for index in range(60))

    chunks = split_text_with_overlap(
        text=text,
        chunk_size=100,
        chunk_overlap=20,
    )

    assert len(chunks) > 1

    previous_tail = chunks[0][-15:]

    assert previous_tail.strip() in chunks[1] or chunks[0].split()[-1] in chunks[1]


def test_invalid_chunk_size_is_rejected() -> None:
    with pytest.raises(
        TextChunkingError,
        match="Chunk size must be positive",
    ):
        split_text_with_overlap(
            text="content",
            chunk_size=0,
            chunk_overlap=0,
        )


def test_negative_overlap_is_rejected() -> None:
    with pytest.raises(
        TextChunkingError,
        match="cannot be negative",
    ):
        split_text_with_overlap(
            text="content",
            chunk_size=100,
            chunk_overlap=-1,
        )


def test_overlap_must_be_smaller_than_size() -> None:
    with pytest.raises(
        TextChunkingError,
        match="smaller than chunk size",
    ):
        split_text_with_overlap(
            text="content",
            chunk_size=100,
            chunk_overlap=100,
        )


def test_document_sections_keep_metadata() -> None:
    document = ExtractedDocument(
        sections=[
            ExtractedSection(
                text="First policy section.",
                page_number=2,
                section_title="Leave Policy",
                metadata={
                    "source": "policy",
                },
            )
        ],
        page_count=3,
    )

    chunks = chunk_extracted_document(
        document=document,
        chunk_size=100,
        chunk_overlap=20,
    )

    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].page_number == 2
    assert chunks[0].section_title == "Leave Policy"
    assert chunks[0].metadata["source"] == ("policy")


def test_chunk_indices_continue_across_sections() -> None:
    document = ExtractedDocument(
        sections=[
            ExtractedSection(
                text="First section.",
            ),
            ExtractedSection(
                text="Second section.",
            ),
        ]
    )

    chunks = chunk_extracted_document(
        document=document,
        chunk_size=100,
        chunk_overlap=20,
    )

    assert [chunk.chunk_index for chunk in chunks] == [0, 1]


def test_token_count_is_estimated() -> None:
    token_count = estimate_token_count("A" * 40)

    assert token_count == 10

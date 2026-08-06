from dataclasses import dataclass
from typing import Any

from services.document.text_extractor import (
    ExtractedDocument,
    ExtractedSection,
)


class TextChunkingError(ValueError):
    """Raised when extracted text cannot be chunked safely."""


@dataclass(slots=True)
class TextChunk:
    chunk_index: int
    content: str
    token_count: int
    page_number: int | None
    section_title: str | None
    metadata: dict[str, Any]


def estimate_token_count(text: str) -> int:
    if not text:
        return 0

    return max(
        1,
        len(text) // 4,
    )


def split_text_with_overlap(
    *,
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    if chunk_size < 1:
        raise TextChunkingError("Chunk size must be positive.")

    if chunk_overlap < 0:
        raise TextChunkingError("Chunk overlap cannot be negative.")

    if chunk_overlap >= chunk_size:
        raise TextChunkingError("Chunk overlap must be smaller than chunk size.")

    normalized_text = text.strip()

    if not normalized_text:
        return []

    chunks: list[str] = []
    start = 0

    while start < len(normalized_text):
        target_end = min(
            start + chunk_size,
            len(normalized_text),
        )
        end = target_end

        if target_end < len(normalized_text):
            search_start = max(
                start,
                target_end - 150,
            )

            boundary_positions = [
                normalized_text.rfind(
                    "\n",
                    search_start,
                    target_end,
                ),
                normalized_text.rfind(
                    ". ",
                    search_start,
                    target_end,
                ),
                normalized_text.rfind(
                    " ",
                    search_start,
                    target_end,
                ),
            ]

            valid_boundaries = [
                position for position in boundary_positions if position > start
            ]

            if valid_boundaries:
                end = max(valid_boundaries)

                if normalized_text[end : end + 2] == ". ":
                    end += 1

        chunk = normalized_text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(normalized_text):
            break

        next_start = end - chunk_overlap

        if next_start <= start:
            next_start = end

        start = next_start

    return chunks


def chunk_extracted_section(
    *,
    section: ExtractedSection,
    chunk_size: int,
    chunk_overlap: int,
    starting_index: int,
) -> list[TextChunk]:
    section_chunks = split_text_with_overlap(
        text=section.text,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    chunks: list[TextChunk] = []

    for local_index, chunk_content in enumerate(section_chunks):
        chunks.append(
            TextChunk(
                chunk_index=(starting_index + local_index),
                content=chunk_content,
                token_count=estimate_token_count(chunk_content),
                page_number=section.page_number,
                section_title=section.section_title,
                metadata={
                    **section.metadata,
                    "section_chunk_index": local_index,
                },
            )
        )

    return chunks


def chunk_extracted_document(
    *,
    document: ExtractedDocument,
    chunk_size: int,
    chunk_overlap: int,
) -> list[TextChunk]:
    chunks: list[TextChunk] = []

    for section in document.sections:
        section_chunks = chunk_extracted_section(
            section=section,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            starting_index=len(chunks),
        )

        chunks.extend(section_chunks)

    if not chunks:
        raise TextChunkingError("The document produced no text chunks.")

    return chunks

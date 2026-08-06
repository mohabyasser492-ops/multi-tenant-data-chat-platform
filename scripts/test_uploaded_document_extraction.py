import asyncio

from sqlalchemy import select

from db.session import AsyncSessionFactory, engine
from models.knowledge_base import Document
from services.document.text_extractor import (
    extract_document_text,
)
from services.storage.minio_service import (
    minio_storage,
)


async def test_uploaded_document() -> None:
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(Document)
            .where(Document.file_extension == "txt")
            .order_by(Document.created_at.desc())
            .limit(1)
        )
        document = result.scalar_one_or_none()

        if document is None:
            print("No uploaded TXT document was found.")
            return

        content = await minio_storage.download_bytes(object_key=document.storage_key)

        extracted = extract_document_text(
            content=content,
            file_extension=document.file_extension,
        )

        print(f"Document: {document.original_filename}")
        print(f"Sections: {len(extracted.sections)}")
        print("Extracted text:")
        print(extracted.text)


async def main() -> None:
    try:
        await test_uploaded_document()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

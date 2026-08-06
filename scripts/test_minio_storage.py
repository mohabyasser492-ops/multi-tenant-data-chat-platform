import asyncio
import uuid

from services.storage.minio_service import (
    build_document_storage_key,
    minio_storage,
)


async def test_minio_storage() -> None:
    tenant_id = uuid.uuid4()
    knowledge_base_id = uuid.uuid4()
    document_id = uuid.uuid4()

    original_content = b"Temporary MinIO integration test."

    object_key = build_document_storage_key(
        tenant_id=tenant_id,
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
        filename="integration test.txt",
    )

    stored_object = await minio_storage.upload_bytes(
        object_key=object_key,
        content=original_content,
        content_type="text/plain",
    )

    print("Upload successful")
    print(f"Bucket: {stored_object.bucket_name}")
    print(f"Object key: {stored_object.object_key}")
    print(f"Size: {stored_object.size_bytes}")

    downloaded_content = await minio_storage.download_bytes(object_key=object_key)

    if downloaded_content != original_content:
        raise RuntimeError("Downloaded content does not match.")

    print("Download verification successful")

    await minio_storage.delete_object(object_key=object_key)

    print("Deletion successful")


if __name__ == "__main__":
    asyncio.run(test_minio_storage())

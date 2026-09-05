"""Сборка малых чанков в корректный S3 multipart и отмена при сбое."""

import threading
from typing import Any

import pytest
from test_task_008_storage import FakeS3Client, build_client

from app.integrations.storage import S3StorageError


class ComposeClient(FakeS3Client):
    closed = False
    aborted = False

    def create_multipart_upload(self, **kwargs: Any) -> dict[str, str]:
        assert threading.current_thread() is not threading.main_thread()
        return super().create_multipart_upload(**kwargs)

    def abort_multipart_upload(self, **kwargs: Any) -> None:
        self.aborted = True
        super().abort_multipart_upload(**kwargs)

    def close(self) -> None:
        self.closed = True


@pytest.mark.anyio
async def test_small_chunks_are_grouped_above_s3_minimum() -> None:
    fake = ComposeClient()
    storage, _ = build_client(fake)
    payloads = [b"a" * (2 * 1024 * 1024 + 3), b"b" * (4 * 1024 * 1024), b"c" * 321]
    keys = [f"part-{index}" for index in range(3)]
    for key, payload in zip(keys, payloads, strict=True):
        await storage.put_object(key, payload)
    result = await storage.compose_objects(keys, "final", "video/webm")
    assert fake.objects[(result.bucket, result.key)] == b"".join(payloads)
    parts = list(fake.multipart_parts["upload-123"].values())
    assert len(parts) == 2
    assert all(len(part) >= 5 * 1024 * 1024 for part in parts[:-1])
    assert fake.closed and not fake.aborted


@pytest.mark.anyio
async def test_failed_assembly_aborts_multipart_and_closes_client() -> None:
    fake = ComposeClient()
    storage, _ = build_client(fake)
    with pytest.raises(S3StorageError):
        await storage.compose_objects(["missing"], "final", "audio/webm")
    assert fake.aborted and fake.closed
    assert not fake.objects and not fake.multipart_parts

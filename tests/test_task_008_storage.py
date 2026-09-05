"""Tests for TASK-008 S3/MinIO storage wrapper."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from io import BytesIO

from botocore.exceptions import ClientError

from app.config import Settings
from app.integrations import MultipartUpload, MultipartUploadPart, S3StorageClient


class FakeS3Client:
    """In-memory S3-like client for wrapper tests."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.multipart_parts: dict[str, dict[int, bytes]] = defaultdict(dict)
        self.last_kwargs: dict[str, object] = {}
        self.bucket_exists = False

    def head_bucket(self, *, Bucket: str) -> None:
        if not self.bucket_exists:
            raise ClientError({"Error": {"Code": "404"}}, "HeadBucket")

    def create_bucket(self, *, Bucket: str) -> None:
        self.bucket_exists = True

    def put_object(self, **kwargs: object) -> dict[str, str]:
        self.last_kwargs = kwargs
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = kwargs["Body"]  # type: ignore[index]
        return {"ETag": '"etag-put"'}

    def get_object(self, **kwargs: object) -> dict[str, BytesIO]:
        payload = self.objects[(kwargs["Bucket"], kwargs["Key"])]  # type: ignore[index]
        return {"Body": BytesIO(payload)}

    def generate_presigned_url(self, **kwargs: object) -> str:
        self.last_kwargs = kwargs
        return f"https://storage.local/{kwargs['Params']['Bucket']}/{kwargs['Params']['Key']}"  # type: ignore[index]

    def create_multipart_upload(self, **kwargs: object) -> dict[str, str]:
        self.last_kwargs = kwargs
        return {"UploadId": "upload-123"}

    def upload_part(self, **kwargs: object) -> dict[str, str]:
        self.multipart_parts[kwargs["UploadId"]][kwargs["PartNumber"]] = kwargs["Body"]  # type: ignore[index]
        return {"ETag": f'"etag-{kwargs["PartNumber"]}"'}

    def complete_multipart_upload(self, **kwargs: object) -> dict[str, str]:
        key = (kwargs["Bucket"], kwargs["Key"])  # type: ignore[index]
        upload_id = kwargs["UploadId"]  # type: ignore[index]
        parts = kwargs["MultipartUpload"]["Parts"]  # type: ignore[index]
        self.objects[key] = b"".join(
            self.multipart_parts[upload_id][part["PartNumber"]] for part in parts
        )
        return {"ETag": '"etag-complete"'}

    def abort_multipart_upload(self, **kwargs: object) -> None:
        self.multipart_parts.pop(kwargs["UploadId"], None)  # type: ignore[index]


class FakeSession:
    """Session wrapper that returns the fake client and keeps config kwargs."""

    def __init__(self, client_instance: FakeS3Client) -> None:
        self.client_instance = client_instance
        self.last_client_kwargs: dict[str, object] | None = None

    def client(self, service_name: str, **kwargs: object) -> FakeS3Client:
        assert service_name == "s3"
        self.last_client_kwargs = kwargs
        return self.client_instance


def build_client(
    fake_client: FakeS3Client,
    *,
    path_style: bool = True,
) -> tuple[S3StorageClient, FakeSession]:
    settings = Settings(
        _env_file=None,
        s3_endpoint_url="http://minio.local:9000",
        s3_region="us-east-1",
        s3_access_key_id="minioadmin",
        s3_secret_access_key="minioadmin",
        s3_bucket="interviewer-media",
        s3_presigned_url_ttl_seconds=900,
        s3_use_path_style=path_style,
    )
    session = FakeSession(client_instance=fake_client)
    return (
        S3StorageClient(settings=settings, session_factory=lambda: session),  # type: ignore[arg-type]
        session,
    )


def test_put_get_and_presigned_url_roundtrip() -> None:
    fake_client = FakeS3Client()
    client, _ = build_client(fake_client)

    async def run() -> tuple[object, bytes, str]:
        await client.ensure_bucket()
        uploaded = await client.put_object(
            "candidate/audio.txt",
            b"hello-storage",
            content_type="text/plain",
        )
        payload = await client.get_object_bytes("candidate/audio.txt")
        presigned = await client.generate_presigned_get_url("candidate/audio.txt")
        return uploaded, payload, presigned

    uploaded, payload, presigned = asyncio.run(run())

    assert uploaded.bucket == "interviewer-media"
    assert uploaded.key == "candidate/audio.txt"
    assert uploaded.etag == '"etag-put"'
    assert payload == b"hello-storage"
    assert presigned == "https://storage.local/interviewer-media/candidate/audio.txt"
    assert fake_client.bucket_exists is True


def test_multipart_upload_uploads_parts_and_completes_object() -> None:
    fake_client = FakeS3Client()
    client, _ = build_client(fake_client)

    async def run() -> tuple[
        MultipartUpload, MultipartUploadPart, MultipartUploadPart, object, bytes
    ]:
        upload = await client.create_multipart_upload(
            "chunks/audio.webm",
            content_type="audio/webm",
        )
        part_one = await client.upload_part(upload, part_number=1, data=b"chunk-1")
        part_two = await client.upload_part(upload, part_number=2, data=b"chunk-2")
        completed = await client.complete_multipart_upload(upload, [part_two, part_one])
        payload = await client.get_object_bytes("chunks/audio.webm")
        return upload, part_one, part_two, completed, payload

    upload, part_one, part_two, completed, payload = asyncio.run(run())

    assert upload == MultipartUpload(
        bucket="interviewer-media",
        key="chunks/audio.webm",
        upload_id="upload-123",
    )
    assert part_one == MultipartUploadPart(part_number=1, etag='"etag-1"')
    assert part_two == MultipartUploadPart(part_number=2, etag='"etag-2"')
    assert completed.etag == '"etag-complete"'
    assert payload == b"chunk-1chunk-2"


def test_client_builds_boto_config_for_minio_path_style() -> None:
    fake_client = FakeS3Client()
    client, session = build_client(fake_client, path_style=True)

    asyncio.run(client.generate_presigned_get_url("topic/evidence.json"))

    assert session.last_client_kwargs is not None
    assert session.last_client_kwargs["endpoint_url"] == "http://minio.local:9000"
    assert session.last_client_kwargs["aws_access_key_id"] == "minioadmin"
    config = session.last_client_kwargs["config"]
    assert getattr(config, "s3") == {"addressing_style": "path"}


def test_reads_and_writes_run_off_event_loop_and_close_body() -> None:
    import threading

    class ThreadCheckingClient(FakeS3Client):
        body = BytesIO(b"audio")

        def get_object(self, **kwargs: object) -> dict[str, BytesIO]:
            assert threading.current_thread() is not threading.main_thread()
            return {"Body": self.body}

        def put_object(self, **kwargs: object) -> dict[str, str]:
            assert threading.current_thread() is not threading.main_thread()
            return super().put_object(**kwargs)

    fake = ThreadCheckingClient()
    client, _ = build_client(fake)

    async def run() -> None:
        await client.put_object("tts/test.mp3", b"audio")
        assert await client.get_object_bytes("tts/test.mp3") == b"audio"

    asyncio.run(run())
    assert fake.body.closed


def test_missing_object_preserves_s3_error_code() -> None:
    import pytest

    from app.integrations.storage import S3StorageError

    class MissingClient(FakeS3Client):
        def get_object(self, **kwargs: object) -> dict[str, BytesIO]:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")

    client, _ = build_client(MissingClient())
    with pytest.raises(S3StorageError) as error:
        asyncio.run(client.get_object_bytes("tts/missing.mp3"))
    assert error.value.code == "NoSuchKey"
    assert error.value.__cause__ is not None


def test_storage_error_can_be_chained_and_caught() -> None:
    import pytest

    from app.integrations.storage import S3StorageError

    with pytest.raises(S3StorageError) as error:
        try:
            raise ClientError({"Error": {"Code": "XMinioStorageFull"}}, "PutObject")
        except ClientError as exc:
            raise S3StorageError(
                message="S3 operation 'put_object' failed",
                bucket="interviewer-media",
                key="tts/core.mp3",
                code="XMinioStorageFull",
            ) from exc

    assert error.value.code == "XMinioStorageFull"
    assert isinstance(error.value.__cause__, ClientError)

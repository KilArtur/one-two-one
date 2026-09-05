"""S3/MinIO storage wrapper with presigned URLs and multipart uploads."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import boto3.session
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from app.config import Settings, get_settings


@dataclass(slots=True, frozen=True)
class MultipartUpload:
    """Descriptor of an initiated multipart upload."""

    bucket: str
    key: str
    upload_id: str


@dataclass(slots=True, frozen=True)
class MultipartUploadPart:
    """A single uploaded part ready for completion."""

    part_number: int
    etag: str


@dataclass(slots=True, frozen=True)
class S3Object:
    """Stored object metadata returned by the wrapper."""

    bucket: str
    key: str
    etag: str | None = None


@dataclass(slots=True, frozen=True)
class S3StorageError(Exception):
    """Typed storage-layer error for S3-compatible providers."""

    message: str
    bucket: str
    key: str | None = None
    code: str | None = None

    def __str__(self) -> str:
        return self.message


class S3StorageClient:
    """Async facade over a boto3 S3 client."""

    def __init__(
        self,
        settings: Settings | None = None,
        session_factory: type[boto3.session.Session] = boto3.session.Session,
    ) -> None:
        self._settings = settings or get_settings()
        self._session_factory = session_factory

    async def ensure_bucket(self) -> None:
        """Creates the target bucket if it does not exist."""
        self._call(
            "head_bucket",
            error_bucket=self._settings.s3_bucket,
            Bucket=self._settings.s3_bucket,
        )

    async def put_object(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> S3Object:
        """Uploads object bytes into the configured bucket."""
        response = await asyncio.to_thread(
            self._call,
            "put_object",
            error_bucket=self._settings.s3_bucket,
            error_key=key,
            Body=data,
            Bucket=self._settings.s3_bucket,
            ContentType=content_type,
            Key=key,
        )
        return S3Object(
            bucket=self._settings.s3_bucket,
            key=key,
            etag=response.get("ETag"),
        )

    async def get_object_bytes(self, key: str) -> bytes:
        """Downloads object bytes from the configured bucket."""
        response = await asyncio.to_thread(
            self._call,
            "get_object",
            error_bucket=self._settings.s3_bucket,
            error_key=key,
            Bucket=self._settings.s3_bucket,
            Key=key,
        )
        body = response["Body"]
        try:
            return await asyncio.to_thread(body.read)
        finally:
            await asyncio.to_thread(body.close)

    async def generate_presigned_get_url(
        self,
        key: str,
        *,
        expires_in: int | None = None,
    ) -> str:
        """Builds a presigned GET URL for the object."""
        ttl = expires_in or self._settings.s3_presigned_url_ttl_seconds
        return self._call(
            "generate_presigned_url",
            error_bucket=self._settings.s3_bucket,
            error_key=key,
            ClientMethod="get_object",
            Params={"Bucket": self._settings.s3_bucket, "Key": key},
            ExpiresIn=ttl,
        )

    async def create_multipart_upload(
        self,
        key: str,
        *,
        content_type: str = "application/octet-stream",
    ) -> MultipartUpload:
        """Starts a multipart upload and returns its descriptor."""
        response = self._call(
            "create_multipart_upload",
            error_bucket=self._settings.s3_bucket,
            error_key=key,
            Bucket=self._settings.s3_bucket,
            ContentType=content_type,
            Key=key,
        )
        return MultipartUpload(
            bucket=self._settings.s3_bucket,
            key=key,
            upload_id=response["UploadId"],
        )

    async def upload_part(
        self,
        upload: MultipartUpload,
        *,
        part_number: int,
        data: bytes,
    ) -> MultipartUploadPart:
        """Uploads a single multipart chunk."""
        response = self._call(
            "upload_part",
            error_bucket=upload.bucket,
            error_key=upload.key,
            Bucket=upload.bucket,
            Body=data,
            Key=upload.key,
            PartNumber=part_number,
            UploadId=upload.upload_id,
        )
        return MultipartUploadPart(part_number=part_number, etag=response["ETag"])

    async def complete_multipart_upload(
        self,
        upload: MultipartUpload,
        parts: list[MultipartUploadPart],
    ) -> S3Object:
        """Finalizes a multipart upload."""
        response = self._call(
            "complete_multipart_upload",
            error_bucket=upload.bucket,
            error_key=upload.key,
            Bucket=upload.bucket,
            Key=upload.key,
            UploadId=upload.upload_id,
            MultipartUpload={
                "Parts": [
                    {"PartNumber": part.part_number, "ETag": part.etag}
                    for part in sorted(parts, key=lambda item: item.part_number)
                ]
            },
        )
        return S3Object(
            bucket=upload.bucket,
            key=upload.key,
            etag=response.get("ETag"),
        )

    async def abort_multipart_upload(self, upload: MultipartUpload) -> None:
        """Aborts a multipart upload."""
        self._call(
            "abort_multipart_upload",
            error_bucket=upload.bucket,
            error_key=upload.key,
            Bucket=upload.bucket,
            Key=upload.key,
            UploadId=upload.upload_id,
        )

    async def delete_object(self, key: str) -> None:
        """Удаляет объект из бакета (идемпотентно для отсутствующего ключа)."""
        self._call(
            "delete_object",
            error_bucket=self._settings.s3_bucket,
            error_key=key,
            Bucket=self._settings.s3_bucket,
            Key=key,
        )

    async def compose_objects(self, keys: list[str], target: str, content_type: str) -> S3Object:
        """Собирает малые чанки в multipart-части S3 размером минимум 5 MiB."""
        return await asyncio.to_thread(self._compose_objects, keys, target, content_type)

    def _compose_objects(self, keys: list[str], target: str, content_type: str) -> S3Object:
        bucket = self._settings.s3_bucket
        client = self._build_client()
        upload_id = None
        try:
            upload_id = client.create_multipart_upload(
                Bucket=bucket, Key=target, ContentType=content_type
            )["UploadId"]
            parts: list[dict[str, Any]] = []
            buffer = bytearray()

            def send() -> None:
                response = client.upload_part(
                    Bucket=bucket,
                    Key=target,
                    UploadId=upload_id,
                    PartNumber=len(parts) + 1,
                    Body=bytes(buffer),
                )
                parts.append({"PartNumber": len(parts) + 1, "ETag": response["ETag"]})
                buffer.clear()

            for key in keys:
                body = client.get_object(Bucket=bucket, Key=key)["Body"]
                try:
                    while data := body.read(1024 * 1024):
                        buffer.extend(data)
                        if len(buffer) >= 5 * 1024 * 1024:
                            send()
                finally:
                    body.close()
            if buffer:
                send()
            if not parts:
                raise S3StorageError("Cannot assemble empty recording", bucket, target)
            response = client.complete_multipart_upload(
                Bucket=bucket, Key=target, UploadId=upload_id, MultipartUpload={"Parts": parts}
            )
            return S3Object(bucket, target, response.get("ETag"))
        except Exception as exc:
            if upload_id:
                try:
                    client.abort_multipart_upload(Bucket=bucket, Key=target, UploadId=upload_id)
                except (ClientError, BotoCoreError):
                    pass
            raise S3StorageError("Recording assembly failed", bucket, target) from exc
        finally:
            client.close()

    def _build_client(self) -> Any:
        session = self._session_factory()
        return session.client(
            "s3",
            endpoint_url=self._settings.s3_endpoint_url,
            region_name=self._settings.s3_region,
            aws_access_key_id=self._settings.s3_access_key_id,
            aws_secret_access_key=self._settings.s3_secret_access_key,
            config=BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path" if self._settings.s3_use_path_style else "auto"},
            ),
        )

    def _call(
        self,
        operation: str,
        *,
        error_bucket: str,
        error_key: str | None = None,
        **kwargs: Any,
    ) -> Any:
        try:
            return self._invoke(operation, **kwargs)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if operation == "head_bucket" and error_code in {"404", "NoSuchBucket", "NotFound"}:
                self._invoke("create_bucket", Bucket=error_bucket)
                return None
            raise S3StorageError(
                message=f"S3 operation '{operation}' failed",
                bucket=error_bucket,
                key=error_key,
                code=error_code,
            ) from exc
        except BotoCoreError as exc:
            raise S3StorageError(
                message=f"S3 operation '{operation}' failed",
                bucket=error_bucket,
                key=error_key,
            ) from exc

    def _invoke(self, operation: str, **kwargs: Any) -> Any:
        client = self._build_client()
        method = getattr(client, operation)
        return method(**kwargs)


@lru_cache
def get_s3_storage_client() -> S3StorageClient:
    """Returns a cached storage client for the application."""
    return S3StorageClient()

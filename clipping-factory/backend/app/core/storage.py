"""
S3-compatible storage client (MinIO in dev, AWS S3 in prod) with
local filesystem fallback and automatic retry/connection recovery.
"""
import io
import os
import shutil
import time
from pathlib import Path
from typing import BinaryIO

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError, EndpointConnectionError

from app.core.config import get_settings

settings = get_settings()

_LOCAL_FALLBACK = Path(settings.storage_local_path)
_LOCAL_FALLBACK.mkdir(parents=True, exist_ok=True)
_STORAGE_RETRIES = 3
_STORAGE_RETRY_DELAY = 2

_client = None
_storage_available = True


def _make_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.storage_endpoint if not settings.is_production else None,
        aws_access_key_id=settings.storage_access_key,
        aws_secret_access_key=settings.storage_secret_key,
        region_name=settings.storage_region,
        config=Config(
            signature_version="s3v4",
            connect_timeout=10,
            read_timeout=300,
            retries={"max_attempts": 3, "mode": "adaptive"},
            # Keep parts small + aligned so MinIO multipart uploads don't fail
            # with IncompleteBody (Content-Length mismatch on large files).
            multipart_threshold=8 * 1024 * 1024,
            multipart_chunksize=8 * 1024 * 1024,
        ),
        use_ssl=settings.storage_use_ssl,
    )


def _refresh_client():
    global _client, _storage_available
    _client = _make_client()
    _storage_available = True


def get_storage_client():
    global _client, _storage_available
    if _client is None:
        _client = _make_client()
    return _client


def _local_path(bucket: str, key: str) -> Path:
    return _LOCAL_FALLBACK / bucket / key


def _with_retry(fn, *args, **kwargs):
    for attempt in range(1, _STORAGE_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except (EndpointConnectionError, ClientError) as exc:
            if attempt < _STORAGE_RETRIES:
                time.sleep(_STORAGE_RETRY_DELAY * attempt)
                _refresh_client()
                continue
            return None


def _check_connectivity() -> bool:
    global _storage_available
    try:
        client = get_storage_client()
        client.list_buckets()
        _storage_available = True
        return True
    except Exception:
        _storage_available = False
        return False


def ensure_buckets() -> None:
    client = get_storage_client()
    for bucket in [
        settings.storage_bucket_source,
        settings.storage_bucket_clips,
        settings.storage_bucket_deliverables,
    ]:
        local_bucket = _LOCAL_FALLBACK / bucket
        local_bucket.mkdir(parents=True, exist_ok=True)
        for attempt in range(1, _STORAGE_RETRIES + 1):
            try:
                client.head_bucket(Bucket=bucket)
                break
            except ClientError as e:
                if e.response["Error"]["Code"] in ("404", "NoSuchBucket"):
                    try:
                        client.create_bucket(Bucket=bucket)
                        break
                    except Exception:
                        if attempt == _STORAGE_RETRIES:
                            raise
                else:
                    if attempt == _STORAGE_RETRIES:
                        raise
            except EndpointConnectionError:
                if attempt < _STORAGE_RETRIES:
                    time.sleep(_STORAGE_RETRY_DELAY)
                    _refresh_client()
                    continue
                break


def upload_file(
    local_path: str | Path,
    bucket: str,
    key: str,
    content_type: str = "application/octet-stream",
    metadata: dict | None = None,
) -> str:
    local_fp = _local_path(bucket, key)
    local_fp.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(local_path), str(local_fp))

    if not _check_connectivity():
        return key

    client = get_storage_client()
    extra = {"ContentType": content_type}
    if metadata:
        extra["Metadata"] = {k: str(v) for k, v in metadata.items()}

    # Open the file ourselves and pass an explicit ContentLength so MinIO
    # multipart uploads never fail with IncompleteBody (Content-Length
    # mismatch). Retry on that specific error a few times.
    for attempt in range(1, _STORAGE_RETRIES + 1):
        try:
            with open(str(local_path), "rb") as fh:
                size = os.fstat(fh.fileno()).st_size
                fh.seek(0)
                client.upload_fileobj(
                    fh, bucket, key,
                    ExtraArgs={**extra, "ContentLength": size},
                )
            return key
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("IncompleteBody",) and attempt < _STORAGE_RETRIES:
                time.sleep(_STORAGE_RETRY_DELAY * attempt)
                _refresh_client()
                continue
            if attempt < _STORAGE_RETRIES and isinstance(
                exc, (EndpointConnectionError,)
            ):
                time.sleep(_STORAGE_RETRY_DELAY * attempt)
                _refresh_client()
                continue
            # Last attempt: fall back to local-only copy already saved above.
            return key
        except EndpointConnectionError:
            if attempt < _STORAGE_RETRIES:
                time.sleep(_STORAGE_RETRY_DELAY * attempt)
                _refresh_client()
                continue
            return key
    return key


def upload_bytes(
    data: bytes | BinaryIO,
    bucket: str,
    key: str,
    content_type: str = "application/octet-stream",
) -> str:
    local_fp = _local_path(bucket, key)
    local_fp.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        local_fp.write_bytes(data)
    else:
        with open(local_fp, "wb") as f:
            shutil.copyfileobj(data, f)

    if not _check_connectivity():
        return key

    if isinstance(data, bytes):
        data = io.BytesIO(data)
    client = get_storage_client()
    result = _with_retry(client.upload_fileobj, data, bucket, key, ExtraArgs={"ContentType": content_type})
    if result is None:
        pass
    return key


def download_file(bucket: str, key: str, local_path: str | Path) -> Path:
    local_path = Path(local_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)

    local_fp = _local_path(bucket, key)
    if local_fp.exists():
        shutil.copy2(str(local_fp), str(local_path))
        return local_path

    if not _check_connectivity():
        if local_fp.exists():
            shutil.copy2(str(local_fp), str(local_path))
            return local_path
        raise ConnectionError("Storage unavailable and no local fallback copy found")

    client = get_storage_client()
    result = _with_retry(client.download_file, bucket, key, str(local_path))
    if result is None:
        if local_fp.exists():
            shutil.copy2(str(local_fp), str(local_path))
            return local_path
        raise ConnectionError("Failed to download from storage after retries")
    if local_fp.exists():
        local_fp.unlink()
    local_fp.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(local_path), str(local_fp))
    return local_path


def download_bytes(bucket: str, key: str) -> bytes:
    local_fp = _local_path(bucket, key)
    if local_fp.exists():
        return local_fp.read_bytes()

    if not _check_connectivity():
        if local_fp.exists():
            return local_fp.read_bytes()
        raise ConnectionError("Storage unavailable and no local fallback copy found")

    client = get_storage_client()
    result = _with_retry(lambda: client.get_object(Bucket=bucket, Key=key)["Body"].read())
    if result is None:
        if local_fp.exists():
            return local_fp.read_bytes()
        raise ConnectionError("Failed to read from storage after retries")
    local_fp.parent.mkdir(parents=True, exist_ok=True)
    local_fp.write_bytes(result)
    return result


def get_presigned_url(bucket: str, key: str, expiry_seconds: int = 3600) -> str:
    if not _check_connectivity():
        return str(_local_path(bucket, key))
    client = get_storage_client()
    result = _with_retry(
        client.generate_presigned_url,
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expiry_seconds,
    )
    if result is None:
        return str(_local_path(bucket, key))
    return result


def delete_object(bucket: str, key: str) -> None:
    local_fp = _local_path(bucket, key)
    if local_fp.exists():
        local_fp.unlink()
    if _check_connectivity():
        client = get_storage_client()
        _with_retry(client.delete_object, Bucket=bucket, Key=key)


def object_exists(bucket: str, key: str) -> bool:
    local_fp = _local_path(bucket, key)
    if local_fp.exists():
        return True
    if not _check_connectivity():
        return local_fp.exists()
    client = get_storage_client()
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError:
        return False


def list_objects(bucket: str, prefix: str = "") -> list[dict]:
    if _check_connectivity():
        client = get_storage_client()
        paginator = client.get_paginator("list_objects_v2")
        objects = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            objects.extend(page.get("Contents", []))
        return objects
    local_bucket = _LOCAL_FALLBACK / bucket
    if not local_bucket.exists():
        return []
    prefix_path = local_bucket / prefix
    results = []
    for p in prefix_path.rglob("*") if prefix_path.exists() else []:
        if p.is_file():
            rel = p.relative_to(local_bucket)
            results.append({"Key": str(rel), "Size": p.stat().st_size})
    return results


def get_object_size(bucket: str, key: str) -> int:
    local_fp = _local_path(bucket, key)
    if local_fp.exists():
        return local_fp.stat().st_size
    if _check_connectivity():
        client = get_storage_client()
        result = _with_retry(client.head_object, Bucket=bucket, Key=key)
        if result:
            return result["ContentLength"]
    if local_fp.exists():
        return local_fp.stat().st_size
    return 0

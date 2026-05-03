"""Storage backend abstraction for file-service.

Supports local disk storage (dev) and Google Cloud Storage (production / Cloud Run).
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Optional


class StorageBackend(ABC):
    @abstractmethod
    def save(self, file_bytes: bytes, key: str, content_type: Optional[str] = None) -> str:
        """Persist `file_bytes` under `key` and return a public URL."""

    @abstractmethod
    def serve(self, key: str):
        """Return either raw bytes or a redirect URL for serving the object."""

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def url(self, key: str) -> str:
        """Public URL clients should use to fetch the object."""


def _public_base() -> str:
    return os.getenv("FILE_SERVICE_PUBLIC_URL", "http://localhost:8005").rstrip("/")


class LocalStorage(StorageBackend):
    def __init__(self, upload_dir: Optional[str] = None) -> None:
        self.upload_dir = upload_dir or os.getenv("UPLOAD_DIR", "/app/uploads")
        os.makedirs(self.upload_dir, exist_ok=True)

    def _path(self, key: str) -> str:
        # `key` is a forward-slash path like "Resume/foo.pdf"
        return os.path.join(self.upload_dir, *key.split("/"))

    def save(self, file_bytes: bytes, key: str, content_type: Optional[str] = None) -> str:
        path = self._path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(file_bytes)
        return self.url(key)

    def serve(self, key: str):
        path = self._path(key)
        with open(path, "rb") as f:
            return f.read()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if os.path.exists(path):
            os.remove(path)

    def exists(self, key: str) -> bool:
        return os.path.exists(self._path(key))

    def url(self, key: str) -> str:
        return f"{_public_base()}/static/{key}"


class GCSStorage(StorageBackend):
    def __init__(self, bucket_name: Optional[str] = None) -> None:
        from google.cloud import storage  # local import so dev doesn't need it

        self.bucket_name = bucket_name or os.environ["GCS_BUCKET"]
        self._client = storage.Client()
        self._bucket = self._client.bucket(self.bucket_name)

    def _blob(self, key: str):
        return self._bucket.blob(key)

    def save(self, file_bytes: bytes, key: str, content_type: Optional[str] = None) -> str:
        blob = self._blob(key)
        blob.upload_from_string(file_bytes, content_type=content_type or "application/octet-stream")
        return self.url(key)

    def serve(self, key: str) -> str:
        # Return a signed URL (1 hour) — caller redirects to it.
        blob = self._blob(key)
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(hours=1),
            method="GET",
        )

    def delete(self, key: str) -> None:
        blob = self._blob(key)
        if blob.exists():
            blob.delete()

    def exists(self, key: str) -> bool:
        return self._blob(key).exists()

    def url(self, key: str) -> str:
        # Persisted "logical" URL. Frontend hits the file-service /static/<key> route
        # which 302s to a fresh signed URL. We deliberately don't store signed URLs in
        # the DB because they expire.
        return f"{_public_base()}/static/{key}"


_singleton: Optional[StorageBackend] = None


def get_storage() -> StorageBackend:
    global _singleton
    if _singleton is not None:
        return _singleton
    backend = os.getenv("STORAGE_BACKEND", "local").lower()
    if backend == "gcs":
        _singleton = GCSStorage()
    else:
        _singleton = LocalStorage()
    return _singleton

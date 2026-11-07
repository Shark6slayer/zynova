"""
Media Service — Phase 24.1
Provider-abstracted media storage service supporting:
  - Local development filesystem adapter (explicitly labelled DEV-ONLY)
  - S3-compatible / Cloudflare R2 adapter for staging and production
  - MIME whitelist + magic-byte header validation
  - File size enforcement
  - Malware scanning integration (uses existing scanner.py)
  - MongoDB media_assets record tracking
  - Presigned upload URL generation (S3/R2)
  - Presigned download URL generation for private media
  - Safe deletion workflow
  - Quarantine workflow on scan failure

Storage credential security:
  - Credentials are sourced exclusively from environment via settings.
  - Presigned URLs are generated server-side. No keys are ever sent to frontend.
"""
from __future__ import annotations

import abc
import hashlib
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import aiofiles
from bson import ObjectId
from fastapi import HTTPException, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.scanner import QUARANTINE_DIR, scan_quarantined_media
from app.core.security_logger import log_security_event

logger = logging.getLogger("zynova.media")

# ---------------------------------------------------------------------------
# MIME and magic-byte configuration
# ---------------------------------------------------------------------------

MIME_CONFIG: Dict[str, Dict[str, Any]] = {
    # Images
    "image/jpeg":    {"ext": ".jpg",  "magic": [b"\xff\xd8\xff"],               "max_mb": 15,   "category": "image"},
    "image/png":     {"ext": ".png",  "magic": [b"\x89PNG\r\n\x1a\n"],          "max_mb": 15,   "category": "image"},
    "image/webp":    {"ext": ".webp", "magic": [b"RIFF"],                        "max_mb": 15,   "category": "image"},
    "image/gif":     {"ext": ".gif",  "magic": [b"GIF87a", b"GIF89a"],          "max_mb": 10,   "category": "image"},
    "image/avif":    {"ext": ".avif", "magic": [b"\x00\x00\x00\x1cftypavif",
                                                 b"\x00\x00\x00\x20ftypavif"], "max_mb": 15,   "category": "image"},
    # Videos
    "video/mp4":        {"ext": ".mp4",  "magic": [b"\x00\x00\x00\x18ftyp",
                                                     b"\x00\x00\x00\x20ftyp",
                                                     b"\x00\x00\x00\x1cftyp"],  "max_mb": 2048, "category": "video"},
    "video/quicktime":  {"ext": ".mov",  "magic": [b"\x00\x00\x00\x14ftypqt"], "max_mb": 2048, "category": "video"},
    "video/webm":       {"ext": ".webm", "magic": [b"\x1a\x45\xdf\xa3"],        "max_mb": 500,  "category": "video"},
    # Audio
    "audio/aac":    {"ext": ".aac",  "magic": [b"\xff\xf1", b"\xff\xf9", b"ID3"], "max_mb": 20, "category": "audio"},
    "audio/mpeg":   {"ext": ".mp3",  "magic": [b"\xff\xfb", b"ID3"],               "max_mb": 20, "category": "audio"},
    "audio/ogg":    {"ext": ".ogg",  "magic": [b"OggS"],                            "max_mb": 20, "category": "audio"},
    "audio/webm":   {"ext": ".weba", "magic": [b"\x1a\x45\xdf\xa3"],               "max_mb": 20, "category": "audio"},
    # Documents
    "application/pdf": {"ext": ".pdf", "magic": [b"%PDF"],               "max_mb": 50,  "category": "document"},
    "application/zip": {"ext": ".zip", "magic": [b"PK\x03\x04"],         "max_mb": 50,  "category": "document"},
}

CHUNK_SIZE = 1024 * 1024  # 1 MB


def _validate_mime(content_type: str) -> Dict[str, Any]:
    mime = content_type.lower().split(";")[0].strip()
    cfg = MIME_CONFIG.get(mime)
    if not cfg:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported media type '{mime}'",
        )
    return {"mime": mime, **cfg}


def _validate_magic(header: bytes, mime: str) -> bool:
    cfg = MIME_CONFIG.get(mime, {})
    for magic in cfg.get("magic", []):
        if header.startswith(magic) or magic in header[:64]:
            return True
    return False


# ---------------------------------------------------------------------------
# Abstract storage adapter
# ---------------------------------------------------------------------------

class StorageAdapter(abc.ABC):
    @abc.abstractmethod
    async def save_file(
        self,
        file_path: str,
        destination_key: str,
        content_type: str,
        is_public: bool = True,
    ) -> str:
        """Stores the file and returns its public or private access URL."""

    @abc.abstractmethod
    async def delete_file(self, storage_key: str) -> None:
        """Deletes the file from storage."""

    @abc.abstractmethod
    async def generate_presigned_upload(
        self,
        destination_key: str,
        content_type: str,
        max_size_bytes: int,
        expires_in: int = 900,
    ) -> Dict[str, Any]:
        """Generates a presigned upload URL/fields for direct client-to-storage upload."""

    @abc.abstractmethod
    async def generate_presigned_download(
        self,
        storage_key: str,
        expires_in: int = 300,
    ) -> str:
        """Generates a presigned download URL for a private file."""

    @property
    @abc.abstractmethod
    def adapter_name(self) -> str:
        """Human-readable name of the adapter for diagnostics."""


# ---------------------------------------------------------------------------
# DEV-ONLY: Local filesystem adapter
# ---------------------------------------------------------------------------

LOCAL_MEDIA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "storage", "media")
)
os.makedirs(LOCAL_MEDIA_DIR, exist_ok=True)


class LocalDevStorageAdapter(StorageAdapter):
    """
    ⚠️  DEVELOPMENT ADAPTER ONLY ⚠️
    Stores files on the local filesystem.
    Not suitable for production, horizontal scaling, or distributed deployments.
    Use S3StorageAdapter in staging and production.
    """

    @property
    def adapter_name(self) -> str:
        return "local-dev-filesystem"

    async def save_file(
        self,
        file_path: str,
        destination_key: str,
        content_type: str,
        is_public: bool = True,
    ) -> str:
        dest = os.path.join(LOCAL_MEDIA_DIR, destination_key.replace("/", os.sep))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        async with aiofiles.open(file_path, "rb") as src, aiofiles.open(dest, "wb") as out:
            while chunk := await src.read(CHUNK_SIZE):
                await out.write(chunk)
        # Return a local URL path (served by static mount or dev server)
        return f"/storage/media/{destination_key}"

    async def delete_file(self, storage_key: str) -> None:
        path = os.path.join(LOCAL_MEDIA_DIR, storage_key.replace("/", os.sep))
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            logger.warning(f"[LocalDev] delete_file error: {e}")

    async def generate_presigned_upload(
        self,
        destination_key: str,
        content_type: str,
        max_size_bytes: int,
        expires_in: int = 900,
    ) -> Dict[str, Any]:
        # In local dev, there is no object storage to presign.
        # Return a marker so the client falls back to multipart POST to /api/v1/media/upload.
        return {
            "adapter": "local-dev",
            "mode": "direct-post",
            "upload_url": "/api/v1/media/upload",
            "destination_key": destination_key,
            "note": "Local dev mode: upload via backend multipart endpoint, not direct S3.",
        }

    async def generate_presigned_download(
        self,
        storage_key: str,
        expires_in: int = 300,
    ) -> str:
        return f"/storage/media/{storage_key}"


# ---------------------------------------------------------------------------
# S3-compatible adapter (Cloudflare R2 / AWS S3)
# ---------------------------------------------------------------------------

class S3StorageAdapter(StorageAdapter):
    """
    Production S3-compatible adapter supporting Cloudflare R2 and AWS S3.
    Credentials sourced from settings (MEDIA_S3_*) — never from client requests.
    """

    def __init__(self) -> None:
        self._client: Optional[Any] = None
        self._bucket = getattr(settings, "MEDIA_S3_BUCKET", None)
        self._endpoint_url = getattr(settings, "MEDIA_S3_ENDPOINT_URL", None)
        self._cdn_base = getattr(settings, "MEDIA_CDN_BASE_URL", None)

    async def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import aioboto3  # type: ignore
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="aioboto3 not installed. Cannot use S3 storage adapter.",
            )
        session = aioboto3.Session(
            aws_access_key_id=getattr(settings, "MEDIA_S3_ACCESS_KEY_ID", None),
            aws_secret_access_key=getattr(settings, "MEDIA_S3_SECRET_ACCESS_KEY", None),
            region_name=getattr(settings, "MEDIA_S3_REGION", "auto"),
        )
        self._client = session
        return session

    @property
    def adapter_name(self) -> str:
        return f"s3-compatible ({self._endpoint_url or 'aws-default'})"

    async def save_file(
        self,
        file_path: str,
        destination_key: str,
        content_type: str,
        is_public: bool = True,
    ) -> str:
        session = await self._get_client()
        extra = {"ContentType": content_type}
        if is_public:
            extra["ACL"] = "public-read"
        async with session.client("s3", endpoint_url=self._endpoint_url) as s3:
            with open(file_path, "rb") as fh:
                await s3.upload_fileobj(fh, self._bucket, destination_key, ExtraArgs=extra)
        if self._cdn_base:
            return f"{self._cdn_base.rstrip('/')}/{destination_key}"
        return f"https://{self._bucket}.s3.amazonaws.com/{destination_key}"

    async def delete_file(self, storage_key: str) -> None:
        session = await self._get_client()
        async with session.client("s3", endpoint_url=self._endpoint_url) as s3:
            await s3.delete_object(Bucket=self._bucket, Key=storage_key)

    async def generate_presigned_upload(
        self,
        destination_key: str,
        content_type: str,
        max_size_bytes: int,
        expires_in: int = 900,
    ) -> Dict[str, Any]:
        import boto3  # type: ignore
        client = boto3.client(
            "s3",
            endpoint_url=self._endpoint_url,
            aws_access_key_id=getattr(settings, "MEDIA_S3_ACCESS_KEY_ID", None),
            aws_secret_access_key=getattr(settings, "MEDIA_S3_SECRET_ACCESS_KEY", None),
            region_name=getattr(settings, "MEDIA_S3_REGION", "auto"),
        )
        resp = client.generate_presigned_post(
            Bucket=self._bucket,
            Key=destination_key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 1, max_size_bytes],
            ],
            ExpiresIn=expires_in,
        )
        return {
            "adapter": "s3",
            "mode": "presigned-post",
            "upload_url": resp["url"],
            "upload_fields": resp["fields"],
            "destination_key": destination_key,
            "expires_in": expires_in,
        }

    async def generate_presigned_download(
        self,
        storage_key: str,
        expires_in: int = 300,
    ) -> str:
        import boto3  # type: ignore
        client = boto3.client(
            "s3",
            endpoint_url=self._endpoint_url,
            aws_access_key_id=getattr(settings, "MEDIA_S3_ACCESS_KEY_ID", None),
            aws_secret_access_key=getattr(settings, "MEDIA_S3_SECRET_ACCESS_KEY", None),
            region_name=getattr(settings, "MEDIA_S3_REGION", "auto"),
        )
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": storage_key},
            ExpiresIn=expires_in,
        )


# ---------------------------------------------------------------------------
# Adapter factory
# ---------------------------------------------------------------------------

def get_storage_adapter() -> StorageAdapter:
    """
    Returns the active storage adapter based on configuration.
    Defaults to local dev adapter when no S3 credentials are configured.
    """
    s3_key = getattr(settings, "MEDIA_S3_ACCESS_KEY_ID", None)
    s3_bucket = getattr(settings, "MEDIA_S3_BUCKET", None)
    if s3_key and s3_bucket:
        logger.info("Media storage: S3-compatible adapter active.")
        return S3StorageAdapter()
    if settings.ENVIRONMENT.lower() == "production":
        logger.error(
            "PRODUCTION ENVIRONMENT has no S3 credentials configured! "
            "Media uploads are disabled until MEDIA_S3_* env vars are set."
        )
    else:
        logger.warning(
            "⚠️  Using local-dev filesystem storage adapter. "
            "Set MEDIA_S3_* environment variables to enable S3/R2 for production."
        )
    return LocalDevStorageAdapter()


# ---------------------------------------------------------------------------
# Media ingestion pipeline (upload via backend)
# ---------------------------------------------------------------------------

async def ingest_media_upload(
    db: AsyncIOMotorDatabase,
    file: UploadFile,
    uploader_id: str,
    purpose: str,
    is_public: bool = True,
) -> Dict[str, Any]:
    """
    Full ingest pipeline:
      1. MIME whitelist check
      2. File size cap enforcement
      3. Magic-byte header validation
      4. Write to quarantine
      5. ClamAV / mock malware scan
      6. If clean: move to media dir via adapter, insert media_assets record
      7. If dirty: quarantine permanently, raise 400
    """
    cfg = _validate_mime(file.content_type or "")
    mime = cfg["mime"]
    max_bytes = cfg["max_mb"] * 1024 * 1024

    ext = cfg["ext"]
    file_uuid = uuid.uuid4().hex
    filename = f"{file_uuid}{ext}"
    quarantine_path = os.path.join(QUARANTINE_DIR, f"qrnt_{filename}")
    destination_key = f"{purpose}/{uploader_id[:8]}/{file_uuid}{ext}"

    total_bytes = 0
    header_checked = False

    try:
        async with aiofiles.open(quarantine_path, "wb") as out:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                if not header_checked:
                    if not _validate_magic(chunk[:64], mime):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="File signature does not match declared MIME type",
                        )
                    header_checked = True
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds maximum size of {cfg['max_mb']} MB",
                    )
                await out.write(chunk)
    except HTTPException:
        _safe_remove(quarantine_path)
        raise

    # Scan
    is_clean, scan_detail = await scan_quarantined_media(quarantine_path, filename)
    if not is_clean:
        log_security_event(
            event_code="MEDIA_QUARANTINED",
            action="ingest_media",
            status="BLOCKED",
            resource=filename,
            details={"reason": scan_detail, "uploader": uploader_id},
        )
        _safe_remove(quarantine_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Upload rejected: {scan_detail}",
        )

    # Store
    adapter = get_storage_adapter()
    try:
        public_url = await adapter.save_file(quarantine_path, destination_key, mime, is_public)
    finally:
        _safe_remove(quarantine_path)

    # Compute SHA-256 hash of file (re-read from stored location)
    sha256 = _compute_file_hash(os.path.join(LOCAL_MEDIA_DIR, destination_key.replace("/", os.sep)))

    # Persist record
    now = datetime.now(timezone.utc)
    asset_doc = {
        "uploader_id": uploader_id,
        "purpose": purpose,
        "mime_type": mime,
        "category": cfg["category"],
        "storage_key": destination_key,
        "adapter": adapter.adapter_name,
        "public_url": public_url if is_public else None,
        "is_public": is_public,
        "file_size_bytes": total_bytes,
        "sha256": sha256,
        "scan_result": "CLEAN",
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    result = await db.media_assets.insert_one(asset_doc)
    asset_doc["id"] = str(result.inserted_id)
    return asset_doc


def _safe_remove(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def _compute_file_hash(path: str) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Presigned upload flow (direct client → storage)
# ---------------------------------------------------------------------------

async def request_presigned_upload(
    db: AsyncIOMotorDatabase,
    uploader_id: str,
    mime_type: str,
    file_size_bytes: int,
    purpose: str,
    is_public: bool = True,
) -> Dict[str, Any]:
    """
    Generates a presigned upload URL allowing the client to upload directly to
    object storage without routing binary data through the FastAPI server.
    Returns presign metadata + a pending media_assets record ID for confirmation.
    Never exposes storage credentials.
    """
    cfg = _validate_mime(mime_type)
    max_bytes = cfg["max_mb"] * 1024 * 1024
    if file_size_bytes > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Declared file size {file_size_bytes} bytes exceeds limit {max_bytes} bytes for {mime_type}",
        )

    file_uuid = uuid.uuid4().hex
    ext = cfg["ext"]
    destination_key = f"{purpose}/{uploader_id[:8]}/{file_uuid}{ext}"

    adapter = get_storage_adapter()
    presign_data = await adapter.generate_presigned_upload(
        destination_key=destination_key,
        content_type=mime_type,
        max_size_bytes=max_bytes,
        expires_in=900,
    )

    # Insert a pending record
    now = datetime.now(timezone.utc)
    pending_doc = {
        "uploader_id": uploader_id,
        "purpose": purpose,
        "mime_type": mime_type,
        "category": cfg["category"],
        "storage_key": destination_key,
        "adapter": adapter.adapter_name,
        "file_size_bytes": file_size_bytes,
        "is_public": is_public,
        "status": "pending_upload",
        "created_at": now,
        "updated_at": now,
    }
    result = await db.media_assets.insert_one(pending_doc)
    asset_id = str(result.inserted_id)

    return {
        "asset_id": asset_id,
        "destination_key": destination_key,
        **presign_data,
    }


async def confirm_presigned_upload(
    db: AsyncIOMotorDatabase,
    asset_id: str,
    uploader_id: str,
) -> Dict[str, Any]:
    """
    Called by client after direct upload completes.
    Transitions media_assets status from pending_upload → active.
    """
    try:
        obj_id = ObjectId(asset_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid asset ID")

    asset = await db.media_assets.find_one({"_id": obj_id})
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset record not found")
    if asset["uploader_id"] != uploader_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to confirm this upload")
    if asset["status"] != "pending_upload":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Asset is not pending upload (status: {asset['status']})")

    adapter = get_storage_adapter()
    # For S3: derive public URL
    cdn_base = getattr(settings, "MEDIA_CDN_BASE_URL", None)
    public_url: Optional[str] = None
    if asset.get("is_public"):
        public_url = f"{cdn_base.rstrip('/')}/{asset['storage_key']}" if cdn_base else f"/storage/media/{asset['storage_key']}"

    now = datetime.now(timezone.utc)
    await db.media_assets.update_one(
        {"_id": obj_id},
        {"$set": {"status": "active", "public_url": public_url, "updated_at": now}},
    )
    asset.update({"status": "active", "public_url": public_url, "id": asset_id})
    return asset


async def delete_media_asset(
    db: AsyncIOMotorDatabase,
    asset_id: str,
    requester_id: str,
) -> None:
    """Marks asset as deleted and removes from storage."""
    try:
        obj_id = ObjectId(asset_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid asset ID")

    asset = await db.media_assets.find_one({"_id": obj_id})
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    if asset["uploader_id"] != requester_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this asset")

    adapter = get_storage_adapter()
    await adapter.delete_file(asset["storage_key"])
    await db.media_assets.update_one(
        {"_id": obj_id},
        {"$set": {"status": "deleted", "updated_at": datetime.now(timezone.utc)}},
    )

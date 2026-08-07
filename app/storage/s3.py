"""S3 storage backend через boto3: latest + zip snapshot + retention."""
from __future__ import annotations

import io
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..logging import logger
from .base import StorageBackend


class S3StorageBackend(StorageBackend):
    name = "s3"

    def __init__(self, bucket: str, prefix: str, endpoint_url: str = "",
                 access_key_id: str = "", secret_access_key: str = "",
                 region: str = "", verify_ssl: bool = True,
                 snapshot: bool = False, retention_days: int | None = None):
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.snapshot = snapshot
        self.retention_days = retention_days
        self._client = None
        session_kwargs = {}
        if access_key_id:
            session_kwargs["aws_access_key_id"] = access_key_id
            session_kwargs["aws_secret_access_key"] = secret_access_key
        if region:
            session_kwargs["region_name"] = region
        import boto3
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            verify=verify_ssl,
            **session_kwargs,
        )

    def store(self, backup_root: Path, timestamp: str, manifest) -> None:
        kb = backup_root / "knowledge-base"
        # загружаем latest
        logger.info("Uploading to s3")
        for p in kb.rglob("*"):
            if p.is_file():
                key = f"{self.prefix}/latest/knowledge-base/{_rel(p, kb)}"
                self._client.upload_file(str(p), self.bucket, key)
        mf_key = f"{self.prefix}/latest/manifest.json"
        self._client.upload_file(str(backup_root / "manifest.json"), self.bucket, mf_key)
        logger.info("latest uploaded")

        if self.snapshot:
            zip_data = self._make_zip(kb)
            snap_key = f"{self.prefix}/snapshots/{timestamp}/knowledge-base.zip"
            self._client.put_object(Bucket=self.bucket, Key=snap_key, Body=zip_data)
            logger.info("Snapshot created")

        self.cleanup()

    @staticmethod
    def _make_zip(kb: Path) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in kb.rglob("*"):
                if f.is_file():
                    zf.write(f, _rel(f, kb))
        return buf.getvalue()

    def cleanup(self) -> None:
        if not self.retention_days:
            return
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
        # листим snapshots
        prefix = f"{self.prefix}/snapshots/"
        try:
            resp = self._client.list_objects_v2(Bucket=self.bucket, Prefix=prefix,
                                                Delimiter="/")
        except Exception as exc:  # noqa: BLE001
            logger.warn(f"S3 retention list failed: {exc}")
            return
        for common in (resp.get("CommonPrefixes") or []):
            name = common["Prefix"].rstrip("/").split("/")[-1]
            try:
                ts = datetime.strptime(name, "%Y-%m-%dT%H%M%S").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if ts < cutoff:
                logger.info(f"Removing old S3 snapshot {name}")
                objects = self._client.list_objects_v2(
                    Bucket=self.bucket, Prefix=common["Prefix"]).get("Contents", [])
                if objects:
                    self._client.delete_objects(
                        Bucket=self.bucket,
                        Delete={"Objects": [{"Key": o["Key"]} for o in objects]})


def _rel(path: Path, base: Path) -> str:
    return str(path.relative_to(base)).replace("\\", "/")
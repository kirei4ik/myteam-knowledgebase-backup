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
                 snapshot: bool = False, retention_days: int | None = None,
                 retention_count: int | None = None,
                 min_interval_minutes: float = 0):
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.snapshot = snapshot
        self.retention_days = retention_days
        self.retention_count = retention_count
        self.min_interval_minutes = min_interval_minutes
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
        rp_key = f"{self.prefix}/latest/report.md"
        self._client.upload_file(str(backup_root / "report.md"), self.bucket, rp_key)
        logger.info("latest uploaded")

        if self.snapshot:
            snap_key = f"{self.prefix}/snapshots/{timestamp}/knowledge-base.zip"
            if self._should_interval_skip(snap_key):
                logger.info(f"Skipping snapshot (min interval "
                            f"{self.min_interval_minutes:g}m)")
            else:
                zip_data = self._make_zip(kb)
                self._client.put_object(Bucket=self.bucket, Key=snap_key,
                                        Body=zip_data)
                logger.info("Snapshot created")

        self.cleanup()

    def _should_interval_skip(self, snap_key: str) -> bool:
        if self.min_interval_minutes <= 0:
            return False
        try:
            resp = self._client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=f"{self.prefix}/snapshots/",
                Delimiter="/")
        except Exception as exc:  # noqa: BLE001
            logger.warn(f"S3 interval check failed: {exc}")
            return False
        common = resp.get("CommonPrefixes") or []
        # сортируем по LastModified времени создания снапшота
        items = []
        for c in common:
            name = c["Prefix"].rstrip("/").split("/")[-1]
            try:
                ts = datetime.strptime(name, "%Y-%m-%dT%H%M%S").replace(
                    tzinfo=timezone.utc)
            except ValueError:
                continue
            items.append(ts)
        if not items:
            return False
        newest = max(items)
        now_utc = datetime.now(timezone.utc)
        elapsed = (now_utc - newest).total_seconds() / 60
        return elapsed < self.min_interval_minutes

    @staticmethod
    def _make_zip(kb: Path) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in kb.rglob("*"):
                if f.is_file():
                    zf.write(f, _rel(f, kb))
            for name in ("manifest.json", "report.md"):
                src = kb.parent / name
                if src.is_file():
                    zf.write(src, name)
        return buf.getvalue()

    def _list_snapshots(self) -> list[tuple[datetime, str]]:
        """Возвращает [(ts, prefix)] для снапшотов, отсортированные DESC."""
        prefix = f"{self.prefix}/snapshots/"
        try:
            resp = self._client.list_objects_v2(Bucket=self.bucket, Prefix=prefix,
                                                Delimiter="/")
        except Exception as exc:  # noqa: BLE001
            logger.warn(f"S3 retention list failed: {exc}")
            return []
        items: list[tuple[datetime, str]] = []
        for common in (resp.get("CommonPrefixes") or []):
            name = common["Prefix"].rstrip("/").split("/")[-1]
            try:
                ts = datetime.strptime(name, "%Y-%m-%dT%H%M%S").replace(
                    tzinfo=timezone.utc)
            except ValueError:
                continue
            items.append((ts, common["Prefix"]))
        return sorted(items, key=lambda x: x[0], reverse=True)

    def _delete_snapshot(self, prefix: str) -> None:
        objects = self._client.list_objects_v2(
            Bucket=self.bucket, Prefix=prefix).get("Contents", [])
        if objects:
            self._client.delete_objects(
                Bucket=self.bucket,
                Delete={"Objects": [{"Key": o["Key"]} for o in objects]})

    def cleanup(self) -> None:
        if not self.retention_days and self.retention_count is None:
            return
        items = self._list_snapshots()

        if self.retention_days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
            for ts, prefix in items:
                if ts < cutoff:
                    logger.info(f"Removing old S3 snapshot {prefix}")
                    self._delete_snapshot(prefix)

        if self.retention_count is not None and self.retention_count >= 0:
            kept = [p for _, p in self._list_snapshots()]
            for prefix in kept[self.retention_count:]:
                logger.info(f"Removing old S3 snapshot (count) {prefix}")
                self._delete_snapshot(prefix)


def _rel(path: Path, base: Path) -> str:
    return str(path.relative_to(base)).replace("\\", "/")
"""Local storage backend: latest + snapshots zip + retention."""
from __future__ import annotations

import shutil
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from ..logging import logger
from .base import StorageBackend


class LocalStorageBackend(StorageBackend):
    name = "local"

    def __init__(self, backups_dir: str | Path, snapshot: bool = False,
                 retention_days: int | None = None,
                 retention_count: int | None = None,
                 min_interval_minutes: float = 0):
        self.backups_dir = Path(backups_dir)
        self.snapshot = snapshot
        self.retention_days = retention_days
        self.retention_count = retention_count
        self.min_interval_minutes = min_interval_minutes

    def store(self, backup_root: Path, timestamp: str, manifest) -> None:
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        latest_dir = self.backups_dir / "latest"

        # атомарная замена latest через tmp
        staging = self.backups_dir / f".latest-tmp-{timestamp}"
        if staging.exists():
            shutil.rmtree(staging)
        _copy_contents(backup_root, staging)
        logger.info(f"Writing local latest -> {latest_dir}")
        _replace_dir(latest_dir, staging)

        if self.snapshot:
            self._create_snapshot(latest_dir, timestamp, manifest)

        self.cleanup()

    def _snapshot_ts(self, name: str) -> datetime | None:
        try:
            return datetime.strptime(name, "%Y-%m-%dT%H%M%S")
        except ValueError:
            return None

    def _snapshot_dirs(self) -> list[tuple[datetime, Path]]:
        snap_dir = self.backups_dir / "snapshots"
        if not snap_dir.is_dir():
            return []
        found: list[tuple[datetime, Path]] = []
        for snap in snap_dir.iterdir():
            if not snap.is_dir():
                continue
            ts = self._snapshot_ts(snap.name)
            if ts is not None:
                found.append((ts, snap))
        return found

    def _create_snapshot(self, latest_dir: Path, timestamp: str, manifest) -> None:
        # минимальный интервал:
        now = datetime.strptime(timestamp, "%Y-%m-%dT%H%M%S")
        if self.min_interval_minutes > 0:
            newest = max((ts for ts, _ in self._snapshot_dirs()), default=None)
            if newest is not None:
                elapsed = (now - newest).total_seconds() / 60
                if elapsed < self.min_interval_minutes:
                    logger.info(
                        f"Skipping snapshot (last {elapsed:.0f}m ago, "
                        f"min interval {self.min_interval_minutes:g}m)")
                    return
        snap_dir = self.backups_dir / "snapshots" / timestamp
        snap_dir.mkdir(parents=True, exist_ok=True)
        zip_path = snap_dir / "knowledge-base.zip"
        logger.info("Creating snapshot")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            kb = latest_dir / "knowledge-base"
            if kb.is_dir():
                for p in kb.rglob("*"):
                    if p.is_file():
                        zf.write(p, p.relative_to(kb))
            for name in ("manifest.json", "report.md"):
                src = latest_dir / name
                if src.is_file():
                    zf.write(src, name)
        logger.info("Snapshot created")

    def _cleanup(self) -> None:
        found = sorted(self._snapshot_dirs(), key=lambda x: x[0], reverse=True)
        if not found:
            return

        # retention по дням
        if self.retention_days:
            cutoff = datetime.now() - timedelta(days=self.retention_days)
            for ts, snap in found:
                if ts < cutoff:
                    shutil.rmtree(snap, ignore_errors=True)
                    logger.info(f"Removed old snapshot {snap.name} (days)")

        # retention по количеству (оставляем N самых свежих)
        if self.retention_count is not None and self.retention_count >= 0:
            kept = sorted(
                self._snapshot_dirs(), key=lambda x: x[0], reverse=True)
            for _, snap in kept[self.retention_count:]:
                shutil.rmtree(snap, ignore_errors=True)
                logger.info(f"Removed old snapshot {snap.name} (count)")


    def cleanup(self) -> None:
        if not self.retention_days and self.retention_count is None:
            return
        self._cleanup()


def _replace_dir(target: Path, staging: Path) -> None:
    shutil.rmtree(target, ignore_errors=True)
    shutil.move(str(staging), str(target))


def _copy_contents(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)
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
                 retention_days: int | None = None):
        self.backups_dir = Path(backups_dir)
        self.snapshot = snapshot
        self.retention_days = retention_days

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

    def _create_snapshot(self, latest_dir: Path, timestamp: str, manifest) -> None:
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
        logger.info("Snapshot created")

    def cleanup(self) -> None:
        if not self.retention_days:
            return
        snapshots_dir = self.backups_dir / "snapshots"
        if not snapshots_dir.is_dir():
            return
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        for snap in snapshots_dir.iterdir():
            if not snap.is_dir():
                continue
            try:
                ts = datetime.strptime(snap.name, "%Y-%m-%dT%H%M%S")
            except ValueError:
                continue
            if ts < cutoff:
                shutil.rmtree(snap)
                logger.info(f"Removed old snapshot {snap.name}")


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
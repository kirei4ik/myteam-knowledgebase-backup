from __future__ import annotations

import zipfile
from pathlib import Path

from app.storage.local import LocalStorageBackend


def _store(backend: LocalStorageBackend, backup_dir: Path, stamp: str) -> None:
    root = backup_dir / ".stage"
    (root / "knowledge-base").mkdir(parents=True, exist_ok=True)
    (root / "knowledge-base" / "a.md").write_text("# A")
    (root / "manifest.json").write_text("{}")
    (root / "report.md").write_text("# Report")
    backend.store(root, stamp, object())


def _mk_snapshots(d: Path, *stamps: str) -> None:
    for s in stamps:
        (d / "snapshots" / s).mkdir(parents=True, exist_ok=True)


def _snapshot_names(backup_dir: Path) -> list[str]:
    d = backup_dir / "snapshots"
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir() if p.is_dir())


def test_min_interval_skips_snapshot(tmp_path: Path) -> None:
    d = tmp_path / "b"
    backend = LocalStorageBackend(d, snapshot=True, min_interval_minutes=60)
    # первый снапшот создаётся
    _store(backend, d, "2026-08-07T000000")
    assert _snapshot_names(d) == ["2026-08-07T000000"]
    # второй через 30 мин (в пределах 60) — пропуск
    _store(backend, d, "2026-08-07T003000")
    assert _snapshot_names(d) == ["2026-08-07T000000"]
    # спустя 2 часа — создаётся
    _store(backend, d, "2026-08-07T020000")
    assert _snapshot_names(d) == ["2026-08-07T000000", "2026-08-07T020000"]


def test_min_interval_disabled_when_zero(tmp_path: Path) -> None:
    d = tmp_path / "b"
    backend = LocalStorageBackend(d, snapshot=True, min_interval_minutes=0)
    _store(backend, d, "2026-08-07T000000")
    _store(backend, d, "2026-08-07T010000")
    assert _snapshot_names(d) == ["2026-08-07T000000", "2026-08-07T010000"]


def test_latest_contains_report(tmp_path: Path) -> None:
    d = tmp_path / "b"
    backend = LocalStorageBackend(d, snapshot=True)
    _store(backend, d, "2026-08-07T000000")
    assert (d / "latest" / "manifest.json").is_file()
    assert (d / "latest" / "report.md").is_file()


def test_snapshot_zip_contains_report_and_manifest(tmp_path: Path) -> None:
    d = tmp_path / "b"
    backend = LocalStorageBackend(d, snapshot=True)
    _store(backend, d, "2026-08-07T000000")
    zip_path = d / "snapshots" / "2026-08-07T000000" / "knowledge-base.zip"
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
    assert "report.md" in names
    assert "manifest.json" in names
    assert "a.md" in names


def test_retention_by_count(tmp_path: Path) -> None:
    d = tmp_path / "b"
    backend = LocalStorageBackend(d, snapshot=False, retention_count=3)
    _mk_snapshots(d, "2026-08-07T000000", "2026-08-07T010000",
                  "2026-08-07T020000", "2026-08-07T030000", "2026-08-07T040000")
    backend.cleanup()
    assert _snapshot_names(d) == ["2026-08-07T020000", "2026-08-07T030000",
                                  "2026-08-07T040000"]
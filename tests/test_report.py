from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.manifest import Manifest
from app.report import build_report


def _report(backup_dir: Path, manifest: Manifest) -> str:
    build_report(backup_dir, manifest, datetime(2026, 8, 8, 2, 30, 0))
    return (backup_dir / "report.md").read_text(encoding="utf-8")


def test_report_ok(tmp_path: Path) -> None:
    m = Manifest(source="https://kb.example", categories=3, articles=10,
                 images=5, attachments=2)
    m.files = {"1/a.png": "digest"}
    text = _report(tmp_path, m)
    assert "Статус: OK" in text
    assert "Категорий: 3" in text
    assert "Статей: 10" in text
    assert "Картинок: 5" in text
    assert "Вложений: 2" in text
    assert "Файлов: 1" in text
    assert "Ошибки" not in text


def test_report_with_errors(tmp_path: Path) -> None:
    m = Manifest(source="https://kb.example", categories=1, articles=2)
    m.errors.append("group 5: boom")
    m.errors.append("[Статья] fetch failed")
    text = _report(tmp_path, m)
    assert "Статус: Ошибки (2)" in text
    assert "- group 5: boom" in text
    assert "- [Статья] fetch failed" in text
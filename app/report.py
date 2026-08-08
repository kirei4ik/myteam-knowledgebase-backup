"""Формирование человекочитаемого отчёта report.md о прогоне бэкапа."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .manifest import Manifest


def build_report(backup_dir: Path, manifest: Manifest,
                 started_at: datetime) -> None:
    """Пишет report.md в backup_dir рядом с manifest.json."""
    created = manifest.to_dict()["created_at"]
    duration = max(0, (datetime.now() - started_at).total_seconds())
    errors = manifest.errors
    if errors:
        status = f"Ошибки ({len(errors)})"
    else:
        status = "OK"

    lines = [
        "# Отчёт о бэкапе базы знаний",
        "",
        f"- Источник: `{manifest.source}`",
        f"- Время создания: {created}",
        f"- Статус: {status}",
        f"- Длительность: {duration:.1f} с",
        f"- Категорий: {manifest.categories}",
        f"- Статей: {manifest.articles}",
        f"- Картинок: {manifest.images}",
        f"- Вложений: {manifest.attachments}",
        f"- Файлов: {len(manifest.files)}",
    ]

    if errors:
        lines.append("")
        lines.append(f"## Ошибки ({len(errors)})")
        lines.append("")
        for err in errors:
            lines.append(f"- {err}")

    lines.append("")
    (backup_dir / "report.md").write_text(
        "\n".join(lines), encoding="utf-8")
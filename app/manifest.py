"""Формирование manifest.json."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Manifest:
    source: str
    categories: int = 0
    articles: int = 0
    images: int = 0
    attachments: int = 0
    errors: list[str] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "created_at": datetime.now(timezone.utc).astimezone().isoformat(
                timespec="seconds"),
            "source": self.source,
            "categories": self.categories,
            "articles": self.articles,
            "images": self.images,
            "attachments": self.attachments,
            "files": self.files,
            "errors": self.errors,
        }

    def write(self, backup_dir: Path) -> None:
        (backup_dir / "manifest.json").write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8")
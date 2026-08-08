"""Абстракция storage backend."""
from __future__ import annotations

import abc
from pathlib import Path


class StorageBackend(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def store(self, backup_root: Path, timestamp: str, manifest) -> None:
        """Передаёт полностью сформированный backup на хранение.

        backup_root содержит подкаталог `knowledge-base/`, `manifest.json`
        и `report.md`. Операция должна быть атомарной на уровне публикации
        `latest`.
        """
        raise NotImplementedError

    def cleanup(self) -> None:
        """Опциональная очистка устаревших снапшотов (retention)."""
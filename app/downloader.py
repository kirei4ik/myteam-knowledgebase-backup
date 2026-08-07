"""Скачивание картинок и вложений, контрольные суммы."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

from .logging import logger
from .myteam_client import MyTeamClient


class AssetError(Exception):
    """Ошибка скачивания ресурса."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Downloader:
    def __init__(self, client: MyTeamClient, article_dir: Path,
                 fail_on_error: bool,
                 progress: Callable[[str], None] | None = None):
        self.client = client
        self.article_dir = article_dir
        self.fail_on_error = fail_on_error
        self.progress = progress or (lambda msg: None)
        self.errors: list[str] = []
        self.downloaded: dict[str, str] = {}  # локальный путь -> sha256

    def download_to(self, url: str, rel_path: str) -> str | None:
        """Скачивает ресурс по URL в rel_path внутри каталога статьи.

        Возвращает sha256 или None при ошибке (записывает в self.errors).
        """
        target = self.article_dir / rel_path
        safe_rel = rel_path.replace("\\", "/")
        if ".." in Path(safe_rel).parts:
            self.errors.append(f"Unsafe path: {rel_path}")
            return None
        try:
            self.progress(f"Downloading {url}")
            data = self.client.download(url)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            digest = sha256(data)
            self.downloaded[safe_rel] = digest
            logger.info(f"Downloaded {rel_path}")
            return digest
        except Exception as exc:  # noqa: BLE001
            self.errors.append(f"Download {url} -> {rel_path}: {exc}")
            if self.fail_on_error:
                raise AssetError(f"{rel_path}: {exc}") from exc
            return None

    def errors_blocking(self) -> bool:
        return bool(self.errors)
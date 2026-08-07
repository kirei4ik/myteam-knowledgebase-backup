"""Построение структуры базы знаний в рабочем каталоге."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

from .common import sanitize_component
from .downloader import Downloader
from .html_converter import build_markdown
from .logging import logger
from .myteam_client import MyTeamClient
from .redact import redact_credentials, redact_object


class ArticleError(Exception):
    pass


def normalize_date(value: str | None) -> str:
    """'20.08.2025 08:54' -> '2025-08-20 08:54'. Пустые значения не трогаем."""
    if not value:
        return ""
    m = re.match(r"^(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})", value.strip())
    if m:
        day, month, year, hh, mm = m.groups()
        return f"{year}-{month}-{day} {hh}:{mm}"
    return value


def _category_map(groups: list[dict]) -> dict[int, str]:
    return {int(g["id"]): g.get("name", "") for g in groups}


def _dir_name(title: str, article_id: int) -> str:
    """Безопасное имя каталога статьи с ID при конфликте."""
    return sanitize_component(title)


def _author(item: dict) -> str:
    user = item.get("user") or {}
    return user.get("name", "") or ""


def _tags(item: dict) -> list[str]:
    return [str(t) for t in (item.get("tags") or [])]


def front_matter(item: dict, category_name: str) -> str:
    lines = ["---"]
    lines.append(f"myteam_id: {item.get('id')}")
    title = str(item.get("name", ""))
    lines.append(f'title: "{title.replace(chr(34), chr(39))}"')
    lines.append(f"category_id: {(item.get('group') or {}).get('id', '')}")
    lines.append(f'category: "{category_name.replace(chr(34), chr(39))}"')
    author = _author(item)
    if author:
        lines.append(f'author: "{author.replace(chr(34), chr(39))}"')
    created = normalize_date(item.get("createdDate"))
    if created:
        lines.append(f'created: "{created}"')
    updated = normalize_date(item.get("updatedDate"))
    if updated:
        lines.append(f'updated: "{updated}"')
    tags = _tags(item)
    if tags:
        lines.append("tags:")
        for t in tags:
            lines.append(f"  - {t}")
    lines.append("---")
    return "\n".join(lines)


class Exporter:
    def __init__(self, client: MyTeamClient, base_url: str,
                 fail_on_asset_error: bool,
                 redact: bool = True,
                 progress: Callable[[str], None] | None = None):
        self.client = client
        self.base_url = base_url
        self.fail_on_asset_error = fail_on_asset_error
        self.redact = redact
        self.progress = progress or (lambda msg: None)

    def build_tree(self, work_dir: Path, groups: list[dict],
                   articles_by_group: dict[int, list[dict]]) -> list[Path]:
        """Создаёт каталоги категорий. Возвращает список корневых каталогов."""
        roots: list[Path] = []
        for group in groups:
            group_name = group.get("name", "")
            group_dir = work_dir / sanitize_component(group_name)
            group_dir.mkdir(parents=True, exist_ok=True)
            roots.append(group_dir)
        return roots

    def export_article(self, article_dir: Path, item: dict,
                       category_name: str) -> dict:
        """Формирует статью: Markdown, ресурсы, .source.html, .metadata.json.

        Возвращает статистику: {images, attachments, files} и список ошибок.
        """
        article_dir.mkdir(parents=True, exist_ok=True)
        title = str(item.get("name", ""))
        content_html = item.get("content") or ""

        # 0. маскируем креденшиалы в контенте, если включено
        if self.redact:
            content_html = redact_credentials(content_html)

        # 1. HTML -> Markdown, ищем внутренние ресурсы
        result = build_markdown(content_html, self.base_url)
        markdown = result.markdown

        # 2. скачиваем встроенные картинки/видео
        downloader = Downloader(
            self.client, article_dir, self.fail_on_asset_error, self.progress)
        embedded_shas: dict[str, str] = {}
        inline_attachments = 0
        for res in result.resources:
            digest = downloader.download_to(res.url, res.rel_path)
            if digest:
                embedded_shas[res.rel_path] = digest
            if res.tag != "img":
                inline_attachments += 1

        # 3. прикреплённые файлы
        attachment_shas: dict[str, str] = {}
        attachments = item.get("files") or []
        for f in attachments:
            document = f.get("document") or {}
            name = document.get("name", "")
            download_path = document.get("download_path", "")
            if not name or not download_path:
                continue
            safe_name = sanitize_component(name)
            digest = downloader.download_to(self.base_url + download_path, safe_name)
            if digest:
                attachment_shas[safe_name] = digest

        # 4. Markdown: front matter + вложения
        md_parts = [front_matter(item, category_name), "", markdown]
        if attachments:
            md_parts.append("")
            md_parts.append("## Вложения")
            md_parts.append("")
            for f in attachments:
                document = f.get("document") or {}
                name = document.get("name", "")
                if not name:
                    continue
                safe_name = sanitize_component(name)
                md_parts.append(f"- [{name}]({safe_name})")
        md_text = "\n".join(md_parts).rstrip() + "\n"

        safe_title = sanitize_component(title) + ".md"
        (article_dir / safe_title).write_text(md_text, encoding="utf-8")
        (article_dir / ".source.html").write_text(content_html, encoding="utf-8")
        meta = json.loads(json.dumps(item))
        if self.redact:
            redact_object(meta)
        (article_dir / ".metadata.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        logger.info(f"Markdown generated: {title}")
        if downloader.errors:
            logger.error(f"Article {item.get('id')} asset errors: "
                         f"{'; '.join(downloader.errors)}")

        return {
            "id": item.get("id"),
            "title": title,
            "images": len([1 for r in result.resources if r.tag == "img"]),
            "attachments": len(attachment_shas) + inline_attachments,
            "files": {**embedded_shas, **attachment_shas},
            "errors": downloader.errors,
        }
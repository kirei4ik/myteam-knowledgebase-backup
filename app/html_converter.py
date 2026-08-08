"""Преобразование HTML статьи в Markdown и обработка встроенных ресурсов."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from markdownify import markdownify as _markdownify


@dataclass
class EmbeddedResource:
    """Внешний ресурс внутри HTML статьи."""
    tag: str          # img | video | source | a
    attr: str         # src | href
    url: str          # абсолютный URL (внутри хоста)
    rel_path: str     # локальный относительный путь после сохранения


@dataclass
class ConvertResult:
    markdown: str
    resources: list[EmbeddedResource] = field(default_factory=list)
    skipped: int = 0  # количество пропущенных локальных ресурсов (file:// и т.п.)


LOCAL_FILE_PLACEHOLDER = ("[❗ Изображение недоступно: локальный файл у автора, "
                          "на сервере отсутствует]")


def is_internal_url(url: str, base_url: str) -> bool:
    """True, если URL указывает на внутреннее хранилище «МояКоманда»."""
    if not url or url.startswith("data:"):
        return False
    if url.startswith(("http://", "https://")):
        return urlparse(url).netloc == urlparse(base_url).netloc
    if "://" in url:
        return False  # file://, ftp:// и прочие схемы — внешние
    return True  # относительный путь — внутренний


def _is_local_scheme(url: str) -> bool:
    """True, если URL использует не http(s) схему (file://, ftp:// и т.п.)."""
    return "://" in url and not url.startswith(("http://", "https://"))


def _is_downloadable(tag: str, abs_url: str) -> bool:
    """Ресурс можно локально скачать.

    img/video/source всегда при внутреннем URL. <a> — только если ссылка
    ведёт на файловое хранилище (/storage/), а не на страницу сервиса
    (например /knowledge-base/12).
    """
    if tag == "a":
        return "/storage/" in urlparse(abs_url).path
    return True


def _abs_url(url: str, base_url: str) -> str:
    if url.startswith(("http://", "https://")):
        return url
    return f"{base_url}{url}"


def _basename(url: str) -> str:
    path = urlparse(url).path
    name = path.rsplit("/", 1)[-1]
    return name or "file"


def _unique_basename(url: str, used: set[str], default: str) -> str:
    base = _basename(url) or default
    name, ext = base.rsplit(".", 1) if "." in base else (base, "bin")
    candidate, i = base, 1
    while candidate.lower() in used:
        candidate = f"{name}-{i}.{ext}"
        i += 1
    used.add(candidate.lower())
    return candidate


def build_markdown(content_html: str, base_url: str) -> ConvertResult:
    """Конвертирует HTML в Markdown, находя внутренние ресурсы.

    Возвращает Markdown, в котором src/href внутренних ресурсов заменены на
    локальные относительные имена файлов, а также список ресурсов для скачивания.
    """
    soup = BeautifulSoup(content_html or "", "html.parser")
    resources: list[EmbeddedResource] = []
    used_names: set[str] = set()
    skipped = 0

    for node in soup.find_all(["img", "video", "source", "a"]):
        attr = "src" if node.name != "a" else "href"
        raw = (node.get(attr) or node.get("data-src") or "").strip()
        if not raw or raw.startswith("data:"):
            continue
        # локальные файловые схемы (file:// и т.п.) — не скачиваются вовсе,
        # заменяются маркером и попадают в перечень пропущенных.
        if _is_local_scheme(raw):
            if node.name != "a":
                node.replace_with(LOCAL_FILE_PLACEHOLDER)
                skipped += 1
            continue
        if not is_internal_url(raw, base_url):
            continue

        abs_url = _abs_url(raw, base_url)
        if not _is_downloadable(node.name, abs_url):
            continue

        default = f"{node.name}-{len(resources) + 1}"
        filename = _unique_basename(raw, used_names, default)
        node[attr] = filename
        resources.append(EmbeddedResource(
            tag=node.name,
            attr=attr,
            url=abs_url,
            rel_path=filename,
        ))

    md = _markdownify(str(soup), heading_style="ATX", bullets="*")
    return ConvertResult(markdown=md.strip() + "\n", resources=resources,
                         skipped=skipped)


def to_plain_markdown(content_html: str) -> str:
    """Простой конвертер HTML→Markdown без локальных замен (для метаданных)."""
    if not content_html:
        return ""
    md = _markdownify(content_html, heading_style="ATX")
    return md.strip() + "\n"
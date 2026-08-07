from __future__ import annotations

import pytest

from app.exporter import normalize_date
from app.html_converter import build_markdown, is_internal_url

BASE = "https://profitreid.ismyteam.ru"


def test_normalize_date():
    assert normalize_date("20.08.2025 08:54") == "2025-08-20 08:54"
    assert normalize_date("") == ""


def test_is_internal_url():
    assert is_internal_url("/storage/public/a.png", BASE)
    assert is_internal_url("https://profitreid.ismyteam.ru/x.png", BASE)
    assert not is_internal_url("https://evil.com/x.png", BASE)
    assert not is_internal_url("data:image/png;base64,xxx", BASE)


def test_html_to_markdown_heading_paragraph():
    r = build_markdown("<h1>Заголовок</h1><p>Текст</p>", BASE)
    assert "# Заголовок" in r.markdown
    assert "Текст" in r.markdown


def test_img_relative_replacement():
    r = build_markdown(
        '<p><img src="/storage/public/post-content/abc.png"></p>', BASE)
    assert len(r.resources) == 1
    res = r.resources[0]
    assert res.url == f"{BASE}/storage/public/post-content/abc.png"
    assert res.rel_path == "abc.png"
    # markdownify выдаёт ссылку на локальный файл
    assert "abc.png" in r.markdown
    assert "ismyteam.ru" not in r.markdown.replace(BASE, "")


def test_img_with_alt():
    r = build_markdown(
        '<img alt="Котик" src="/storage/a.png">', BASE)
    assert "Котик" in r.markdown


def test_unique_names():
    html = ('<img src="/storage/a.png"><img src="/storage/a.png">')
    r = build_markdown(html, BASE)
    names = [res.rel_path for res in r.resources]
    assert names[0] != names[1]
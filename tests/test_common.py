from __future__ import annotations

import pytest

from app.common import sanitize_component, sanitize_filename


@pytest.mark.parametrize("raw,expected", [
    ("Настроить Proxy для Telegram", "Настроить Proxy для Telegram"),
    ("a/b/c", "c"),
    (r"a\b", "a_b"),
    ('bad:name*?<>|"file', "bad_name______file"),
    ("trailing.  ", "trailing"),
    ("con", "_"),
    ("", "_"),
    (".", "_"),
    ("..", "_"),
])
def test_sanitize_component(raw, expected):
    assert sanitize_component(raw) == expected


def test_sanitize_filename_keeps_dirs():
    assert sanitize_filename("Ит/Обходы", allow_dir=True) == "Ит/Обходы"


def test_sanitize_rejects_unsafe():
    with pytest.raises(ValueError):
        sanitize_filename("../x", allow_dir=True)
    with pytest.raises(ValueError):
        sanitize_filename("/abs", allow_dir=True)
    with pytest.raises(ValueError):
        sanitize_filename("a/../../x", allow_dir=True)
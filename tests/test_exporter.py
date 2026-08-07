from __future__ import annotations

from app.exporter import Exporter, front_matter


def _item(**overrides):
    item = {
        "id": 8,
        "name": "Настроить Proxy для Telegram",
        "content": "<p>text</p>",
        "files": [],
        "user": {"id": 1, "name": "Иван"},
        "createdDate": "04.05.2026 13:19",
        "updatedDate": "20.07.2026 11:59",
        "group": {"id": 7, "name": "Обходы блокировок"},
        "tags": ["tag1", "tag2"],
    }
    item.update(overrides)
    return item


def test_front_matter_fields():
    fm = front_matter(_item(), "Обходы блокировок")
    assert "myteam_id: 8" in fm
    assert 'category: "Обходы блокировок"' in fm
    assert 'created: "2026-05-04 13:19"' in fm
    assert 'updated: "2026-07-20 11:59"' in fm
    assert "  - tag1" in fm


def test_front_matter_no_tags():
    fm = front_matter(_item(tags=[]), "Обходы блокировок")
    assert "tags:" not in fm


def test_tree_build(tmp_path):
    groups = [
        {"id": 1, "name": "ИТ - инструменты"},
        {"id": 2, "name": "Общая информация"},
    ]
    articles = {1: [{"id": 5, "name": "Настроить Proxy"}]}

    class DummyClient:
        pass

    exporter = Exporter(DummyClient(), "https://x.ru", fail_on_asset_error=True)
    roots = exporter.build_tree(tmp_path, groups, articles)
    assert sorted(p.name for p in roots) == [
        "ИТ - инструменты", "Общая информация"]
    assert (tmp_path / "ИТ - инструменты").is_dir()
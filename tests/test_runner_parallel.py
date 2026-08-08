from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Config
from app.downloader import AssetError
from app.myteam_client import MyTeamError
from app.runner import BackupError, build_backup


def _config(tmp_path: Path, concurrency: int) -> Config:
    return Config(
        myteam_base_url="https://x.ru",
        myteam_email="e@x.ru",
        myteam_password="pw",
        storage_backend="local",
        local_backup_dir=str(tmp_path / "backups"),
        work_dir=str(tmp_path / "work"),
        backup_concurrency=concurrency,
    )


class FakeClient:
    def __init__(self, config, session=None, token=None):
        self.config = config

    def authenticate(self):
        return "tok"

    def get_groups(self):
        return [{"id": 1, "name": "Отдел А"}]

    def get_group_articles(self, gid):
        return [{"id": 1, "name": "A1"}, {"id": 2, "name": "A2"}]

    def get_article(self, aid):
        if aid == 2:
            raise MyTeamError("boom article 2")
        return {"id": aid, "name": f"A{aid}", "content": "",
                "group": {"id": 1}, "files": []}

    def clone(self):
        return FakeClient(self.config)


def _patch(monkeypatch, exporter_cls):
    from app import runner as runner_mod
    monkeypatch.setattr(runner_mod, "MyTeamClient", FakeClient)
    monkeypatch.setattr(
        runner_mod, "Exporter",
        lambda c, b, f, redact=True: exporter_cls(c))
    return runner_mod


class OkExporter:
    def __init__(self, client):
        self.client = client

    def export_article(self, art_dir, item, category_name):
        art_dir.mkdir(parents=True, exist_ok=True)
        (art_dir / f"a{item['id']}.md").write_text(str(item["id"]))
        return {"images": 1, "attachments": 0, "files": {"x.png": "dig"},
                "errors": []}


class FatalExporter:
    def __init__(self, client):
        self.client = client

    def export_article(self, art_dir, item, category_name):
        raise AssetError("image gone")


def _patch(monkeypatch, exporter_cls):
    from app import runner as runner_mod
    monkeypatch.setattr(runner_mod, "MyTeamClient", FakeClient)
    monkeypatch.setattr(
        runner_mod, "Exporter",
        lambda c, b, f, redact=True: exporter_cls(c))
    return runner_mod


def test_build_backup_parallel_isolates_errors(monkeypatch, tmp_path):
    _patch(monkeypatch, OkExporter)
    manifest = build_backup(_config(tmp_path, concurrency=2))

    assert manifest.articles == 2
    assert manifest.images == 1          # успешна одна статья
    assert manifest.files == {"1/x.png": "dig"}
    assert len(manifest.errors) == 1
    assert "boom article 2" in manifest.errors[0]
    assert (tmp_path / "work" / "knowledge-base").is_dir()


def test_build_backup_sequential_same_behavior(monkeypatch, tmp_path):
    _patch(monkeypatch, OkExporter)
    manifest = build_backup(_config(tmp_path, concurrency=1))
    assert manifest.articles == 2
    assert len(manifest.errors) == 1
    assert manifest.files == {"1/x.png": "dig"}


def test_fatal_asset_error_raises_backup_error(monkeypatch, tmp_path):
    _patch(monkeypatch, FatalExporter)
    with pytest.raises(BackupError):
        build_backup(_config(tmp_path, concurrency=2))


class NestedGroupsClient(FakeClient):
    def get_groups(self):
        return [{
            "id": 1,
            "name": "Общая информация компании",
            "children": [
                {"id": 3, "name": "Юридические лица и реквизиты",
                 "children": [{"id": 11, "name": "Карточка организации - АЭК"}]},
            ],
        }]

    def get_group_articles(self, gid):
        return [{"id": 1, "name": "A1", "group": {"id": 11}}]

    def get_article(self, aid):
        return {"id": aid, "name": f"A{aid}", "content": "",
                "group": {"id": 11}, "files": []}

    def clone(self):
        return NestedGroupsClient(self.config)


class NestedExporter:
    def __init__(self, client):
        self.client = client

    def export_article(self, art_dir, item, category_name):
        art_dir.mkdir(parents=True, exist_ok=True)
        (art_dir / f"a{item['id']}.md").write_text(str(item["id"]))
        return {"images": 0, "attachments": 0, "files": {}, "errors": []}


@pytest.mark.parametrize("concurrency", [1, 4])
def test_build_backup_nested_group_hierarchy(monkeypatch, tmp_path, concurrency):
    from app import runner as runner_mod
    monkeypatch.setattr(runner_mod, "MyTeamClient", NestedGroupsClient)
    monkeypatch.setattr(
        runner_mod, "Exporter",
        lambda c, b, f, redact=True: NestedExporter(c))
    build_backup(_config(tmp_path, concurrency=concurrency))

    nested = (tmp_path / "work" / "knowledge-base"
              / "Общая информация компании"
              / "Юридические лица и реквизиты"
              / "Карточка организации - АЭК" / "A1")
    assert (nested / "a1.md").is_file()
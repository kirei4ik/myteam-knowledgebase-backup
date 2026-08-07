from __future__ import annotations

import json

import pytest

from app.myteam_client import _per_page, _total_pages


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def json(self):
        return self._payload

    @property
    def text(self):
        return json.dumps(self._payload)


def test_total_pages():
    assert _total_pages({"totalPages": 3}) == 3
    assert _total_pages(None) is None


def test_per_page_default():
    assert _per_page(None) == 15


def make_client(monkeypatch):
    from app.config import Config
    from app.myteam_client import MyTeamClient

    cfg = Config(
        myteam_base_url="https://example.ru", myteam_email="e", myteam_password="p",
        storage_backend="local", local_backup_dir="./backups", work_dir="/tmp/x",
    )
    return MyTeamClient(cfg)


def test_get_group_articles_paginates(monkeypatch):
    client = make_client(monkeypatch)
    calls = []

    def fake_get(path, params=None, **kw):
        calls.append(params)
        page = (params or {}).get("page", 1)
        batch = [{"id": (page - 1) * 2 + i} for i in range(1, 3)]
        return {"data": {
            "articles": batch,
            "pagination": {"totalPages": 2, "perPage": 2},
        }}

    monkeypatch.setattr(client, "_get", fake_get)
    articles = client.get_group_articles(1)
    assert len(articles) == 4
    assert calls == [{"page": 1}, {"page": 2}]


def test_get_group_articles_single_page(monkeypatch):
    client = make_client(monkeypatch)

    def fake_get(path, params=None, **kw):
        return {"data": {"articles": [{"id": 1}], "pagination": {"totalPages": 1}}}

    monkeypatch.setattr(client, "_get", fake_get)
    assert len(client.get_group_articles(1)) == 1
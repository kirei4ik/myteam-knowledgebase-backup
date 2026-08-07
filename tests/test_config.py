from __future__ import annotations

import pytest

from app.config import ConfigError, build_config
from app.storage.factory import build_storage
from app.storage.github import GithubStorageBackend
from app.storage.local import LocalStorageBackend
from app.storage.s3 import S3StorageBackend


def _cfg(monkeypatch, **overrides):
    import os
    env = {
        "MYTEAM_BASE_URL": "https://x.ru",
        "MYTEAM_EMAIL": "e@x.ru",
        "MYTEAM_PASSWORD": "pw",
        "STORAGE_BACKEND": "local",
        **overrides,
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    for k in ("GITHUB_TOKEN", "GITHUB_REPOSITORY", "S3_BUCKET",
              "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY"):
        if k not in env:
            monkeypatch.delenv(k, raising=False)
    return build_config(dry_run=False)


def test_storage_backend_factory(monkeypatch):
    cfg = _cfg(monkeypatch, STORAGE_BACKEND="local")
    assert isinstance(cfg.storage_backend, str)
    s = build_storage(cfg)
    assert isinstance(s, LocalStorageBackend)


def test_github_backend_selection(monkeypatch):
    cfg = _cfg(monkeypatch, STORAGE_BACKEND="github",
               GITHUB_TOKEN="t", GITHUB_REPOSITORY="o/r")
    s = build_storage(cfg)
    assert isinstance(s, GithubStorageBackend)


def test_s3_backend_selection(monkeypatch):
    cfg = _cfg(monkeypatch, STORAGE_BACKEND="s3",
               S3_BUCKET="b", S3_ACCESS_KEY_ID="a", S3_SECRET_ACCESS_KEY="s")
    s = build_storage(cfg)
    assert isinstance(s, S3StorageBackend)


def test_config_missing_required_local(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("MYTEAM_EMAIL", "")
    monkeypatch.setenv("MYTEAM_PASSWORD", "")
    with pytest.raises(ConfigError):
        build_config()


def test_config_requires_github_creds(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "github")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(ConfigError):
        _cfg(monkeypatch, STORAGE_BACKEND="github")


def test_config_no_github_required_when_local(monkeypatch):
    cfg = _cfg(monkeypatch, STORAGE_BACKEND="local")
    assert cfg.storage_backend == "local"


def test_snapshot_min_interval_parses_hours_and_minutes(monkeypatch):
    cfg = _cfg(monkeypatch,
               SNAPSHOT_MIN_INTERVAL_HOURS="2",
               SNAPSHOT_MIN_INTERVAL_MINUTES="30")
    assert cfg.snapshot_min_interval == 150.0


def test_snapshot_min_interval_only_minutes(monkeypatch):
    monkeypatch.setenv("SNAPSHOT_MIN_INTERVAL_HOURS", "")
    cfg = _cfg(monkeypatch, SNAPSHOT_MIN_INTERVAL_MINUTES="45")
    assert cfg.snapshot_min_interval == 45.0


def test_snapshot_retention_count_parsed(monkeypatch):
    cfg = _cfg(monkeypatch, SNAPSHOT_RETENTION_COUNT="7")
    assert cfg.snapshot_retention_count == 7


def test_snapshot_options_propagate_to_local(monkeypatch):
    cfg = _cfg(monkeypatch,
               SNAPSHOT_RETENTION_COUNT="5",
               SNAPSHOT_MIN_INTERVAL_HOURS="1")
    s = build_storage(cfg)
    assert isinstance(s, LocalStorageBackend)
    assert s.retention_count == 5
    assert s.min_interval_minutes == 60.0
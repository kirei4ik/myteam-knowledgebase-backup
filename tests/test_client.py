from __future__ import annotations

from app.config import Config
from app.myteam_client import MyTeamClient, build_session


def _cfg(**overrides) -> Config:
    base = dict(
        myteam_base_url="https://x.ru",
        myteam_email="e@x.ru",
        myteam_password="pw",
        storage_backend="local",
        local_backup_dir="./backups",
        work_dir="/tmp/x",
    )
    base.update(overrides)
    return Config(**base)


def test_build_session_has_retry_adapter():
    s = build_session(retry_count=3, retry_backoff=0.5)
    adapter = s.get_adapter("https://x.ru")
    from urllib3.util.retry import Retry
    assert isinstance(adapter.max_retries, Retry)
    assert adapter.max_retries.total == 3
    assert adapter.max_retries.backoff_factor == 0.5


def test_build_session_zero_retries_disabled():
    s = build_session(retry_count=0)
    adapter = s.get_adapter("https://x.ru")
    assert adapter.max_retries.total == 0


def test_client_clone_reuses_token_and_new_session():
    cfg = _cfg()
    client = MyTeamClient(cfg)
    client._token = "abc"
    clone = client.clone()
    assert clone is not client
    assert clone._token == "abc"
    assert clone.session is not client.session


def test_client_default_session_from_config():
    cfg = _cfg(retry_count=2, retry_backoff=0.7)
    client = MyTeamClient(cfg)
    adapter = client.session.get_adapter("https://x.ru")
    assert adapter.max_retries.total == 2
    assert adapter.max_retries.backoff_factor == 0.7
"""Regression tests for S3 bucket-root and nested-prefix keys."""
from unittest.mock import MagicMock, patch

import pytest

from app.storage.s3 import S3StorageBackend


@pytest.mark.parametrize("prefix,expected", [
    ("", "latest/manifest.json"),
    ("/", "latest/manifest.json"),
    ("myteam-kb", "myteam-kb/latest/manifest.json"),
    ("/myteam-kb/", "myteam-kb/latest/manifest.json"),
])
def test_s3_key(prefix, expected):
    with patch("boto3.client", return_value=MagicMock()):
        storage = S3StorageBackend(bucket="backups", prefix=prefix)
    assert storage._key("latest", "manifest.json") == expected


@pytest.mark.parametrize("prefix,expected", [
    ("", "snapshots/"),
    ("myteam-kb", "myteam-kb/snapshots/"),
])
def test_snapshot_listing_prefix(prefix, expected):
    client = MagicMock()
    client.list_objects_v2.return_value = {"CommonPrefixes": []}
    with patch("boto3.client", return_value=client):
        storage = S3StorageBackend(bucket="backups", prefix=prefix,
                                   min_interval_minutes=30)
    storage._should_interval_skip(storage._key("snapshots", "2026-11-13T083000", "knowledge-base.zip"))
    storage._list_snapshots()
    assert client.list_objects_v2.call_count == 2
    for call in client.list_objects_v2.call_args_list:
        assert call.kwargs["Prefix"] == expected

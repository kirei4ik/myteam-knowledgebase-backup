"""Фабрика storage backend по конфигурации."""
from __future__ import annotations

from pathlib import Path

from ..config import Config
from .base import StorageBackend
from .github import GithubStorageBackend
from .local import LocalStorageBackend
from .s3 import S3StorageBackend


def build_storage(config: Config) -> StorageBackend:
    if config.storage_backend == "local":
        return LocalStorageBackend(
            backups_dir=config.local_backup_dir,
            snapshot=config.snapshot_enabled,
            retention_days=config.snapshot_retention_days,
        )
    if config.storage_backend == "github":
        return GithubStorageBackend(
            token=config.github_token,
            repository=config.github_repository,
            branch=config.github_branch,
            backup_path=config.github_backup_path,
            commit_author_name=config.github_commit_author_name,
            commit_author_email=config.github_commit_author_email,
        )
    if config.storage_backend == "s3":
        return S3StorageBackend(
            bucket=config.s3_bucket,
            prefix=config.s3_prefix,
            endpoint_url=config.s3_endpoint_url,
            access_key_id=config.s3_access_key_id,
            secret_access_key=config.s3_secret_access_key,
            region=config.s3_region,
            verify_ssl=config.s3_verify_ssl,
            snapshot=config.snapshot_enabled,
            retention_days=config.snapshot_retention_days,
        )
    raise ValueError(f"Unknown storage backend: {config.storage_backend}")
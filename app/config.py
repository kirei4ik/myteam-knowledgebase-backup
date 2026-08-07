"""Конфигурация приложения из environment variables."""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

VALID_BACKENDS = {"local", "github", "s3"}

# Секреты, которые нельзя выводить в лог
SECRET_ENV_KEYS = (
    "MYTEAM_PASSWORD",
    "GITHUB_TOKEN",
    "S3_SECRET_ACCESS_KEY",
    "S3_ACCESS_KEY_ID",
)


def _env(key: str, default: str = "") -> str:
    if key not in os.environ:
        return default
    return os.environ[key] or default


def set_env(key: str, value: str) -> None:
    """Позволяет CLI-аргументам переопределять env-настройки."""
    os.environ[key] = value


def _as_bool(value: str, default: bool = False) -> bool:
    if value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Config:
    myteam_base_url: str
    myteam_email: str
    myteam_password: str

    storage_backend: str
    local_backup_dir: str
    work_dir: str
    output_dir: str | None = None
    dry_run: bool = False

    create_snapshot: bool = True
    snapshot_format: str = "zip"
    snapshot_retention_days: int | None = None
    fail_on_asset_error: bool = True
    redact_secrets: bool = True

    github_token: str = ""
    github_repository: str = ""
    github_branch: str = "main"
    github_backup_path: str = "knowledge-base"
    github_commit_author_name: str = "MyTeam Backup"
    github_commit_author_email: str = ""

    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_bucket: str = ""
    s3_region: str = ""
    s3_prefix: str = "myteam-kb"
    s3_verify_ssl: bool = True

    @property
    def snapshot_enabled(self) -> bool:
        return self.create_snapshot and self.snapshot_format == "zip"

    def secret_values(self) -> list[str]:
        return [
            v for v in (self.myteam_password, self.github_token,
                        self.s3_secret_access_key, self.s3_access_key_id) if v
        ]


def _validate_required(config: Config, errors: list[str]) -> None:
    if not config.myteam_base_url:
        errors.append("MYTEAM_BASE_URL is required")
    if not config.myteam_email:
        errors.append("MYTEAM_EMAIL is required")
    if not config.myteam_password:
        errors.append("MYTEAM_PASSWORD is required")

    if config.storage_backend == "github":
        if not config.github_token:
            errors.append("GITHUB_TOKEN is required for storage_backend=github")
        if not config.github_repository:
            errors.append("GITHUB_REPOSITORY is required for storage_backend=github")
    elif config.storage_backend == "s3":
        if not config.s3_bucket:
            errors.append("S3_BUCKET is required for storage_backend=s3")
        if not config.s3_access_key_id:
            errors.append("S3_ACCESS_KEY_ID is required for storage_backend=s3")
        if not config.s3_secret_access_key:
            errors.append("S3_SECRET_ACCESS_KEY is required for storage_backend=s3")


def build_config(dry_run: bool = False, output_dir: str | None = None) -> Config:
    load_dotenv()

    backend = _env("STORAGE_BACKEND", "local")
    errors: list[str] = []
    if backend not in VALID_BACKENDS:
        errors.append(
            f"STORAGE_BACKEND must be one of {', '.join(sorted(VALID_BACKENDS))}, got '{backend}'"
        )

    cfg = Config(
        myteam_base_url=_env("MYTEAM_BASE_URL", "https://profitreid.ismyteam.ru").rstrip("/"),
        myteam_email=_env("MYTEAM_EMAIL"),
        myteam_password=_env("MYTEAM_PASSWORD"),
        storage_backend=backend,
        local_backup_dir=_env("LOCAL_BACKUP_DIR", "./backups"),
        work_dir=_env("WORK_DIR", "/tmp/myteam-kb-backup"),
        output_dir=output_dir,
        dry_run=dry_run,
        create_snapshot=_as_bool(_env("CREATE_SNAPSHOT", "true"), True),
        snapshot_format=_env("SNAPSHOT_FORMAT", "zip"),
        snapshot_retention_days=_int_or_none(_env("SNAPSHOT_RETENTION_DAYS", "")),
        fail_on_asset_error=_as_bool(_env("FAIL_ON_ASSET_ERROR", "true"), True),
        redact_secrets=_as_bool(_env("REDACT", "true"), True),
        github_token=_env("GITHUB_TOKEN"),
        github_repository=_env("GITHUB_REPOSITORY"),
        github_branch=_env("GITHUB_BRANCH", "main"),
        github_backup_path=_env("GITHUB_BACKUP_PATH", "knowledge-base"),
        github_commit_author_name=_env("GITHUB_COMMIT_AUTHOR_NAME", "MyTeam Backup"),
        github_commit_author_email=_env("GITHUB_COMMIT_AUTHOR_EMAIL"),
        s3_endpoint_url=_env("S3_ENDPOINT_URL"),
        s3_access_key_id=_env("S3_ACCESS_KEY_ID"),
        s3_secret_access_key=_env("S3_SECRET_ACCESS_KEY"),
        s3_bucket=_env("S3_BUCKET"),
        s3_region=_env("S3_REGION"),
        s3_prefix=_env("S3_PREFIX", "myteam-kb"),
        s3_verify_ssl=_as_bool(_env("S3_VERIFY_SSL", "true"), True),
    )

    # CLI --output переопределяет LOCAL_BACKUP_DIR
    if output_dir:
        cfg.local_backup_dir = output_dir

    _validate_required(cfg, errors)
    if errors:
        raise ConfigError("\n".join(errors))

    return cfg


def _int_or_none(value: str) -> int | None:
    if value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


class ConfigError(Exception):
    pass
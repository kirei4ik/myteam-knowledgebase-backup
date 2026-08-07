"""Оркестрация выгрузки базы знаний."""
from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

from .common import sanitize_component
from .config import ConfigError, build_config
from .downloader import AssetError
from .exporter import Exporter
from .logging import logger
from .manifest import Manifest
from .myteam_client import MyTeamClient, MyTeamError
from .storage.factory import build_storage

BACKUP_SUBDIR = "knowledge-base"


class BackupError(Exception):
    pass


def _now_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H%M%S")


def build_backup(config: Config) -> Manifest:
    """Строит полный backup в WORK_DIR. Бросает BackupError при критичных ошибках."""
    work_root = Path(config.work_dir)
    work_root.mkdir(parents=True, exist_ok=True)
    for child in work_root.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)

    client = MyTeamClient(config)
    client.authenticate()
    exporter = Exporter(client, config.myteam_base_url,
                        config.fail_on_asset_error,
                        redact=config.redact_secrets)

    groups = client.get_groups()
    logger.info(f"Categories loaded: {len(groups)}")
    group_names = {int(g["id"]): g.get("name", "") for g in groups if "id" in g}

    kb_root = work_root / BACKUP_SUBDIR
    kb_root.mkdir(parents=True, exist_ok=True)

    manifest = Manifest(source=config.myteam_base_url, categories=len(groups))

    category_dirs: dict[int, Path] = {}
    for g in groups:
        gid = g["id"]
        dir_name = sanitize_component(g.get("name", f"category-{gid}"))
        gdir = kb_root / dir_name
        gdir.mkdir(parents=True, exist_ok=True)
        category_dirs[gid] = gdir

    all_articles: list[dict] = []
    for g in groups:
        gid = g["id"]
        try:
            articles = client.get_group_articles(gid)
        except MyTeamError as exc:
            logger.error(f"Failed to load articles for group {gid}: {exc}")
            manifest.errors.append(f"group {gid}: {exc}")
            continue
        all_articles.extend(articles)

    manifest.articles = len(all_articles)
    logger.info(f"Articles discovered: {len(all_articles)}")

    for i, art in enumerate(all_articles, start=1):
        aid = art.get("id")
        title = art.get("name", str(aid))
        logger.info(f"Processing article {i}/{len(all_articles)}: {title}")
        try:
            item = client.get_article(aid)
            gid = (item.get("group") or {}).get("id")
            category_name = group_names.get(gid, "")
            art_dir = category_dirs.get(gid, kb_root) / sanitize_component(title)
            stat = exporter.export_article(art_dir, item, category_name)
            manifest.images += stat["images"]
            manifest.attachments += stat["attachments"]
            for rel, digest in stat["files"].items():
                manifest.files[f"{aid}/{rel}"] = digest
            manifest.errors.extend(f"[{title}] {e}" for e in stat["errors"])
        except AssetError as exc:
            logger.error(f"Article {aid} asset failed: {exc}")
            raise BackupError(f"Article {aid} asset failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Article {aid} failed: {exc}")
            manifest.errors.append(f"[{title}] {exc}")

    manifest.write(work_root)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="backup.py")
    parser.add_argument("--dry-run", action="store_true",
                        help="build the backup but do not publish")
    parser.add_argument("--output", help="write backup into the given local dir")
    args = parser.parse_args(argv)

    try:
        config = build_config(dry_run=args.dry_run, output_dir=args.output)
    except ConfigError as exc:
        logger.error(f"Configuration error: {exc}")
        return 1
    logger.configure(config.secret_values())

    backup_root = Path(config.work_dir)

    try:
        manifest = build_backup(config)
    except BackupError as exc:
        logger.error(f"Backup failed: {exc}")
        return 1
    except MyTeamError as exc:
        logger.error(f"Backup failed: {exc}")
        return 1

    if manifest.errors and config.fail_on_asset_error:
        logger.error(f"Backup completed with {len(manifest.errors)} error(s); "
                     f"FAIL_ON_ASSET_ERROR=true")
        return 1

    if config.dry_run:
        logger.info("Dry-run: not publishing")
        return 0

    storage = build_storage(config)
    timestamp = _now_timestamp()
    try:
        storage.store(backup_root, timestamp, manifest)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Storage publish failed: {exc}")
        return 1

    if manifest.errors:
        logger.warn(f"Backup completed with {len(manifest.errors)} non-fatal error(s)")
    logger.info("Backup completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
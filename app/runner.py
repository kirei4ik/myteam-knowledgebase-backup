"""Оркестрация выгрузки базы знаний."""
from __future__ import annotations

import argparse
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from .common import sanitize_component
from .config import ConfigError, build_config
from .downloader import AssetError
from .exporter import Exporter
from .logging import logger
from .manifest import Manifest
from .myteam_client import MyTeamClient, MyTeamError
from .report import build_report
from .storage.factory import build_storage

BACKUP_SUBDIR = "knowledge-base"


class BackupError(Exception):
    pass


def _now_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H%M%S")


def build_backup(config: Config) -> Manifest:
    """Строит полный backup в WORK_DIR. Бросает BackupError при критичных ошибках."""
    started_at = datetime.now()
    work_root = Path(config.work_dir)
    work_root.mkdir(parents=True, exist_ok=True)
    for child in work_root.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)

    client = MyTeamClient(config)
    client.authenticate()

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

    concurrency = max(1, config.backup_concurrency or 1)

    # requests.Session не потокобезопасен: каждый воркер получает свою
    # сессию с тем же токеном (client.clone) и лениво создаёт Exporter.
    worker_state = threading.local()

    def _worker_exporter() -> Exporter:
        exporter = getattr(worker_state, "exporter", None)
        if exporter is None:
            exporter = Exporter(
                client.clone(),
                config.myteam_base_url,
                config.fail_on_asset_error,
                redact=config.redact_secrets)
            worker_state.exporter = exporter
        return exporter

    def process_one(art: dict) -> dict:
        """Обрабатывает одну статью. Возвращает dict с результатом."""
        aid = art.get("id")
        title = art.get("name", str(aid))
        try:
            exporter = _worker_exporter()
            item = exporter.client.get_article(aid)
            gid = (item.get("group") or {}).get("id")
            category_name = group_names.get(gid, "")
            art_dir = category_dirs.get(gid, kb_root) / sanitize_component(title)
            stat = exporter.export_article(art_dir, item, category_name)
            return {"ok": True, "stat": stat, "title": title, "aid": aid}
        except AssetError as exc:
            logger.error(f"Article {aid} asset failed: {exc}")
            return {"ok": False, "fatal": True, "message": f"Article {aid} "
                    f"asset failed: {exc}", "title": title, "aid": aid}
        except MyTeamError as exc:
            logger.error(f"Article {aid} failed: {exc}")
            return {"ok": False, "fatal": False,
                    "message": f"[{title}] {exc}", "title": title, "aid": aid}
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Article {aid} failed: {exc}")
            return {"ok": False, "fatal": False,
                    "message": f"[{title}] {exc}", "title": title, "aid": aid}

    if concurrency > 1:
        _process_parallel(process_one, all_articles, concurrency, manifest)
    else:
        _process_sequential(process_one, all_articles, manifest)

    build_report(work_root, manifest, started_at)
    manifest.write(work_root)
    return manifest


def _process_sequential(process_one, all_articles, manifest) -> None:
    total = len(all_articles)
    for i, art in enumerate(all_articles, start=1):
        logger.info(f"Processing article {i}/{total}: {art.get('name', art.get('id'))}")
        _collect(manifest, process_one(art), f"{i}/{total}")


def _process_parallel(process_one, all_articles, concurrency, manifest) -> None:
    total = len(all_articles)
    done = 0
    with ThreadPoolExecutor(max_workers=concurrency,
                            thread_name_prefix="kb-worker") as pool:
        futs = {pool.submit(process_one, art): art for art in all_articles}
        for future in as_completed(futs):
            done += 1
            art = futs[future]
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Worker failed for {art.get('id')}: {exc}")
                result = {"ok": False, "fatal": False,
                          "message": f"[{art.get('name', art.get('id'))}] {exc}"}
            idx = f"{done}/{total}"
            logger.info(f"Processing article {idx}: {result['title']}")
            _collect(manifest, result, idx)
            if done % 10 == 0 or done == total:
                logger.info(f"Progress: {done}/{total} articles")


def _collect(manifest, result, label) -> None:
    if not result["ok"]:
        if result.get("fatal"):
            raise BackupError(result["message"]) from None
        manifest.errors.append(result["message"])
        return
    stat = result["stat"]
    manifest.images += stat["images"]
    manifest.attachments += stat["attachments"]
    for rel, digest in stat["files"].items():
        manifest.files[f"{result['aid']}/{rel}"] = digest
    manifest.errors.extend(f"[{result['title']}] {e}" for e in stat["errors"])


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
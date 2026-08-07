"""GitHub storage backend через git clone/commit/push."""
from __future__ import annotations

import subprocess
from pathlib import Path

from ..logging import logger
from .base import StorageBackend


class GitError(Exception):
    pass


class GithubStorageBackend(StorageBackend):
    name = "github"

    def __init__(self, token: str, repository: str, branch: str,
                 backup_path: str, commit_author_name: str,
                 commit_author_email: str):
        if "/" not in repository:
            raise GitError(f"GITHUB_REPOSITORY must be 'owner/repo', got '{repository}'")
        self.token = token
        self.repository = repository
        self.branch = branch
        self.backup_path = backup_path.strip("/")
        self.commit_author_name = commit_author_name
        self.commit_author_email = commit_author_email

    def store(self, backup_root: Path, timestamp: str, manifest) -> None:
        clone_dir = Path(backup_root).parent / "_github_clone"
        self._clone(clone_dir)
        import shutil
        target = clone_dir / self.backup_path
        btr = backup_root / "knowledge-base"
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(btr, target)
        shutil.copy2(backup_root / "manifest.json", target.parent / "manifest.json")

        self._commit_and_push(clone_dir, timestamp)

    def _clone(self, clone_dir: Path) -> None:
        import shutil
        if clone_dir.exists():
            shutil.rmtree(clone_dir)
        url = f"https://x-access-token:{self.token}@github.com/{self.repository}.git"
        self._run(["git", "clone", "--branch", self.branch,
                   "--single-branch", url, str(clone_dir)],
                  cwd=str(clone_dir.parent))

    def _commit_and_push(self, clone_dir: Path, timestamp: str) -> None:
        self._run(["git", "add", "-A"], cwd=str(clone_dir))
        diff = self._run(["git", "diff", "--cached", "--quiet"], cwd=str(clone_dir),
                         check=False)
        if diff == 0:
            logger.info("No changes, skipping commit")
            return
        message = f"MyTeam KB backup: {timestamp}"
        env = {"GIT_AUTHOR_NAME": self.commit_author_name,
               "GIT_AUTHOR_EMAIL": self.commit_author_email,
               "GIT_COMMITTER_NAME": self.commit_author_name,
               "GIT_COMMITTER_EMAIL": self.commit_author_email}
        self._run(["git", "commit", "-m", message], cwd=str(clone_dir), env=env)
        self._run(["git", "push", "origin", self.branch], cwd=str(clone_dir))

    @staticmethod
    def _run(args: list[str], cwd: str, check: bool = True, env: dict | None = None) -> int:
        proc = subprocess.run(args, cwd=cwd, check=False, env=env,
                              capture_output=True, text=True)
        if check and proc.returncode != 0:
            raise GitError(
                f"{' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}")
        return proc.returncode
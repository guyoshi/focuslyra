from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SOURCES_DIR = ROOT / "sources"


class SourceSyncError(RuntimeError):
    pass


def _run_git(args: list[str], cwd: Path | None = None) -> str:
    if shutil.which("git") is None:
        raise SourceSyncError("Git is not installed or not available on PATH.")
    process = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        message = (process.stderr or process.stdout or "Git command failed").strip()
        raise SourceSyncError(message)
    return process.stdout.strip()


def load_sources() -> list[dict[str, Any]]:
    path = DATA_DIR / "sources.json"
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def find_source(source_id: str) -> dict[str, Any]:
    for source in load_sources():
        if source.get("id") == source_id:
            return source
    raise SourceSyncError(f"Unknown memory source: {source_id}")


def _clone_source(target: Path, branch: str, remote_url: str) -> None:
    if target.exists():
        shutil.rmtree(target)
    _run_git(["clone", "--depth", "1", "--branch", branch, remote_url, str(target)])


def sync_git_source(source_id: str) -> dict[str, Any]:
    source = find_source(source_id)
    if source.get("type") != "git":
        raise SourceSyncError("Only Git sources are supported in the current MVP.")
    if source.get("mode") != "read_only":
        raise SourceSyncError("MVP source sync requires read_only mode.")

    repository = source["repository"]
    branch = source.get("branch", "main")
    target = SOURCES_DIR / source_id
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)

    # HTTPS lets the user's normal Git Credential Manager handle private repos.
    remote_url = f"https://github.com/{repository}.git"

    if not (target / ".git").exists():
        _clone_source(target, branch, remote_url)
    else:
        # The source directory is a disposable read-only cache. Keep origin correct,
        # fetch the configured branch, and reset to FETCH_HEAD. A shallow fetch such
        # as `git fetch origin main --depth 1` is not guaranteed to create/update
        # refs/remotes/origin/main, so resetting to origin/main can fail with
        # "ambiguous argument 'origin/main'" even though the fetch itself succeeded.
        _run_git(["remote", "set-url", "origin", remote_url], cwd=target)
        _run_git(["fetch", "origin", branch, "--depth", "1"], cwd=target)
        _run_git(["reset", "--hard", "FETCH_HEAD"], cwd=target)

    commit = _run_git(["rev-parse", "HEAD"], cwd=target)
    return {
        "id": source_id,
        "repository": repository,
        "branch": branch,
        "commit": commit,
        "local_path": str(target.relative_to(ROOT)).replace("\\", "/"),
    }

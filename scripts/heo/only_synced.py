"""Exit 0 if the changes between two git refs touch only `synced` blocks of existing files.

The weekly sync PR is merged automatically only when this holds: no new files,
no deleted files, and no curated field or body changed.

Usage: python -m scripts.heo.only_synced BASE_REF [HEAD_REF]
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .content import parse


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def strip(text: str, path: str) -> tuple[dict, str]:
    item = parse(text, Path(path))
    meta = {k: v for k, v in item.meta.items() if k != "synced"}
    return meta, item.body


def main(argv: list[str]) -> int:
    base = argv[0]
    head = argv[1] if len(argv) > 1 else "HEAD"
    changes = [line.split("\t") for line in git("diff", "--name-status", f"{base}...{head}").splitlines() if line]
    if not changes:
        print("no changes")
        return 0
    for status, *paths in changes:
        path = paths[-1]
        if status != "M" or not (path.startswith("content/") and path.endswith((".md", ".html"))):
            print(f"not synced-only: {status} {path}")
            return 1
        before = strip(git("show", f"{base}:{path}"), path)
        after = strip(git("show", f"{head}:{path}"), path)
        if before != after:
            print(f"not synced-only: curated fields changed in {path}")
            return 1
    print(f"synced-only: {len(changes)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

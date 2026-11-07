"""Sync GitHub repository data into content/_projects/.

For every project with a `github: owner/repo` field, refresh its `synced` block
(stars, language, description, homepage, last push, topics, archived).
With --discover, also create hidden project files for your own public,
non-fork repositories pushed within --days that no project file covers yet.

Environment: GITHUB_TOKEN (optional, raises the rate limit), GITHUB_USER (default ajturner)
Usage: python -m scripts.heo.sync_github [--discover] [--days 365]
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys

from .content import CONTENT, Item, iter_items, merge_synced, save, slugify
from .http import check, session

API = "https://api.github.com"


def repo_synced(r: dict) -> dict:
    return {
        "description": r.get("description") or "",
        "stars": r.get("stargazers_count", 0),
        "forks": r.get("forks_count", 0),
        "language": r.get("language") or "",
        "homepage": r.get("homepage") or "",
        "pushed_at": (r.get("pushed_at") or "")[:10],
        "topics": r.get("topics", []),
        "archived": bool(r.get("archived")),
        "url": r.get("html_url"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--discover", action="store_true")
    ap.add_argument("--days", type=int, default=365)
    args = ap.parse_args(argv)

    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    s = session(headers=headers)
    user = os.environ.get("GITHUB_USER", "ajturner")

    projects = list(iter_items(["_projects"]))
    covered = {str(p.meta["github"]).lower() for p in projects if p.meta.get("github")}
    updated = created = 0

    for item in projects:
        full = item.meta.get("github")
        if not full:
            continue
        resp = s.get(f"{API}/repos/{full}", timeout=30)
        if resp.status_code == 404:
            print(f"warning: {full} not found (renamed or private?)", file=sys.stderr)
            continue
        merge_synced(item, repo_synced(check(resp).json()))
        if save(item):
            updated += 1

    if args.discover:
        cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.days)).isoformat()[:10]
        page = 1
        while True:
            repos = check(s.get(f"{API}/users/{user}/repos", params={"type": "owner", "sort": "pushed", "per_page": 100, "page": page}, timeout=30)).json()
            if not repos:
                break
            for r in repos:
                if r["fork"] or r["private"] or r["full_name"].lower() in covered:
                    continue
                if (r.get("pushed_at") or "")[:10] < cutoff:
                    continue
                path = CONTENT / "_projects" / f"{slugify(r['name'])}.md"
                if path.exists():
                    continue
                item = Item(path=path, meta={
                    "source_id": f"github:{r['full_name'].lower()}", "title": r["name"], "era": "personal",
                    "status": "active", "github": r["full_name"], "repo": r["html_url"],
                    "summary": r.get("description") or "", "hidden": True,
                }, body="")
                merge_synced(item, repo_synced(r))
                save(item)
                created += 1
            page += 1

    print(f"GitHub: {updated} projects refreshed, {created} new hidden projects")
    return 0


if __name__ == "__main__":
    sys.exit(main())

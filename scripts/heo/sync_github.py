"""Sync GitHub repository data into content/_projects/.

For every project with a `github: owner/repo` field, refresh its `synced` block
(stars, language, description, homepage, last push, topics, archived).

Only your repositories with the `portfolio` topic appear on the site: a project
backed by one of your repositories without that topic is left out of the build and
of WordPress publishing (see content.portfolio_excluded). Projects from other
owners are curated by hand and always shown.

With --discover, also create a project file for each of your public repositories
that has the `portfolio` topic and no project file yet. Repositories listed in
_data/github_exclude.yml are never added.

Environment: GITHUB_TOKEN (optional, raises the rate limit), GITHUB_USER (default ajturner)
Usage: python -m scripts.heo.sync_github [--discover]
"""
from __future__ import annotations

import argparse
import os
import sys

import yaml

from .content import CONTENT, DATA, PORTFOLIO_TOPIC, Item, iter_items, merge_synced, save, slugify
from .http import check, session

API = "https://api.github.com"


def pages_url(r: dict) -> str:
    """Public URL of the repository's GitHub Pages site, or "" if it has none."""
    if not r.get("has_pages"):
        return ""
    owner, name = r["full_name"].split("/")
    if name.lower() in (f"{owner.lower()}.github.io", f"{owner.lower()}.github.com"):
        return f"https://{owner.lower()}.github.io/"
    return f"https://{owner.lower()}.github.io/{name}/"


def repo_synced(r: dict) -> dict:
    return {
        "pages_url": pages_url(r),
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
    args = ap.parse_args(argv)

    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    s = session(headers=headers)
    user = os.environ.get("GITHUB_USER", "ajturner")

    projects = list(iter_items(["_projects"]))
    covered = {str(p.meta["github"]).lower() for p in projects if p.meta.get("github")}
    # Repositories listed in _data/github_exclude.yml are never added.
    exclude_file = DATA / "github_exclude.yml"
    if exclude_file.exists():
        data = yaml.safe_load(exclude_file.read_text()) or {}
        covered |= {str(e["name"]).lower() for e in data.get("repos", []) if e.get("name")}
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
        page = 1
        while True:
            repos = check(s.get(f"{API}/users/{user}/repos", params={"type": "owner", "sort": "pushed", "per_page": 100, "page": page}, timeout=30)).json()
            if not repos:
                break
            for r in repos:
                if r["private"] or r["full_name"].lower() in covered:
                    continue
                if PORTFOLIO_TOPIC not in [t.lower() for t in r.get("topics") or []]:
                    continue
                path = CONTENT / "_projects" / f"{slugify(r['name'])}.md"
                if path.exists():
                    continue
                item = Item(path=path, meta={
                    "source_id": f"github:{r['full_name'].lower()}", "title": r["name"], "era": "personal",
                    "status": "archived" if r.get("archived") else "active", "github": r["full_name"],
                    "repo": r["html_url"], "summary": r.get("description") or "",
                    "year": int((r.get("created_at") or "0000")[:4]) or None,
                }, body="")
                item.meta = {k: v for k, v in item.meta.items() if v not in (None, "")}
                merge_synced(item, repo_synced(r))
                save(item)
                covered.add(r["full_name"].lower())
                created += 1
            page += 1

    print(f"GitHub: {updated} projects refreshed, {created} new portfolio projects")
    return 0


if __name__ == "__main__":
    sys.exit(main())

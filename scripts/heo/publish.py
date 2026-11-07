"""Publish content files to WordPress through the heo/v1 REST routes.

Usage:
  python -m scripts.heo.publish [--dry-run] [--force] [paths ...]

Environment:
  WP_URL            site root, e.g. https://highearthorbit.com
  WP_USER           the publishing user (Editor role)
  WP_APP_PASSWORD   that user's application password
  HEO_NEW_STATUS    status for items WordPress has never seen: draft (default) or publish

With no paths, every content file is considered; items whose content hash
matches what WordPress already stores are skipped. Existing items keep the
status they have in WordPress, so publishing a draft in wp-admin sticks.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import markdown

from .content import CONTENT, ROOT, Item, iter_items, load
from .http import check, require_env, session

TYPE_FIELDS = {
    "post": ["legacy_url"],
    "external_article": ["publication", "url"],
    "talk": ["event", "location", "youtube_id", "video_url", "slides_url", "writeup_url"],
    "project": ["era", "role", "status", "year", "repo", "demo", "writeup_url", "github"],
    "photo_album": ["flickr_id", "place"],
}


def render_body(item: Item) -> str:
    if item.meta.get("format") == "html":
        return item.body
    return markdown.markdown(item.body, extensions=["extra", "sane_lists"], output_format="html")


def payload(item: Item, new_status: str) -> dict:
    m = item.meta
    synced = m.get("synced") or {}
    meta = {
        "summary": m.get("summary", ""),
        "featured": bool(m.get("featured", False)),
        "synced": json.dumps(synced, sort_keys=True, default=str) if synced else None,
    }
    for key in TYPE_FIELDS[item.post_type]:
        val = m.get(key)
        meta[key] = None if val is None else val
    body = {
        "type": item.post_type,
        "source_id": item.source_id,
        "title": m.get("title", ""),
        "slug": m.get("slug"),
        "content": render_body(item),
        "excerpt": m.get("summary", ""),
        "date": str(m["date"]) if m.get("date") else None,
        "hidden": bool(m.get("hidden", False)),
        "new_status": new_status,
        "tags": m.get("tags", []),
        "meta": meta,
        "hash": item.content_hash(),
    }
    if m.get("wp_id"):
        body["wp_id"] = m["wp_id"]
    if item.post_type == "post" and m.get("categories"):
        body["categories"] = m["categories"]
    if item.post_type == "photo_album" and synced.get("cover_url"):
        body["featured_image_url"] = synced["cover_url"]
    return {k: v for k, v in body.items() if v is not None}


def select(paths: list[str]) -> list[Item]:
    if not paths:
        return list(iter_items())
    items = []
    for p in paths:
        path = (ROOT / p).resolve() if not Path(p).is_absolute() else Path(p)
        if path.suffix in (".md", ".html") and CONTENT in path.parents and path.exists():
            items.append(load(path))
    return items


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="content files to publish (default: all)")
    ap.add_argument("--dry-run", action="store_true", help="report what would change; write nothing")
    ap.add_argument("--force", action="store_true", help="send items even if their hash is unchanged")
    args = ap.parse_args(argv)

    url, user, password = require_env("WP_URL", "WP_USER", "WP_APP_PASSWORD")
    new_status = os.environ.get("HEO_NEW_STATUS", "draft")
    if new_status not in ("draft", "publish"):
        raise SystemExit("HEO_NEW_STATUS must be 'draft' or 'publish'")
    api = url.rstrip("/") + "/wp-json/heo/v1"
    s = session(auth=(user, password))

    remote = {r["source_id"]: r for r in check(s.get(f"{api}/index", timeout=60)).json()}
    items = select(args.paths)
    counts: dict[str, int] = {}
    failures = 0

    for item in items:
        sid = item.source_id
        known = remote.get(sid)
        if known and known.get("hash") == item.content_hash() and not args.force:
            counts["unchanged"] = counts.get("unchanged", 0) + 1
            continue
        verb = "update" if known else ("adopt" if item.meta.get("wp_id") else "create")
        rel = item.path.relative_to(ROOT)
        if args.dry_run:
            print(f"would {verb}: {rel} ({item.post_type} {sid})")
            counts[f"would {verb}"] = counts.get(f"would {verb}", 0) + 1
            continue
        try:
            body = payload(item, new_status)
            if args.force:
                body["force"] = True
            res = check(s.post(f"{api}/upsert", json=body, timeout=120)).json()
            print(f"{res['action']}: {rel} -> #{res['id']} [{res['status']}] {res.get('link', '')}")
            counts[res["action"]] = counts.get(res["action"], 0) + 1
        except Exception as exc:  # keep going; report at the end
            failures += 1
            print(f"FAILED: {rel}: {exc}", file=sys.stderr)

    summary = ", ".join(f"{v} {k}" for k, v in sorted(counts.items())) or "nothing to do"
    print(f"\n{len(items)} items considered: {summary}" + (f", {failures} failed" if failures else ""))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write(f"### Publish to {url}\n\n{summary}" + (f", **{failures} failed**" if failures else "") + "\n")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

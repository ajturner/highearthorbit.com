"""Import WordPress posts that are not in content/_posts/ yet.

Posts already present are matched by wp_id and skipped (use --overwrite to replace them).

Each post becomes a file with `wp_id` set, so the first publish adopts the
existing post instead of creating a duplicate. Bodies keep their stored block
markup (`format: html`) when credentials allow reading it, else the rendered HTML.

Environment: WP_URL, and optionally WP_USER + WP_APP_PASSWORD (to read raw block markup and drafts)
Usage: python -m scripts.heo.import_wordpress [--overwrite]
"""
from __future__ import annotations

import argparse
import html
import os
import re
import sys

from .content import CONTENT, Item, iter_items, save, slugify
from .http import check, require_env, session


def plain(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    text = html.unescape(text).replace("\xa0", " ")
    text = re.sub(r"\s*\[(&hellip;|…)\]\s*$", "", text)
    text = re.sub(r"\s*\[…\]\s*$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def terms(s, base: str, kind: str) -> dict[int, str]:
    out, page = {}, 1
    while True:
        r = s.get(f"{base}/{kind}", params={"per_page": 100, "page": page}, timeout=30)
        if r.status_code == 400:
            break
        batch = check(r).json()
        if not batch:
            break
        out.update({t["id"]: html.unescape(t["name"]) for t in batch})
        page += 1
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--overwrite", action="store_true", help="replace files that already exist")
    args = ap.parse_args(argv)
    (url,) = require_env("WP_URL")
    auth = (os.environ["WP_USER"], os.environ["WP_APP_PASSWORD"]) if os.environ.get("WP_APP_PASSWORD") else None
    base = url.rstrip("/") + "/wp-json/wp/v2"
    s = session(auth=auth)
    cats, tags = terms(s, base, "categories"), terms(s, base, "tags")
    params = {"per_page": 100, "context": "edit" if auth else "view", "status": "publish"}

    # Posts already in the repository (including the 2004-2017 archive) are matched by wp_id.
    posts_here = list(iter_items(["_posts"]))
    existing = {i.meta["wp_id"]: i.path for i in posts_here if i.meta.get("wp_id")}
    # Files written outside WordPress (no wp_id) are matched by date and slug, and adopted.
    by_stem = {i.path.stem: i for i in posts_here if not i.meta.get("wp_id")}
    written = skipped = adopted = 0
    page = 1
    while True:
        r = s.get(f"{base}/posts", params={**params, "page": page}, timeout=60)
        if r.status_code == 400:  # past the last page
            break
        posts = check(r).json()
        if not posts:
            break
        for p in posts:
            date = p["date"][:10]
            stem = f"{date}-{slugify(p['slug'])}"
            if p["id"] not in existing and stem in by_stem:
                twin = by_stem.pop(stem)
                twin.meta["wp_id"] = p["id"]
                twin.meta.setdefault("legacy_url", p["link"])
                save(twin)
                adopted += 1
                continue
            path = existing.get(p["id"]) or CONTENT / "_posts" / f"{stem}.html"
            if path.exists() and not args.overwrite:
                skipped += 1
                continue
            body = (p["content"].get("raw") or p["content"]["rendered"]).strip()
            summary = plain(p["excerpt"].get("raw") or p["excerpt"]["rendered"])
            meta = {
                "source_id": f"wp-{p['id']}",
                "wp_id": p["id"],
                "title": plain(p["title"].get("raw") or p["title"]["rendered"]) or "(untitled)",
                "slug": p["slug"],
                "date": p["date"].replace("T", " ")[:16],
                "summary": summary[:300],
                "categories": [cats[c] for c in p.get("categories", []) if c in cats and cats[c] != "Uncategorized"],
                "tags": [tags[t] for t in p.get("tags", []) if t in tags],
                "legacy_url": p["link"],
                "format": "html",
            }
            meta = {k: v for k, v in meta.items() if v not in ([], "")}
            save(Item(path=path, meta=meta, body=body))
            written += 1
        page += 1

    print(f"Imported {written} posts, linked {adopted} existing files to WordPress, {skipped} already present")
    return 0


if __name__ == "__main__":
    sys.exit(main())

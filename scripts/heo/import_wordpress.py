"""Import WordPress posts that are not in content/_posts/ yet.

Posts already linked by wp_id are skipped (use --overwrite to replace them). Posts in
the repository without a wp_id (the 2004-2017 archive, whose IDs come from an older
WordPress database) are matched by slug, then title, and get the live wp_id.

Each post becomes a file with `wp_id` set, so the first publish adopts the
existing post instead of creating a duplicate. Bodies keep their stored block
markup (`format: html`) when credentials allow reading it, else the rendered HTML.

Environment: WP_URL, and optionally WP_USER + WP_APP_PASSWORD (to read raw block markup and drafts)
Usage: python -m scripts.heo.import_wordpress [--overwrite]
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import os
import re
import sys
import unicodedata
import urllib.parse

from .content import CONTENT, Item, iter_items, save, slugify
from .http import check, require_env, session


def plain(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    text = html.unescape(text).replace("\xa0", " ")
    text = re.sub(r"\s*\[(&hellip;|…)\]\s*$", "", text)
    text = re.sub(r"\s*\[…\]\s*$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_slug(slug: str) -> str:
    """WordPress slugs can carry percent-encoded junk (e.g. %ef%bf%bc, an object
    replacement character pasted with a title). Decode and keep plain ASCII."""
    text = urllib.parse.unquote(slug)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return slugify(text, max_len=80)


def norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", html.unescape(str(title)).lower()).strip()


def _days(a: str, b: str) -> int:
    try:
        return abs((dt.date.fromisoformat(a) - dt.date.fromisoformat(b)).days)
    except ValueError:
        return 10**6


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

    # Match live posts to files already here. A file that already has this wp_id is
    # the same post. Otherwise match by slug, then by title, among files that have no
    # wp_id yet: the 2004-2017 archive came from an older WordPress database whose
    # post IDs (kept as legacy_wp_id) do not match the current site.
    posts_here = list(iter_items(["_posts"]))
    by_wp_id = {i.meta["wp_id"]: i for i in posts_here if i.meta.get("wp_id")}
    unlinked = [i for i in posts_here if not i.meta.get("wp_id")]
    by_slug = {}
    for i in unlinked:
        by_slug.setdefault(i.meta.get("slug") or i.path.stem[11:], []).append(i)
    by_title = {}
    for i in unlinked:
        by_title.setdefault(norm_title(i.meta.get("title", "")), []).append(i)

    written = skipped = adopted = 0
    unmatched_twins = []
    page = 1
    while True:
        r = s.get(f"{base}/posts", params={**params, "page": page}, timeout=60)
        if r.status_code == 400:  # past the last page
            break
        posts = check(r).json()
        if not posts:
            break
        for p in posts:
            slug = clean_slug(p["slug"])
            title = plain(p["title"].get("raw") or p["title"]["rendered"]) or "(untitled)"
            if p["id"] in by_wp_id and not args.overwrite:
                skipped += 1
                continue
            twin = None
            if p["id"] not in by_wp_id:
                candidates = by_slug.get(slug) or by_title.get(norm_title(title)) or []
                if len(candidates) == 1:
                    twin = candidates[0]
                elif len(candidates) > 1:
                    # Several files share the slug or title: pick the closest date.
                    live = p["date"][:10]
                    twin = min(candidates, key=lambda i: abs(_days(str(i.meta.get("date", ""))[:10], live)))
            if twin is not None:
                twin.meta["wp_id"] = p["id"]
                twin.meta["legacy_url"] = p["link"]
                save(twin)
                for group in (by_slug, by_title):
                    for lst in group.values():
                        if twin in lst:
                            lst.remove(twin)
                adopted += 1
                if str(twin.meta.get("date", ""))[:10] != p["date"][:10]:
                    unmatched_twins.append(f"{twin.path.name}: date {str(twin.meta.get('date'))[:10]} here, {p['date'][:10]} on WordPress")
                continue
            path = by_wp_id[p["id"]].path if p["id"] in by_wp_id else CONTENT / "_posts" / f"{p['date'][:10]}-{slug}.html"
            body = (p["content"].get("raw") or p["content"]["rendered"]).strip()
            summary = plain(p["excerpt"].get("raw") or p["excerpt"]["rendered"])
            meta = {
                "source_id": f"post:{slug}",
                "wp_id": p["id"],
                "title": title,
                "slug": slug,
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

    for line in unmatched_twins:
        print(f"note: {line}")
    print(f"Imported {written} new posts, linked {adopted} existing files to their WordPress posts, {skipped} already linked")
    return 0


if __name__ == "__main__":
    sys.exit(main())

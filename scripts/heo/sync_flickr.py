"""Sync Flickr albums into content/_photos/.

Selection rule: albums whose title starts with a YYYY-MM-DD date, minus the IDs
in _data/flickr_exclude.yml, plus the IDs in _data/flickr_include.yml.
New albums are created visible; albums that become excluded are set hidden.
Only public photos are read (API key, no sign-in).

Environment: FLICKR_API_KEY, FLICKR_USER_ID (default 51648834@N00)
Usage: python -m scripts.heo.sync_flickr [--max-photos 24]
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys

import yaml

from .content import CONTENT, DATA, Item, iter_items, merge_synced, save, slugify
from .http import check, require_env, session

API = "https://api.flickr.com/services/rest/"
DATED = re.compile(r"^(\d{4}-\d{2}-\d{2})\s+(.+)$")
PHOTOS = CONTENT / "_photos"


def _list(name: str) -> dict[str, str]:
    p = DATA / name
    data = yaml.safe_load(p.read_text()) if p.exists() else None
    return {str(a["id"]): a.get("title", "") for a in (data or {}).get("albums", [])}


def call(s, key: str, method: str, **params) -> dict:
    params.update(method=method, api_key=key, format="json", nojsoncallback=1)
    data = check(s.get(API, params=params, timeout=60)).json()
    if data.get("stat") != "ok":
        raise RuntimeError(f"Flickr {method}: {data.get('message')}")
    return data


def select_albums(albums: list[dict], exclude: dict, include: dict) -> list[dict]:
    chosen = []
    for a in albums:
        aid, title = a["id"], a["title"]["_content"]
        if aid in exclude:
            continue
        if DATED.match(title) or aid in include:
            chosen.append(a)
    return chosen


def album_synced(s, key: str, user: str, album: dict, max_photos: int) -> dict:
    aid = album["id"]
    photos, page = [], 1
    while True:
        data = call(
            s, key, "flickr.photosets.getPhotos", photoset_id=aid, user_id=user, privacy_filter=1,
            extras="url_l,url_m,date_taken,path_alias", per_page=500, page=page,
        )["photoset"]
        photos.extend(data["photo"])
        if page >= int(data.get("pages", 1)):
            break
        page += 1
    taken = sorted(p["datetaken"][:10] for p in photos if p.get("datetaken") and p.get("datetakenunknown") != "1")
    primary = album.get("primary_photo_extras", {})
    grid = []
    for p in photos[:max_photos]:
        src, w, h = (p.get("url_l"), p.get("width_l"), p.get("height_l")) if p.get("url_l") else (p.get("url_m"), p.get("width_m"), p.get("height_m"))
        if not src:
            continue
        grid.append({
            "id": p["id"], "title": p.get("title", ""), "src": src, "width": int(w or 0), "height": int(h or 0),
            "page_url": f"https://www.flickr.com/photos/{user}/{p['id']}/in/album-{aid}/",
        })
    return {
        "title": album["title"]["_content"],
        "count": len(photos),
        "date_start": taken[0] if taken else None,
        "date_end": taken[-1] if taken else None,
        "cover_url": primary.get("url_l") or primary.get("url_m")
        or f"https://live.staticflickr.com/{album['server']}/{album['primary']}_{album['secret']}_b.jpg",
        "url": f"https://www.flickr.com/photos/{user}/albums/{aid}",
        "photos": grid,
        "updated": album.get("date_update"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-photos", type=int, default=24)
    args = ap.parse_args(argv)
    (key,) = require_env("FLICKR_API_KEY")
    user = os.environ.get("FLICKR_USER_ID", "51648834@N00")
    s = session()

    albums = call(s, key, "flickr.photosets.getList", user_id=user, per_page=500,
                  primary_photo_extras="url_l,url_m")["photosets"]["photoset"]
    exclude, include = _list("flickr_exclude.yml"), _list("flickr_include.yml")
    chosen = select_albums(albums, exclude, include)
    existing = {str(i.meta.get("flickr_id")): i for i in iter_items(["_photos"])}
    created = updated = hidden = 0

    for album in chosen:
        aid, title = album["id"], album["title"]["_content"]
        synced = album_synced(s, key, user, album, args.max_photos)
        if synced["count"] == 0:
            continue  # no public photos
        item = existing.get(aid)
        if item is None:
            m = DATED.match(title)
            date, place = (m.group(1), m.group(2)) if m else (synced["date_start"], title)
            slug = slugify(f"{place} {date[:4] if date else ''}")
            item = Item(path=PHOTOS / f"{slug}.md", meta={
                "source_id": f"flickr:{aid}", "title": place, "flickr_id": aid, "place": place,
                **({"date": date} if date else {}), "hidden": False,
            })
            created += 1
        before = dict(item.meta.get("synced") or {})
        merge_synced(item, synced)
        if save(item) and before:
            updated += 1

    for aid, item in existing.items():
        if aid in exclude and not item.meta.get("hidden"):
            item.meta["hidden"] = True
            save(item)
            hidden += 1

    print(f"Flickr: {len(chosen)} albums selected; {created} new, {updated} updated, {hidden} newly hidden "
          f"({dt.date.today().isoformat()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

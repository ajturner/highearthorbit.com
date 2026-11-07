"""Sync the talks playlist from YouTube into content/_talks/.

Existing talks (matched by youtube_id) get a refreshed `synced` block.
Videos with no talk file get a new hidden file for you, or the curator task,
to fill in the event and summary.

Environment: YOUTUBE_API_KEY, YOUTUBE_PLAYLIST_ID (default: "Andrew Turner Talks")
Usage: python -m scripts.heo.sync_youtube
"""
from __future__ import annotations

import os
import sys

from .content import CONTENT, Item, iter_items, merge_synced, save, slugify
from .http import check, require_env, session

API = "https://www.googleapis.com/youtube/v3/playlistItems"
DEFAULT_PLAYLIST = "PLJN4HgE09_NTKB8WYsGL8_1AIPfu0eemF"


def fetch_playlist(s, key: str, playlist: str) -> list[dict]:
    items, token = [], None
    while True:
        params = {"part": "snippet,contentDetails", "playlistId": playlist, "maxResults": 50, "key": key}
        if token:
            params["pageToken"] = token
        data = check(s.get(API, params=params, timeout=30)).json()
        items.extend(data.get("items", []))
        token = data.get("nextPageToken")
        if not token:
            return items


def video_synced(v: dict) -> dict:
    sn = v["snippet"]
    thumbs = sn.get("thumbnails", {})
    best = next((thumbs[k]["url"] for k in ("maxres", "standard", "high", "medium") if k in thumbs), "")
    return {
        "title": sn.get("title", ""),
        "published_at": (v["contentDetails"].get("videoPublishedAt") or sn.get("publishedAt") or "")[:10],
        "channel": sn.get("videoOwnerChannelTitle", ""),
        "description": (sn.get("description") or "")[:600],
        "thumbnail": best,
    }


def main() -> int:
    (key,) = require_env("YOUTUBE_API_KEY")
    playlist = os.environ.get("YOUTUBE_PLAYLIST_ID", DEFAULT_PLAYLIST)
    s = session()
    by_id = {i.meta.get("youtube_id"): i for i in iter_items(["_talks"]) if i.meta.get("youtube_id")}
    created = updated = 0

    for v in fetch_playlist(s, key, playlist):
        vid = v["contentDetails"]["videoId"]
        if v["snippet"].get("title") in ("Private video", "Deleted video"):
            continue
        synced = video_synced(v)
        item = by_id.get(vid)
        if item is None:
            date = synced["published_at"] or "0000-00-00"
            item = Item(path=CONTENT / "_talks" / f"{date}-{slugify(synced['title'], 50)}.md", meta={
                "source_id": f"youtube:{vid}", "title": synced["title"], "date": date,
                "event": "", "youtube_id": vid, "summary": "", "hidden": True,
            })
            created += 1
        elif item.meta.get("synced") != synced:
            updated += 1
        merge_synced(item, synced)
        save(item)

    print(f"YouTube: {created} new hidden talks, {updated} refreshed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

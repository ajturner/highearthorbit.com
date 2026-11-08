"""Sync the talks playlist from YouTube into content/_talks/.

Each playlist video is matched to a talk by, in order: the talk's `youtube_id`, the
`_data/youtube_map.yml` table (video ID -> source_id), and a conservative title match
(one normalized title contains the other). Matched talks get a refreshed `synced` block
and, if they had no video yet, the `youtube_id`. Videos that match nothing become new
hidden talk files for you to fill in with the event and a summary.

With YOUTUBE_API_KEY the playlist is read from the YouTube Data API. Without a key the
public playlist feed, the playlist page and oEmbed are used instead, so the weekly sync
runs either way.

Environment: YOUTUBE_API_KEY (optional), YOUTUBE_PLAYLIST_ID (default: "Andrew Turner Talks")
Usage: python -m scripts.heo.sync_youtube
"""
from __future__ import annotations

import json
import os
import re
import sys
import xml.etree.ElementTree as ET

import yaml

from .content import CONTENT, DATA, Item, iter_items, merge_synced, save, slugify
from .http import check, session

API = "https://www.googleapis.com/youtube/v3/playlistItems"
FEED = "https://www.youtube.com/feeds/videos.xml"
PAGE = "https://www.youtube.com/playlist"
OEMBED = "https://www.youtube.com/oembed"
WATCH = "https://www.youtube.com/watch"
DEFAULT_PLAYLIST = "PLJN4HgE09_NTKB8WYsGL8_1AIPfu0eemF"
UNAVAILABLE = ("Private video", "Deleted video")
ATOM = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
        "media": "http://search.yahoo.com/mrss/"}
BROWSER_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}


# ---- reading the playlist --------------------------------------------------------

def _video(vid: str, title: str, published: str, channel: str, description: str, thumbnail: str) -> dict:
    """The `synced` block for a video, plus its id (not written)."""
    return {"id": vid, "title": title, "published_at": published[:10], "channel": channel,
            "description": (description or "")[:600], "thumbnail": thumbnail}


def fetch_playlist_api(s, key: str, playlist: str) -> list[dict]:
    out, token = [], None
    while True:
        params = {"part": "snippet,contentDetails", "playlistId": playlist, "maxResults": 50, "key": key}
        if token:
            params["pageToken"] = token
        data = check(s.get(API, params=params, timeout=30)).json()
        for v in data.get("items", []):
            sn = v["snippet"]
            if sn.get("title") in UNAVAILABLE:
                continue
            thumbs = sn.get("thumbnails", {})
            best = next((thumbs[k]["url"] for k in ("maxres", "standard", "high", "medium") if k in thumbs), "")
            out.append(_video(v["contentDetails"]["videoId"], sn.get("title", ""),
                              v["contentDetails"].get("videoPublishedAt") or sn.get("publishedAt") or "",
                              sn.get("videoOwnerChannelTitle", ""), sn.get("description"), best))
        token = data.get("nextPageToken")
        if not token:
            return out


def parse_feed(xml_text: str) -> list[dict]:
    """Videos in a playlist Atom feed (YouTube returns the newest 15)."""
    root = ET.fromstring(xml_text)
    out = []
    for e in root.findall("a:entry", ATOM):
        group = e.find("media:group", ATOM)
        thumb = group.find("media:thumbnail", ATOM) if group is not None else None
        desc = group.findtext("media:description", default="", namespaces=ATOM) if group is not None else ""
        out.append(_video(e.findtext("yt:videoId", default="", namespaces=ATOM),
                          e.findtext("a:title", default="", namespaces=ATOM),
                          e.findtext("a:published", default="", namespaces=ATOM),
                          e.findtext("a:author/a:name", default="", namespaces=ATOM),
                          desc, thumb.get("url", "") if thumb is not None else ""))
    return out


def playlist_page_ids(page_html: str, playlist: str) -> list[str]:
    """Every video ID the playlist page links as part of this playlist, in order, without
    duplicates. Recommended videos elsewhere on the page link without the list parameter."""
    pattern = r"/watch\?v=([A-Za-z0-9_-]{11})(?:&amp;|&|\\u0026)list=" + re.escape(playlist)
    return list(dict.fromkeys(re.findall(pattern, page_html)))


def fetch_playlist_public(s, playlist: str) -> list[dict]:
    """No API key: the feed gives the newest 15 videos in full; older ones come from the
    playlist page (IDs), oEmbed (title, channel, thumbnail) and the watch page (date)."""
    videos = parse_feed(check(s.get(FEED, params={"playlist_id": playlist}, timeout=30)).text)
    known = {v["id"] for v in videos}
    try:
        page = check(s.get(PAGE, params={"list": playlist}, headers=BROWSER_UA, timeout=30)).text
        ids = playlist_page_ids(page, playlist)
    except Exception as exc:  # the feed alone is still useful
        print(f"warning: playlist page not read ({exc}); only the newest videos were checked")
        ids = []
    for vid in ids:
        if vid in known:
            continue
        r = s.get(OEMBED, params={"url": f"{WATCH}?v={vid}", "format": "json"}, headers=BROWSER_UA, timeout=30)
        if r.status_code != 200:  # private or deleted
            continue
        o = r.json()
        published, description = "", ""
        try:
            w = check(s.get(WATCH, params={"v": vid}, headers=BROWSER_UA, timeout=30)).text
            m = re.search(r'"(?:publishDate|uploadDate)":"(\d{4}-\d{2}-\d{2})', w)
            published = m.group(1) if m else ""
            m = re.search(r'"shortDescription":"((?:[^"\\]|\\.)*)"', w)
            description = json.loads(f'"{m.group(1)}"') if m else ""  # a JSON string literal
        except Exception:
            pass
        videos.append(_video(vid, o.get("title", ""), published, o.get("author_name", ""), description,
                             o.get("thumbnail_url", "")))
    return videos


# ---- matching videos to talks ----------------------------------------------------

def normalize(title: str) -> str:
    """Lower-case words only, with the speaker's name and bracketed tags removed."""
    t = re.sub(r"[\[(#].*?[\])]|#\w+", " ", title or "")
    t = re.sub(r"\b(andrew|andy)\s+turner\b", " ", t, flags=re.I)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t.lower()).split())


def video_map() -> dict[str, str]:
    p = DATA / "youtube_map.yml"
    data = yaml.safe_load(p.read_text()) if p.exists() else None
    return {str(k): str(v) for k, v in ((data or {}).get("videos") or {}).items()}


def match_talk(video: dict, talks: list[Item], mapping: dict[str, str]) -> Item | None:
    vid = video["id"]
    for t in talks:
        if t.meta.get("youtube_id") == vid:
            return t
    if vid in mapping:
        for t in talks:
            if t.meta.get("source_id") == mapping[vid]:
                return t
        print(f"warning: youtube_map.yml points {vid} at {mapping[vid]}, which no talk has")
    vt = normalize(video["title"])
    if len(vt) < 12:
        return None
    hits = []
    for t in talks:
        tt = normalize(t.meta.get("title", ""))
        if len(tt) >= 12 and (tt in vt or vt in tt):
            hits.append(t)
    return hits[0] if len(hits) == 1 else None


def main() -> int:
    key = os.environ.get("YOUTUBE_API_KEY")
    playlist = os.environ.get("YOUTUBE_PLAYLIST_ID", DEFAULT_PLAYLIST)
    s = session()
    videos = fetch_playlist_api(s, key, playlist) if key else fetch_playlist_public(s, playlist)
    talks = list(iter_items(["_talks"]))
    mapping = video_map()
    created = updated = linked = extra = 0

    for v in videos:
        synced = {k: val for k, val in v.items() if k != "id"}
        item = match_talk(v, talks, mapping)
        if item is None:
            date = synced["published_at"] or "0000-00-00"
            item = Item(path=CONTENT / "_talks" / f"{date}-{slugify(synced['title'], 50)}.md", meta={
                "source_id": f"youtube:{v['id']}", "title": synced["title"], "date": date,
                "event": synced["channel"], "youtube_id": v["id"], "summary": "", "hidden": True,
            }, body="[Set the event and date, write a summary, then set `hidden: false`.]")
            talks.append(item)
            created += 1
        elif item.meta.get("youtube_id") not in (None, v["id"]):
            extra += 1  # a second recording of a talk that already has its video; nothing to write
            continue
        else:
            if "youtube_id" not in item.meta:
                item.meta["youtube_id"] = v["id"]
                linked += 1
            if item.meta.get("synced") != synced:
                updated += 1
        merge_synced(item, synced)
        save(item)

    print(f"YouTube: {len(videos)} videos; {created} new hidden talks, {linked} talks given a video, "
          f"{updated} refreshed, {extra} extra recordings skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Sync blog posts from the Notion Writing database into content/_posts/.

A Notion page is published here when both are true:
  - its Tags include "Blog" (any letter case), and
  - its Status is "Published", or its Tags include "Published".

Each page becomes content/_posts/<date>-<slug>.md with source_id notion:<page id>.
The file name and slug are fixed the first time a page is written, so renaming
the page in Notion changes its title but not its URL. Pages that stop matching
(the tag or status removed) are marked `hidden: true`, not deleted. Images
uploaded to Notion are downloaded into assets/notion/, since Notion's file
links expire after an hour.

Notion is the source for these posts: edit them there, not in the file. A page that
still contains a `[TK: ...]` placeholder or a `[verify]` note (see docs/voice/style-guide.md) is skipped.
Callouts marked 🎙️ or 🔍 are editing notes and are left out of the post.

Environment: NOTION_TOKEN (an internal integration with access to the Writing
database), NOTION_DATABASE_ID (default: the Writing database)
Usage: python -m scripts.heo.sync_notion [--dry-run]
"""
from __future__ import annotations

import argparse
import mimetypes
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

from .content import CONTENT, ROOT, Item, iter_items, save, slugify
from .http import check, require_env, session

API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
DEFAULT_DATABASE = "1ae8069c359380e3a02aeb21a918bc2d"
ASSETS = ROOT / "assets" / "notion"
BLOG_TAG = "blog"
# Callouts with these icons hold editing notes for Andrew and are never published.
EDITORIAL_ICONS = {"\U0001F399\uFE0F", "\U0001F399", "\U0001F50D"}  # studio microphone, magnifying glass
# A page still holding one of these markers isn't ready; the site keeps the last synced version.
UNFINISHED = ("[TK:", "[verify")
PUBLISHED = "published"


# ---------------------------------------------------------------- selection

def names(prop: dict | None) -> list[str]:
    """Option names of a select, multi_select or status property."""
    if not prop:
        return []
    kind = prop.get("type")
    value = prop.get(kind)
    if kind == "multi_select":
        return [o["name"] for o in value or []]
    if kind in ("select", "status") and value:
        return [value["name"]]
    return []


def is_published(page: dict) -> bool:
    props = page.get("properties", {})
    tags = [t.lower() for t in names(props.get("Tags"))]
    status = [s.lower() for s in names(props.get("Status"))]
    return BLOG_TAG in tags and (PUBLISHED in status or PUBLISHED in tags)


def plain_text(rich: list[dict] | None) -> str:
    return "".join(r.get("plain_text", "") for r in rich or [])


# ---------------------------------------------------------------- markdown

def rich_to_md(rich: list[dict] | None) -> str:
    out = []
    for r in rich or []:
        text = r.get("plain_text", "")
        if r.get("type") == "equation":
            out.append(f"${text}$")
            continue
        a = r.get("annotations") or {}
        if text.strip():
            lead = text[: len(text) - len(text.lstrip())]
            trail = text[len(text.rstrip()):]
            core = text.strip()
            if a.get("code"):
                core = f"`{core}`"
            if a.get("bold"):
                core = f"**{core}**"
            if a.get("italic"):
                core = f"*{core}*"
            if a.get("strikethrough"):
                core = f"~~{core}~~"
            href = r.get("href")
            if href:
                core = f"[{core}]({href})"
            text = lead + core + trail
        out.append(text)
    return "".join(out)


class Converter:
    """Turns a list of Notion blocks (with children already attached under
    block["children"]) into Markdown. `fetch_file(url, block_id)` returns the
    site path for an uploaded file."""

    def __init__(self, fetch_file=None):
        self.fetch_file = fetch_file or (lambda url, block_id: url)

    def convert(self, blocks: list[dict], indent: str = "") -> str:
        parts: list[str] = []
        number = 0
        for b in blocks:
            kind = b.get("type")
            number = number + 1 if kind == "numbered_list_item" else 0
            md = self.block(b, indent, number)
            if md is None:
                continue
            # List items sit together; everything else is a separate paragraph.
            tight = kind in ("bulleted_list_item", "numbered_list_item", "to_do")
            if parts and tight and parts[-1][0] == kind:
                parts[-1] = (kind, parts[-1][1] + "\n" + md)
            else:
                parts.append((kind, md))
        return "\n\n".join(md for _, md in parts)

    def children(self, b: dict, indent: str) -> str:
        kids = b.get("children") or []
        return self.convert(kids, indent) if kids else ""

    def media_src(self, value: dict, block_id: str) -> str:
        if value.get("type") == "file":
            return self.fetch_file(value["file"]["url"], block_id)
        return (value.get("external") or {}).get("url", "")

    def block(self, b: dict, indent: str, number: int) -> str | None:
        kind = b.get("type")
        v = b.get(kind) or {}
        text = rich_to_md(v.get("rich_text"))
        sub = indent + "    "
        if kind == "paragraph":
            body = indent + text if text else ""
            kids = self.children(b, indent)
            return "\n\n".join(x for x in (body, kids) if x) or None
        if kind in ("heading_1", "heading_2", "heading_3"):
            level = {"heading_1": 2, "heading_2": 3, "heading_3": 4}[kind]
            return f"{indent}{'#' * level} {text}"
        if kind in ("bulleted_list_item", "numbered_list_item", "to_do"):
            if kind == "bulleted_list_item":
                marker = "-"
            elif kind == "numbered_list_item":
                marker = f"{number}."
            else:
                marker = "- [x]" if v.get("checked") else "- [ ]"
            line = f"{indent}{marker} {text}"
            kids = self.children(b, sub)
            return line + ("\n\n" + kids if kids else "")
        if kind == "quote":
            kids = self.children(b, "")
            lines = (text + ("\n\n" + kids if kids else "")).split("\n")
            return "\n".join(f"{indent}> {l}".rstrip() for l in lines)
        if kind == "callout":
            icon = (v.get("icon") or {}).get("emoji", "")
            if icon in EDITORIAL_ICONS:
                return None  # notes for Andrew (voice pass, review), not part of the post
            kids = self.children(b, "")
            lines = ((icon + " " if icon else "") + text + ("\n\n" + kids if kids else "")).split("\n")
            return "\n".join(f"{indent}> {l}".rstrip() for l in lines)
        if kind == "toggle":
            kids = self.children(b, indent)
            return f"{indent}**{text}**" + ("\n\n" + kids if kids else "")
        if kind == "code":
            lang = (v.get("language") or "").replace("plain text", "")
            code = plain_text(v.get("rich_text"))
            return f"{indent}```{lang}\n{code}\n{indent}```"
        if kind == "equation":
            return f"{indent}$$\n{v.get('expression', '')}\n$$"
        if kind == "divider":
            return f"{indent}---"
        if kind == "image":
            src = self.media_src(v, b.get("id", ""))
            caption = plain_text(v.get("caption"))
            return f"{indent}![{caption}]({src})" + (f"\n{indent}*{caption}*" if caption else "")
        if kind in ("video", "file", "pdf", "audio"):
            src = self.media_src(v, b.get("id", ""))
            caption = plain_text(v.get("caption")) or Path(urlsplit(src).path).name or kind
            return f"{indent}[{caption}]({src})"
        if kind in ("bookmark", "embed", "link_preview"):
            url = v.get("url", "")
            caption = plain_text(v.get("caption")) or url
            return f"{indent}[{caption}]({url})"
        if kind == "table":
            rows = [r for r in b.get("children") or [] if r.get("type") == "table_row"]
            if not rows:
                return None
            cells = [[rich_to_md(c).replace("|", "\\|") for c in r["table_row"]["cells"]] for r in rows]
            width = max(len(c) for c in cells)
            cells = [c + [""] * (width - len(c)) for c in cells]
            lines = ["| " + " | ".join(cells[0]) + " |", "|" + " --- |" * width]
            lines += ["| " + " | ".join(c) + " |" for c in cells[1:]]
            return "\n".join(indent + l for l in lines)
        if kind in ("column_list", "column", "synced_block"):
            return self.children(b, indent) or None
        # child_page, child_database, table_of_contents, breadcrumb, unsupported: skip
        return None


# ---------------------------------------------------------------- Notion API

def blog_filter(schema: dict) -> dict | None:
    """A query filter for pages tagged Blog, built from the Tags options that exist.
    Notion rejects a filter naming an option the property doesn't have, so with no
    Blog option yet there is nothing to ask for."""
    tags = (schema.get("properties", {}).get("Tags") or {}).get("multi_select") or {}
    names = [o["name"] for o in tags.get("options", []) if o.get("name", "").lower() == BLOG_TAG]
    if not names:
        return None
    clauses = [{"property": "Tags", "multi_select": {"contains": n}} for n in names]
    return clauses[0] if len(clauses) == 1 else {"or": clauses}


def query(s, database: str) -> list[dict]:
    schema = check(s.get(f"{API}/databases/{database}", timeout=60)).json()
    flt = blog_filter(schema)
    if flt is None:
        print('Notion: the Writing database has no "Blog" tag yet; nothing to sync. '
              "Add the tag to a page (type Blog in its Tags) and set Status to Published.")
        return []
    body = {"filter": flt, "page_size": 100}
    pages, cursor = [], None
    while True:
        if cursor:
            body["start_cursor"] = cursor
        data = check(s.post(f"{API}/databases/{database}/query", json=body, timeout=60)).json()
        pages += data.get("results", [])
        if not data.get("has_more"):
            return pages
        cursor = data.get("next_cursor")


def blocks(s, block_id: str) -> list[dict]:
    out, cursor = [], None
    while True:
        params = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        data = check(s.get(f"{API}/blocks/{block_id}/children", params=params, timeout=60)).json()
        for b in data.get("results", []):
            if b.get("has_children") and b.get("type") not in ("child_page", "child_database"):
                b["children"] = blocks(s, b["id"])
            out.append(b)
        if not data.get("has_more"):
            return out
        cursor = data.get("next_cursor")


def make_fetcher(s, dry_run: bool):
    def fetch(url: str, block_id: str) -> str:
        ext = Path(urlsplit(url).path).suffix.lower() or ".bin"
        name = f"{block_id.replace('-', '')}{ext}"
        path = ASSETS / name
        if not path.exists() and not dry_run:
            r = check(s.get(url, timeout=120, headers={"Authorization": None, "Notion-Version": None}))
            if ext == ".bin":
                guess = mimetypes.guess_extension((r.headers.get("content-type") or "").split(";")[0]) or ".bin"
                path = path.with_suffix(guess)
                name = path.name
            ASSETS.mkdir(parents=True, exist_ok=True)
            path.write_bytes(r.content)
        return f"/assets/notion/{name}"
    return fetch


# ---------------------------------------------------------------- files

def page_meta(page: dict) -> dict:
    props = page.get("properties", {})
    title = plain_text((props.get("Title") or {}).get("title")) or "Untitled"
    date = ((props.get("Date") or {}).get("date") or {}).get("start") or page.get("created_time", "")
    date = date.replace("T", " ")[:16]
    meta = {
        "title": title,
        "date": date,
        "summary": plain_text((props.get("Summary") or {}).get("rich_text")),
        "tags": names(props.get("Topic")),
        "notion_url": page.get("url", ""),
    }
    return {k: v for k, v in meta.items() if v not in ("", [])}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report what would change without writing")
    args = ap.parse_args(argv)
    (token,) = require_env("NOTION_TOKEN")
    database = os.environ.get("NOTION_DATABASE_ID", DEFAULT_DATABASE).replace("-", "")
    s = session(headers={"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION})
    convert = Converter(make_fetcher(s, args.dry_run))

    existing = {str(i.meta["source_id"]): i for i in iter_items(["_posts"])
                if str(i.meta.get("source_id", "")).startswith("notion:")}
    seen, written, hidden = set(), 0, 0
    for page in query(s, database):
        if page.get("archived") or page.get("in_trash") or not is_published(page):
            continue
        sid = f"notion:{page['id'].replace('-', '')}"
        seen.add(sid)
        meta = page_meta(page)
        current = existing.get(sid)
        if current:
            path, slug = current.path, current.meta.get("slug") or current.path.stem[11:]
        else:
            slug = slugify(meta["title"], 70)
            path = CONTENT / "_posts" / f"{meta['date'][:10]}-{slug}.md"
        full = {"source_id": sid, **{k: meta[k] for k in ("title", "date") if k in meta}, "slug": slug}
        full.update({k: v for k, v in meta.items() if k not in full})
        if current and current.meta.get("wp_id"):
            full["wp_id"] = current.meta["wp_id"]
        full["format"] = "markdown"
        body = convert.convert(blocks(s, page["id"]))
        open_marks = [m for m in UNFINISHED if m in body]
        if open_marks:
            print(f"skipped {meta['title']!r}: it still has {', '.join(m + ' ...]' for m in open_marks)} to resolve; the site keeps the last synced version")
            continue
        item = Item(path=path, meta=full, body=body)
        if args.dry_run:
            print(f"would write {path.relative_to(ROOT)}")
            continue
        if save(item):
            written += 1
            print(f"wrote {path.relative_to(ROOT)}")

    for sid, item in existing.items():
        if sid not in seen and not item.meta.get("hidden"):
            item.meta["hidden"] = True
            if not args.dry_run:
                save(item)
            hidden += 1
            print(f"hid {item.path.relative_to(ROOT)} (no longer tagged Blog and Published)")

    print(f"Notion: {written} posts written, {hidden} hidden, {len(seen)} published in Notion")
    return 0


if __name__ == "__main__":
    sys.exit(main())
